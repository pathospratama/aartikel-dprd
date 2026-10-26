"""Filter berita lokal Kabupaten Kuningan.

Tujuan versi ini:
- Berita DPRD tetap diterima.
- Berita pemerintahan umum (Pemkab, bupati/wabup, dinas, layanan publik,
  anggaran daerah, pembangunan, dan sebagainya) juga diterima walau tidak
  membahas DPRD.
- Pemeriksaan wilayah menggunakan judul, ringkasan, isi, URL, dan identitas
  sumber resmi lokal.
- Artikel lokal non-pemerintahan juga boleh lolos; filter ini bukan lagi
  gerbang khusus DPRD. Blacklist hanya dipakai untuk konten yang jelas-jelas
  bukan berita (olahraga/hiburan) bila tidak ada konteks lokal/pemerintahan.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from config import OTHER_REGIONS, NON_KUNINGAN_PENALTY

log = logging.getLogger("filter_dprd")

# Indikator DPRD/legislatif. Hanya untuk pelabelan, bukan syarat kelolosan.
DPRD_TERMS = (
    "dprd", "dewan perwakilan rakyat daerah", "anggota dewan",
    "ketua dewan", "wakil ketua dewan", "anggota legislatif",
    "komisi i", "komisi ii", "komisi iii", "komisi iv",
    "badan anggaran", "banggar", "bapemperda", "badan kehormatan",
    "badan musyawarah", "fraksi", "pansus", "rapat paripurna",
    "rapat dengar pendapat", "rdp dprd", "sekretariat dprd",
)

# Kata-kata ini membantu memberi label berita pemerintahan umum.
GOVERNMENT_TERMS = (
    "pemerintah kabupaten", "pemkab", "pemerintah daerah", "pemda",
    "bupati", "wakil bupati", "wabup", "sekda", "sekretaris daerah",
    "bappeda", "badan perencanaan pembangunan", "dinas", "disdikbud",
    "diskominfo", "dinkes", "dishub", "dlh", "dpmptsp", "dinsos",
    "disnaker", "dpmd", "inspektorat", "badan keuangan daerah",
    "apbd", "rapbd", "anggaran daerah", "peraturan daerah", "perda",
    "raperda", "pelayanan publik", "layanan publik", "pembangunan daerah",
    "musrenbang", "program pemerintah", "kebijakan pemerintah",
    "pelantikan pejabat", "asn", "aparatur sipil negara",
)

LOCAL_MARKERS = (
    "kabupaten kuningan", "pemkab kuningan", "pemerintah kabupaten kuningan",
    "kuningan", "ciremai", "linggarjati", "cigugur", "jalaksana",
    "cibingbin", "luragung", "kadugede", "cibuntu", "palutungan",
    "waduk darma", "telaga biru cicerem", "tirta kamuning",
)

# Konten ini tidak otomatis dibuang jika memuat konteks pemerintahan/lokal.
NON_LOCAL_ENTERTAINMENT = re.compile(
    r"\b(fc|futsal|persib|persija|persebaya|madura united|pfl|liga|"
    r"sepak\s*bola|voli|bulu\s*tangkis|motogp|pembalap|sirkuit|"
    r"kualifikasi|juara\s*dunia|dangdut|artis|selebritis|sinetron|"
    r"film|konser|panggung|pentas|drama|teater)\b", re.I,
)

# Domain yang secara eksplisit merupakan situs instansi pemerintah daerah.
LOCAL_GOV_HOST_SUFFIXES = (
    "kuningankab.go.id", "kuningankab.go.id.",
)


def _field(article: dict, *names: str) -> str:
    return " ".join(str(article.get(name) or "") for name in names).strip().lower()


def _contains_any(text: str, terms) -> bool:
    return any(term in text for term in terms)


def is_dprd_article(article: dict) -> bool:
    """Label DPRD saja; bukan kriteria untuk menolak berita umum."""
    return _contains_any(_field(article, "title", "summary", "content"), DPRD_TERMS)


def is_government_article(article: dict) -> bool:
    """True jika teks mengandung indikator pemerintahan/layanan publik."""
    return _contains_any(
        _field(article, "title", "summary", "content"), GOVERNMENT_TERMS
    )


def is_kuningan(article: dict, source_name: str = "", source_url: str = "") -> bool:
    """Tentukan konteks Kuningan tanpa mewajibkan kata DPRD."""
    text = _field(article, "title", "summary", "content", "link", "url")
    if _contains_any(text, LOCAL_MARKERS):
        return True

    # Situs resmi Pemkab/OPD/PPID lokal dianggap sumber lokal.
    candidate_urls = [source_url, str(article.get("link") or article.get("url") or "")]
    for candidate in candidate_urls:
        host = (urlparse(candidate).hostname or "").lower()
        if any(host == suffix or host.endswith("." + suffix) for suffix in LOCAL_GOV_HOST_SUFFIXES):
            return True

    # Sumber lokal yang namanya jelas mengandung Kuningan.
    if "kuningan" in (source_name or "").lower():
        # Tetap perlu ada penanda lokal atau konteks pemerintah di teks,
        # kecuali artikel berasal dari domain resmi lokal (ditangani di atas).
        return _contains_any(text, LOCAL_MARKERS) or is_government_article(article)

    return False


def _is_nonlocal_sports_or_entertainment(article: dict) -> bool:
    text = _field(article, "title", "summary")
    if not NON_LOCAL_ENTERTAINMENT.search(text):
        return False
    # Jangan menolak berita lokal/pemerintahan hanya karena ada kata yang
    # kebetulan sama; blacklist hanya berlaku jika konteks lokal tidak ada.
    return not _contains_any(text, LOCAL_MARKERS) and not is_government_article(article)


def filter_articles(
    articles: list[dict],
    is_official: bool = False,
    source_weight: float = 1.0,
    source_name: str = "",
    source_url: str = "",
) -> list[dict]:
    """Loloskan berita lokal Kuningan, baik DPRD maupun pemerintahan umum.

    Catatan: ``is_official`` dipertahankan agar kompatibel dengan pemanggil lama.
    Penilaian skor hanya untuk urutan, bukan untuk menolak artikel relevan.
    """
    seen_links: set[str] = set()
    accepted: list[dict] = []
    rejected = {"duplikat": 0, "tanpa_judul": 0, "wilayah": 0, "hiburan_olahraga": 0}

    for article in articles or []:
        if not isinstance(article, dict):
            continue
        link = str(article.get("link") or article.get("url") or "").strip()
        title = str(article.get("title") or article.get("judul") or "").strip()
        summary = str(article.get("summary") or article.get("ringkasan") or "").strip()
        content = str(article.get("content") or article.get("isi") or "").strip()

        if not title:
            rejected["tanpa_judul"] += 1
            continue
        if link and link in seen_links:
            rejected["duplikat"] += 1
            continue
        if link:
            seen_links.add(link)

        # Salin field normalisasi agar fungsi juga kompatibel dengan variasi skema.
        article.setdefault("title", title)
        article.setdefault("summary", summary)
        article.setdefault("content", content)
        if link:
            article.setdefault("link", link)

        local = is_kuningan(article, source_name=source_name, source_url=source_url)
        if not local:
            rejected["wilayah"] += 1
            continue

        if _is_nonlocal_sports_or_entertainment(article):
            rejected["hiburan_olahraga"] += 1
            continue

        text = _field(article, "title", "summary", "content")
        dprd_flag = is_dprd_article(article)
        gov_flag = is_government_article(article)
        # Skor tidak menjadi gate. Gunakan untuk mengurutkan berita yang paling
        # terkait dengan pemerintahan/DPRD terlebih dahulu.
        score = 0
        if dprd_flag:
            score += 100
        if gov_flag:
            score += 50
        if _contains_any(text, LOCAL_MARKERS):
            score += 20
        score = int(score * max(0.1, float(source_weight or 1.0)))

        article["relevance_score"] = score
        article["is_kuningan"] = True
        article["is_dprd"] = dprd_flag
        article["is_government_news"] = gov_flag
        article["is_legislative_work"] = dprd_flag and _contains_any(
            text,
            ("rapat", "pengawasan", "aspirasi", "raperda", "perda", "komisi",
             "banggar", "bapemperda", "paripurna", "fraksi", "pansus"),
        )
        accepted.append(article)

    log.info(
        "  filter berita lokal: %s → %s lolos "
        "(wilayah=%s, tanpa_judul=%s, duplikat=%s, olahraga/hiburan=%s)",
        len(articles or []), len(accepted), rejected["wilayah"],
        rejected["tanpa_judul"], rejected["duplikat"], rejected["hiburan_olahraga"],
    )
    return sorted(accepted, key=lambda item: item.get("relevance_score", 0), reverse=True)
