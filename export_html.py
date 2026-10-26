"""Export artikel DPRD ke HTML dashboard interaktif dengan modal detail inline.

Versi v3:
- Fallback image: kalau a['image'] kosong tapi a['images'] ada, pakai images[0].
- Badge 📍 DPRD untuk artikel yang lolos filter DPRD.
- Tampilkan trust score sumber di modal.
"""
import json
import logging
from datetime import datetime
from html import escape

log = logging.getLogger("export_html")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard DPRD Kuningan — {date}</title>
<style>
  :root {{ --bg:#0d1117; --card:#161b22; --border:#30363d;
           --text:#c9d1d9; --muted:#8b949e; --accent:#58a6ff;
           --green:#238636; --red:#da3633; --yellow:#d29922; --purple:#a371f7; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:0; background:var(--bg); color:var(--text);
         font-family:-apple-system,'Segoe UI',Roboto,sans-serif; }}

  header {{ background:linear-gradient(135deg,#161b22 0%,#1c2128 100%);
           border-bottom:1px solid var(--border); padding:28px 24px; text-align:center; }}
  header h1 {{ margin:0 0 8px; color:var(--accent); font-size:1.8rem; }}
  header p {{ margin:0; color:var(--muted); font-size:.9rem; }}

  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
            gap:14px; max-width:1400px; margin:20px auto; padding:0 24px; }}
  .stat {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
          padding:16px; text-align:center; }}
  .stat .num {{ font-size:2rem; font-weight:700; color:var(--accent); }}
  .stat .lbl {{ font-size:.8rem; color:var(--muted); text-transform:uppercase;
                letter-spacing:.5px; margin-top:4px; }}
  .stat.pos .num {{ color:var(--green); }}
  .stat.neg .num {{ color:var(--red); }}
  .stat.neu .num {{ color:var(--yellow); }}
  .stat.off .num {{ color:var(--purple); }}

  .controls {{ max-width:1400px; margin:16px auto; padding:0 24px;
              display:flex; gap:12px; flex-wrap:wrap; }}
  .controls input, .controls select {{ background:var(--card); border:1px solid var(--border);
              color:var(--text); padding:10px 14px; border-radius:8px;
              font-size:.9rem; outline:none; }}
  .controls input {{ flex:1; min-width:200px; }}
  .controls input:focus, .controls select:focus {{ border-color:var(--accent); }}

  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
           gap:20px; max-width:1400px; margin:24px auto; padding:0 24px; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
           overflow:hidden; display:flex; flex-direction:column; cursor:pointer;
           transition:transform .2s, box-shadow .2s, border-color .2s; position:relative; }}
  .card:hover {{ transform:translateY(-4px); box-shadow:0 8px 24px rgba(88,166,255,.15);
                border-color:var(--accent); }}
  .thumb {{ width:100%; height:170px; object-fit:cover; background:#21262d;
           display:block; }}
  .thumb-placeholder {{ display:flex; align-items:center; justify-content:center;
           color:#8b949e; font-size:.85rem; }}
  .body {{ padding:16px; flex:1; display:flex; flex-direction:column; }}
  .title {{ font-size:1rem; font-weight:600; margin:0 0 10px; line-height:1.4; }}
  .meta {{ font-size:.75rem; color:var(--muted); margin-bottom:8px;
          display:flex; flex-wrap:wrap; gap:6px; align-items:center; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:10px;
           font-size:.7rem; font-weight:600; }}
  .badge.official {{ background:var(--purple); color:#fff; }}
  .badge.media {{ background:var(--accent); color:#0d1117; }}
  .badge.pos {{ background:var(--green); color:#fff; }}
  .badge.neg {{ background:var(--red); color:#fff; }}
  .badge.neu {{ background:var(--yellow); color:#0d1117; }}
  .badge.region {{ background:#1f6feb; color:#fff; }}
  .badge.dprd {{ background:#f778ba; color:#0d1117; }}
  .score {{ display:inline-block; background:#21262d; color:var(--accent);
           padding:2px 8px; border-radius:10px; font-size:.72rem; font-weight:600; }}
  .summary {{ font-size:.85rem; color:var(--muted); line-height:1.5;
             flex:1; margin-bottom:0; overflow:hidden;
             display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; }}
  .readmore {{ font-size:.75rem; color:var(--accent); margin-top:10px;
              font-weight:600; }}

  .modal-bg {{ display:none; position:fixed; top:0; left:0; right:0; bottom:0;
              background:rgba(0,0,0,.85); z-index:1000; overflow-y:auto;
              padding:20px; animation:fadeIn .2s; }}
  .modal-bg.active {{ display:block; }}
  @keyframes fadeIn {{ from {{ opacity:0 }} to {{ opacity:1 }} }}
  .modal {{ background:var(--card); border:1px solid var(--border); border-radius:16px;
           max-width:900px; margin:20px auto; overflow:hidden;
           animation:slideUp .3s; }}
  @keyframes slideUp {{ from {{ transform:translateY(30px); opacity:0 }}
                       to {{ transform:translateY(0); opacity:1 }} }}
  .modal-hero {{ width:100%; max-height:400px; object-fit:cover; display:block;
                background:#21262d; }}
  .modal-body {{ padding:28px; }}
  .modal-header {{ display:flex; justify-content:space-between; align-items:flex-start;
                  gap:16px; margin-bottom:16px; }}
  .modal-title {{ font-size:1.5rem; font-weight:700; margin:0; line-height:1.3;
                 flex:1; }}
  .modal-close {{ background:var(--red); color:#fff; border:none; border-radius:8px;
                 width:36px; height:36px; font-size:1.2rem; cursor:pointer;
                 flex-shrink:0; font-weight:700; }}
  .modal-close:hover {{ opacity:.85; }}
  .modal-meta {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:20px;
                padding-bottom:20px; border-bottom:1px solid var(--border); }}
  .modal-section {{ margin-bottom:24px; }}
  .modal-section h3 {{ color:var(--accent); font-size:1rem; margin:0 0 12px;
                      text-transform:uppercase; letter-spacing:.5px; }}
  .modal-content {{ font-size:.95rem; line-height:1.8; color:var(--text);
                   white-space:pre-wrap; }}
  .modal-content p {{ margin:0 0 14px; }}
  .gallery {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
             gap:10px; }}
  .gallery img {{ width:100%; height:120px; object-fit:cover; border-radius:8px;
                 cursor:pointer; transition:transform .2s; }}
  .gallery img:hover {{ transform:scale(1.05); }}
  .sentiment-box {{ background:#21262d; border-radius:10px; padding:14px;
                   font-size:.85rem; line-height:1.6; }}
  .sentiment-box .hit {{ display:inline-block; background:#30363d; color:var(--text);
                        padding:2px 8px; border-radius:8px; margin:2px;
                        font-size:.75rem; }}
  .sentiment-box .hit.pos {{ background:rgba(35,134,54,.3); color:#56d364; }}
  .sentiment-box .hit.neg {{ background:rgba(218,54,51,.3); color:#ff7b72; }}
  .modal-link {{ display:inline-block; margin-top:8px; padding:10px 18px;
                background:var(--accent); color:#0d1117; border-radius:8px;
                text-decoration:none; font-weight:600; font-size:.9rem; }}
  .modal-link:hover {{ opacity:.85; }}

  .lightbox {{ display:none; position:fixed; top:0; left:0; right:0; bottom:0;
              background:rgba(0,0,0,.95); z-index:2000; align-items:center;
              justify-content:center; padding:20px; }}
  .lightbox.active {{ display:flex; }}
  .lightbox img {{ max-width:95%; max-height:95%; border-radius:8px; }}
  .lightbox-close {{ position:absolute; top:20px; right:20px; background:var(--red);
                    color:#fff; border:none; border-radius:50%; width:44px; height:44px;
                    font-size:1.4rem; cursor:pointer; font-weight:700; }}

  .empty {{ text-align:center; padding:60px 20px; color:var(--muted);
           grid-column:1/-1; }}
  .empty h3 {{ color:var(--yellow); }}

  ::-webkit-scrollbar {{ width:10px; height:10px; }}
  ::-webkit-scrollbar-track {{ background:var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:5px; }}
  ::-webkit-scrollbar-thumb:hover {{ background:var(--accent); }}
</style>
</head>
<body>

<header>
  <h1>🏛️ Dashboard DPRD Kuningan</h1>
  <p>Analisis Berita DPRD & Sentimen Publik • Dibuat {date}</p>
</header>

<div class="stats">
  <div class="stat off"><div class="num">{total_official}</div><div class="lbl">🏛️ Artikel Resmi</div></div>
  <div class="stat"><div class="num">{total_media}</div><div class="lbl">📰 Artikel Media</div></div>
  <div class="stat pos"><div class="num">{sent_pos}</div><div class="lbl">😊 Sentimen Positif</div></div>
  <div class="stat neg"><div class="num">{sent_neg}</div><div class="lbl">😟 Sentimen Negatif</div></div>
  <div class="stat neu"><div class="num">{sent_neu}</div><div class="lbl">😐 Netral</div></div>
  <div class="stat"><div class="num">{total}</div><div class="lbl">📊 Total Artikel DPRD</div></div>
</div>

<div class="controls">
  <input type="text" id="searchInput" placeholder="🔍 Cari judul, sumber, kategori...">
  <select id="filterSource">
    <option value="">Semua Sumber</option>
  </select>
  <select id="filterSentiment">
    <option value="">Semua Sentimen</option>
    <option value="positif">😊 Positif</option>
    <option value="negatif">😟 Negatif</option>
    <option value="netral">😐 Netral</option>
  </select>
  <select id="filterType">
    <option value="">Semua Tipe</option>
    <option value="official">🏛️ Resmi DPRD</option>
    <option value="media">📰 Media</option>
  </select>
</div>

<div class="grid" id="grid">
{cards}
</div>

<div class="modal-bg" id="modalBg">
  <div class="modal" id="modalContent"></div>
</div>

<div class="lightbox" id="lightbox">
  <button class="lightbox-close" onclick="closeLightbox()">×</button>
  <img id="lightboxImg" src="" alt="">
</div>

<script>
const DATA = {data_json};

const sources = [...new Set(DATA.map(a => a.source))].sort();
const selSource = document.getElementById('filterSource');
sources.forEach(s => {{
  const o = document.createElement('option');
  o.value = s; o.textContent = s;
  selSource.appendChild(o);
}});

function applyFilters() {{
  const q = document.getElementById('searchInput').value.toLowerCase();
  const src = document.getElementById('filterSource').value;
  const sent = document.getElementById('filterSentiment').value;
  const type = document.getElementById('filterType').value;

  document.querySelectorAll('.card').forEach(card => {{
    const t = card.dataset.title.toLowerCase();
    const s = card.dataset.source;
    const se = card.dataset.sentiment;
    const ty = card.dataset.type;

    const ok = (!q || t.includes(q) || s.toLowerCase().includes(q))
            && (!src || s === src)
            && (!sent || se === sent)
            && (!type || ty === type);

    card.style.display = ok ? '' : 'none';
  }});
}}

document.getElementById('searchInput').addEventListener('input', applyFilters);
document.getElementById('filterSource').addEventListener('change', applyFilters);
document.getElementById('filterSentiment').addEventListener('change', applyFilters);
document.getElementById('filterType').addEventListener('change', applyFilters);

function openModal(idx) {{
  const a = DATA[idx];
  const s = a.sentiment || {{}};
  const sentLabel = s.label || 'netral';
  const sentBadge = {{positif:'pos', negatif:'neg', netral:'neu'}}[sentLabel];
  const typeBadge = a.is_official
    ? '<span class="badge official">🏛️ Resmi DPRD</span>'
    : '<span class="badge media">📰 Media</span>';
  const regionBadge = a.is_kuningan
    ? '<span class="badge region">📍 Kuningan</span>'
    : '';
  const dprdBadge = a.is_dprd
    ? '<span class="badge dprd">🏛️ DPRD</span>'
    : '';
  const trustBadge = a.trust
    ? `<span class="score">🔒 Trust: ${{a.trust}}</span>`
    : '';

  let hitsHtml = '';
  if ((s.positive_hits||[]).length) {{
    hitsHtml += '<div><strong style="color:#56d364">Kata positif:</strong> ' +
      s.positive_hits.map(h=>`<span class="hit pos">${{h}}</span>`).join('') + '</div>';
  }}
  if ((s.negative_hits||[]).length) {{
    hitsHtml += '<div style="margin-top:6px"><strong style="color:#ff7b72">Kata negatif:</strong> ' +
      s.negative_hits.map(h=>`<span class="hit neg">${{h}}</span>`).join('') + '</div>';
  }}
  if (!hitsHtml) hitsHtml = '<em>Tidak ada kata kunci sentimen terdeteksi.</em>';

  const imgs = (a.images||[]).filter(u => u && u !== a.image);
  const galleryHtml = imgs.length
    ? `<div class="modal-section"><h3>🖼️ Galeri Gambar (${{imgs.length}})</h3>
       <div class="gallery">${{imgs.map(u=>`<img src="${{u}}" onclick="openLightbox('${{u}}')" loading="lazy" alt="">`).join('')}}</div></div>`
    : '';

  const contentHtml = (a.content && a.content.trim())
    ? `<div class="modal-section"><h3>📄 Isi Lengkap</h3>
       <div class="modal-content">${{escapeHtml(a.content)}}</div></div>`
    : '<div class="modal-section"><h3>📄 Isi Lengkap</h3><div class="modal-content"><em>Konten tidak tersedia (gagal fetch detail).</em></div></div>';

  const heroSrc = a.image || (a.images && a.images[0]) || '';
  const hero = heroSrc
    ? `<img class="modal-hero" src="${{heroSrc}}" alt="" loading="lazy">`
    : '';

  const cats = (a.category||[]).length
    ? a.category.map(c=>`<span class="hit">${{escapeHtml(c)}}</span>`).join('')
    : '<em>-</em>';

  document.getElementById('modalContent').innerHTML = `
    ${{hero}}
    <div class="modal-body">
      <div class="modal-header">
        <h2 class="modal-title">${{escapeHtml(a.title || '(tanpa judul)')}}</h2>
        <button class="modal-close" onclick="closeModal()">×</button>
      </div>

      <div class="modal-meta">
        ${{typeBadge}}
        ${{dprdBadge}}
        ${{regionBadge}}
        <span class="badge ${{sentBadge}}">${{sentLabel.toUpperCase()}}</span>
        <span class="score">⭐ Skor: ${{a.relevance_score || 0}}</span>
        ${{trustBadge}}
        <span class="score">📅 ${{a.date || 'n/a'}}</span>
        <span class="score">📡 ${{escapeHtml(a.source)}}</span>
        ${{a.author ? `<span class="score">✍️ ${{escapeHtml(a.author)}}</span>` : ''}}
      </div>

      ${{a.summary ? `<div class="modal-section"><h3>📝 Ringkasan</h3><div class="modal-content">${{escapeHtml(a.summary)}}</div></div>` : ''}}

      <div class="modal-section">
        <h3>🏷️ Kategori</h3>
        <div>${{cats}}</div>
      </div>

      <div class="modal-section">
        <h3>💭 Analisis Sentimen</h3>
        <div class="sentiment-box">
          <div><strong>Label:</strong> ${{sentLabel.toUpperCase()}}
            (skor positif: ${{s.positive_score||0}}, negatif: ${{s.negative_score||0}})</div>
          <div style="margin-top:8px">${{hitsHtml}}</div>
        </div>
      </div>

      ${{contentHtml}}
      ${{galleryHtml}}

      <div class="modal-section">
        <a class="modal-link" href="${{escapeHtml(a.link)}}" target="_blank" rel="noopener">
          🌐 Buka Artikel Asli di Sumber
        </a>
      </div>
    </div>
  `;

  document.getElementById('modalBg').classList.add('active');
  document.body.style.overflow = 'hidden';
}}

function closeModal() {{
  document.getElementById('modalBg').classList.remove('active');
  document.body.style.overflow = '';
}}

document.getElementById('modalBg').addEventListener('click', e => {{
  if (e.target.id === 'modalBg') closeModal();
}});

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{ closeModal(); closeLightbox(); }}
}});

function openLightbox(url) {{
  document.getElementById('lightboxImg').src = url;
  document.getElementById('lightbox').classList.add('active');
}}
function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('active');
}}
document.getElementById('lightbox').addEventListener('click', e => {{
  if (e.target.id === 'lightbox') closeLightbox();
}});

function escapeHtml(str) {{
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}}
</script>
</body>
</html>"""


def _resolve_image(a: dict) -> str | None:
    """Resolve image: pakai a['image'], fallback ke images[0]."""
    img = a.get("image")
    if img:
        return img
    imgs = a.get("images") or []
    for u in imgs:
        if u:
            return u
    return None


def _card_html(idx: int, a: dict, is_official: bool) -> str:
    img = _resolve_image(a)
    if img:
        thumb = f'<img class="thumb" src="{escape(img)}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
    else:
        thumb = (
            '<div class="thumb thumb-placeholder">📷 Tanpa gambar</div>'
        )

    s = a.get("sentiment", {})
    sent_label = s.get("label", "netral")
    sent_badge_cls = {
        "positif": "pos", "negatif": "neg", "netral": "neu",
    }.get(sent_label, "neu")

    type_badge = (
        '<span class="badge official">🏛️ Resmi</span>'
        if is_official
        else '<span class="badge media">📰 Media</span>'
    )

    region_badge = (
        '<span class="badge region">📍 Kuningan</span>'
        if a.get("is_kuningan")
        else ""
    )

    dprd_badge = (
        '<span class="badge dprd">🏛️ DPRD</span>'
        if a.get("is_dprd")
        else ""
    )

    trust = a.get("trust")
    trust_badge = (
        f'<span class="score">🔒 {trust}</span>' if trust else ""
    )

    title = escape(a.get("title") or "-")
    summary = escape((a.get("summary") or "")[:200])

    return f"""
    <div class="card"
         data-title="{title.lower()}"
         data-source="{escape(a.get('source',''))}"
         data-sentiment="{sent_label}"
         data-type="{'official' if is_official else 'media'}"
         onclick="openModal({idx})">
      {thumb}
      <div class="body">
        <h3 class="title">{title}</h3>
        <div class="meta">
          {type_badge}
          {dprd_badge}
          {region_badge}
          <span class="badge {sent_badge_cls}">{sent_label.upper()}</span>
          <span class="score">⭐ {a.get('relevance_score', 0)}</span>
          {trust_badge}
          <span>{escape(a.get('date') or 'n/a')}</span>
        </div>
        <div class="meta" style="font-size:.7rem">📡 {escape(a.get('source',''))}</div>
        <p class="summary">{summary}</p>
        <div class="readmore">👁️ Klik untuk lihat detail lengkap →</div>
      </div>
    </div>"""


def export_html(all_results: list[dict], stats: dict, path: str):
    cards = []
    data_for_js = []
    idx = 0

    # Resmi dulu
    for r in all_results:
        if not r.get("is_official"):
            continue
        for a in r.get("filtered", []):
            a_copy = dict(a)
            a_copy["source"] = r["source"]
            a_copy["is_official"] = True
            a_copy["trust"] = r.get("trust")
            data_for_js.append(a_copy)
            cards.append(_card_html(idx, a_copy, True))
            idx += 1

    # Lalu media
    for r in all_results:
        if r.get("is_official"):
            continue
        for a in r.get("filtered", []):
            a_copy = dict(a)
            a_copy["source"] = r["source"]
            a_copy["is_official"] = False
            a_copy["trust"] = r.get("trust")
            data_for_js.append(a_copy)
            cards.append(_card_html(idx, a_copy, False))
            idx += 1

    if not cards:
        cards.append(
            '<div class="empty"><h3>⚠️ Tidak ada artikel</h3>'
            '<p>Tidak ada artikel untuk ditampilkan.</p></div>'
        )

    sentiments = stats.get("sentiments", {})
    sent_pos = sentiments.get("positif", 0)
    sent_neg = sentiments.get("negatif", 0)
    sent_neu = sentiments.get("netral", 0)

    sent_total = sent_pos + sent_neg + sent_neu
    if sent_total != stats.get("total", 0):
        log.warning(
            f"Statistik tidak konsisten: "
            f"sentiments={sent_total}, total={stats.get('total', 0)}. "
        )

    html = HTML_TEMPLATE.format(
        date=datetime.now().strftime("%d %B %Y %H:%M"),
        total=stats.get("total", 0),
        total_official=stats.get("official_count", 0),
        total_media=stats.get("media_count", 0),
        sent_pos=sent_pos,
        sent_neg=sent_neg,
        sent_neu=sent_neu,
        cards="\n".join(cards),
        data_json=json.dumps(data_for_js, ensure_ascii=False),
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return len(data_for_js)
