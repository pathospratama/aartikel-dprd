# DDPS DPRD Kuningan — v5.0 (HTTP-only)

## Prinsip versi ini

- Tidak menggunakan Chromium, Playwright, atau browser automation.
- Pengambilan live memakai `requests` HTTP biasa.
- Tidak menggunakan `curl_cffi` atau `cloudscraper` untuk memutar fingerprint atau melewati challenge.
- Verifikasi TLS selalu aktif; tidak ada `verify=False`.
- RSS/Atom/WordPress REST API dicoba jika endpoint yang dikonfigurasi mengizinkan akses publik.
- Bila server mengembalikan halaman perantara (`Mohon tunggu sebentar…`), HTTP fetch berhenti dan mencatat penyebabnya. Mengganti selector tidak bisa mengubah halaman challenge menjadi berita.
- Untuk delapan sumber yang memiliki HTML yang pernah diperiksa, proyek dapat memakai snapshot lokal di `manual_html/`. Hasil diberi status `partial`, `fetch_mode=local_snapshot`, `mode_pengambilan=snapshot_lokal`, dan `snapshot_file`. **Ini bukan data live**.

## Solusi selain Chromium

1. Gunakan RSS/API publik yang benar-benar dapat diakses oleh HTTP biasa.
2. Minta pengelola website menyediakan endpoint RSS/API atau mengizinkan IP scraper melalui allowlist.
3. Simpan source HTML halaman daftar berita yang normal melalui Safari/browser biasa dan letakkan di folder `manual_html/` sebagai snapshot lokal.
4. Untuk data live yang konsisten, solusi paling kuat adalah endpoint resmi yang tidak mengirim halaman challenge untuk permintaan server-ke-server.

Jangan mematikan validasi TLS atau mencoba mengakali WAF. Jika server tidak mengirim data artikel, scraper tidak dapat membuat data live dari respons tersebut.

## Jalankan

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 diagnose_sources.py --all-endpoints
python3 main.py
```

Tidak ada `main_browser.py`, `requirements-browser.txt`, atau `extract_cookies.py` pada versi ini.

## Perbarui snapshot lokal

1. Buka halaman situs dengan Safari atau browser biasa yang kamu gunakan.
2. Pastikan yang tampil adalah daftar berita normal, bukan halaman perantara.
3. Simpan source HTML dan ganti file yang sesuai pada `manual_html/`. Petunjuk dan nama file ada di `manual_html/README.md`.
4. Jalankan `python3 main.py`.
5. Periksa `mode_pengambilan` pada JSON. `snapshot_lokal` berarti hasil berasal dari file HTML lokal, bukan fetch live.

## Output

- `hasil_dprd_kuningan_*.json`: data artikel dan statistik.
- `dashboard_dprd_kuningan_*.html`: dashboard.
- `diagnostik_sumber_*.json`: status HTTP, judul halaman, jumlah tautan, dan penyebab kegagalan endpoint.
- `scraper.log`: log fetch, parser, isi detail, dan snapshot fallback.

## Batasan

- Snapshot hanya berisi halaman daftar yang disimpan. Tanpa HTML detail atau API, isi ditandai `ringkasan_saja`, bukan konten penuh.
- Snapshot dapat usang dan perlu diperbarui.
- Bila TLS gagal, periksa CA bundle lokal atau minta pengelola memperbaiki rantai sertifikat. `verify=False` tidak digunakan.
- Versi ini tidak mengklaim semua 21 website dapat diakses live; status live harus dibuktikan oleh diagnostik terbaru.
