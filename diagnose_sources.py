"""Diagnose DDPS source URLs without crawling every article detail page.

Default: check each source's primary listing URL.
Use --all-endpoints to also check HTML fallbacks, RSS feeds and API endpoints.
Writes diagnostik_sumber_*.json. TLS certificate verification remains enabled.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from config import SOURCES
from scraper import (
    safe_get, parse_list_page, _FETCH_DIAGNOSTICS,
    _is_challenge_page, _parse_structured_payload,
)


def build_targets(all_endpoints: bool):
    targets = []
    seen = set()
    for source in SOURCES:
        name = source.get("name", "Sumber tidak bernama")
        groups = [("html_utama", [source.get("url", "")])]
        if all_endpoints:
            groups.extend([
                ("html_fallback", source.get("fallback_urls", []) or []),
                ("rss_feed", source.get("feed_urls", []) or []),
                ("api", source.get("api_urls", []) or []),
            ])
        for kind, urls in groups:
            for url in urls:
                url = str(url or "").strip()
                if not url:
                    continue
                key = (name, kind, url)
                if key in seen:
                    continue
                seen.add(key)
                targets.append({"source": source, "name": name, "kind": kind, "url": url})
    return targets


def diagnose_target(target: dict) -> dict:
    source, url, kind = target["source"], target["url"], target["kind"]
    row = {
        "source": target["name"], "endpoint_type": kind, "url": url,
        "final_url": None, "http_status": None, "title": None,
        "html_bytes": 0, "challenge_detected": None,
        "configured_items": 0, "configured_titles": 0,
        "parsed_articles": 0, "diagnostic": None, "fetch_errors": [],
    }
    response = safe_get(url)
    if response is None:
        errors = _FETCH_DIAGNOSTICS.get(url, [])[-8:]
        row["fetch_errors"] = errors
        error_text = " ".join(errors).lower()
        if any(token in error_text for token in ("challenge/waf", "mohon tunggu sebentar", "please wait")):
            row["challenge_detected"] = True
            row["diagnostic"] = (
                "Respons ditahan oleh halaman perantara/challenge (indikasi dari error fetch); "
                "HTML artikel tidak diteruskan ke parser. Periksa halaman normal menggunakan browser biasa/Safari, impor snapshot HTML lokal, atau gunakan feed/API resmi yang diizinkan."
            )
        elif any(token in error_text for token in ("certificate_verify_failed", "certificateverifyerror", "ssl: certificate_verify_failed")):
            row["challenge_detected"] = False
            row["diagnostic"] = (
                "Verifikasi sertifikat TLS gagal. Jangan menonaktifkan verify; periksa CA bundle lokal "
                "dan/atau rantai sertifikat server."
            )
        elif any(token in error_text for token in ("http 403", "http 401", "http 451", "access denied")):
            row["challenge_detected"] = True
            row["diagnostic"] = "Server menolak permintaan (HTTP/access denied); bukan kegagalan selector HTML."
        elif any(token in error_text for token in ("name or service not known", "dns", "getaddrinfo failed")):
            row["diagnostic"] = "Resolusi DNS gagal; cek host, DNS, atau koneksi jaringan."
        else:
            row["diagnostic"] = errors[-1] if errors else "Tidak ada respons HTTP valid"
        return row

    html = response.text or ""
    soup = BeautifulSoup(html, "lxml")
    row.update({
        "final_url": response.url,
        "http_status": response.status_code,
        "title": soup.title.get_text(" ", strip=True)[:160] if soup.title else None,
        "html_bytes": len(html.encode("utf-8", errors="replace")),
        "challenge_detected": _is_challenge_page(html),
    })

    if row["challenge_detected"]:
        row["diagnostic"] = "Respons tampak sebagai challenge/WAF; tidak dicoba untuk dilewati."
    elif kind in ("rss_feed", "api"):
        parsed = _parse_structured_payload(response, response.url or url)
        row["parsed_articles"] = len(parsed)
        if parsed:
            row["diagnostic"] = "Endpoint terstruktur mengembalikan artikel."
        else:
            row["diagnostic"] = "Endpoint berhasil diakses tetapi payload tidak terbaca sebagai RSS/Atom/WordPress API."
    else:
        selectors = source.get("selectors", {})
        try:
            row["configured_items"] = len(soup.select(selectors.get("item") or "article"))
            row["configured_titles"] = len(soup.select(selectors.get("title") or "h1,h2,h3,h4"))
        except Exception as exc:
            row["diagnostic"] = f"Selector konfigurasi tidak valid: {type(exc).__name__}: {exc}"
        if not row["diagnostic"]:
            row["parsed_articles"] = len(parse_list_page(html, response.url or url, selectors))
            if row["parsed_articles"]:
                row["diagnostic"] = "Daftar artikel berhasil diparse."
            else:
                row["diagnostic"] = (
                    "HTTP berhasil tetapi tidak ditemukan artikel; periksa judul halaman, "
                    "HTML aktual, selector, maintenance, atau konten yang dimuat JavaScript."
                )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostik sumber DDPS tanpa crawl detail.")
    parser.add_argument(
        "--all-endpoints", action="store_true",
        help="Periksa juga URL fallback, RSS feed, dan API setiap sumber.",
    )
    args = parser.parse_args()
    targets = build_targets(args.all_endpoints)
    print(f"Memeriksa {len(targets)} endpoint untuk {len(SOURCES)} sumber (tanpa crawl seluruh detail artikel).\n")
    rows = []
    for index, target in enumerate(targets, 1):
        print(f"[{index}/{len(targets)}] {target['name']} [{target['kind']}]: {target['url']}")
        row = diagnose_target(target)
        rows.append(row)
        if row.get("http_status") is None:
            print(f"    GAGAL: {(row.get('diagnostic') or 'Tidak ada respons')[:200]}")
        else:
            print(
                f"    HTTP {row['http_status']} | bytes={row['html_bytes']} | "
                f"articles={row['parsed_articles']} | challenge={row['challenge_detected']} | "
                f"{row['diagnostic']}"
            )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"diagnostik_sumber_{stamp}.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nLaporan tersimpan: {out}")
    if not args.all_endpoints:
        print("Tip: jalankan ulang dengan --all-endpoints untuk memeriksa fallback/feed/API.")
    print("Sertifikat TLS tidak dilewati. Kirim JSON ini beserta scraper.log bila masih ada kegagalan.")


if __name__ == "__main__":
    main()
