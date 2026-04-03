# 🎨 TranslateKomik Editor HD

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Termux](https://img.shields.io/badge/Termux-000000?style=for-the-badge&logo=termux&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)

Sebuah aplikasi web lokal (Local Web App) canggih yang dirancang khusus untuk memudahkan para penerjemah (*scanlator*) melakukan proses penerjemahan (*typesetting* dan *cleaning*) halaman komik, manga, manhwa, atau manhua secara langsung melalui browser. Aplikasi ini dapat dijalankan dengan mulus baik di HP (menggunakan Termux) maupun di PC/Laptop.

Aplikasi ini menggabungkan antarmuka editor visual interaktif dengan mesin pemrosesan gambar *backend* menggunakan Python (Pillow) untuk merender hasil teks ke gambar dengan kualitas resolusi asli (HD) tanpa kompresi *screenshot*.

---

## ✨ Fitur Utama

- 🖱️ **Antarmuka Visual Editor (Drag & Drop)**: Tambahkan, geser (*drag*), dan ubah ukuran kotak teks (*resize*) secara interaktif di atas *preview* gambar komik menggunakan mouse atau sentuhan (touchscreen).
- 🔠 **Auto-Scale Font**: Ukuran teks akan menyesuaikan secara otomatis secara proporsional saat Anda mengubah dimensi (melebarkan atau meninggikan) kotak teks.
- 🎨 **Smart Auto-Clean Balloon (Warna Background Dinamis)**: Sistem dapat secara otomatis mengambil *sample* warna dari *background* komik/balon percakapan asli di belakang kotak teks, sehingga teks asli yang berbahasa asing tertutupi dengan sempurna tanpa perlu melakukan *redrawing* manual.
- 🔍 **Zoom Canvas Terintegrasi**: Gunakan *slider* Zoom In/Out untuk melihat detail komik saat mengatur posisi teks (*typesetting*) presisi tinggi.
- 🤖 **Terjemahan Otomatis Berbasis AI (Gemini OCR & Vision)**: Terintegrasi dengan Google Gemini (versi 2.5 Flash) untuk mendeteksi (*OCR*) dan menerjemahkan teks asli (Jepang, Korea, dll.) secara langsung.
- 📁 **Auto-Title & Folder Manajemen**: AI juga dapat menebak/menyarankan "Judul Komik" secara otomatis. Hasil ekspor komik akan dikelompokkan secara rapi berdasarkan nama bahasa (misal di folder `hasil/Indonesia/`).
- 🔄 **Fitur Ganti Bahasa Teks Cepat**: Ingin menerjemahkan satu halaman komik ke banyak bahasa sekaligus? Fitur "Ganti Bahasa (Teks)" memungkinkan Anda menerjemahkan semua teks yang sudah ditata di kanvas ke bahasa lain (contoh: Indonesia ke Inggris atau Jawa) hanya dengan sekali klik tanpa mengubah posisi kotak teks.
- 🖼️ **Export Resolusi Tinggi (HD)**: Proses penyimpanan (Export) tidak sekadar melakukan *screenshot* browser. Koordinat dan pengaturan gaya teks dikirim ke server lokal Python untuk "dicetak" ulang ke atas gambar asli dengan resolusi tinggi.

---

## 🛠️ Persyaratan Sistem (Requirements)

Aplikasi ini sangat ringan dan hanya membutuhkan instalasi Python 3. Pastikan Anda telah menginstal Python di perangkat Anda (PC/Windows/Mac/Linux atau via Termux di Android).

Dependensi eksternal yang digunakan:
- `requests` (Untuk mengambil/mengirim data ke API Gemini)
- `Pillow` / `PIL` (Untuk pemrosesan gambar beresolusi tinggi di server)

---

## 📂 Struktur Proyek & Panduan File

| File / Folder | Deskripsi |
| --- | --- |
| `index.html` | 🌐 **Frontend**: Antarmuka utama (UI/UX, logika JavaScript, dan desain gaya CSS). |
| `server.py` | ⚙️ **Backend**: Server HTTP Python untuk menangani upload, komunikasi Gemini, dan *rendering* gambar HD. |
| `requirements.txt`| 📦 **Dependencies**: Daftar pustaka/modul Python yang dibutuhkan untuk menjalankan aplikasi. |
| `bahan/` | 🖼️ **Input Storage**: Folder *default* untuk meletakkan gambar-gambar komik mentahan yang akan diedit. |
| `hasil/` | 💾 **Output Storage**: Folder tempat semua gambar yang sudah diedit & diekspor (dikelompokkan berdasarkan bahasa). |
| `Font/` | 🔤 **Custom Fonts**: Folder untuk menyimpan *font custom* (`ComicNeue-Bold.ttf` disediakan secara default). |
| `gemini/` | 🔑 **API Keys**: Folder wajib untuk menyimpan file `gemini_key.txt` yang berisi deretan API Key Google Gemini Anda. |

---

## 🚀 Panduan Instalasi & Persiapan

### 1. Klon/Unduh Repositori Ini
Pastikan Anda sudah berada di dalam folder proyek `TranslateKomikGemini`.

```bash
git clone https://github.com/aminmaskur88/TranslateKomikGemini.git
cd TranslateKomikGemini
```

### 2. Instal Modul Python yang Dibutuhkan
Buka terminal atau Termux Anda, dan jalankan perintah berikut:
```bash
pip install -r requirements.txt
```

### 3. Siapkan Google Gemini API Key
- Buat sebuah folder bernama `gemini` di dalam direktori root proyek ini (jika belum ada).
- Di dalam folder `gemini/`, buat sebuah file teks bernama `gemini_key.txt`.
- Buka Google AI Studio, dapatkan API Key Anda, lalu masukkan (*paste*) teks API Key tersebut ke dalam file `gemini_key.txt`.
- Anda dapat memasukkan lebih dari satu baris API Key jika Anda ingin menggunakan fitur rotasi key (untuk menghindari *limit quota*).

### 4. Siapkan Font Tambahan (Opsional)
Jika Anda ingin menggunakan font lain selain bawaan, Anda bisa mengganti file `ComicNeue-Bold.ttf` di dalam folder `Font/` dengan font TTF lain, lalu pastikan Anda menyesuaikan jalurnya di bagian atas file `server.py` (`FONT_PATH = 'Font/ComicNeue-Bold.ttf'`).

---

## 💻 Cara Menjalankan Aplikasi

Aplikasi dijalankan melalui baris perintah (Terminal/Command Prompt/Termux).

### 🟢 Cara Biasa (Default Mode)
Secara bawaan, aplikasi akan membaca file gambar dari folder `bahan/`.
```bash
python server.py
```

### 🟡 Cara Kustom (Custom Directory Mode)
Jika Anda memiliki gambar di folder lain (misalnya folder hasil ekstraksi manga di lokasi spesifik), Anda bisa langsung membuka folder tersebut di aplikasi dengan menambahkan jalur *path* sebagai argumen.
```bash
# Contoh membuka folder Chapter_01
python server.py /path/ke/folder/komik/Chapter_01
```
*Note: Ketika menggunakan mode ini, UI web akan langsung menampilkan gambar-gambar dari folder tersebut, dan file `history.json` (riwayat status terjemahan) juga akan disimpan di folder tersebut agar rapi.*

---

## 📖 Panduan Penggunaan Web UI

Setelah server berjalan (biasanya di `http://localhost:8080` atau `http://0.0.0.0:8080`), buka alamat tersebut menggunakan browser modern seperti Chrome, Firefox, Edge, atau Safari.

### 1️⃣ Memilih Gambar
- **Dari Server/Folder**: Di panel sebelah kiri, terdapat *dropdown* daftar file yang ada di folder kerja Anda (bisa `bahan/` atau folder yang Anda tentukan). Pilih file dari *dropdown* lalu klik tombol **Buka**.
- **Upload Manual**: Anda juga dapat mengklik tombol **Upload File Lokal** untuk mengunggah gambar satuan langsung dari galeri/penyimpanan perangkat Anda ke server.

### 2️⃣ Fitur Auto-Translate (Gemini AI)
- Di sebelah kiri, pilih **Bahasa Asal** teks komik (atau biarkan di **Auto**).
- Pilih **Bahasa Tujuan** (misal: Indonesia, English, Jawa, Sunda, Tagalog).
- Klik tombol biru **Terjemahkan (Gambar)**.
- Tunggu beberapa detik. AI akan menganalisis gambar, mengekstrak teks asli, menerjemahkannya, memisahkan per-balon, dan bahkan **mengisi otomatis judul komik**.
- Setelah selesai, beberapa kotak teks akan langsung muncul bersusun di kanvas gambar Anda.

### 3️⃣ Melakukan Typesetting (Editing Teks)
- **Edit Isi**: Klik **2 kali (Double Click)** pada kotak teks untuk mengubah isinya.
- **Pindahkan Posisi**: Klik (jangan dilepas), tahan, dan geser (*drag*) kotak teks ke atas balon percakapan yang sesuai.
- **Ubah Ukuran**: Di setiap pojok kanan bawah kotak teks, terdapat indikator segitiga kecil (*resizer*). Tarik/geser bagian tersebut untuk melebarkan atau meninggikan kotak. Ukuran font di dalamnya akan otomatis menyesuaikan agar muat (*auto-scale*).
- **Hapus Teks**: Jika ada kotak teks berlebih, klik satu kali pada kotak teks tersebut, lalu klik ikon tempat sampah (🗑️) berwarna merah di panel kiri bawah (atau tekan tombol `Delete` di keyboard PC).
- **Warna Teks & Background**:
  - Gunakan pemilih warna (*color picker*) di panel kiri untuk mengubah warna teks (`#000000` default) atau warna *background* kotak teks (`#ffffff` default).
  - Anda bisa menggunakan pipet warna (*eyedropper*) sistem jika didukung oleh browser Anda untuk mengambil warna dari bagian gambar tertentu.
  - Untuk *background* transparan, kosongkan atau set *opacity* warna ke 0.

### 4️⃣ Fitur Ganti Bahasa (Teks)
Jika Anda sudah menyusun posisi kotak-kotak teks di satu bahasa (misalnya Bahasa Indonesia), dan ingin mengekspor halaman yang sama dalam bahasa lain (misalnya Bahasa Inggris):
- Ubah pengaturan **Bahasa Tujuan** di menu kiri ke (misal) `English`.
- Klik tombol **Ganti Bahasa (Teks)**.
- AI akan membaca semua teks yang saat ini tampil di kanvas, lalu menggantinya dengan bahasa baru *tanpa mengubah* tata letak dan ukuran kotaknya.

### 5️⃣ Export Gambar (Simpan Hasil)
- Setelah semua teks sudah rapi, klik tombol biru **Export HD** di panel paling kanan atas.
- Server Python akan merender ulang gambar asli dengan menyisipkan kotak dan teks *custom* Anda dengan akurasi dan kualitas tinggi.
- Gambar akhir yang sudah jadi akan disimpan secara otomatis di dalam folder `hasil/[Nama_Bahasa]/` di direktori proyek lokal Anda.
- Muncul indikator (riwayat ekspor) di bawah tombol "Terjemahkan" yang memberi tahu Anda ke bahasa apa saja gambar ini sudah diekspor (contoh: "Telah di-export ke: Indonesia, English").

---

## 🤖 Special Thanks
Dikembangkan dan disempurnakan dengan bantuan kecerdasan buatan:

**Gemini AI (Google)** - Menangani logika OCR, otomasi *Typesetting*, perancangan UI interaktif, dan dokumentasi profesional ini.

License: MIT | Author: Amin Maskur