"""Entry point: scrape → filter → sentimen → statistik → export.

Versi v5:
- Mempertahankan pipeline dan preview terminal v4.
- Output JSON utama berupa array artikel dengan provenance kualitas isi untuk audit.
- Menyimpan checkpoint setelah setiap sumber selesai.
- Deduplikasi output hanya berdasarkan URL yang persis sama.
- Tetap membuat HTML dashboard dan statistik terpisah.
"""
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table

from config import (
    SOURCES, MAX_ARTICLES_OFFICIAL, MAX_ARTICLES_MEDIA,
    FETCH_DETAIL_ENABLED, SOURCE_TRUST,
)
from scraper import fetch_source
from filter_dprd import filter_articles
from sentiment import add_sentiment_to_articles
from analytics import compute_stats
from preview import (
    print_banner, print_source_status, print_article_premium,
    print_summary_table, print_stats_panel,
)
from export_html import export_html

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
console = Console()


def _print_source_summary(all_results: list[dict]):
    t = Table(title="📡 Ringkasan Sumber", show_lines=True, expand=True)
    t.add_column("Sumber", style="bold")
    t.add_column("Status", justify="center")
    t.add_column("Scraped", justify="right")
    t.add_column("Lolos Filter", justify="right", style="green")
    t.add_column("Trust", justify="right", style="cyan")
    t.add_column("Error", style="red", overflow="fold")

    for r in all_results:
        status_code = r.get("status")
        status = "✅" if status_code == "ok" else ("⚠️" if status_code == "partial" else "❌")
        trust = SOURCE_TRUST.get(r.get("source", ""), 0.7)
        t.add_row(
            r.get("source", "unknown"),
            status,
            str(r.get("count", len(r.get("articles", [])))),
            str(len(r.get("filtered", []))),
            f"{trust:.2f}",
            (r.get("error") or "-")[:60],
        )
    console.print(t)


def _domain(url: str, fallback: str = "") -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or fallback


def _iso_date(value):
    if value in (None, ""):
        return None
    raw = str(value).strip()
    try:
        from dateutil import parser as dateparser
        parsed = dateparser.parse(raw)
        return parsed.isoformat(timespec="seconds") if parsed else raw
    except (ValueError, TypeError, OverflowError):
        return raw


def _to_result_article(article: dict, source_name: str) -> dict:
    """Konversi skema internal DDPS ke 7 field hasil-1.json."""
    url = str(article.get("link") or article.get("url") or "").strip()
    summary = str(article.get("summary") or article.get("ringkasan") or "").strip()
    content = str(article.get("content") or article.get("isi") or "").strip()
    quality = article.get("content_quality")
    if not quality:
        quality = "lengkap" if content and len(content) > len(summary) + 100 else (
            "ringkasan_saja" if content or summary else "kosong"
        )
    return {
        "judul": str(article.get("title") or article.get("judul") or "").strip(),
        "url": url,
        "tanggal": _iso_date(article.get("date") or article.get("tanggal")),
        "gambar": article.get("image") or article.get("gambar") or None,
        "ringkasan": summary,
        "isi": content or summary,
        "sumber": _domain(url, source_name),
        "kualitas_isi": quality,
        "mode_pengambilan": article.get("source_mode") or "live_http",
        "asal_isi": article.get("content_source") or "tidak_diketahui",
        "snapshot_file": article.get("snapshot_file"),
    }


def _write_json(path: str, articles: list[dict]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def main():
    print_banner()
    all_results = []
    output_articles = []
    seen_exact_urls = set()

    total_sources = len(SOURCES)
    console.print(
        f"\n[bold cyan]🔍 Scraping {total_sources} sumber...[/bold cyan]\n"
    )

    for i, src in enumerate(SOURCES, 1):
        is_official = src.get("is_official", False)
        trust = SOURCE_TRUST.get(src["name"], 0.7)

        console.print(
            f"[cyan]({i}/{total_sources})[/cyan] "
            f"[bold]{src['name']}[/bold] — trust: {trust}"
        )

        try:
            result = fetch_source(src, fetch_detail_enabled=FETCH_DETAIL_ENABLED)
        except Exception as exc:
            logging.exception("Gagal scraping sumber %s", src["name"])
            result = {
                "source": src["name"], "status": "error", "count": 0,
                "articles": [], "error": str(exc),
            }

        raw_articles = result.get("articles", [])
        if is_official:
            articles = (
                raw_articles[:MAX_ARTICLES_OFFICIAL]
                if MAX_ARTICLES_OFFICIAL else raw_articles
            )
        else:
            articles = (
                raw_articles[:MAX_ARTICLES_MEDIA]
                if MAX_ARTICLES_MEDIA else raw_articles
            )

        try:
            filtered = filter_articles(
                articles,
                is_official=is_official,
                source_weight=trust,
                source_name=src.get("name", ""),
                source_url=src.get("url", ""),
            )
            filtered = add_sentiment_to_articles(filtered)
        except Exception as exc:
            logging.exception("Filter/sentimen gagal untuk %s", src["name"])
            filtered = []
            result["error"] = (result.get("error") or "") + f" filter/sentimen: {exc}"

        result["articles"] = articles
        result["filtered"] = filtered
        # A source can produce listing articles while detail extraction remains partial.
        # Preserve this as a warning instead of showing a misleading full-success icon.
        qualities = [str(a.get("content_quality") or "") for a in articles]
        if result.get("status") == "ok" and any(q in {"ringkasan_saja", "kosong"} for q in qualities):
            result["status"] = "partial"
            fallback_n = qualities.count("ringkasan_saja")
            empty_n = qualities.count("kosong")
            result["error"] = f"Konten tidak seluruhnya lengkap: {fallback_n} ringkasan saja, {empty_n} kosong"
        result["is_official"] = is_official
        result["trust"] = trust
        result.setdefault("source", src["name"])
        result.setdefault("status", "ok")
        result.setdefault("count", len(raw_articles))
        all_results.append(result)

        source_added = 0
        for article in filtered:
            converted = _to_result_article(article, src["name"])
            url = converted["url"]

            # URL kosong tidak bisa diidentifikasi secara andal untuk deduplikasi.
            if not converted["judul"] or not url:
                continue
            # Sesuai kebutuhan: hanya URL yang PERSIS sama yang dianggap duplikat.
            if url in seen_exact_urls:
                continue
            seen_exact_urls.add(url)
            output_articles.append(converted)
            source_added += 1

        console.print(
            f"    → scraped: {len(raw_articles)}, "
            f"lolos: [green]{len(filtered)}[/green], "
            f"ditambahkan ke JSON: {source_added}"
        )

        # Checkpoint format hasil-1.json setelah tiap sumber.
        _write_json("hasil_dprd_kuningan.json", output_articles)
        console.print(
            f"    💾 Checkpoint: {len(output_articles)} artikel tersimpan"
        )

    _print_source_summary(all_results)
    stats = compute_stats(all_results)
    print_stats_panel(stats)

    sent_total = sum(stats["sentiments"].values())
    console.print(
        f"\n[bold green]✅ Validasi statistik:[/bold green] "
        f"total={stats['total']} = resmi={stats['official_count']} + "
        f"media={stats['media_count']}"
    )
    if sent_total == stats["total"]:
        console.print(
            f"[bold green]✅ Sentimen:[/bold green] "
            f"positif={stats['sentiments']['positif']} + "
            f"negatif={stats['sentiments']['negatif']} + "
            f"netral={stats['sentiments']['netral']} = {sent_total}"
        )
    else:
        console.print(
            f"[bold yellow]⚠️ Sentimen tidak konsisten:[/bold yellow] "
            f"sentiments={sent_total}, total={stats['total']}"
        )

    # Preview terminal tetap dipertahankan.
    for r in all_results:
        if r.get("is_official") and r.get("filtered"):
            console.rule(
                f"[bold green]🏛️ {r['source']} "
                f"(RESMI — {len(r['filtered'])} artikel)[/bold green]"
            )
            for idx, art in enumerate(r["filtered"], 1):
                print_article_premium(art, idx)

    for r in all_results:
        if not r.get("is_official") and r.get("filtered"):
            console.rule(
                f"[bold magenta]📰 {r['source']} "
                f"({len(r['filtered'])} artikel)[/bold magenta]"
            )
            for idx, art in enumerate(r["filtered"], 1):
                print_article_premium(art, idx)

    print_summary_table(all_results)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = f"hasil_dprd_kuningan_{stamp}.json"
    html_path = f"hasil_dprd_kuningan_{stamp}.html"
    stats_path = f"statistik_dprd_kuningan_{stamp}.json"

    # File JSON utama: array datar dengan 7 field seperti hasil-1.json.
    _write_json(json_path, output_articles)
    _write_json("hasil_dprd_kuningan.json", output_articles)

    # Statistik dipisah agar tidak merusak skema JSON artikel.
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump({"stats": stats, "sources": all_results},
                  f, ensure_ascii=False, indent=2)

    exported = export_html(all_results, stats, html_path)
    console.print(f"\n💾 JSON artikel: [bold]{json_path}[/bold]")
    console.print("💾 JSON artikel terbaru: [bold]hasil_dprd_kuningan.json[/bold]")
    console.print(f"📊 Statistik: [bold]{stats_path}[/bold]")
    console.print(f"🌐 HTML: [bold]{html_path}[/bold] ({exported} artikel)")
    console.print(f"📰 Artikel unik berdasarkan URL persis: {len(output_articles)}")


if __name__ == "__main__":
    main()
