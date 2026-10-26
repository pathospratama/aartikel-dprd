"""Konfigurasi sumber berita DPRD Kuningan — v6.

Perubahan v6:
- Tambah sumber: kuninganmass.com, kuninganjabarinfo.id, inilahkuningan.com,
  jabar.antaranews.com, bappeda.kuningankab.go.id, rri.co.id
- Fix image extractor WordPress (data-src, srcset, background-image)
- Blacklist dilonggarkan (kritik DPRD tetap lolos)
- Tag is_legislative_work untuk sumber resmi
- Gate title untuk media: wajib ada kata DPRD di title
"""

# =====================================================
# SUMBER RESMI DPRD (is_official=True → tanpa filter wilayah + auto tag legislative)
# =====================================================
OFFICIAL_SOURCES = [
    {
        "name": "DPRD Kuningan (Resmi)",
        "url": "https://dprd.kuningankab.go.id/berita/page/1",
        "fallback_urls": [],
        "is_official": True,
        "is_official_gov": True,
        "max_pages": 30,
        "selectors": {
            "item": "div.card, div.berita, article, .post, .news-item, .col-md-4",
            "title": "h2, h3, h4, .card-title, .judul",
            "link": "a[href*='/berita/']",
            "date": ".tanggal, .date, time, small",
            "summary": "p, .card-text, .ringkasan",
            "image": "img",
        },
        "detail": {
            "content": "article.newsSingleWrap",
            "content_fallback": "article p, article h2, article h3, article li",
            "author": ".author, .penulis, [rel='author']",
            "date": ".tanggal, time, .date, .post-date",
            "category": ".category, .kategori, .tags a",
            "image": "article img, .newsSingleWrap img",
            "exclude_selectors": (
                "nav, header, footer, aside, "
                ".hdNavWrap, .hdRighterWrap, .swiper, .swiper-slide, .swiper-wrapper, "
                ".profil, .fraksi, .alat-kelengkapan, .pengaduan, "
                ".footerAside, .breadcrumb, .widget"
            ),
        },
    },
    # === Sumber resmi pemerintah (Bappeda) ===
    {
        "name": "Bappeda Kuningan",
        "url": "https://bappeda.kuningankab.go.id/category/berita/",
        "fallback_urls": [
            "https://bappeda.kuningankab.go.id/category/berita/page/2/",
            "https://bappeda.kuningankab.go.id/2026/10/",
            "https://bappeda.kuningankab.go.id/2026/09/",
            "https://bappeda.kuningankab.go.id/",
        ],
        # WordPress REST API dan RSS diprioritaskan sebagai jalur alternatif.
        "api_urls": [
            "https://bappeda.kuningankab.go.id/wp-json/wp/v2/posts?_embed=1",
        ],
        "feed_urls": [
            "https://bappeda.kuningankab.go.id/category/berita/feed/",
            "https://bappeda.kuningankab.go.id/feed/",
        ],
        "is_official": True,
        "is_official_gov": True,
        "max_pages": 3,
        "selectors": {
            # Berdasarkan HTML Inspect: tema WordPress/JNews.
            "item": "article.jeg_post, .jeg_post, article, .post",
            "title": ".jeg_post_title a, h2 a, h3 a, .entry-title a",
            "link": ".jeg_post_title a, h2 a, h3 a, .entry-title a",
            "date": ".jeg_meta_date, time, .entry-date, .date",
            "summary": ".jeg_post_excerpt, .entry-summary, .excerpt, .jeg_post_content p",
            "image": ".jeg_thumb img, .jeg_post_thumb img, img[data-src], img[data-lazy-src], img",
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div.post-content, div[class*='content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .entry-author",
            "date": ".entry-date, time, .posted-on",
            "category": ".cat-links a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .menu, .breadcrumb",
        },
    },
]


# =====================================================
# SUMBER SEMI-RESMI PEMERINTAH (bukan DPRD, tapi masih resmi)
# =====================================================
SEMI_OFFICIAL_SOURCES = [
    {
        "name": "Pemkab Kuningan — Kategori Daerah",
        "url": "https://kuningankab.go.id/home/category/daerah/",
        "feed_urls": ["https://kuningankab.go.id/home/feed/", "https://kuningankab.go.id/feed/"],

        "fallback_urls": [
            "https://kuningankab.go.id/home/publikasi-berita/",
            "https://kuningankab.go.id/home/",
        ],
        "is_official": True,
        "is_official_gov": True,
        "max_pages": 5,
        "selectors": {
            "item": "article.jeg_post",
            "title": ".jeg_post_title a",
            "link": ".jeg_post_title a",
            "date": ".jeg_meta_date",
            "summary": ".jeg_post_excerpt",
            "image": ".jeg_thumb img, .jeg_post_thumb img, img",
        },
        "detail": {
            "content": ".content-inner .content, .jeg_post_content, .entry-content, article",
            "content_fallback": ".jeg_post_content p, .entry-content p, article p, main p",
            "author": ".jeg_meta_author, .author, .entry-author",
            "date": ".jeg_meta_date, time, .entry-date",
            "category": ".jeg_meta_category a, .cat-links a",
            "image": ".content-inner img, .jeg_post_content img, .entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .jeg_postblock, .jeg_related_post, .breadcrumb, .jeg_share_button",
        },
    },
    {
        "name": "Pemkab Kuningan — Publikasi Berita",
        "url": "https://kuningankab.go.id/home/publikasi-berita/",
        "fallback_urls": [
            "https://kuningankab.go.id/home/category/daerah/",
            "https://kuningankab.go.id/home/",
            "https://kuningankab.go.id/",
        ],
        "feed_urls": [
            "https://kuningankab.go.id/home/publikasi-berita/feed/",
            "https://kuningankab.go.id/home/feed/",
            "https://kuningankab.go.id/feed/",
        ],
        "is_official": True,
        "is_official_gov": True,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post-item, .berita-item, .pengumuman-item, .news-item, .card, .item, [class*='publication-item']",
            "title": "h1 a, h2 a, h3 a, h4 a, .entry-title, .card-title, .title",
            "link": "h1 a, h2 a, h3 a, h4 a, .entry-title a, .card-title a, a[href*='/home/']",
            "date": "time, .date, .entry-date, .tanggal, .post-date",
            "summary": ".entry-summary, .excerpt, .summary, .description, p",
            "image": "img, img[data-src], img[data-lazy-src], img[data-original]",
        },
        "detail": {
            "content": "article, .entry-content, .post-content, .article-content, .detail-content, .content-detail, [class*='detail-berita']",
            "content_fallback": "article p, .entry-content p, .post-content p, main p",
            "author": ".author, .entry-author, .penulis",
            "date": "time, .entry-date, .date, .tanggal",
            "category": ".cat-links a, .category a, .kategori a",
            "image": "article img, .entry-content img, .post-content img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .menu, .breadcrumb",
        },
    },
    {
        "name": "Pemkab Kuningan — Publikasi Pengumuman",
        "url": "https://kuningankab.go.id/home/publikasi-pengumuman/",
        "fallback_urls": [
            "https://kuningankab.go.id/home/",
            "https://kuningankab.go.id/",
        ],
        "feed_urls": [
            "https://kuningankab.go.id/home/publikasi-pengumuman/feed/",
            "https://kuningankab.go.id/home/feed/",
            "https://kuningankab.go.id/feed/",
        ],
        "is_official": True,
        "is_official_gov": True,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post-item, .berita-item, .pengumuman-item, .news-item, .card, .item, [class*='publication-item']",
            "title": "h1 a, h2 a, h3 a, h4 a, .entry-title, .card-title, .title",
            "link": "h1 a, h2 a, h3 a, h4 a, .entry-title a, .card-title a, a[href*='/home/']",
            "date": "time, .date, .entry-date, .tanggal, .post-date",
            "summary": ".entry-summary, .excerpt, .summary, .description, p",
            "image": "img, img[data-src], img[data-lazy-src], img[data-original]",
        },
        "detail": {
            "content": "article, .entry-content, .post-content, .article-content, .detail-content, .content-detail, [class*='detail-pengumuman']",
            "content_fallback": "article p, .entry-content p, .post-content p, main p",
            "author": ".author, .entry-author, .penulis",
            "date": "time, .entry-date, .date, .tanggal",
            "category": ".cat-links a, .category a, .kategori a",
            "image": "article img, .entry-content img, .post-content img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .menu, .breadcrumb",
        },
    },
    {
        "name": "PPID Kuningan",
        "url": "https://ppid.kuningankab.go.id/artikel",
        "fallback_urls": ["https://ppid.kuningankab.go.id/"],
        "is_official": False,
        "is_official_gov": True,
        "max_pages": 2,
        "selectors": {
            "item": "div[class*='item'], article, .post, .artikel-item, .card, .list-item",
            "title": "article h2, h2, h3, .title, .judul",
            "link": "h2 a, h3 a, a[href*='/artikel/']",
            "date": "time, .date, .tanggal",
            "summary": "p, .ringkasan",
            "image": "article img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "div[class*='content'], div.artikel-content, article .content, div.post-content",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .penulis",
            "date": "time, .date, .tanggal",
            "category": ".kategori a, .category a",
            "image": "article img, .artikel-content img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .menu",
        },
    },
]


# =====================================================
# SUMBER MEDIA — LOKAL & REGIONAL
# =====================================================
MEDIA_SOURCES = [
    # === kuninganmass.com — query ?s=dprd ===
    {
        "name": "Kuningan Mass",
        "url": "https://kuninganmass.com/?s=dprd",
        "fallback_urls": [
            "https://kuninganmass.com/",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": ".post, article, div[class*='post']",
            "title": ".entry-title, h2, h3",
            "link": ".entry-title a, h2 a, h3 a, a[href*='kuninganmass.com']",
            "date": ".posted-on, time, .entry-date",
            "summary": ".entry-summary p, .entry-content p, p",
            # ✅ Fix gambar WP
            "image": "img[src*='wp-content'], img[data-src*='wp-content'], img[data-lazy-src*='wp-content'], img",
        },
        "detail": {
            "content": "div.entry-content, div[itemprop='text'], article .entry-content",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .entry-author",
            "date": ".posted-on, time",
            "category": ".cat-links a, .tags-links a",
            "image": ".entry-content img, figure img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy",
        },
    },
    # === kuninganjabarinfo.id/category/dprd/ ===
    {
        "name": "Kuningan Jabar Info",
        "url": "https://kuninganjabarinfo.id/category/dprd/",
        "fallback_urls": [
            "https://kuninganjabarinfo.id/",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .td_module_wrap, .card, div[class*='post']",
            "title": ".title, h2, h3, .entry-title",
            "link": "a[href], h2 a, h3 a, .entry-title a",
            "date": "time, .date, .entry-date",
            "summary": "p, .entry-summary",
            # ✅ Fix gambar WP: cek semua lazy-load attr
            "image": (
                "img[src*='wp-content'], img[data-src*='wp-content'], "
                "img[data-lazy-src*='wp-content'], img[data-original*='wp-content'], "
                "img[srcset*='wp-content'], img"
            ),
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div[class*='entry-content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .td-post-author-name",
            "date": "time, .entry-date",
            "category": ".cat-links a, .td-category a",
            "image": ".entry-content img, article img, figure img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts",
        },
    },
    # === inilahkuningan.com ===
    {
        "name": "Inilah Kuningan",
        "url": "https://inilahkuningan.com/indeks-berita/",
        "api_urls": ["https://inilahkuningan.com/wp-json/wp/v2/posts?_embed=1"],
        "feed_urls": ["https://inilahkuningan.com/feed/"],

        "fallback_urls": [
            "https://inilahkuningan.com/indeks-berita/",
            "https://inilahkuningan.com/category/berita/",
            "https://inilahkuningan.com/",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .news-item, .card, .berita-item, div[class*='post']",
            "title": "h2, h3, .title, .entry-title",
            "link": "h2 a, h3 a, .title a, a[href*='inilahkuningan.com']",
            "date": ".date, time, .tanggal, .entry-date",
            "summary": "p, .summary, .excerpt",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": (
                "div.entry-content, div.post-content, div.article-content, "
                "div.detail-content, article .content, div.isi, div[class*='content']"
            ),
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .penulis",
            "date": ".date, time, .tanggal",
            "category": ".cat-links a, .category a, .kategori a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .menu",
        },
    },
    # === jabar.antaranews.com ===
    {
        "name": "Antara News Jabar",
        "url": "https://jabar.antaranews.com/tag/kuningan",
        "fallback_urls": [
            "https://jabar.antaranews.com/",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "div[class*='card'], article, .post, .news-item",
            "title": "h2, h3, .title, .entry-title",
            "link": "h2 a, h3 a, a[href*='/berita/']",
            "date": ".date, time, .entry-date",
            "summary": "p, .summary, .excerpt",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": (
                "div.post-content, div.entry-content, div.article-content, "
                "div[class*='content'], article .content"
            ),
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .entry-author",
            "date": ".date, time, .entry-date",
            "category": ".cat-links a, .category a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts",
        },
    },
    # === rri.co.id ===
    {
        "name": "RRI Kuningan",
        "url": "https://rri.co.id/kuningan",
        "fallback_urls": [
            "https://rri.co.id/",
            "https://rri.co.id/berita",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .news-item, .card, div[class*='post'], div[class*='news']",
            "title": "h2, h3, .title, .entry-title",
            "link": "h2 a, h3 a, a[href*='/kuningan/'], a[href*='/berita/']",
            "date": ".date, time, .entry-date",
            "summary": "p, .summary, .excerpt",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": (
                "div.entry-content, div.post-content, div.article-content, "
                "div.detail-content, div[class*='content'], article .content"
            ),
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .penulis",
            "date": ".date, time, .entry-date",
            "category": ".cat-links a, .category a, .kategori a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .menu",
        },
    },
    # === Media lain yang sudah ada ===
    {
        "name": "Radar Kuningan",
        "url": "https://radarkuningan.disway.id/",
        "fallback_urls": [],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "div[class*='post'], article, .news-item",
            "title": "a[title], h2, h3, .title, .entry-title",
            "link": "a[href*='/read/']",
            "date": ".date, time, .entry-date, .post-date",
            "summary": "p, .summary, .excerpt",
            "image": "img, img[data-src], img[data-lazy-src], img[data-original]",
        },
        "detail": {
            "content": "div.entry-content, div[class*='entry-content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .entry-author",
            "date": ".date, time, .entry-date",
            "category": ".cat-links a, .category a",
            "image": "article img, .entry-content img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy, .menu",
        },
    },
    {
        "name": "Kabar Kuningan (PR)",
        "url": "https://kabarkuningan.pikiran-rakyat.com/",
        "fallback_urls": ["https://kabarkuningan.pikiran-rakyat.com/kabar-kuningan"],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "div.pt-10, li.pt-10, div[class*='pt-10'], div[class*='card'], article, .post",
            "title": "h2, h3, .title, .entry-title",
            "link": "a[href*='/kabar-kuningan/'], a[href*='pikiran-rakyat.com/'], h2 a, h3 a",
            "date": ".date, time, .entry-date, .post-date",
            "summary": "p, .summary, .excerpt",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "div.entry-content, div.post-content, div.article-content, div.detail-content, div.txt-article, div[class*='content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .entry-author",
            "date": ".date, time, .entry-date",
            "category": ".cat-links a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy, .menu",
        },
    },
    {
        "name": "Potret Kuningan",
        "url": "https://potretkuningan.com/category/headline/",
        "api_urls": ["https://potretkuningan.com/wp-json/wp/v2/posts?_embed=1"],
        "feed_urls": ["https://potretkuningan.com/feed/"],

        "fallback_urls": [
            "https://potretkuningan.com/",
            "https://potretkuningan.com/?s=dprd",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .td_module_wrap, .card, .news-item, div[class*='post']",
            "title": "h2, h3, .entry-title, .title",
            "link": "h2 a, h3 a, .entry-title a, a[href*='potretkuningan.com']",
            "date": ".date, time, .entry-date",
            "summary": "p, .entry-summary",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div.post-content, div[class*='content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .td-post-author-name",
            "date": ".entry-date, time",
            "category": ".cat-links a, .td-category a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy",
        },
    },
    {
        "name": "Media Kuningan",
        "url": "https://mediakuningan.com/",
        "api_urls": ["https://mediakuningan.com/wp-json/wp/v2/posts?_embed=1"],
        "feed_urls": ["https://mediakuningan.com/feed/"],

        "fallback_urls": [
            "https://mediakuningan.com/category/berita/",
            "https://mediakuningan.com/?s=dprd",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .td_module_wrap, .card, div[class*='post']",
            "title": "h2, h3, .entry-title",
            "link": "h2 a, h3 a, .entry-title a",
            "date": ".date, time, .entry-date",
            "summary": "p, .entry-summary",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div[class*='content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .td-post-author-name",
            "date": ".entry-date, time",
            "category": ".cat-links a, .td-category a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts",
        },
    },
    {
        "name": "Ciremai Today",
        "url": "https://ciremaitoday.com/",
        "api_urls": ["https://ciremaitoday.com/wp-json/wp/v2/posts?_embed=1"],
        "feed_urls": ["https://ciremaitoday.com/feed/"],

        "fallback_urls": ["https://ciremaitoday.com/tag/kuningan/", "https://ciremaitoday.com/category/berita/"],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "div[class*='post'], article, .td_module_wrap",
            "title": "h2, h3, .entry-title, .title",
            "link": "a[href], h2 a, h3 a, .entry-title a",
            "date": "time, .date, .entry-date",
            "summary": "p, .entry-summary",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div[class*='content'], div[class*='detail'], div[class*='article'], div[class*='body']",
            "content_fallback": "article p, article h2, article h3, main p, main h2, main h3",
            "author": ".author, .td-post-author-name",
            "date": "time, .entry-date, .date",
            "category": ".cat-links a, .td-category a",
            "image": "article img, .entry-content img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .list-content",
        },
    },
    {
        "name": "iNews Kuningan",
        "url": "https://kuningan.inews.id/",
        "fallback_urls": ["https://kuningan.inews.id/news", "https://kuningan.inews.id/peristiwa"],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .news-item, .card, .list-news, div[class*='card']",
            "title": "article h2, h2, h3, .title, .entry-title",
            "link": "a[href*='/read/'], h2 a, h3 a, .title a",
            "date": ".date, time, .entry-date, .post-date",
            "summary": "p, .summary, .excerpt",
            "image": "article img, img[data-src]",
        },
        "detail": {
            "content": "div.entry-content, div.post-content, div.article-content, div.detail-content, div.content-detail, div[class*='content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .entry-author",
            "date": ".date, time, .entry-date",
            "category": ".cat-links a, .category a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .menu",
        },
    },
    {
        "name": "Kuningan Religi",
        "url": "https://kuninganreligi.com/",
        "api_urls": ["https://kuninganreligi.com/wp-json/wp/v2/posts?_embed=1"],
        "feed_urls": ["https://kuninganreligi.com/feed/"],

        "fallback_urls": [
            "https://kuninganreligi.com/category/kuningan/",
            "https://kuninganreligi.com/?s=dprd",
        ],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "article, .post, .td_module_wrap, div[class*='post']",
            "title": "h2, h3, .entry-title",
            "link": "h2 a, h3 a, .entry-title a",
            "date": ".date, time, .entry-date",
            "summary": "p, .entry-summary",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div[class*='content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .td-post-author-name",
            "date": ".entry-date, time",
            "category": ".cat-links a, .td-category a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget",
        },
    },
    {
        "name": "Media Identitas",
        "url": "https://mediaidentitas.com/",
        "fallback_urls": ["https://mediaidentitas.com/category/berita/"],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": ".post, article, .td_module_wrap, div[class*='post']",
            "title": ".entry-title, h2, h3",
            "link": "a[href], h2 a, h3 a, .entry-title a",
            "date": "time, .entry-date",
            "summary": "p, .entry-summary",
            "image": "article img, img[data-src], img[data-lazy-src], img",
        },
        "detail": {
            "content": "div.entry-content, article .entry-content, div[class*='entry-content'], div[class*='post-content']",
            "content_fallback": "article p, article h2, article h3",
            "author": ".author, .td-post-author-name",
            "date": "time, .entry-date",
            "category": ".cat-links a, .td-category a",
            "image": ".entry-content img, article img",
            "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget",
        },
    },
    {
        "name": "Kuningan News",
        "url": "https://www.kuningannews.com/",
        "fallback_urls": ["https://kuningannews.com/", "https://www.kuningannews.com/search/label/Politik"],
        "is_official": False,
        "max_pages": 5,
        "selectors": {
            "item": "div[class*='post'], .post, .post-outer, article",
            "title": "h2, h3, .post-title, .entry-title",
            "link": "a[href*='.html'], .post-title a, h2 a, h3 a",
            "date": ".date-header, time, .post-date",
            "summary": ".post-body, .snippet, p",
            "image": "img, img[data-src], img[data-lazy-src]",
        },
        "detail": {
            "content": "article.post-outer-container .post-content, article.post-outer-container .post-body.entry-content, div.post-content",
            "content_fallback": "article.post-outer-container p, article.post-outer-container h2",
            "author": ".post-author, .author",
            "date": ".date-header, time, .post-date",
            "category": ".post-labels a, .category a",
            "image": ".post-body img, .post-content img",
            "exclude_selectors": "nav, header, footer, aside, .widget, .PopularPosts, .post-snippet, .list-label-widget-content, .blog-pager, .sidebar-invisible, .header-image-wrapper",
        },
    },
    {
        "name": "Detik (Tag Kuningan)",
        "url": "https://www.detik.com/tag/kuningan",
        "fallback_urls": ["https://www.detik.com/tag/kabupaten-kuningan"],
        "is_official": False,
        "max_pages": 2,
        "selectors": {
            "item": "article",
            "title": ".title, h2, h3",
            "link": "a[href*='/berita/']",
            "date": ".date",
            "summary": "article p",
            "image": "article img",
        },
        "detail": {
            "content": "div.detail__body-text, div.itp_bodycontent, div[class*='body-text'], article.detail",
            "content_fallback": "article.detail p, article.detail h2",
            "author": ".author, .detail__author",
            "date": ".detail__date, .date",
            "category": ".detail__category, .breadcrumb a",
            "image": ".detail__media img, article.detail img",
            "exclude_selectors": "nav, header, footer, aside, .list-content, .list-content__item, .box, .cb-artikel-lainnya",
        },
    },
]


SOURCES = OFFICIAL_SOURCES + SEMI_OFFICIAL_SOURCES + MEDIA_SOURCES

# Selector profil di bawah diselaraskan dengan HTML halaman daftar yang diberikan.
# Selector detail tetap memiliki fallback generik karena file yang tersedia terutama
# berupa halaman daftar, bukan halaman detail untuk setiap artikel.
HTML_SNAPSHOT_PROFILES = {
    "DPRD Kuningan (Resmi)": {
        "url": "https://dprd.kuningankab.go.id/berita/page/1",
        "selectors": {"item": "article.npbColumn", "title": ".npbDescriptionWrap h3 a", "link": ".npbDescriptionWrap h3 a", "date": "time.npbTimeTag", "summary": ".npbDescriptionWrap p", "image": ".image-news img"},
        "detail": {"content": ".newsSingleWrap, .newsSingleWrap .textWrap, article.newsSingleWrap, .newsContent, .article-content", "content_fallback": ".newsSingleWrap p, article p, main p", "image": ".newsSingleWrap img, article img", "date": ".newsSingleWrap time, .newsSingleWrap .npbTimeTag, time", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .breadcrumb, .pagination"},
    },
    "Bappeda Kuningan": {
        "url": "https://bappeda.kuningankab.go.id/category/berita/",
        "selectors": {"item": "article.jeg_post", "title": ".jeg_post_title a", "link": ".jeg_post_title a", "date": ".jeg_meta_date, .jeg_post_meta time, time", "summary": ".jeg_post_excerpt, .jeg_postblock_content p", "image": ".jeg_thumb img, .jeg_post_thumb img, img", "fallback_title_links": True},
        "detail": {"content": ".jeg_post_content, .content-inner .content, .entry-content, article .content", "content_fallback": ".jeg_post_content p, .content-inner p, .entry-content p, article p", "date": ".jeg_meta_date, time, .entry-date", "image": ".jeg_post_content img, .content-inner img, .entry-content img", "exclude_selectors": "nav, header, footer, aside, .jeg_sidebar, .sidebar, .widget, .jeg_postblock, .jeg_related_post, .breadcrumb"},
    },
    "Pemkab Kuningan — Kategori Daerah": {
        "url": "https://kuningankab.go.id/home/category/daerah/",
        "selectors": {"item": "article.jeg_post", "title": ".jeg_post_title a", "link": ".jeg_post_title a", "date": ".jeg_meta_date, .jeg_post_meta time, time", "summary": ".jeg_post_excerpt, .jeg_postblock_content p", "image": ".jeg_thumb img, .jeg_post_thumb img, img"},
        "detail": {"content": ".jeg_post_content, .content-inner .content, .entry-content, article .content", "content_fallback": ".jeg_post_content p, .content-inner p, .entry-content p, article p", "date": ".jeg_meta_date, time, .entry-date", "image": ".jeg_post_content img, .content-inner img, .entry-content img", "exclude_selectors": "nav, header, footer, aside, .jeg_sidebar, .sidebar, .widget, .jeg_postblock, .jeg_related_post, .breadcrumb"},
    },
    "Pemkab Kuningan — Publikasi Berita": {
        "url": "https://kuningankab.go.id/home/publikasi-berita/",
        "selectors": {"item": "article.jeg_post", "title": ".jeg_post_title a", "link": ".jeg_post_title a", "date": ".jeg_meta_date, .jeg_post_meta time, time", "summary": ".jeg_post_excerpt, .jeg_postblock_content p", "image": ".jeg_thumb img, .jeg_post_thumb img, img"},
        "detail": {"content": ".jeg_post_content, .content-inner .content, .entry-content, article .content", "content_fallback": ".jeg_post_content p, .content-inner p, .entry-content p, article p", "date": ".jeg_meta_date, time, .entry-date", "image": ".jeg_post_content img, .content-inner img, .entry-content img", "exclude_selectors": "nav, header, footer, aside, .jeg_sidebar, .sidebar, .widget, .jeg_postblock, .jeg_related_post, .breadcrumb"},
    },
    "Pemkab Kuningan — Publikasi Pengumuman": {
        "url": "https://kuningankab.go.id/home/publikasi-pengumuman/",
        "selectors": {"item": "article.jeg_post", "title": ".jeg_post_title a", "link": ".jeg_post_title a", "date": ".jeg_meta_date, .jeg_post_meta time, time", "summary": ".jeg_post_excerpt, .jeg_postblock_content p", "image": ".jeg_thumb img, .jeg_post_thumb img, img"},
        "detail": {"content": ".jeg_post_content, .content-inner .content, .entry-content, article .content", "content_fallback": ".jeg_post_content p, .content-inner p, .entry-content p, article p", "date": ".jeg_meta_date, time, .entry-date", "image": ".jeg_post_content img, .content-inner img, .entry-content img", "exclude_selectors": "nav, header, footer, aside, .jeg_sidebar, .sidebar, .widget, .jeg_postblock, .jeg_related_post, .breadcrumb"},
    },
    "PPID Kuningan": {
        "url": "https://ppid.kuningankab.go.id/artikel",
        "selectors": {"item": ".row.okta-blog-row, article", "title": "h2.article-title a, .article-title a, h2 a", "link": "h2.article-title a, .article-title a, h2 a", "date": "time[datetime], time", "summary": ".article-intro p, .article-intro, .article-description p, p", "image": ".article-intro img, img"},
        "detail": {"content": ".com-content-article__body, .item-page, .com-content-article, article", "content_fallback": ".com-content-article__body p, .item-page p, article p, main p", "date": "time[datetime], time", "image": ".com-content-article__body img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .menu, .pagination, .article-info"},
    },
    "Kuningan Mass": {
        "selectors": {"item": "article.post", "title": ".entry-title a, h2.entry-title a", "link": ".entry-title a, h2.entry-title a", "date": "time.entry-date, .posted-on time, time", "summary": ".entry-summary, .post-excerpt, .entry-content p", "image": ".post-thumbnail img, .post-image img, img"},
        "detail": {"content": "div.entry-content, div[itemprop='text'], article .entry-content", "content_fallback": "article .entry-content p, article p, article h2, article h3", "date": "time.entry-date, time", "image": ".entry-content img, figure img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy"},
    },
    "Kuningan Jabar Info": {
        "url": "https://kuninganjabarinfo.id/category/dprd/",
        "selectors": {"item": ".bs-blog-post, .multi-post-widget .bs-blog-post", "title": "h4.title a, .title a", "link": "h4.title a, .title a", "date": "time[datetime], time, .date", "summary": ".bs-blog-post p, .entry-summary, p", "image": ".bs-blog-post img, img"},
        "detail": {"content": ".entry-content, .post-content, .td-post-content, article", "content_fallback": ".entry-content p, .post-content p, article p, main p", "date": "time[datetime], time, .entry-date", "image": ".entry-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts"},
    },
    "Inilah Kuningan": {
        "url": "https://inilahkuningan.com/indeks-berita/",
        "selectors": {"item": ".indeks-item.media", "title": ".media-title, h2 a", "link": ".media-title, h2 a", "date": ".indeks-date time, .indeks-date, time, [class*=date]", "summary": ".indeks-summary, .indeks-item p, p", "image": ".indeks-image img, .media-image img, img"},
        "detail": {"content": ".post-content, .entry-content, .article-content, .detail-content, .single-content, article", "content_fallback": ".post-content p, .entry-content p, article p, main p", "date": "time[datetime], time, .date", "image": ".post-content img, .entry-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy"},
    },
    "Antara News Jabar": {
        "selectors": {"item": ".card__post", "title": ".card__post__title a, h2 a, h3 a", "link": ".card__post__title a, h2 a, h3 a", "date": "time, .post-date, .date", "summary": ".card__post__content p, .card__post__body p, p", "image": ".card__post__picture img, .card__post img, img"},
        "detail": {"content": ".post-content, .detail__body, .article-content, article", "content_fallback": ".post-content p, .detail__body p, article p, main p", "date": "time, .date, .post-date", "image": ".post-content img, .detail__body img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .related, .card__post"},
    },
    "RRI Kuningan": {
        "url": "https://rri.co.id/kuningan",
        "selectors": {"item": ".news-list-item.articles-list, .news-list-item, .articles-list", "title": "h4 a.title, h4 a, a.title", "link": "h4 a.title, h4 a, a.title", "date": "time, .date, [class*='date']", "summary": ".post-info-2 p, .post-info p, p", "image": "a.thumb img, img"},
        "detail": {"content": ".detail-content, .article-content, .content-article, article", "content_fallback": ".detail-content p, .article-content p, article p, main p", "date": "time, [class*='date']", "image": ".detail-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .related, .recommended"},
    },
    "Radar Kuningan": {
        "selectors": {"item": "div.media:has(.media-heading a[href*='/kuningan/read/'])", "title": ".media-heading a, h2 a", "link": ".media-heading a[href*='/kuningan/read/']", "date": ".date, time, .post-date", "summary": ".media-content p, .media-body p, p", "image": ".media-left img, .media-object, img"},
        "detail": {"content": ".article-content, .content-detail, .detail-content, article", "content_fallback": ".article-content p, .content-detail p, article p, main p", "date": "time, .date", "image": ".article-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy, .menu"},
    },
    "Kabar Kuningan (PR)": {
        "selectors": {"item": ".hl__b-item, .hl__b-box, .article-item, .news-item", "title": "h2.hl__b-title a, .hl__b-title a, h2 a", "link": "h2.hl__b-title a, .hl__b-title a, h2 a", "date": "time, [class*='date'], .article-date", "summary": ".hl__b-desc, .description, p", "image": ".hl__b-img img, .hl__b-image img, img", "fallback_title_links": True},
        "detail": {"content": ".detail__body, .content-detail, .txt-article, article", "content_fallback": ".detail__body p, .content-detail p, .txt-article p, article p, main p", "date": "time, [class*='date']", "image": ".detail__body img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy, .menu"},
    },
    "Potret Kuningan": {
        "url": "https://potretkuningan.com/category/headline/",
        "selectors": {"item": ".media.media-item", "title": ".media-title, .media-link, h2 a", "link": ".media-link, .media-title, h2 a", "date": ".media-date, time, .date", "summary": ".media-text p, .media-text, .entry-summary", "image": ".media-image img, .media-box img, .media-item img"},
        "detail": {"content": ".entry-content, .post-content, .article-content, .td-post-content, article", "content_fallback": ".entry-content p, .post-content p, .td-post-content p, article p, main p", "date": "time, .entry-date, .date", "image": ".entry-content img, .post-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .sharedaddy"},
    },
    "Media Kuningan": {
        "url": "https://mediakuningan.com/",
        "selectors": {"item": "article.item-content", "title": "h2.entry-title a", "link": "h2.entry-title a", "date": "time.entry-date, time[datetime], time", "summary": ".entry-content-archive p, .entry-summary p, .entry-excerpt p, p", "image": ".content-thumbnail img, .post-thumbnail img, .wp-post-image, img"},
        "detail": {"content": ".entry-content:not(.entry-content-archive), article .entry-content, .post-content, .post-body, article", "content_fallback": ".entry-content:not(.entry-content-archive) p, .post-content p, .post-body p, article p, main p", "date": "time.entry-date, time[datetime], time", "image": ".entry-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .entry-content-archive"},
    },
    "Ciremai Today": {
        "selectors": {"item": ".fl-post-grid-post, .fl-post, article, .post", "title": "h2.fl-post-title a, .fl-post-title a, h1 a, h2 a, h3 a", "link": "h2.fl-post-title a, .fl-post-title a, h1 a, h2 a, h3 a", "date": ".fl-post-meta, time, .date", "summary": ".fl-post-excerpt, .fl-post-text p, .fl-post-content p, p", "image": ".fl-post-image img, .fl-post-content img, img"},
        "detail": {"content": ".fl-post-content, .fl-rich-text, .fl-builder-content .fl-module-rich-text, .entry-content, .post-content, article", "content_fallback": ".fl-post-content p, .fl-rich-text p, .fl-builder-content .fl-module-rich-text p, .entry-content p, .post-content p, article p, main p", "date": "time, .fl-post-meta, .entry-date", "image": ".fl-post-content img, .fl-rich-text img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts, .fl-post-grid, .fl-post-feed"},
    },
    "iNews Kuningan": {
        "selectors": {"item": "article.cardArticle", "title": "h4.cardTitle a, .cardTitle a", "link": "h4.cardTitle a, .cardTitle a", "date": "time, .date, [class*='date']", "summary": ".cardDescription, .cardBody p, p", "image": ".cardImage img, .cardThumb img, img"},
        "detail": {"content": ".detailContent, .contentNews, .read__content, article", "content_fallback": ".detailContent p, .contentNews p, .read__content p, article p, main p", "date": "time, [class*='date']", "image": ".detailContent img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .related, .recommendation"},
    },
    "Kuningan Religi": {
        "url": "https://kuninganreligi.com/",
        "selectors": {"item": ".blog-over-hero-item, article.cv-post", "title": ".blog-over-hero-title a, .cv-post-title a", "link": ".blog-over-hero-title a, .cv-post-title a", "date": ".cv-post-date time, .cv-post-meta time, time[datetime], time", "summary": ".cv-post-content, .blog-over-hero-excerpt, p", "image": ".blog-over-hero-image, .cv-post-thumb img, .wp-post-image, img"},
        "detail": {"content": ".entry-content, .post-content, .article-content, .blog-over-page-content, article", "content_fallback": ".entry-content p, .post-content p, .blog-over-page-content p, article p, main p", "date": "time[datetime], time, .entry-date", "image": ".entry-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts"},
    },
    "Media Identitas": {
        # HTML untuk domain ini tidak tampak pada kiriman; pakai fallback WordPress sampai snapshot asli tersedia.
        "selectors": {"item": "article, .post, .td_module_wrap, .card, .entry", "title": ".entry-title a, h2 a, h3 a", "link": ".entry-title a, h2 a, h3 a", "date": "time, .entry-date, .date", "summary": ".entry-summary, .excerpt, p", "image": ".post-thumbnail img, .entry-content img, img"},
        "detail": {"content": ".entry-content, .post-content, .article-content, article", "content_fallback": ".entry-content p, .post-content p, article p, main p", "date": "time, .entry-date", "image": ".entry-content img, article img", "exclude_selectors": "nav, header, footer, aside, .sidebar, .widget, .related-posts"},
    },
    "Kuningan News": {
        "selectors": {"item": "article.post-outer-container, .post-outer-container", "title": "h3.post-title a, .post-title a", "link": "h3.post-title a, .post-title a", "date": "time.published, time, .date-header", "summary": ".post-body, .post-snippet, .snippet-item, p", "image": ".post-body img, .post-thumbnail img, img"},
        "detail": {"content": ".post-body.entry-content, .post-content, .post-body", "content_fallback": ".post-body p, .post-body h2, article p", "author": ".post-author, .author", "date": "time.published, time, .post-date", "category": ".post-labels a, .category a", "image": ".post-body img, .post-content img", "exclude_selectors": "nav, header, footer, aside, .widget, .PopularPosts, .post-snippet, .list-label-widget-content, .blog-pager, .sidebar-invisible"},
    },
    "Detik (Tag Kuningan)": {
        "selectors": {"item": "article.list-content__item, article, .list-content__item", "title": "h3.media__title a, .media__title a, h3 a", "link": "h3.media__title a, .media__title a, h3 a", "date": ".media__date, .date, time", "summary": ".media__desc, .media__text p, p", "image": ".media__image img, img", "url_regex": r"/jabar/.*?/d-"},
        "detail": {"content": ".detail__body-text, .itp_bodycontent, [class*='body-text'], article.detail", "content_fallback": "article.detail p, .detail__body-text p, article p", "author": ".author, .detail__author", "date": ".detail__date, time, .date", "category": ".detail__category, .breadcrumb a", "image": ".detail__media img, article.detail img", "exclude_selectors": "nav, header, footer, aside, .list-content, .list-content__item, .box, .cb-artikel-lainnya"},
    },
}

for _source in SOURCES:
    _profile = HTML_SNAPSHOT_PROFILES.get(_source.get("name"), {})
    if _profile.get("url"):
        _source["url"] = _profile["url"]
    if _profile.get("selectors"):
        _source["selectors"] = _profile["selectors"]
    if _profile.get("detail"):
        _source["detail"] = _profile["detail"]


# =====================================================
# BOBOT KEPERCAYAAN PER SUMBER
# =====================================================
SOURCE_TRUST = {
    "DPRD Kuningan (Resmi)": 1.0,
    "Bappeda Kuningan": 0.95,
    "Pemkab Kuningan — Kategori Daerah": 0.95,
    "Pemkab Kuningan — Publikasi Berita": 0.95,
    "Pemkab Kuningan — Publikasi Pengumuman": 0.95,
    "PPID Kuningan": 0.85,
    "Kuningan Mass": 0.9,
    "Kuningan Jabar Info": 0.85,
    "Inilah Kuningan": 0.9,
    "Antara News Jabar": 0.95,
    "RRI Kuningan": 0.9,
    "Radar Kuningan": 0.95,
    "Kabar Kuningan (PR)": 0.95,
    "Potret Kuningan": 0.9,
    "Media Kuningan": 0.85,
    "Ciremai Today": 0.85,
    "iNews Kuningan": 0.85,
    "Kuningan Religi": 0.8,
    "Media Identitas": 0.8,
    "Kuningan News": 0.9,
    "Detik (Tag Kuningan)": 0.6,
}


# =====================================================
# FILTER DPRD — kata kunci
# =====================================================
DPRD_KEYWORDS_STRONG = {
    "dprd": 10, "dewan perwakilan rakyat daerah": 10, "anggota dewan": 8,
    "rapat paripurna": 9, "paripurna": 7, "pansus": 9, "legislasi": 6,
    "ketua dprd": 9, "wakil ketua dprd": 9, "sekretariat dprd": 7,
    "badan anggaran": 8, "banggar": 7, "fraksi": 5,
    "komisi i": 5, "komisi ii": 5, "komisi iii": 5, "komisi iv": 5,
    "rapat dengar pendapat": 8, "rdp": 6,
    "aspirasi masyarakat": 6, "fungsi pengawasan": 5,
}

DPRD_KEYWORDS_WEAK = {
    "kuningan": 2,
    "apbd": 3, "raperda": 4, "perda": 3,
    "aspirasi": 2, "pengawasan": 2, "anggaran": 2, "politik": 1,
    "pemerintah daerah": 2, "pemkab": 1, "bupati": 1,
    "pemkab kuningan": 2, "pemkot kuningan": 2,
    "dinilai": 1, "didesak": 2, "disorot": 2,
}

KUNINGAN_KEYWORDS = {
    "kuningan": 5,
    "kabupaten kuningan": 6,
    "pemkab kuningan": 5,
    "pemkot kuningan": 5,
    "ciremai": 3,
    "linggarjati": 3,
    "jalaksana": 2, "cigugur": 2, "cibingbin": 2, "luragung": 2,
    "kadugede": 2, "cibuntu": 2, "palutungan": 2,
    "waduk darma": 2,
    "pam tirta kamuning": 3,
}

NON_KUNINGAN_PENALTY = 15

OTHER_REGIONS = {
    "mempawah", "banten", "jakarta", "dki jakarta", "bandung",
    "surabaya", "semarang", "medan", "makassar", "papua",
    "cirebon", "indramayu", "majalengka", "tasikmalaya",
    "ciamis", "banjar", "pangandaran", "brebes", "tegal",
    "jember", "gresik", "sidoarjo", "magelang", "bogor",
    "kalteng", "kalimantan", "sumatera", "sulawesi", "bali",
    "riau", "jambi", "lampung", "aceh", "ntb", "ntt",
    "malaysia", "arab saudi", "israel", "iran", "amerika",
}

# ✅ DITURUNKAN dari 12 → 8 supaya tidak terlalu ketat
DPRD_MIN_SCORE = 8

# ✅ Gate title untuk media — wajib ada salah satu kata ini di TITLE
DPRD_TITLE_GATE = [
    "dprd", "dewan", "komisi", "fraksi", "banggar",
    "pansus", "legislatif", "anggota dewan",
]


# =====================================================
# TAG is_legislative_work (untuk sumber resmi)
# =====================================================
LEGISLATIVE_WORK_KEYWORDS = [
    "paripurna", "rapat", "pansus", "komisi", "fraksi",
    "pengawasan", "legislasi", "anggaran",
]


# =====================================================
# SENTIMEN
# =====================================================
SENTIMENT_KEYWORDS = {
    "positif": {
        "apresiasi": 3, "mengapresiasi": 3, "dukung": 3, "mendukung": 3,
        "memuji": 3, "berhasil": 2, "sukses": 2, "baik": 1, "peduli": 2,
        "bantuan": 2, "sinergi": 2, "kolaborasi": 2, "transparan": 3,
        "akuntabel": 3, "responsif": 2, "proaktif": 2, "solusi": 2,
        "harapan": 1, "optimis": 2, "maju": 1, "melesat": 2,
        "penghargaan": 3, "prestasi": 3, "dedikasi": 2,
        "berkomitmen": 2, "komitmen": 2, "berprestasi": 3,
        "juara": 3, "terbaik": 2, "lolos": 2, "terpilih": 2,
        "diresmikan": 2, "dibuka": 2, "meningkat": 2, "tumbuh": 2,
        "naik": 1, "berdaya": 2, "mandiri": 2, "sejahtera": 3,
        "aman": 2, "kondusif": 2, "tertib": 1,
    },
    "negatif": {
        "kritik": 3, "mengkritik": 3, "menyoroti": 2, "soroti": 2,
        "demo": 4, "demonstrasi": 4, "protes": 4, "desak": 3,
        "mendesak": 3, "tuntut": 3, "menuntut": 3,
        "gagal": 3, "kegagalan": 3, "buruk": 3, "korupsi": 5,
        "polemik": 3, "kontroversi": 4, "mengecam": 4, "kecaman": 4,
        "kecewa": 3, "keluhan": 3, "krisis": 3, "kacau": 3,
        "gaduh": 2, "ribut": 2, "masalah": 2,
        "tewas": 4, "meninggal": 3, "korban": 2, "luka": 2,
        "kecelakaan": 3, "tenggelam": 3, "kebakaran": 2,
        "banjir": 2, "longsor": 3, "keracunan": 4, "karhutla": 3,
        "phk": 4, "pengangguran": 3, "kemiskinan": 3,
        "stunting": 2, "gizi buruk": 4, "busung lapar": 5,
        "tunda bayar": 4, "gagal bayar": 4, "utang": 2,
        "penonaktifan": 2, "dicabut": 2, "ditutup": 2,
        "tuntutan": 2, "unjuk rasa": 3, "tersangka": 3,
        "ditahan": 3, "pembunuhan": 5, "pelecehan": 5,
        "perundungan": 5, "penganiayaan": 5, "narkoba": 4,
        "sabu": 4, "miras": 2, "sengketa": 2, "konflik": 3,
        "gugatan": 3, "tergugat": 2, "anjlok": 3, "turun": 1,
    },
}


# =====================================================
# BATAS & HTTP
# =====================================================
MAX_ARTICLES_OFFICIAL = None
MAX_ARTICLES_MEDIA = 500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

HEADERS_EXTENDED = {
    **HEADERS,
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

REQUEST_TIMEOUT = 30
FETCH_DETAIL_ENABLED = True

BULAN_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
