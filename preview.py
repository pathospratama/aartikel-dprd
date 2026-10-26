"""Tampilan preview premium pakai Rich: kartu 2 kolom, detail penuh, tabel."""
import os
import tempfile
import requests

from rich.console import Console, Group
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

console = Console()


def _try_render_image(url: str, width: int = 32) -> "Text | None":
    """
    Render gambar di terminal.
    Urutan percobaan:
      1. textual-image (jika terpasang)
      2. ASCII art via Pillow (jika terpasang)
      3. Fallback: URL teks
    """
    try:
        r = requests.get(url, timeout=8, stream=True)
        if r.status_code != 200:
            return None
        fd, path = tempfile.mkstemp(suffix=os.path.splitext(url)[1] or ".jpg")
        with os.fdopen(fd, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
    except Exception:
        return None

    # --- Cara 1: textual-image ---
    try:
        from textual_image.renderable import Image as TerminalImage  # type: ignore
        return TerminalImage(path, width=width)  # type: ignore[return-value]
    except Exception:
        pass

    # --- Cara 2: ASCII art via Pillow ---
    try:
        from PIL import Image as PILImage  # type: ignore

        img = PILImage.open(path).convert("L")
        img.thumbnail((width, width // 2))
        chars = " .:-=+*#%@"
        lines = []
        for y in range(img.height):
            line = "".join(
                chars[img.getpixel((x, y)) * (len(chars) - 1) // 255]
                for x in range(img.width)
            )
            lines.append(line)
        return Text("\n".join(lines), style="white")
    except Exception:
        pass

    # --- Cara 3: fallback ---
    return Text(f"🖼️  {url}", style="blue underline")


def print_banner():
    console.print(
        Panel.fit(
            "[bold cyan]🕵️  Scraper Berita DPRD Kuningan — Premium[/bold cyan]\n"
            "[dim]Filter skor relevansi • Detail penuh • Gambar • Metadata[/dim]",
            border_style="cyan",
        )
    )


def print_source_status(results: list[dict]):
    t = Table(title="📡 Status Sumber", show_lines=True, expand=True)
    t.add_column("Sumber", style="bold")
    t.add_column("Tipe", justify="center")
    t.add_column("Status", justify="center")
    t.add_column("Total", justify="right")
    t.add_column("Ditampilkan", justify="right", style="green")
    t.add_column("Error", style="red", overflow="fold")

    for r in results:
        if r["status"] == "ok":
            status = "✅ OK"
        elif r["status"] == "partial":
            status = "⚠️ PARSIAL"
        else:
            status = "❌ GAGAL"
        tipe = "🏛️ Resmi" if r.get("is_official") else "📰 Media"
        shown = len(r.get("filtered", []))
        t.add_row(
            r["source"], tipe, status, str(r["count"]), str(shown), r.get("error") or "-"
        )
    console.print(t)


def print_summary_table(all_results: list[dict]):
    rows = []
    n = 0
    for r in all_results:
        for a in r.get("filtered", []):
            n += 1
            tipe = "🏛️" if r.get("is_official") else "📰"
            rows.append((n, tipe, a.get("date") or "n/a", a.get("title") or "-",
                         a.get("relevance_score", 0), r["source"]))
    if not rows:
        console.print("[yellow]Tidak ada artikel untuk ditampilkan.[/yellow]")
        return

    t = Table(title="🎯 Ringkasan Semua Artikel", show_lines=True, expand=True)
    t.add_column("#", width=3, justify="right")
    t.add_column("Tipe", width=4, justify="center")
    t.add_column("Tanggal", width=12)
    t.add_column("Judul", overflow="fold")
    t.add_column("Skor", width=5, justify="right", style="green")
    t.add_column("Sumber", width=20)
    for row in rows:
        t.add_row(*map(str, row))
    console.print(t)


def _article_meta(a: dict) -> Text:
    m = Text()
    m.append("📅 ", style="yellow")
    m.append(a.get("date") or "n/a", style="yellow")
    m.append("   🏷️ ", style="magenta")
    cats = a.get("category") or []
    m.append(", ".join(cats) if cats else "-", style="magenta")
    m.append("   ✍️ ", style="cyan")
    m.append(a.get("author") or "n/a", style="cyan")
    m.append(f"   ⭐ skor {a.get('relevance_score', 0)}", style="green")
    return m


def print_article_premium(a: dict, idx: int):
    """Kartu artikel: gambar kiri, info kanan; di bawahnya detail lengkap."""
    title = Text(a.get("title") or "(tanpa judul)", style="bold white")

    image_block = None
    if a.get("image"):
        image_block = _try_render_image(a["image"])

    meta = _article_meta(a)
    summary = Text((a.get("summary") or "").strip(), style="dim")
    link = Text(a["link"], style="blue underline")

    right = Group(title, "", meta, "", summary, "", link)

    if image_block is not None:
        body = Columns([image_block, right], expand=True, padding=(0, 2))
    else:
        body = right

    console.print(
        Panel(
            body,
            title=f"[bold green]#{idx}[/bold green]",
            subtitle=f"[dim]{a.get('source', '')}[/dim]",
            border_style="green",
            expand=True,
        )
    )

    # Detail penuh
    if a.get("content"):
        console.print(
            Panel(
                Text(a["content"], style="white"),
                title="[bold yellow]📄 Isi Lengkap[/bold yellow]",
                border_style="yellow",
                expand=True,
            )
        )

    # Galeri gambar
    images = a.get("images") or []
    if images:
        gallery = Table(show_header=True, header_style="bold magenta", expand=True)
        gallery.add_column("#", justify="right", width=3)
        gallery.add_column("Gambar", overflow="fold")
        for j, u in enumerate(images, 1):
            gallery.add_row(str(j), Text(u, style="blue underline"))
        console.print(Panel(gallery, title="🖼️  Galeri Gambar", border_style="magenta"))

    console.print(Rule(style="dim"))


def print_stats_panel(stats: dict):
    """Tampilkan panel statistik di terminal."""
    from rich.table import Table
    sentiments = stats.get("sentiments", {})
    t = Table(title="📊 Statistik Dashboard", show_header=False, expand=True,
              border_style="cyan")
    t.add_column("Metrik", style="bold")
    t.add_column("Nilai", justify="right")

    t.add_row("🏛️ Artikel Resmi DPRD", str(stats.get("official_count", 0)))
    t.add_row("📰 Artikel Media (terfilter)", str(stats.get("media_count", 0)))
    t.add_row("📊 Total Artikel", str(stats.get("total", 0)))
    t.add_row("😊 Sentimen Positif", f"[green]{sentiments.get('positif', 0)}[/green]")
    t.add_row("😟 Sentimen Negatif", f"[red]{sentiments.get('negatif', 0)}[/red]")
    t.add_row("😐 Netral", f"[yellow]{sentiments.get('netral', 0)}[/yellow]")
    console.print(t)
