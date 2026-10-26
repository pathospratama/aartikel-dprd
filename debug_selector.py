#!/usr/bin/env python3
"""
debug_selector.py v8 — HTTP-only Selector Verifier
Perbaikan dari v6:
  - analyze_listing: pilih item selector yang benar-benar mengandung link artikel
  - deteksi link valid (bukan tag/category/#)
  - HTTP requests biasa; verifikasi TLS aktif; challenge dicatat, tidak dilewati
  - manual selector override dari manual_selectors.py
  - deteksi domain mati (DNS error) lebih jelas
"""

import sys
import re
import time
import json
import argparse
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime

import requests
from bs4 import BeautifulSoup



# =====================================================
# TARGET URLS
# =====================================================
TARGET_URLS = [
    ("Radar Kuningan",           "https://radarkuningan.disway.id/"),
    ("Kabar Kuningan (PR)",      "https://kabarkuningan.pikiran-rakyat.com/"),
    ("Kuningan Religi",          "https://kuninganreligi.com/"),
    ("Kuningan Mass",            "https://kuninganmass.com/"),
    ("Detik (Tag Kuningan)",     "https://www.detik.com/tag/kuningan"),
    ("Pemkab Kuningan — Daerah", "https://kuningankab.go.id/home/category/daerah/"),
    ("Potret Kuningan",          "https://potretkuningan.com/"),
    ("Inilah Kuningan",          "https://inilahkuningan.com/"),
    ("Kuningan Jabar Info",      "https://kuninganjabarinfo.id/"),
    ("Media Kuningan",           "https://mediakuningan.com/"),
    ("PPID Kuningan",            "https://ppid.kuningankab.go.id/artikel"),
    ("Ciremai Today",            "https://ciremaitoday.com/"),
    ("iNews Kuningan",           "https://kuningan.inews.id/"),
    ("Media Identitas",          "https://mediaidentitas.com/"),
    ("Kuningan News",            "https://www.kuningannews.com/"),
]


# =====================================================
# URL filter — abaikan link yang bukan artikel
# =====================================================
SKIP_LINK_PATTERNS = re.compile(
    r"(#|/tag/|/tags/|/category/|/categories/|/kategori/|/kanal/|"
    r"/author/|/page/|/search/|/login/|/register/|/about/|/contact/|"
    r"javascript:|mailto:|tel:)", re.IGNORECASE
)

# Link artikel biasanya mengandung salah satu pola ini
ARTICLE_LINK_HINTS = re.compile(
    r"(/read/|/berita/|/artikel/|/news/|/post/|/detail/|/\d{4}/\d{2}/|"
    r"/20\d{2}/|/baca/|/view/|\.html|\.shtml)",
    re.IGNORECASE,
)


def is_article_link(href: str) -> bool:
    """Cek apakah href adalah link artikel (bukan menu/tag/category)."""
    if not href or len(href) < 15:
        return False
    if SKIP_LINK_PATTERNS.search(href):
        return False
    return bool(ARTICLE_LINK_HINTS.search(href))


# =====================================================
# KANDIDAT SELECTOR
# =====================================================
LIST_ITEM_SELECTORS = [
    "article", ".post", ".post-outer", ".td_module_wrap",
    "article.post", "article.type-post", ".hentry",
    ".news-item", ".list-news", ".card", ".berita-item",
    ".item", ".post-item", ".news-list",
    ".pt-10", "li.pt-10", "li.pt-8",
    "div[class*='post']", "div[class*='news']",
    "div[class*='item']", "div[class*='artikel']", "div[class*='berita']",
    ".col-md-4", ".col-md-6", ".list-item",
    ".artikel-item", ".berita", ".post-card", ".news-card",
    ".post-outer", ".post-outer-container", ".blog-posts .post",
    "main article", "section article", "ul li article",
]

# Selector tambahan untuk listing (v7) — spesifik per struktur umum
LIST_ITEM_SELECTORS_SPECIFIC = [
    # Disway (Radar Kuningan)
    "div.row .post-item", ".wrap__list .item",
    "div[class*='post-list'] .item",
    # PR Network (Pikiran Rakyat)
    "div.pt-10", "li.pt-10", "ul li.pt-10",
    "div[class*='pt-10']",
    # Pikiran Rakyat — kartu berita
    ".pt-8", "li.pt-8", "div[class*='pt-8']",
    # iNews
    ".card-news", ".card-article", "div[class*='card-news']",
    # Grid umum
    "div.row > div[class*='col-'] > a",
]

CONTENT_SELECTORS = [
    "article.newsSingleWrap", "div.entry-content", "div.post-content",
    "div.post-body", "div.post-body.entry-content",
    "div.detail__body-text", "div.itp_bodycontent",
    "div.berita-content", "div.content-body", "div.post-entry",
    "div[itemprop='articleBody']", "div[itemprop='text']",
    "div.article-content", "div.detail-content", "div.content-detail",
    "div.txt-article", "div.isi", "div.artikel-content",
    "div.content__article", "div.article__content",
    "article .entry-content", "article .post-content",
    "article .post-body",
    "article.post-outer-container .post-body.entry-content",
    "article.post-outer-container .post-content",
    "article.detail", "article.news-detail", "article.newsDetail",
    "main article .entry-content", "main article .post-content",
    "div.detail__content", "div.body-text",
    "div[class*='body-text']", "div[class*='article-body']",
    "div[class*='post-body']", "div[class*='entry-content']",
    # content wrapper umum WordPress
    "div.content-area", "div.main-content",
    "div.single-content", "div.article-content",
    # fallback
    "article", "main article", "main", ".container",
    "div[class*='content']", "div[class*='berita']",
    "div[class*='artikel']", "div[class*='detail']",
]

TITLE_SELECTORS = [
    "h1.entry-title", "h1.post-title", "h1.article-title",
    "h1.detail__title", "h1.title", "h1.judul",
    "h1[itemprop='headline']", "h2.entry-title", "h2.post-title",
    ".entry-title", ".post-title", ".title", ".judul",
    "article h2", "article h3", "h2", "h3",
    "a > h2", "a > h3", "a > h4",
    "a[title]",  # fallback: pakai atribut title
]

LINK_SELECTORS = [
    "h2 a", "h3 a", "h4 a", ".entry-title a", ".post-title a",
    ".title a", ".judul a",
    "a[href*='/read/']", "a[href*='/berita/']", "a[href*='/artikel/']",
    "a[href*='/news/']", "a[href*='/post/']", "a[href*='/detail/']",
    "a[href*='.html']", "a[href*='.shtml']",
    "a[href]",  # fallback
]

DATE_SELECTORS = [
    ".date", ".tanggal", "time", ".entry-date", ".post-date",
    ".published", ".meta-date", ".detail__date", ".post-meta time",
    "span.date", "small.date", "[datetime]", ".date-header",
    ".entry-meta", ".meta",
]

SUMMARY_SELECTORS = [
    ".entry-summary", ".excerpt", ".summary", ".ringkasan",
    ".post-excerpt", ".card-text", ".description", ".snippet",
    "article p", "p",
]

IMAGE_SELECTORS = [
    "article img", ".entry-content img", ".post-content img",
    ".detail__media img", ".thumb img", "figure img",
    "img[itemprop='image']", "img[src*='wp-content']",
    "img[src*='blogspot']", "img",  # fallback
]

NAV_CLASS_FRAGMENTS = {
    "nav", "menu", "header", "footer", "sidebar", "widget",
    "breadcrumb", "pagination", "share", "related", "popular",
    "swiper", "carousel", "slider", "profil", "fraksi",
    "snippet", "latest", "list-content", "post-snippet",
}

NAV_KEYWORDS = {
    "profil pimpinan", "profil anggota", "sekertaris dprd",
    "fraksi pdip", "fraksi pks", "fraksi golkar",
    "alat kelengkapan", "badan anggaran", "badan kehormatan",
    "pengaduan dan aspirasi", "beranda", "menu", "home", "copyright",
    "baca juga", "baca:", "lihat juga", "simak juga",
    "artikel terkait", "berita terkait", "popular posts",
}

GENERIC_SELECTORS = {"main", "article", "main article", ".container"}

SEMANTIC_KEYWORDS = {
    "entry-content", "post-content", "post-body", "berita-content",
    "content-body", "post-entry", "detail__body", "itp_bodycontent",
    "newssinglewrap", "news-detail", "newsdetail", "articlebody",
    "article-content", "detail-content", "txt-article",
    "article-body", "body-text",
}

CHALLENGE_MARKERS = (
    "checking your browser", "just a moment", "cf-browser-verification",
    "enable javascript and cookies", "ddos protection",
    "please complete the security check", "verify you are human",
    "challenge-platform", "__cf_chl_", "immutable-waf",
    "k2rr", "outer-container",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

IMPERSONATE_PROFILES = [
    "chrome131", "chrome124", "chrome123", "chrome120",
    "chrome116", "chrome110", "safari18_0", "safari17_0",
    "safari15_5", "firefox135", "firefox133", "firefox120",
]


# =====================================================
# Cookie & Manual Override loader
# =====================================================
def load_cookies_for_domain(domain: str) -> dict:
    """Load cookies dari cookies.json berdasarkan domain."""
    path = Path("cookies.json")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    # Dukungan format: { "domain.com": [{"name":..,"value":..}] } atau cookies list
    if isinstance(data, dict):
        if domain in data:
            raw = data[domain]
            if isinstance(raw, list):
                return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
            if isinstance(raw, dict):
                return raw
    if isinstance(data, list):
        return {c["name"]: c["value"] for c in data
                if isinstance(c, dict) and "name" in c and "value" in c}
    return {}


def load_manual_selectors(domain: str) -> dict:
    """Load manual selectors dari manual_selectors.py."""
    path = Path("manual_selectors.py")
    if not path.exists():
        return {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("manual_selectors", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "MANUAL_SELECTORS", {}).get(domain, {})
    except Exception as e:
        print(f"   ⚠️ manual_selectors.py error: {e}")
        return {}


# =====================================================
# Helper umum
# =====================================================
def is_navigation_text(text: str) -> bool:
    t = text.lower().strip()
    if not t:
        return True
    return sum(1 for kw in NAV_KEYWORDS if kw in t) >= 2


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_paragraphs(node, min_len: int = 30) -> list[str]:
    paragraphs, seen = [], set()
    for p in node.find_all(["p", "h2", "h3", "li"]):
        t = clean_text(p.get_text(" ", strip=True))
        if len(t) < min_len or t in seen or is_navigation_text(t):
            continue
        seen.add(t)
        paragraphs.append(t)
    return paragraphs


def is_challenge_page(html: str) -> bool:
    if not html or len(html) < 2000:
        return True
    low = html.lower()
    if len(html) < 30000:
        return any(m in low for m in CHALLENGE_MARKERS)
    return False


def has_nav_class(node) -> bool:
    if not node.get("class"):
        return False
    classes = " ".join(node.get("class", [])).lower()
    return any(frag in classes for frag in NAV_CLASS_FRAGMENTS)


def count_navigation_paragraphs(paragraphs: list[str]) -> int:
    return sum(1 for p in paragraphs if is_navigation_text(p))


def is_specific_selector(selector: str) -> bool:
    return any(c in selector for c in [".", "#", "[", "]"])


def is_semantic_selector(selector: str) -> bool:
    return any(kw in selector.lower() for kw in SEMANTIC_KEYWORDS)


def is_generic_selector(selector: str) -> bool:
    return selector.strip() in GENERIC_SELECTORS


# =====================================================
# FETCH HTTP BIASA — tanpa browser automation atau bypass challenge
# =====================================================
def fetch_html(url: str) -> tuple[str | None, int, str, str]:
    """Ambil HTML dengan requests biasa dan verifikasi TLS selalu aktif."""
    domain = urlparse(url).netloc
    cookies = load_cookies_for_domain(domain)
    if _is_dns_dead(url):
        return None, 0, "DNS tidak resolve", "requests"
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=30, allow_redirects=True,
            verify=True, cookies=cookies or None,
        )
        if response.status_code != 200:
            return None, response.status_code, f"HTTP {response.status_code}", "requests"
        if not response.text:
            return None, response.status_code, "body kosong", "requests"
        if is_challenge_page(response.text):
            return None, response.status_code, "server mengirim halaman verifikasi/challenge; tidak di-bypass", "requests"
        return response.text, response.status_code, "", "requests"
    except requests.exceptions.SSLError as exc:
        return None, 0, f"TLS verifikasi sertifikat gagal: {str(exc)[:120]}", "requests"
    except requests.exceptions.RequestException as exc:
        return None, 0, f"{type(exc).__name__}: {str(exc)[:120]}", "requests"


def _is_dns_dead(url: str) -> bool:
    """Cek apakah domain resolve via DNS."""
    import socket
    try:
        host = urlparse(url).netloc.split(":")[0]
        socket.gethostbyname(host)
        return False
    except socket.gaierror:
        return True
    except Exception:
        return False


# =====================================================
# ANALISIS LISTING — v7 (lebih pintar)
# =====================================================
def _pick_best_item_selector(soup: BeautifulSoup) -> tuple[str | None, list]:
    """
    Pilih item selector yang:
      - punya >= 3 node
      - node pertama punya link artikel valid (is_article_link)
    Skor: (jumlah node dengan link valid) * 10 + spesifisitas selector.
    """
    best_sel, best_nodes, best_score = None, [], 0

    candidates = LIST_ITEM_SELECTORS + LIST_ITEM_SELECTORS_SPECIFIC
    for sel in candidates:
        try:
            nodes = soup.select(sel)
        except Exception:
            continue
        if len(nodes) < 3:
            continue

        # Hitung berapa node yang mengandung link artikel
        valid_count = 0
        for n in nodes[:20]:  # sample 20 pertama saja (cepat)
            for a in n.select("a[href]"):
                href = a.get("href", "")
                if is_article_link(href):
                    valid_count += 1
                    break

        if valid_count < 2:
            continue

        score = valid_count * 10
        if is_specific_selector(sel):
            score += 5

        if score > best_score:
            best_score = score
            best_sel = sel
            best_nodes = nodes

    return best_sel, best_nodes


def analyze_listing(soup: BeautifulSoup) -> dict:
    result = {
        "item": None, "title": None, "link": None,
        "date": None, "summary": None, "image": None,
        "item_count": 0,
    }

    best_sel, best_nodes = _pick_best_item_selector(soup)
    if not best_sel:
        return result

    result["item"] = best_sel
    result["item_count"] = len(best_nodes)

    # Pilih node pertama yang punya link artikel valid
    sample = None
    for n in best_nodes:
        for a in n.select("a[href]"):
            if is_article_link(a.get("href", "")):
                sample = n
                break
        if sample:
            break
    if not sample:
        sample = best_nodes[0]

    # Cari title
    for sel in TITLE_SELECTORS:
        try:
            node = sample.select_one(sel)
            if node:
                text = clean_text(node.get_text()) or node.get("title", "")
                if len(text) > 5:
                    result["title"] = sel
                    break
        except Exception:
            continue

    # Cari link artikel valid
    for sel in LINK_SELECTORS:
        try:
            nodes = sample.select(sel)
            for node in nodes:
                href = node.get("href", "")
                if is_article_link(href):
                    result["link"] = sel
                    break
            if result["link"]:
                break
        except Exception:
            continue

    # Kalau masih belum ada, cari link apa pun yang valid
    if not result["link"]:
        for a in sample.select("a[href]"):
            if is_article_link(a.get("href", "")):
                result["link"] = "a[href]"
                break

    for sel in DATE_SELECTORS:
        try:
            if sample.select_one(sel):
                result["date"] = sel
                break
        except Exception:
            continue

    for sel in SUMMARY_SELECTORS:
        try:
            node = sample.select_one(sel)
            if node and len(clean_text(node.get_text())) > 30:
                result["summary"] = sel
                break
        except Exception:
            continue

    for sel in IMAGE_SELECTORS:
        try:
            node = sample.select_one(sel)
            if node and (node.get("src") or node.get("data-src")):
                result["image"] = sel
                break
        except Exception:
            continue

    return result


# =====================================================
# Scoring konten
# =====================================================
def score_selector(sel: str, match_count: int, paragraphs: list[str], node) -> tuple[int, list[str]]:
    reasons = []
    if not paragraphs:
        return (0, ["tidak ada paragraf"])

    total_chars = sum(len(p) for p in paragraphs)
    nav_count = count_navigation_paragraphs(paragraphs)
    score = 0

    if is_semantic_selector(sel):
        score += 800; reasons.append("+800 SEMANTIK")
    if is_specific_selector(sel):
        score += 500; reasons.append("+500 SPESIFIK")
    if 3 <= len(paragraphs) <= 50:
        score += len(paragraphs) * 20
    elif len(paragraphs) > 50:
        score += 100
    if 500 <= total_chars <= 20000:
        score += total_chars // 10

    if nav_count > 0:
        score -= nav_count * 200
    if has_nav_class(node):
        score -= 1000
    if match_count > 1:
        score -= (match_count - 1) * 100
    if len(paragraphs) < 3:
        score -= 300
    if is_generic_selector(sel):
        score -= 1500

    return (score, reasons)


def pick_top_chain(results: list[dict], max_chain: int = 3) -> list[str]:
    valid = [r for r in results if r["score"] > 0 and r["paragraph_count"] >= 3]
    if not valid:
        return []
    valid.sort(key=lambda x: x["score"], reverse=True)
    threshold = valid[0]["score"] * 0.5
    filtered = [r for r in valid if r["score"] >= threshold]

    semantic = [r for r in filtered if is_semantic_selector(r["selector"])]
    specific = [r for r in filtered
                if is_specific_selector(r["selector"])
                and not is_semantic_selector(r["selector"])]
    generic = [r for r in filtered if is_generic_selector(r["selector"])]

    chain = []
    for lst in (semantic, specific):
        for r in lst:
            if r["selector"] not in chain:
                chain.append(r["selector"])
            if len(chain) >= max_chain:
                return chain
    if len(chain) < 2:
        for r in generic:
            if r["selector"] not in chain:
                chain.append(r["selector"])
            if len(chain) >= max_chain:
                break
    return chain


# =====================================================
# Verifikasi 1 URL
# =====================================================
def verify_url(name: str, url: str) -> dict:
    domain = urlparse(url).netloc
    print(f"\n{'=' * 100}")
    print(f"🔍 [{name}] {url}")
    print(f"🌐 Domain: {domain}")
    print(f"{'=' * 100}")

    # Cek manual override
    manual = load_manual_selectors(domain)
    if manual:
        print(f"   📌 manual_selectors.py ditemukan untuk {domain}")

    html, status, error, method = fetch_html(url)
    if html is None:
        print(f"❌ GAGAL FETCH ({method}): {error}")
        return {
            "name": name, "url": url, "domain": domain,
            "status": 0, "error": error, "method": method,
            "listing": {}, "content": [], "recommendation": None,
        }

    print(f"✅ HTTP {status} | HTML: {len(html):,} karakter | method: {method}")

    if is_challenge_page(html):
        print(f"⚠️  CHALLENGE PAGE — konten asli tidak tersedia")
        return {
            "name": name, "url": url, "domain": domain,
            "status": status, "error": "challenge page",
            "method": method, "listing": {}, "content": [],
            "recommendation": None,
        }

    soup = BeautifulSoup(html, "lxml")

    listing = analyze_listing(soup)
    print("\n📋 ANALISIS LISTING:")
    if listing["item"]:
        print(f"   ✅ item    : {listing['item']} ({listing['item_count']} item)")
        print(f"      title   : {listing.get('title')}")
        print(f"      link    : {listing.get('link')}")
        print(f"      date    : {listing.get('date')}")
        print(f"      summary : {listing.get('summary')}")
        print(f"      image   : {listing.get('image')}")
    else:
        print("   ❌ Tidak ada selector item yang cocok")

    # Analisis konten
    content_results = []
    sample_article_url = None

    if listing.get("item") and listing.get("link"):
        try:
            first_item = soup.select_one(listing["item"])
            if first_item:
                for a in first_item.select(listing["link"]):
                    href = a.get("href", "")
                    if is_article_link(href):
                        sample_article_url = urljoin(url, href)
                        break
        except Exception:
            pass

    if sample_article_url:
        print(f"\n📄 ANALISIS KONTEN (sample: {sample_article_url[:80]}...)")
        art_html, art_status, art_err, art_method = fetch_html(sample_article_url)
        if art_html and not is_challenge_page(art_html):
            art_soup = BeautifulSoup(art_html, "lxml")
            content_results = _analyze_content_selectors(art_soup)
            _print_content_results(content_results)
        else:
            print(f"   ⚠️ Gagal fetch artikel sample: {art_err}")
    else:
        print("\n⚠️  Tidak bisa analisis konten (tidak ada sample link)")

    # Gabung dengan manual override
    recommendation = _build_recommendation(listing, content_results, name, url, manual)

    return {
        "name": name, "url": url, "domain": domain,
        "status": status, "error": error, "method": method,
        "listing": listing, "content": content_results,
        "sample_article": sample_article_url,
        "recommendation": recommendation,
    }


def _analyze_content_selectors(soup: BeautifulSoup) -> list[dict]:
    results = []
    for sel in CONTENT_SELECTORS:
        try:
            nodes = soup.select(sel)
        except Exception:
            continue
        if not nodes:
            continue
        node = nodes[0]
        paragraphs = extract_paragraphs(node)
        total_chars = sum(len(p) for p in paragraphs)
        score, reasons = score_selector(sel, len(nodes), paragraphs, node)
        results.append({
            "selector": sel, "match_count": len(nodes),
            "paragraph_count": len(paragraphs),
            "total_chars": total_chars,
            "score": score, "reasons": reasons,
        })
    return results


def _print_content_results(results: list[dict]):
    print(f"{'Skor':>7}  {'Selector':<45} {'Match':>6} {'Par':>4} {'Chars':>7}")
    print("-" * 90)
    for r in results[:15]:
        mark = "🏆" if r["score"] >= 1000 else \
               "✅" if r["score"] >= 500 else \
               "⚠️ " if r["score"] > 0 else "❌"
        print(f"{mark} {r['score']:>5}  {r['selector']:<45} "
              f"{r['match_count']:>6} {r['paragraph_count']:>4} "
              f"{r['total_chars']:>7}")


def _build_recommendation(listing: dict, content_results: list[dict],
                          name: str, url: str, manual: dict) -> dict:
    rec = {"name": name, "url": url, "selectors": {}, "detail": {}}

    if listing.get("item"):
        rec["selectors"] = {
            "item": listing["item"],
            "title": listing.get("title") or "h2, h3",
            "link": listing.get("link") or "a[href]",
            "date": listing.get("date") or ".date, time",
            "summary": listing.get("summary") or "p",
            "image": listing.get("image") or "img",
        }

    chain = pick_top_chain(content_results, max_chain=3)
    if chain:
        rec["detail"] = {
            "content": ", ".join(chain),
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .penulis, [rel='author']",
            "date": ".date, time, .tanggal, .entry-date",
            "category": ".cat-links a, .category a, .kategori a",
            "image": "article img, .entry-content img, figure img",
            "exclude_selectors": (
                "nav, header, footer, aside, .sidebar, .widget, "
                ".related-posts, .sharedaddy, .menu, .breadcrumb, "
                ".swiper, .carousel, .popular, .list-content"
            ),
        }

    # Merge manual override (manual menang)
    if manual:
        if "selectors" in manual:
            rec["selectors"] = {**rec["selectors"], **manual["selectors"]}
        if "detail" in manual:
            rec["detail"] = {**rec["detail"], **manual["detail"]}

    return rec


# =====================================================
# Dump struktur
# =====================================================
def dump_structure(url: str, max_depth: int = 4):
    html, status, error, method = fetch_html(url)
    if html is None:
        print(f"❌ GAGAL FETCH ({method}): {error}")
        return

    print(f"\n{'=' * 100}")
    print(f"🗂️  STRUKTUR HTML — {url} (method: {method}, {len(html):,} char)")
    print(f"{'=' * 100}\n")

    if is_challenge_page(html):
        print("⚠️  CHALLENGE PAGE, bukan HTML asli.")
        print(f"Raw preview: {html[:500]}...")
        return

    soup = BeautifulSoup(html, "lxml")

    def walk(node, depth=0):
        if depth > max_depth or not getattr(node, "name", None):
            return
        if node.name in ("script", "style", "meta", "link", "noscript"):
            return
        classes = " ".join(node.get("class", [])) if node.get("class") else ""
        node_id = node.get("id", "")
        text_len = len(node.get_text(" ", strip=True))
        if text_len > 20 or node.name in ("article", "main", "section") or depth <= 2:
            indent = "  " * depth
            tag_str = f"<{node.name}"
            if node_id:
                tag_str += f" id='{node_id}'"
            if classes:
                tag_str += f" class='{classes[:60]}'"
            tag_str += ">"
            marker = " ⭐" if node.name in ("article", "main") else ""
            if text_len > 500:
                marker += " 📰"
            print(f"{indent}{tag_str} — {text_len:,} char{marker}")
        for child in node.children:
            if getattr(child, "name", None):
                walk(child, depth + 1)

    walk(soup.body if soup.body else soup)


# =====================================================
# Generate config.py
# =====================================================
def generate_config_from_report(report_path: str = "selector_report.json"):
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ File {report_path} tidak ditemukan.")
        return

    print(f"\n{'=' * 100}")
    print("💡 config.py FRAGMENT (copy-paste ke MEDIA_SOURCES)")
    print(f"{'=' * 100}\n")

    ok_count = 0
    for item in data.get("results", []):
        name = item["name"]
        rec = item.get("recommendation") or {}
        selectors = rec.get("selectors") or {}
        detail = rec.get("detail") or {}

        if not selectors:
            print(f"# {name} — ❌ GAGAL")
            print(f'#   URL: {item["url"]}')
            print(f'#   Error: {item.get("error")}')
            print()
            continue

        ok_count += 1
        print(f"# ============ {name} ============")
        print("{")
        print(f'    "name": "{name}",')
        print(f'    "url": "{item["url"]}",')
        print(f'    "is_official": False,')
        print(f'    "max_pages": 3,')
        print(f'    "selectors": {{')
        for k, v in selectors.items():
            print(f'        "{k}": "{v}",')
        print(f'    }},')
        if detail:
            print(f'    "detail": {{')
            for k, v in detail.items():
                print(f'        "{k}": "{v}",')
            print(f'    }},')
        print("},")
        print()

    print(f"\n# Total berhasil: {ok_count}/{len(data.get('results', []))}")


# =====================================================
# Main
# =====================================================
def main():
    parser = argparse.ArgumentParser(description="debug_selector.py v7")
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--structure", metavar="URL")
    parser.add_argument("--generate-config", action="store_true")
    parser.add_argument("--report", default="selector_report.json")
    args = parser.parse_args()

    if args.structure:
        dump_structure(args.structure)
        return

    if args.generate_config:
        generate_config_from_report(args.report)
        return

    if args.urls:
        targets = [(f"URL-{i+1}", u) for i, u in enumerate(args.urls)]
    else:
        targets = TARGET_URLS

    print(f"\n🚀 Menganalisis {len(targets)} situs...\n")

    all_results = []
    for name, url in targets:
        try:
            all_results.append(verify_url(name, url))
        except Exception as e:
            print(f"\n❌ ERROR pada {url}: {e}")
            all_results.append({
                "name": name, "url": url,
                "domain": urlparse(url).netloc,
                "status": 0, "error": str(e), "method": "error",
                "listing": {}, "content": [], "recommendation": None,
            })

    report = {
        "generated_at": datetime.now().isoformat(),
        "total": len(all_results),
        "ok": sum(1 for r in all_results
                  if r.get("recommendation") and r["recommendation"].get("selectors")),
        "failed": sum(1 for r in all_results
                      if not (r.get("recommendation") and r["recommendation"].get("selectors"))),
        "results": all_results,
    }

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n\n{'=' * 100}")
    print("📊 RINGKASAN AKHIR")
    print(f"{'=' * 100}")
    print(f"   Total     : {report['total']}")
    print(f"   ✅ OK     : {report['ok']}")
    print(f"   ❌ Gagal  : {report['failed']}")
    print(f"   Report    : {args.report}")

    for r in all_results:
        rec = r.get("recommendation") or {}
        method = r.get("method", "?")
        if rec.get("selectors"):
            chain = rec.get("detail", {}).get("content", "-")
            print(f"\n   ✅ {r['name']} [{method}]")
            print(f"      item   : {rec['selectors'].get('item')}")
            print(f"      link   : {rec['selectors'].get('link')}")
            print(f"      content: {chain}")
        else:
            err = r.get("error") or "selector tidak cocok"
            print(f"\n   ❌ {r['name']} [{method}] — {err[:60]}")


if __name__ == "__main__":
    main()
