# Snapshot HTML lokal (tanpa Chromium)

Folder ini menyediakan salinan HTML halaman daftar artikel yang pernah diberikan/diperiksa sebelumnya.
Jika HTTP langsung ditahan challenge/WAF, DDPS boleh menggunakan file ini sebagai **snapshot lokal**.

PENTING: snapshot bukan data live dan mungkin sudah usang. Dashboard/log akan menandainya sebagai `partial` dan menulis `fetch_mode=local_snapshot`. Jangan gunakan hitungan/tanggal snapshot sebagai kondisi terbaru tanpa memperbarui filenya.

Untuk memperbarui snapshot tanpa Chromium automation:
1. Buka situs dengan Safari atau browser biasa yang kamu gunakan.
2. Pastikan halaman daftar berita normal terlihat.
3. Simpan/salin source HTML halaman daftar berita ke file yang sesuai di folder ini, dengan nama yang sama.
4. Jangan simpan halaman `Mohon tunggu sebentar…`/challenge sebagai snapshot berita.
5. Jalankan `python3 main.py` lagi.

Peta file: `bappeda.html`, `pemkab_daerah.html`, `pemkab_publikasi_berita.html`, `pemkab_publikasi_pengumuman.html`, `inilah_kuningan.html`, `potret_kuningan.html`, `media_kuningan.html`, `kuningan_religi.html`.

Kalau situs menolak request HTTP dan pengguna tidak dapat mengambil source normal, cara yang benar untuk data live adalah meminta pengelola menyediakan/whitelist endpoint RSS/API atau memakai sumber publik resmi yang mengizinkan pengambilan data. Jangan nonaktifkan verifikasi TLS.
