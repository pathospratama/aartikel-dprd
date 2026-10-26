"""Fetcher & parser HTML — v5 HTTP-only.

- HTTP requests biasa, tanpa browser automation atau challenge-bypass client.
- Verifikasi TLS tetap aktif; challenge/WAF didiagnosis, bukan dilewati.
- Snapshot HTML lokal memberi fallback transparan dengan status partial.
- Ekstraksi gambar WordPress/JNews dan feed/API terstruktur tetap didukung.
"""
import json
import logging
import re
import socket
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from config import (
    HEADERS, HEADERS_EXTENDED, REQUEST_TIMEOUT, BULAN_ID,
)

log = logging.getLogger("scraper")

_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp")


# =====================================================
# Konstanta
# =====================================================
NAVIGATION_KEYWORDS = {
    "profil pimpinan", "profil anggota", "sekertaris dprd",
    "fraksi pdip", "fraksi pks", "fraksi golkar", "fraksi amanat restorasi",
    "fraksi persatuan pembangunan demokrat", "fraksi pkb", "fraksi gerindra",
    "alat kelengkapan", "badan anggaran", "badan kehormatan",
    "badan musyawarah", "badan pembentukan perda",
    "pengaduan dan aspirasi", "alur sisitem", "sidewa-pasti",
    "beranda", "menu", "home", "copyright",
}

CHALLENGE_MARKERS = (
    "just a moment...", "checking your browser", "cf-browser-verification",
    "attention required! | cloudflare", "please complete the security check",
    "verify you are human", "__cf_chl_", "cloudflare ray id",
    "incapsula incident id", "sucuri website firewall", "request blocked",
    "your request has been blocked", "unusual traffic from your computer network",
    "enable cookies to continue", "browser verification", "bot verification",
    "access denied - security",
)

SKIP_LINK_PATTERNS = re.compile(
    r"(#|/tag/|/tags/|/category/|/categories/|/kategori/|/kanal/|"
    r"/author/|/page/|/search/|/login/|/register/|/about/|/contact/|"
    r"javascript:|mailto:|tel:)", re.IGNORECASE,
)

ARTICLE_LINK_HINTS = re.compile(
    r"(/read/|/berita/|/artikel/|/news/|/post/|/detail/|/\d{4}/\d{2}/|"
    r"/20\d{2}/|/baca/|/view/|\.html|\.shtml|/home/)",
    re.IGNORECASE,
)

COOKIES_FILE = Path("cookies.json")
_COOKIE_CACHE: dict[str, dict] = {}
# Ringkasan penyebab fetch terakhir per URL, untuk log error yang bisa ditindaklanjuti.
_FETCH_DIAGNOSTICS: dict[str, list[str]] = {}
# Host-level cache: avoid repeatedly retrying URLs on the same invalid TLS endpoint.
_TLS_FAILED_HOSTS: set[str] = set()


def _record_fetch_error(url: str, message: str) -> None:
    """Simpan alasan kegagalan tanpa membuat satu sumber menghentikan scraper."""
    messages = _FETCH_DIAGNOSTICS.setdefault(url, [])
    if message and message not in messages:
        messages.append(message[:240])
    # Hindari pertumbuhan memori tak terbatas pada proses panjang.
    if len(_FETCH_DIAGNOSTICS) > 500:
        oldest = next(iter(_FETCH_DIAGNOSTICS))
        if oldest != url:
            _FETCH_DIAGNOSTICS.pop(oldest, None)


# =====================================================
# Helper — deteksi & fetch
# =====================================================
def _is_navigation_text(text: str) -> bool:
    t = text.lower().strip()
    if not t:
        return True
    hits = sum(1 for kw in NAVIGATION_KEYWORDS if kw in t)
    return hits >= 2


def _is_challenge_page(html: str) -> bool:
    """Detect challenge/WAF pages without confusing normal scripts with challenges.

    Some challenge HTML is large, so length is not a reliable exemption. Conversely,
    common JS names such as ``challenge-platform`` can appear in legitimate pages;
    strong messages are combined with lack of article structure before classifying.
    """
    if not html:
        return True
    low = html.lower()
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "").lower()
    body_text = soup.get_text(" ", strip=True).lower()[:12000]
    article_nodes = soup.select(
        "article, .entry-title, .jeg_post_title, .post-title, "
        ".media-title, .headline-title, .fl-post-title, .card-title"
    )
    unmistakable = (
        "just a moment...", "checking your browser", "cf-browser-verification",
        "please complete the security check", "verify you are human",
        "unusual traffic from your computer network", "enable cookies to continue",
    )
    if any(marker in low for marker in unmistakable):
        return True

    explicit_markers = (
        "attention required! | cloudflare", "cloudflare ray id", "incapsula incident id",
        "sucuri website firewall", "your request has been blocked",
        "access denied - security", "bot verification", "browser verification",
    )
    # Several local government/news sites return this lightweight interstitial to
    # non-browser clients. It is not an article listing and should not be reported as
    # a selector mismatch. Only classify it when the page has no recognizable article
    # structure, so an article discussing the phrase is not misclassified.
    wait_title = any(term in title for term in (
        "mohon tunggu sebentar", "sedang memeriksa browser", "please wait",
        "harap tunggu", "sedang memuat halaman",
    ))
    if wait_title and not article_nodes:
        return True

    title_is_security = any(term in title for term in (
        "access denied", "attention required", "security check", "verify you are human",
        "unusual traffic", "request blocked", "robot check", "just a moment",
        "mohon tunggu sebentar", "please wait",
    ))
    body_is_security = any(term in body_text for term in (
        "complete the security check", "verify that you are human",
        "request rejected by security policy", "automated requests are not allowed",
    ))
    if not article_nodes and (title_is_security or body_is_security or any(m in low for m in explicit_markers)):
        return True
    return False


def _is_dns_dead(url: str) -> bool:
    try:
        host = urlparse(url).netloc.split(":")[0]
        socket.gethostbyname(host)
        return False
    except socket.gaierror:
        return True
    except Exception:
        return False


def _load_cookies(domain: str) -> dict:
    if domain in _COOKIE_CACHE:
        return _COOKIE_CACHE[domain]
    if not COOKIES_FILE.exists():
        _COOKIE_CACHE[domain] = {}
        return {}
    try:
        data = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        _COOKIE_CACHE[domain] = {}
        return {}
    if not isinstance(data, dict):
        _COOKIE_CACHE[domain] = {}
        return {}
    raw = data.get(domain)
    cookies: dict[str, str] = {}
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict) and "name" in c and "value" in c:
                cookies[c["name"]] = c["value"]
    elif isinstance(raw, dict):
        cookies = raw
    _COOKIE_CACHE[domain] = cookies
    return cookies


def _wrap_response(status_code: int, text: str, url: str, headers: dict) -> requests.Response:
    r = requests.Response()
    r.status_code = status_code
    r._content = text.encode("utf-8", errors="replace")
    r.url = url
    try:
        r.headers.update(headers)
    except Exception:
        pass
    r.encoding = "utf-8"
    return r


def safe_get(url: str):
    """Ambil URL menggunakan HTTP biasa saja (requests), tanpa browser automation.

    TLS tetap diverifikasi. Jika server mengembalikan challenge/WAF atau status
    penolakan, hentikan percobaan untuk URL tersebut dan catat alasan yang jelas.
    Retry hanya untuk gangguan sementara, bukan untuk challenge, 403, 404, atau TLS.
    """
    _FETCH_DIAGNOSTICS[url] = []
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    domain = parsed.netloc

    if host and host in _TLS_FAILED_HOSTS:
        reason = (
            f"Host {host} sebelumnya gagal verifikasi sertifikat TLS; dilewati. "
            "Periksa CA bundle atau rantai sertifikat server. Verifikasi TLS tetap aktif."
        )
        _record_fetch_error(url, reason)
        log.error("FETCH TLS DILEWATI | url=%s | penyebab=%s", url, reason)
        return None

    if _is_dns_dead(url):
        reason = f"DNS tidak resolve untuk host {domain}; cek domain, DNS, atau koneksi internet"
        _record_fetch_error(url, reason)
        log.error("FETCH GAGAL | url=%s | penyebab=%s", url, reason)
        return None

    cookies = _load_cookies(domain)
    session = requests.Session()
    session.headers.update(HEADERS_EXTENDED or HEADERS)
    if cookies:
        session.cookies.update(cookies)
        log.info("HTTP requests menggunakan %s cookie yang disediakan pengguna untuk %s", len(cookies), domain)

    last_reason = "tidak ada respons valid"
    try:
        for attempt in range(2):
            try:
                response = session.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                    verify=True,
                )
                status = response.status_code

                if status != 200:
                    last_reason = f"HTTP {status} {response.reason or ''}".strip()
                    _record_fetch_error(url, last_reason)
                    log.warning("HTTP gagal | url=%s | status=%s", url, status)
                    # Status permanen: jangan ulang permintaan yang pasti tidak akan membantu.
                    if status in (401, 403, 404, 410, 451):
                        return None
                    if status < 500 or attempt == 1:
                        return None
                    time.sleep(1.0)
                    continue

                if not response.text:
                    last_reason = "HTTP 200 tetapi body kosong"
                    _record_fetch_error(url, last_reason)
                    if attempt == 0:
                        time.sleep(0.5)
                        continue
                    return None

                if _is_challenge_page(response.text):
                    title_soup = BeautifulSoup(response.text, "lxml")
                    title = _txt(title_soup.title) or "(tanpa title)"
                    last_reason = (
                        "HTTP 200 tetapi server mengirim halaman perantara/verifikasi, "
                        f"bukan konten artikel (title={title[:100]!r}). "
                        "HTTP biasa tidak dapat mengambil data dari respons ini."
                    )
                    _record_fetch_error(url, last_reason)
                    log.warning("FETCH DITAHAN HALAMAN PERANTARA | url=%s | %s", url, last_reason)
                    return None

                return response

            except requests.exceptions.SSLError as exc:
                last_reason = f"TLS certificate verification failed: {str(exc)[:180]}"
                _record_fetch_error(url, last_reason)
                if host:
                    _TLS_FAILED_HOSTS.add(host)
                log.error("FETCH TLS GAGAL | url=%s | %s", url, last_reason)
                return None
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_reason = f"{type(exc).__name__}: {str(exc)[:180]}"
                _record_fetch_error(url, last_reason)
                log.warning("HTTP koneksi bermasalah | url=%s | percobaan=%s/2 | %s", url, attempt + 1, last_reason)
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                return None
            except requests.exceptions.RequestException as exc:
                last_reason = f"{type(exc).__name__}: {str(exc)[:180]}"
                _record_fetch_error(url, last_reason)
                log.error("HTTP request gagal | url=%s | %s", url, last_reason)
                return None
    finally:
        session.close()

    _record_fetch_error(url, last_reason)
    return None


# =====================================================
# Helper teks & URL
# =====================================================
def _txt(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _normalize_url(href: str, base_url: str):
    if not href:
        return None
    href = href.strip()
    if href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return f"https:{href}"
    return urljoin(base_url, href)


def _is_article_link(href: str) -> bool:
    if not href or len(href) < 15:
        return False
    if SKIP_LINK_PATTERNS.search(href):
        return False
    return bool(ARTICLE_LINK_HINTS.search(href))


def _derive_title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title() if slug else "(tanpa judul)"


# =====================================================
# ✅ FIX: Ekstrak gambar WordPress total
# =====================================================
def _extract_image(tag, base_url: str):
    """
    Ekstrak URL gambar dari tag <img> — v6 (fix WP total).
    Urutan prioritas:
      1. data-src / data-lazy-src / data-original / data-lazy / dll
      2. srcset / data-srcset (ambil resolusi terbesar)
      3. src biasa
      4. background-image di style tag itu sendiri
      5. background-image di parent
    """
    if tag is None:
        return None

    # === 1. Semua atribut lazy-load WordPress ===
    lazy_attrs = (
        "data-src", "data-lazy-src", "data-original", "data-lazy",
        "data-url", "data-image", "data-img", "data-original-src",
        "data-lazy-original", "data-actualsrc",
    )
    for attr in lazy_attrs:
        val = tag.get(attr)
        if val and isinstance(val, str) and val.strip():
            u = _normalize_url(val.strip(), base_url)
            if u:
                return u

    # === 2. srcset & data-srcset (ambil resolusi terbesar) ===
    for attr in ("srcset", "data-srcset"):
        srcset = tag.get(attr)
        if srcset:
            # Format: "url1 300w, url2 1024w, url3 1080w"
            candidates = []
            for part in srcset.split(","):
                part = part.strip()
                if not part:
                    continue
                pieces = part.split()
                if not pieces:
                    continue
                url_part = pieces[0]
                # Ambil bobot (misal "1080w" → 1080)
                weight = 0
                for p in pieces[1:]:
                    if p.endswith("w"):
                        try:
                            weight = int(p[:-1])
                        except ValueError:
                            weight = 0
                    elif p.endswith("x"):
                        try:
                            weight = int(float(p[:-1]) * 1000)
                        except ValueError:
                            weight = 0
                candidates.append((weight, url_part))
            if candidates:
                # Ambil yang terbesar
                candidates.sort(key=lambda x: x[0], reverse=True)
                u = _normalize_url(candidates[0][1], base_url)
                if u:
                    return u

    # === 3. src biasa ===
    src = tag.get("src")
    if src:
        s_low = src.lower().split("?")[0]
        if any(s_low.endswith(e) for e in _IMAGE_EXT):
            return _normalize_url(src, base_url)

    # === 4. Background-image di style tag itu sendiri ===
    style = tag.get("style") or ""
    m = re.search(
        r"background(?:-image)?\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)",
        style, re.IGNORECASE,
    )
    if m:
        return _normalize_url(m.group(1).strip(), base_url)

    # === 5. Background-image di parent ===
    parent = tag.parent
    if parent and getattr(parent, "get", None):
        pstyle = parent.get("style") or ""
        m = re.search(
            r"background(?:-image)?\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)",
            pstyle, re.IGNORECASE,
        )
        if m:
            return _normalize_url(m.group(1).strip(), base_url)

    return None


BAD_IMAGE_HINTS = (
    "gravatar.com/avatar", "avatar", "favicon", "logo", "placeholder",
    "default-image", "default-avatar", "data:image", "blank.gif",
)


def _is_usable_article_image(url: str | None) -> bool:
    if not url:
        return False
    value = str(url).strip().lower()
    if not value.startswith(("http://", "https://")):
        return False
    if any(hint in value for hint in BAD_IMAGE_HINTS):
        return False
    path = urlparse(value).path.lower()
    return any(path.endswith(ext) for ext in _IMAGE_EXT)


def _image_from_meta(soup: BeautifulSoup, base_url: str) -> str | None:
    for selector, attr in (
        ("meta[property='og:image']", "content"),
        ("meta[property='og:image:secure_url']", "content"),
        ("meta[name='twitter:image']", "content"),
        ("meta[name='twitter:image:src']", "content"),
    ):
        node = soup.select_one(selector)
        value = node.get(attr) if node else None
        candidate = _normalize_url(value, base_url) if value else None
        if _is_usable_article_image(candidate):
            return candidate
    return None


def _extract_all_images_from_soup(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Ambil gambar artikel dengan prioritas metadata dan area konten, bukan avatar/sidebar."""
    images: list[str] = []
    seen: set[str] = set()

    def add(candidate):
        if not _is_usable_article_image(candidate) or candidate in seen:
            return
        seen.add(candidate)
        images.append(candidate)

    # Metadata biasanya menunjuk featured image yang tepat.
    add(_image_from_meta(soup, base_url))

    # Area artikel diprioritaskan agar logo, avatar penulis, dan sidebar tidak terambil.
    selectors = (
        ".bs-blog-thumb img", "img.wp-post-image", ".post-thumbnail img",
        ".td-post-featured-image img", ".entry-thumb img",
        "article .featured-image img", "article figure img",
        ".entry-content img", ".post-content img", "article img",
    )
    for selector in selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            nodes = []
        for node in nodes:
            classes = " ".join(node.get("class", [])).lower()
            parent_classes = " ".join(node.parent.get("class", []) if getattr(node.parent, "get", None) else []).lower()
            if any(x in classes + " " + parent_classes for x in ("avatar", "author", "logo", "related", "sidebar", "widget")):
                continue
            add(_extract_image(node, base_url))
            if len(images) >= 10:
                return images

    # Fallback background-image, tetapi tetap validasi dan batasi jumlah.
    if not images:
        for el in soup.select("[style*='background']"):
            style = el.get("style") or ""
            match = re.search(r"background(?:-image)?\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)", style, re.I)
            if match:
                add(_normalize_url(match.group(1).strip(), base_url))
            if len(images) >= 10:
                break
    return images[:10]


# =====================================================
# Parse tanggal
# =====================================================
def _parse_date(raw: str):
    if not raw:
        return None
    raw = raw.strip()

    m = re.search(
        r"(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|"
        r"september|oktober|november|desember)\s+(\d{4})",
        raw, re.IGNORECASE,
    )
    if m:
        day, bulan, year = m.groups()
        try:
            return f"{int(year):04d}-{BULAN_ID[bulan.lower()]:02d}-{int(day):02d}"
        except (KeyError, ValueError):
            pass

    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return m.group(0)

    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
    if m:
        d, mo, y = m.groups()
        try:
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            pass

    if re.search(r"\b20\d{2}\b", raw):
        try:
            return dateparser.parse(
                raw, fuzzy=True, dayfirst=True,
                tzinfos={"WIB": 25200, "WITA": 28800, "WIT": 32400},
            ).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OverflowError):
            return None
    return None


def _extract_date_from_text(text: str):
    if not text:
        return None
    for pattern in [
        r"\d{1,2}\s+(januari|februari|maret|april|mei|juni|juli|agustus|"
        r"september|oktober|november|desember)\s+\d{4}",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}[/-]\d{1,2}[/-]\d{4}",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _parse_date(m.group(0))
    return None


def _extract_date_from_soup(soup: BeautifulSoup, selectors_detail: dict):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            for key in ("datePublished", "dateCreated", "dateModified"):
                if key in item and item[key]:
                    date = _parse_date(str(item[key]))
                    if date:
                        return date
            graph = item.get("@graph")
            if isinstance(graph, list):
                for g in graph:
                    if isinstance(g, dict):
                        for key in ("datePublished", "dateCreated"):
                            if key in g and g[key]:
                                date = _parse_date(str(g[key]))
                                if date:
                                    return date

    for attr, val in [
        ("property", "article:published_time"),
        ("property", "og:updated_time"),
        ("name", "publish-date"),
        ("name", "pubdate"),
        ("name", "date"),
        ("itemprop", "datePublished"),
        ("itemprop", "dateCreated"),
    ]:
        tag = soup.find("meta", attrs={attr: val})
        if tag and tag.get("content"):
            date = _parse_date(tag["content"])
            if date:
                return date

    t = soup.find("time", attrs={"datetime": True})
    if t:
        date = _parse_date(t["datetime"])
        if date:
            return date

    date_raw = _txt(soup.select_one(selectors_detail.get("date") or ".__none__"))
    date = _parse_date(date_raw)
    if date:
        return date

    content = _extract_content(soup, selectors_detail)
    return _extract_date_from_text(content)


# =====================================================
# Parse list page
# =====================================================

def _pick_article_image(node, base_url: str) -> str | None:
    """Pilih thumbnail dari container artikel dengan selector spesifik terlebih dahulu."""
    # Beberapa situs memakai background-image langsung pada kartu (misalnya
    # Kuningan Jabar Info), bukan elemen <img> di dalamnya.
    direct = _extract_image(node, base_url)
    if _is_usable_article_image(direct):
        return direct

    # Cari background-image pada anak kartu; beberapa template tidak memakai <img>.
    try:
        styled_nodes = node.select('[style*="background"]')
    except Exception:
        styled_nodes = []
    for styled in styled_nodes:
        candidate = _extract_image(styled, base_url)
        if _is_usable_article_image(candidate):
            return candidate

    selectors = (
        ".bs-blog-thumb img", "img.wp-post-image", ".post-thumbnail img",
        ".td-post-featured-image img", ".entry-thumb img",
        "figure img", ".entry-content img", "article img", "img",
    )
    for selector in selectors:
        try:
            candidates = node.select(selector)
        except Exception:
            candidates = []
        for tag in candidates:
            classes = " ".join(tag.get("class", [])).lower()
            if any(x in classes for x in ("avatar", "logo", "icon", "emoji")):
                continue
            candidate = _extract_image(tag, base_url)
            if _is_usable_article_image(candidate):
                return candidate
    return None

def _host_key(url: str) -> str:
    """Kunci host untuk membandingkan www/subdomain media yang sama."""
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    # Suffix publik dua label yang umum di Indonesia/UK/Australia.
    multi_suffixes = {"co.id", "go.id", "or.id", "ac.id", "sch.id", "com.au", "co.uk", "com.br"}
    if len(labels) >= 3 and ".".join(labels[-2:]) in multi_suffixes:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _same_site(url: str, base_url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    base_host = (urlparse(base_url).hostname or "").lower().removeprefix("www.")
    return bool(host and base_host and (host == base_host or host.endswith("." + base_host) or base_host.endswith("." + host) or _host_key(url) == _host_key(base_url)))


def _is_skip_article_anchor(anchor, url: str, base_url: str) -> bool:
    href_path = urlparse(url).path.rstrip("/")
    base_path = urlparse(base_url).path.rstrip("/")
    txt = (anchor.get("title") or _txt(anchor) or "").strip().lower()
    if not href_path or href_path == base_path and urlparse(url).query == urlparse(base_url).query:
        return True
    if SKIP_LINK_PATTERNS.search(url):
        return True
    if txt in {
        "menu", "beranda", "home", "selanjutnya", "next", "previous", "prev",
        "lihat semua", "read more", "baca selengkapnya", "lanjut baca",
        "selengkapnya", "masuk", "login", "register", "daftar", "cari",
    }:
        return True
    return False


def _anchor_candidates(node, link_sel: str, title_sel: str) -> list:
    """Ambil kandidat link artikel dengan prioritas selector yang diberikan."""
    anchors, seen_ids = [], set()

    def add(candidate):
        if candidate is None:
            return
        candidates = []
        if getattr(candidate, "name", None) == "a" and candidate.get("href"):
            candidates.append(candidate)
        else:
            try:
                candidates.extend(candidate.select("a[href]"))
            except Exception:
                pass
        for anchor in candidates:
            ident = id(anchor)
            if ident not in seen_ids:
                seen_ids.add(ident)
                anchors.append(anchor)

    # Jika item sendiri merupakan tag <a> (pola RRI/Radar), tetap diproses.
    add(node)
    try:
        for candidate in node.select(link_sel):
            add(candidate)
    except Exception:
        pass
    try:
        for candidate in node.select(title_sel):
            add(candidate)
    except Exception:
        pass
    try:
        for candidate in node.select("a[href]"):
            add(candidate)
    except Exception:
        pass

    # Judul bermakna dan URL artikel lebih diutamakan daripada anchor generik.
    def score(anchor):
        href = anchor.get("href", "")
        label = (anchor.get("title") or _txt(anchor) or "").strip()
        return (
            5 if ARTICLE_LINK_HINTS.search(href) else 0,
            3 if len(label) >= 15 else 1 if len(label) >= 8 else 0,
            1 if anchor.find_parent(["h1", "h2", "h3", "h4"]) else 0,
            len(label),
        )
    anchors.sort(key=score, reverse=True)
    return anchors


def _title_for_anchor(anchor, item, title_sel: str) -> str:
    label = (anchor.get("title") or _txt(anchor) or "").strip()
    if len(label) >= 8 and label.lower() not in {
        "baca selengkapnya", "selengkapnya", "read more", "lanjut baca", "lihat semua",
    }:
        return re.sub(r"\s+", " ", label)
    # Gunakan judul di heading terdekat dahulu agar tombol baca tidak menjadi judul.
    parent = anchor.find_parent(["h1", "h2", "h3", "h4"])
    if parent:
        candidate = _txt(parent).strip()
        if len(candidate) >= 8:
            return re.sub(r"\s+", " ", candidate)
    try:
        title_node = item.select_one(title_sel) if item is not None else None
    except Exception:
        title_node = None
    candidate = (title_node.get("title") or _txt(title_node) or "").strip() if title_node else ""
    if len(candidate) >= 8 and candidate.lower() not in {"baca selengkapnya", "read more"}:
        return re.sub(r"\s+", " ", candidate)
    return _derive_title_from_url(anchor.get("href", ""))


def parse_list_page(html: str, base_url: str, selectors: dict) -> list[dict]:
    """Parse listing dengan selector spesifik situs plus fallback berbasis judul.

    Halaman daftar yang menggunakan anchor sebagai item, slider clone, maupun tema
    WordPress/JNews/Bootstrap tetap dapat diproses. Satu item tidak akan gagal hanya
    karena selector link pertama ternyata tombol navigasi atau logo.
    """
    soup = BeautifulSoup(html or "", "lxml")
    item_sel = selectors.get("item") or "article"
    title_sel = selectors.get("title") or "h1, h2, h3, h4"
    link_sel = selectors.get("link") or title_sel + " a"
    date_sel = selectors.get("date") or "time, .date, .entry-date"
    summary_sel = selectors.get("summary") or ".entry-summary, .excerpt, p"

    try:
        items = soup.select(item_sel)
    except Exception:
        items = []

    # Sebagian situs (RRI / Disway) punya link berita sebagai elemen utama, bukan <article>.
    # Jika selector item tidak ditemukan, proses judul yang benar-benar ada di heading.
    candidate_groups = [(it, True) for it in items]
    if not items:
        try:
            candidate_groups = [(n, False) for n in soup.select(title_sel)]
        except Exception:
            candidate_groups = []

    results: list[dict] = []
    seen: set[str] = set()
    base_host = urlparse(base_url).hostname or ""

    def append_from(node, strict_item: bool):
        anchors = _anchor_candidates(node, link_sel, title_sel)
        for anchor in anchors:
            href = (anchor.get("href") or "").strip()
            url = _normalize_url(href, base_url)
            if not url or url in seen or not _same_site(url, base_url):
                continue
            url_pattern = selectors.get("url_regex")
            if url_pattern and not re.search(url_pattern, url, re.I):
                continue
            if _is_skip_article_anchor(anchor, url, base_url):
                continue

            title = _title_for_anchor(anchor, node, title_sel)
            if not title or len(title) < 8 or title.lower() in {
                "menu", "beranda", "home", "next", "previous", "baca selengkapnya",
                "read more", "lanjut baca", "pengumuman", "berita", "artikel",
            }:
                continue
            # Link non-artikel yang bukan selector judul perlu punya bentuk URL artikel.
            is_explicit = False
            try:
                is_explicit = bool(node.select_one(link_sel) is anchor) or bool(node.select_one(title_sel) is anchor)
            except Exception:
                pass
            if not ARTICLE_LINK_HINTS.search(url) and not is_explicit:
                # Slug WordPress/Kuningan Mass tidak memuat /berita/; izinkan bila berada
                # langsung pada judul artikel yang spesifik.
                heading = anchor.find_parent(["h1", "h2", "h3", "h4"])
                if not heading:
                    continue

            image = _pick_article_image(node, base_url)
            date = None
            try:
                date_node = node.select_one(date_sel)
            except Exception:
                date_node = None
            if date_node:
                # Teks visual pada situs DPRD punya tanggal benar, sementara datetime-nya
                # kadang template statis lama; utamakan teks yang tampil.
                date = _parse_date(_txt(date_node) or date_node.get("datetime") or "")
                if not date:
                    date = _parse_date(date_node.get("datetime") or "")
            summary = ""
            try:
                summary_node = node.select_one(summary_sel)
                if summary_node:
                    summary = _txt(summary_node)
            except Exception:
                pass
            if not summary:
                # Ambil teks paragraf pertama yang bukan judul/tombol; batasi agar tidak
                # menelan seluruh homepage saat item selector terlalu luas.
                try:
                    paragraphs = [
                        _txt(p) for p in node.select("p")
                        if len(_txt(p)) > 35 and _txt(p).strip() != title
                    ]
                    summary = paragraphs[0] if paragraphs else ""
                except Exception:
                    summary = ""
            results.append({
                "title": title,
                "link": url,
                "date": date,
                "summary": summary[:500],
                "image": image,
            })
            seen.add(url)
            # Satu item bisa memiliki tombol detail tambahan; ambil satu artikel saja.
            break

    for item, strict in candidate_groups:
        append_from(item, strict)

    # Fallback judul untuk kartu yang class-nya berubah atau selector item terlalu ketat.
    # Ini tetap mengejar anchor di heading, bukan semua link navigasi pada halaman.
    fallback_nodes = []
    if not results or selectors.get("fallback_title_links"):
        try:
            fallback_nodes = soup.select("h1 a[href], h2 a[href], h3 a[href], h4 a[href], .entry-title a[href], .jeg_post_title a[href], .cv-post-title a[href], .headline-title a[href]")
        except Exception:
            fallback_nodes = []
    for anchor in fallback_nodes:
        href = anchor.get("href", "")
        url = _normalize_url(href, base_url)
        if not url or url in seen or not _same_site(url, base_url):
            continue
        url_pattern = selectors.get("url_regex")
        if url_pattern and not re.search(url_pattern, url, re.I):
            continue
        if _is_skip_article_anchor(anchor, url, base_url):
            continue
        title = (anchor.get("title") or _txt(anchor) or "").strip()
        if len(title) < 8 or title.lower() in {"baca selengkapnya", "read more", "lanjut baca", "beranda", "home"}:
            continue
        # Cari kartu/ancestor terdekat untuk metadata tanpa mengambil seluruh halaman.
        card = anchor
        for _ in range(5):
            parent = getattr(card, "parent", None)
            if parent is None or getattr(parent, "name", None) in ("body", "html"):
                break
            card = parent
            card_text = _txt(card)
            if len(card_text) >= len(title) + 25 and len(card_text) <= 2200:
                break
        date = None
        try:
            date_node = card.select_one(date_sel) or card.select_one("time, .date, .entry-date, .post-date, .tanggal, [class*='date']")
            if date_node:
                date = _parse_date(_txt(date_node) or date_node.get("datetime") or "")
        except Exception:
            pass
        try:
            summary_node = card.select_one(summary_sel)
            summary = _txt(summary_node) if summary_node else ""
        except Exception:
            summary = ""
        if not summary:
            summary = next((_txt(x) for x in card.select("p") if len(_txt(x)) > 35), "")
        results.append({"title": re.sub(r"\s+", " ", title), "link": url, "date": date,
                        "summary": summary[:500], "image": _pick_article_image(card, base_url)})
        seen.add(url)

    return results


# =====================================================
# Ekstraksi konten
# =====================================================
def _remove_excluded_elements(soup: BeautifulSoup, exclude_sel: str):
    if not exclude_sel:
        return
    for sel in exclude_sel.split(","):
        sel = sel.strip()
        if not sel:
            continue
        try:
            for el in soup.select(sel):
                el.decompose()
        except Exception:
            pass


def _extract_content(soup: BeautifulSoup, selectors_detail: dict) -> str:
    exclude_sel = selectors_detail.get("exclude_selectors", "")

    candidates = selectors_detail.get("content", "").split(",")
    for sel in candidates:
        sel = sel.strip()
        if not sel:
            continue
        try:
            node = soup.select_one(sel)
        except Exception:
            continue
        if not node:
            continue

        node_copy = BeautifulSoup(str(node), "lxml")
        _remove_excluded_elements(node_copy, exclude_sel)

        paragraphs = []
        seen_texts = set()
        for p in node_copy.find_all(["p", "h2", "h3", "li"]):
            t = p.get_text(" ", strip=True)
            if len(t) < 30:
                continue
            if t in seen_texts:
                continue
            if _is_navigation_text(t):
                continue
            if t.lower().startswith((
                "baca juga", "baca:", "lihat juga",
                "copyright", "©", "menu", "beranda",
            )):
                continue
            seen_texts.add(t)
            paragraphs.append(t)

        if len(paragraphs) >= 2 and sum(len(p) for p in paragraphs) > 100:
            return "\n\n".join(paragraphs)

    fallback_sel = selectors_detail.get("content_fallback", "")
    if fallback_sel:
        soup_copy = BeautifulSoup(str(soup), "lxml")
        _remove_excluded_elements(soup_copy, exclude_sel)

        paragraphs = []
        seen_texts = set()
        try:
            nodes = soup_copy.select(fallback_sel)
        except Exception:
            nodes = []
        for node in nodes:
            t = node.get_text(" ", strip=True)
            if len(t) < 50:
                continue
            if t in seen_texts:
                continue
            if _is_navigation_text(t):
                continue
            if t.lower().startswith(("baca juga", "copyright", "©", "berita terkait")):
                continue
            seen_texts.add(t)
            paragraphs.append(t)

        if len(paragraphs) >= 2 and sum(len(p) for p in paragraphs) > 100:
            return "\n\n".join(paragraphs)

    # Fallback universal untuk situs yang memakai class konten berbeda.
    # Buat salinan agar navigasi/sidebar tidak mengotori hasil utama.
    generic_copy = BeautifulSoup(str(soup), "lxml")
    generic_excludes = ", ".join(part for part in (
        exclude_sel,
        "nav, header, footer, aside, script, style, noscript, form, button, "
        ".sidebar, .widget, .related, .related-posts, .author-box, .comments, "
        ".comment-list, .breadcrumb, .pagination",
    ) if part)
    _remove_excluded_elements(generic_copy, generic_excludes)
    generic_selectors = (
        "article .entry-content", "article .post-content", "article .article-content",
        "article .content", "article", "main .entry-content", "main article",
        ".entry-content", ".post-content", ".article-content", ".news-content",
        ".detail-content", ".post-body", ".td-post-content", "main",
    )
    for selector in generic_selectors:
        try:
            node = generic_copy.select_one(selector)
        except Exception:
            node = None
        if not node:
            continue
        extracted = []
        seen = set()
        for paragraph in node.find_all(["p", "h2", "h3", "li"]):
            value = paragraph.get_text(" ", strip=True)
            low = value.lower()
            if len(value) < 35 or value in seen or _is_navigation_text(value):
                continue
            if low.startswith(("baca juga", "baca selengkapnya", "lihat juga", "copyright", "©")):
                continue
            seen.add(value)
            extracted.append(value)
        joined = "\n\n".join(extracted)
        if len(extracted) >= 2 and len(joined) >= 180:
            return joined

    return ""


def fetch_detail(url: str, selectors_detail: dict) -> dict:
    resp = safe_get(url)
    if resp is None:
        return {
            "content": "", "author": None, "date": None,
            "category": [], "images": [], "error": "Gagal fetch detail",
        }

    soup = BeautifulSoup(resp.text, "lxml")
    content = _extract_content(soup, selectors_detail)

    # === Images — pakai extractor WP lengkap ===
    images = _extract_all_images_from_soup(soup, url)

    author = None
    try:
        author_sel = selectors_detail.get("author") or ".__none__"
        author = _txt(soup.select_one(author_sel)) or None
    except Exception:
        pass

    date = _extract_date_from_soup(soup, selectors_detail)

    cats = []
    try:
        cat_sel = selectors_detail.get("category") or ".__none__"
        cats = [
            t for t in (
                _txt(n).strip()
                for n in soup.select(cat_sel)
            ) if t
        ]
    except Exception:
        pass

    detail_error = None if content else (
        f"halaman berhasil diambil tetapi konten utama tidak cocok dengan selector; "
        f"title={_txt(soup.title)[:100]!r}, paragraphs={len(soup.select('p'))}"
    )
    return {
        "content": content,
        "author": author,
        "date": date,
        "category": cats[:5],
        "images": images[:10],
        "error": detail_error,
    }


# =====================================================
# Pagination
# =====================================================
def _next_page_url(soup: BeautifulSoup, current_url: str):
    nxt = soup.select_one("a[rel='next']")
    if nxt and nxt.get("href"):
        return _normalize_url(nxt["href"], current_url)

    for sel in (
        ".next", ".pagination .next", "a.next", ".page-numbers.next",
        "li.next a", ".pager .next a", ".nav-links .next",
        "a[aria-label='Next']", "a[aria-label='next']",
    ):
        nxt = soup.select_one(sel)
        if nxt and nxt.get("href"):
            return _normalize_url(nxt["href"], current_url)

    m = re.search(r"/page/(\d+)", current_url)
    if m:
        n = int(m.group(1)) + 1
        return re.sub(r"/page/\d+", f"/page/{n}", current_url)

    for a in soup.find_all("a", href=True):
        txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True).lower())
        href = a.get("href", "")
        if txt in ("next", "berikutnya", "selanjutnya", "»", "›", "next »", ">"):
            return _normalize_url(href, current_url)
        # Inilah Kuningan and Potret Kuningan use a visible "Muat Lainnya" link
        # whose href points to a normal /page/2/ archive. The former logic missed it.
        if txt in ("muat lainnya", "muat lebih banyak", "load more", "show more", "lihat lainnya"):
            if re.search(r"/page/\d+/?(?:$|[?#])", href) or re.search(r"[?&](?:paged|page|start)=\d+", href):
                return _normalize_url(href, current_url)
    return None


# =====================================================
# Structured feeds / WordPress REST API
# =====================================================
def _strip_html(value) -> str:
    """Ubah field HTML dari REST API/RSS menjadi teks yang bersih."""
    if not value:
        return ""
    if isinstance(value, dict):
        value = value.get("rendered", "")
    return BeautifulSoup(str(value), "lxml").get_text(" ", strip=True)


def _parse_structured_payload(resp, base_url: str) -> list[dict]:
    """
    Parse WordPress REST API JSON atau RSS/Atom.
    Tidak bergantung pada selector HTML tema yang bisa berubah.
    """
    if resp is None or not getattr(resp, "text", ""):
        return []

    raw = resp.text.strip()
    content_type = (getattr(resp, "headers", {}) or {}).get("Content-Type", "").lower()

    # WordPress REST API: daftar object JSON dengan title/link/content/excerpt.
    if "json" in content_type or raw.startswith("[") or raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            payload = None

        if isinstance(payload, dict):
            # Beberapa API membungkus hasil di dalam key data/items/posts.
            for key in ("posts", "items", "data", "results"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break

        if isinstance(payload, list):
            out = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                title = _strip_html(item.get("title", ""))
                link = item.get("link") or item.get("url") or item.get("guid", "")
                if isinstance(link, dict):
                    link = link.get("rendered", "") or link.get("url", "")
                link = _normalize_url(str(link), base_url) if link else None
                if not title or not link:
                    continue

                content_html = item.get("content", "")
                if isinstance(content_html, dict):
                    content_html = content_html.get("rendered", "")
                excerpt_html = item.get("excerpt", item.get("summary", ""))
                content = _strip_html(content_html)
                summary = _strip_html(excerpt_html)[:500]
                date_raw = item.get("date") or item.get("date_gmt") or item.get("published")
                date = _parse_date(str(date_raw)) if date_raw else None

                image = None
                images = []
                embedded = item.get("_embedded", {})
                if isinstance(embedded, dict):
                    media = embedded.get("wp:featuredmedia", [])
                    if media and isinstance(media[0], dict):
                        image = media[0].get("source_url")
                if not image and isinstance(item.get("image"), str):
                    image = item.get("image")
                if image:
                    image = _normalize_url(image, link)
                    if _is_usable_article_image(image):
                        images.append(image)

                author = None
                if isinstance(embedded, dict):
                    authors = embedded.get("author", [])
                    if authors and isinstance(authors[0], dict):
                        author = authors[0].get("name")

                categories = []
                if isinstance(item.get("categories"), list):
                    categories = [str(c) for c in item["categories"] if c]
                elif isinstance(embedded, dict):
                    terms = embedded.get("wp:term", [])
                    for group in terms if isinstance(terms, list) else []:
                        if isinstance(group, list):
                            categories.extend(
                                str(term.get("name")) for term in group
                                if isinstance(term, dict) and term.get("name")
                            )

                out.append({
                    "title": title, "link": link, "date": date,
                    "summary": summary, "content": content,
                    "image": image, "images": images, "author": author,
                    "detail_date": date, "category": categories[:5],
                })
            return out

    # RSS / Atom XML
    try:
        soup = BeautifulSoup(raw, "xml")
    except Exception:
        return []
    entries = soup.find_all(["item", "entry"])
    out = []
    seen = set()
    for entry in entries:
        title = _txt(entry.find("title"))
        link_node = entry.find("link")
        link = ""
        if link_node:
            link = link_node.get("href") or link_node.get_text(strip=True) or link_node.get("href", "")
        if not link:
            guid = entry.find("guid")
            link = _txt(guid)
        link = _normalize_url(link, base_url) if link else None
        if not title or not link or link in seen:
            continue
        seen.add(link)

        summary_node = entry.find(["description", "summary", "content:encoded", "content"])
        summary = _txt(summary_node)[:500] if summary_node else ""
        content_node = entry.find("content:encoded") or entry.find("content")
        content = _txt(content_node) if content_node else summary
        date_node = entry.find(["pubDate", "published", "updated", "dc:date"])
        date = _parse_date(_txt(date_node)) if date_node else None
        image = None
        enclosure = entry.find("enclosure")
        media = entry.find(["media:content", "media:thumbnail"])
        if enclosure and enclosure.get("url"):
            image = enclosure.get("url")
        elif media:
            image = media.get("url")
        image = _normalize_url(image, link) if image else None
        out.append({
            "title": title, "link": link, "date": date,
            "summary": summary, "content": content, "image": image,
            "images": [image] if _is_usable_article_image(image) else [],
            "author": None, "detail_date": date, "category": [],
        })
    return out


def _fetch_structured_source(source: dict) -> list[dict]:
    """
    Coba endpoint API/feed jika dikonfigurasi. Kegagalan endpoint ini
    tidak menghentikan fallback HTML biasa.
    """
    collected = []
    seen = set()
    api_urls = source.get("api_urls", [])
    feed_urls = source.get("feed_urls", [])

    for base_api in api_urls:
        max_pages = int(source.get("api_max_pages", source.get("max_pages", 3)))
        for page_num in range(1, max_pages + 1):
            # WordPress REST memakai page/per_page; jika URL belum punya page,
            # tambahkan parameter secara aman.
            from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
            parts = urlsplit(base_api)
            query = dict(parse_qsl(parts.query, keep_blank_values=True))
            query["page"] = str(page_num)
            query.setdefault("per_page", "100")
            api_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
            resp = safe_get(api_url)
            if resp is None:
                # Kaitkan diagnosis URL aktual (yang mungkin sudah diberi page/per_page)
                # dengan endpoint API asal untuk menghitung host yang benar-benar tertahan.
                base_errors = _FETCH_DIAGNOSTICS.setdefault(base_api, [])
                for message in _FETCH_DIAGNOSTICS.get(api_url, []):
                    if message not in base_errors:
                        base_errors.append(message)
                if page_num == 1:
                    log.warning("[%s] API tidak dapat diakses; lanjut ke feed/HTML.",
                                source.get("name", "sumber"))
                break
            articles = _parse_structured_payload(resp, api_url)
            if not articles:
                # Page kosong / API tidak mendukung endpoint ini.
                break
            added = 0
            for art in articles:
                if art["link"] not in seen:
                    seen.add(art["link"])
                    collected.append(art)
                    added += 1
            log.info("[%s] API page %s: %s artikel baru (total %s)",
                     source.get("name", "sumber"), page_num, added, len(collected))
            if added == 0 or len(articles) < int(query.get("per_page", "100")):
                break

    for feed_url in feed_urls:
        resp = safe_get(feed_url)
        if resp is None:
            log.warning("[%s] feed gagal diakses: %s", source.get("name", "sumber"), feed_url)
            continue
        articles = _parse_structured_payload(resp, feed_url)
        added = 0
        for art in articles:
            if art["link"] not in seen:
                seen.add(art["link"])
                collected.append(art)
                added += 1
        log.info("[%s] feed: %s artikel baru (total %s)",
                 source.get("name", "sumber"), added, len(collected))

    return collected


def _listing_diagnostic(html: str, selectors: dict) -> str:
    """Compact clues for selector mismatch vs. HTML that is not an article listing."""
    try:
        soup = BeautifulSoup(html or "", "lxml")
        title = _txt(soup.title) or "(tanpa title)"
        item_selector = selectors.get("item") or "article"
        title_selector = selectors.get("title") or "h1,h2,h3,h4"
        try:
            item_count = len(soup.select(item_selector))
        except Exception:
            item_count = -1
        try:
            heading_count = len(soup.select(title_selector))
        except Exception:
            heading_count = -1
        article_count = len(soup.select("article"))
        link_count = len(soup.select("a[href]"))
        challenge = _is_challenge_page(html)
        return (f"title={title[:100]!r}, bytes={len(html or '')}, "
                f"items={item_count}, titles={heading_count}, articles={article_count}, "
                f"links={link_count}, challenge={challenge}")
    except Exception as exc:
        return f"diagnostik HTML gagal: {type(exc).__name__}: {exc}"


# Snapshot HTML lokal untuk sumber yang mengembalikan halaman perantara pada HTTP.
# Ini adalah DATA SNAPSHOT, bukan data live. Ganti file ini jika pengguna menyimpan
# salinan HTML terbaru melalui metode yang sah (misalnya Safari/View Source).
LOCAL_SNAPSHOT_FILES = {
    "Bappeda Kuningan": "bappeda.html",
    "Pemkab Kuningan — Kategori Daerah": "pemkab_daerah.html",
    "Pemkab Kuningan — Publikasi Berita": "pemkab_publikasi_berita.html",
    "Pemkab Kuningan — Publikasi Pengumuman": "pemkab_publikasi_pengumuman.html",
    "Inilah Kuningan": "inilah_kuningan.html",
    "Potret Kuningan": "potret_kuningan.html",
    "Media Kuningan": "media_kuningan.html",
    "Kuningan Religi": "kuningan_religi.html",
}


def _load_local_snapshot(source: dict, network_error: str | None = None) -> dict | None:
    """Parse local HTML snapshot as an explicitly marked partial/offline source."""
    filename = LOCAL_SNAPSHOT_FILES.get(source.get("name", ""))
    if not filename:
        return None
    snapshot_path = Path(__file__).resolve().parent / "manual_html" / filename
    if not snapshot_path.is_file():
        return None
    try:
        html = snapshot_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("Snapshot lokal tidak bisa dibaca | file=%s | error=%s", snapshot_path, exc)
        return None

    if _is_challenge_page(html):
        log.error("Snapshot lokal juga merupakan halaman challenge; tidak digunakan | file=%s", snapshot_path)
        return None

    base_url = source.get("url", "")
    articles = parse_list_page(html, base_url, source.get("selectors", {}))
    if not articles:
        log.warning("Snapshot lokal tidak menghasilkan artikel | sumber=%s | file=%s | %s",
                    source.get("name"), snapshot_path.name,
                    _listing_diagnostic(html, source.get("selectors", {})))
        return None

    for article in articles:
        summary = (article.get("summary") or "").strip()
        article["content"] = summary
        article["content_quality"] = "ringkasan_saja" if summary else "kosong"
        article["content_source"] = "snapshot_lokal"
        article["source_mode"] = "snapshot_lokal"
        article["snapshot_file"] = f"manual_html/{snapshot_path.name}"

    message = (
        f"Menggunakan snapshot HTML lokal {snapshot_path.name}; data bukan live dan "
        "tanggal pembaruan snapshot perlu diverifikasi."
    )
    if network_error:
        message = f"Akses live gagal ({network_error[:180]}). {message}"
    log.warning("[%s] %s Artikel snapshot=%s", source.get("name", "sumber"), message, len(articles))
    return {
        "source": source.get("name", "sumber"),
        "url": source.get("url"),
        "status": "partial",
        "is_official": source.get("is_official", False),
        "is_official_gov": source.get("is_official_gov", False),
        "count": len(articles),
        "articles": articles,
        "error": message,
        "fetch_mode": "local_snapshot",
        "snapshot_file": f"manual_html/{snapshot_path.name}",
    }


# =====================================================
# Fetch satu sumber
# =====================================================
def fetch_source(source: dict, fetch_detail_enabled: bool = True) -> dict:
    urls = list(dict.fromkeys([source["url"]] + source.get("fallback_urls", [])))
    max_pages = source.get("max_pages", 1)
    last_err = None

    # Endpoint terstruktur (REST API/RSS) lebih stabil daripada selector tema.
    structured_articles = _fetch_structured_source(source)
    if structured_articles:
        if fetch_detail_enabled:
            # Konten REST/RSS biasanya sudah menyertakan isi. Ambil detail HTML
            # hanya bila isinya belum tersedia, agar tidak mengulang fetch yang sia-sia.
            for art in structured_articles:
                if not art.get("content") and source.get("detail"):
                    try:
                        detail = fetch_detail(art["link"], source["detail"])
                        art["content"] = detail.get("content", "")
                        art["images"] = detail.get("images", [])
                        art["author"] = detail.get("author") or art.get("author")
                        art["category"] = detail.get("category", [])
                        art["detail_date"] = detail.get("date")
                    except Exception as exc:
                        log.warning("[%s] detail API fallback gagal | url=%s | error=%s",
                                    source.get("name", "sumber"), art.get("link"), exc)
        for art in structured_articles:
            if (art.get("content") or "").strip():
                art.setdefault("content_quality", "lengkap")
                art.setdefault("content_source", "feed_api")
            elif (art.get("summary") or "").strip():
                art["content"] = art["summary"].strip()
                art["content_quality"] = "ringkasan_saja"
                art["content_source"] = "feed_api_ringkasan"
            else:
                art["content_quality"] = "kosong"
                art["content_source"] = "tidak_tersedia"
        log.info("[%s] memakai data terstruktur: %s artikel",
                 source.get("name", "sumber"), len(structured_articles))
        # Samakan kontrak hasil API/RSS dengan hasil parser HTML agar dashboard
        # tidak menandai sumber berhasil sebagai error atau menghitung 0 artikel.
        return {
            "source": source.get("name", "sumber"),
            "url": source.get("url"),
            "status": "ok",
            "is_official": source.get("is_official", False),
            "is_official_gov": source.get("is_official_gov", False),
            "count": len(structured_articles),
            "articles": structured_articles,
            "error": None,
            "fetch_mode": "structured",
        }

    blocked_hosts = set()
    # Bila semua API/feed publik untuk host yang sama sudah diblokir oleh halaman
    # perantara/403/TLS, jangan ulangi request listing ke host itu berkali-kali.
    structured_urls = list(source.get("api_urls", []) or []) + list(source.get("feed_urls", []) or [])
    by_host: dict[str, list[str]] = {}
    for endpoint in structured_urls:
        endpoint_host = (urlparse(endpoint).hostname or "").lower()
        if endpoint_host:
            by_host.setdefault(endpoint_host, []).append(endpoint)
    restrictive = (
        "halaman challenge/waf", "halaman perantara", "certificate_verify_failed",
        "certificateverifyerror", "tls certificate verification failed", "http 403",
        "http 401", "http 451", "access denied",
    )
    for endpoint_host, endpoint_urls in by_host.items():
        endpoint_errors = [_FETCH_DIAGNOSTICS.get(endpoint, []) for endpoint in endpoint_urls]
        if endpoint_errors and all(errs and any(tok in " ".join(errs).lower() for tok in restrictive) for errs in endpoint_errors):
            blocked_hosts.add(endpoint_host)
            log.warning("[%s] endpoint API/feed pada %s semuanya tertahan; skip request HTML live berulang dan gunakan snapshot lokal bila tersedia.",
                        source.get("name", "sumber"), endpoint_host)

    for start_url in urls:
        host = (urlparse(start_url).hostname or "").lower()
        if host in blocked_hosts:
            log.warning("[%s] melewati fallback %s karena host %s sudah terdeteksi menolak/menantang request",
                        source.get("name", "sumber"), start_url, host)
            continue
        log.info(f"[{source['name']}] GET {start_url}")
        resp = safe_get(start_url)
        if resp is None:
            details = _FETCH_DIAGNOSTICS.get(start_url, [])
            last_reason = details[-1] if details else "tidak ada respons valid"
            last_err = f"Gagal fetch {start_url}: {last_reason}"
            diagnostics = " ".join(details).lower()
            if any(token in diagnostics for token in (
                "challenge/waf", "halaman perantara", "certificate_verify_failed", "certificateverifyerror",
                "http 403", "http 451", "request blocked",
            )):
                blocked_hosts.add(host)
            continue

        all_articles = []
        seen_links = set()
        current_url = start_url
        page = 1
        html = resp.text

        while current_url and page <= max_pages:
            if page > 1:
                log.info(f"[{source['name']}] GET page {page}: {current_url}")
                r = safe_get(current_url)
                if r is None:
                    log.warning(
                        "[%s] pagination dihentikan pada page %s karena gagal fetch: %s. "
                        "Artikel dari halaman sebelumnya tetap diproses.",
                        source.get("name", "sumber"), page, current_url,
                    )
                    break
                html = r.text

            try:
                soup = BeautifulSoup(html, "lxml")
                page_articles = parse_list_page(html, current_url, source["selectors"])
            except Exception as e:
                log.error(f"  parse_list_page error: {e}")
                page_articles = []

            new_count = 0
            for art in page_articles:
                if art["link"] not in seen_links:
                    seen_links.add(art["link"])
                    all_articles.append(art)
                    new_count += 1

            log.info(
                f"  page {page}: {new_count} artikel baru "
                f"(total {len(all_articles)})"
            )
            if new_count == 0:
                break

            current_url = _next_page_url(soup, current_url)
            page += 1
            time.sleep(0.5)

        if not all_articles:
            last_err = (
                f"Tidak ada artikel berhasil diparse dari {start_url}; "
                "selector mungkin tidak cocok, halaman kosong, atau struktur situs berubah"
            )
            log.warning("[%s] %s. Mencoba URL cadangan jika tersedia.", source.get("name", "sumber"), last_err)
            log.warning("[%s] diagnostik listing: %s", source.get("name", "sumber"),
                        _listing_diagnostic(html, source.get("selectors", {})))
            continue

        if fetch_detail_enabled and source.get("detail"):
            content_ok = 0
            content_summary_fallback = 0
            content_fail = 0
            for i, art in enumerate(all_articles, 1):
                log.info(f"  ↳ detail {i}/{len(all_articles)}: {art['link'][:70]}...")
                try:
                    detail = fetch_detail(art["link"], source["detail"])
                except Exception as e:
                    log.warning(f"    ⚠️ detail error: {e}")
                    detail = {
                        "content": "", "author": None, "date": None,
                        "category": [], "images": [], "error": str(e),
                    }

                full_content = (detail.get("content") or "").strip()
                art["images"] = detail.get("images", [])
                art["author"] = detail.get("author") or art.get("author")
                art["detail_date"] = detail.get("date")
                art["category"] = detail.get("category", [])
                if full_content:
                    art["content"] = full_content
                    art["content_quality"] = "lengkap"
                    art["content_source"] = "halaman_detail"
                else:
                    if detail.get("error"):
                        log.warning("[%s] detail tanpa isi yang dapat diekstrak | url=%s | %s",
                                    source.get("name", "sumber"), art.get("link"), detail.get("error"))
                    # Keep a clearly-marked summary fallback for sentiment/relevance analysis.
                    # Never represent this fallback as full article text.
                    summary_fallback = (art.get("summary") or "").strip()
                    if summary_fallback:
                        art["content"] = summary_fallback
                        art["content_quality"] = "ringkasan_saja"
                        art["content_source"] = "halaman_daftar"
                        content_summary_fallback += 1
                    else:
                        art["content"] = ""
                        art["content_quality"] = "kosong"
                        art["content_source"] = "tidak_tersedia"
                        content_fail += 1
                    if detail.get("error"):
                        log.warning("[%s] isi detail tidak lengkap | url=%s | penyebab=%s",
                                    source.get("name", "sumber"), art.get("link"), detail.get("error"))

                if not art.get("date") and detail["date"]:
                    art["date"] = detail["date"]
                # Ganti gambar placeholder/avatar dengan gambar valid dari halaman detail.
                if not _is_usable_article_image(art.get("image")):
                    art["image"] = next(
                        (img for img in art.get("images", []) if _is_usable_article_image(img)),
                        None,
                    )

                if full_content:
                    content_ok += 1
                time.sleep(0.3)

            log.info(
                "  📊 Konten: %s lengkap, %s memakai ringkasan fallback, %s kosong",
                content_ok, content_summary_fallback, content_fail,
            )

        return {
            "source": source["name"],
            "url": start_url,
            "status": "ok",
            "is_official": source.get("is_official", False),
            "is_official_gov": source.get("is_official_gov", False),
            "count": len(all_articles),
            "articles": all_articles,
            "error": None,
        }

    # Jika semua endpoint live gagal, gunakan snapshot yang tersedia secara lokal.
    # Hasil diberi status partial agar tidak disalahartikan sebagai data live.
    local_result = _load_local_snapshot(source, last_err)
    if local_result is not None:
        return local_result

    return {
        "source": source["name"],
        "url": source["url"],
        "status": "error",
        "is_official": source.get("is_official", False),
        "is_official_gov": source.get("is_official_gov", False),
        "count": 0,
        "articles": [],
        "error": last_err,
        "fetch_mode": "http_only",
    }
