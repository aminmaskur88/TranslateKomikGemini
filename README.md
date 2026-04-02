# TranslateKomik Editor

TranslateKomik Editor adalah aplikasi web lokal (Local Web App) yang dirancang khusus untuk memudahkan proses penerjemahan (*typesetting* dan *cleaning*) halaman komik/manga/manhwa secara langsung melalui browser, baik di HP (via Termux) maupun di PC.

Aplikasi ini menggabungkan antarmuka editor visual yang interaktif (seperti memindahkan dan mengubah ukuran kotak teks langsung di atas gambar) dengan mesin pemrosesan gambar *backend* menggunakan Python (Pillow) untuk menghasilkan gambar *output* beresolusi tinggi (HD).

## Fitur Utama

*   **Antarmuka Visual Editor (Drag & Drop):** Tambahkan teks, geser (*drag*), dan ubah ukuran kotak teks (*resize*) langsung di atas *preview* gambar komik.
*   **Auto-Scale Font:** Ukuran font akan menyesuaikan secara otomatis secara proporsional ketika Anda mengubah ukuran kotak teks.
*   **Smart Auto-Clean Balloon:** Saat Anda menempatkan kotak teks di atas balon percakapan, latar belakang kotak akan otomatis mendeteksi dan menggunakan warna dominan dari balon tersebut, sehingga teks asli di belakangnya tertutupi secara rapi tanpa perlu menghapusnya secara manual.
*   **Zoom Canvas:** Fitur *Zoom In* dan *Zoom Out* untuk melihat detail komik saat melakukan *typesetting*.
*   **Terjemahan Otomatis Berbasis AI (Gemini OCR):** Terintegrasi dengan Google Gemini Vision API untuk memindai teks asli (Jepang, Korea, dll.) pada gambar dan langsung menerjemahkannya ke bahasa tujuan (Indonesia/Inggris). Hasil terjemahan otomatis muncul sebagai kotak teks di layar.
*   **Export Resolusi Tinggi (HD):** Berbeda dengan aplikasi web biasa, saat Anda menekan tombol Export, sistem tidak hanya mengambil *screenshot* layar browser. Sebaliknya, koordinat teks Anda dikirim ke server Python lokal, yang kemudian akan "mencetak" teks tersebut ke file gambar asli menggunakan font berkualitas tinggi (`ComicNeue-Bold.ttf`), tanpa menurunkan resolusi gambar sedikit pun.
*   **Manajemen File Lokal (@bahan):** Mendukung pengunggahan file atau memilih gambar langsung dari folder `bahan/` di dalam direktori proyek.

## Struktur Direktori

*   `index.html`: *Frontend* aplikasi (Antarmuka pengguna, CSS, dan logika interaksi JavaScript).
*   `server.py`: *Backend* aplikasi (Server HTTP lokal Python untuk memproses *upload*, integrasi AI OCR, dan *rendering* gambar HD saat *export*).
*   `bahan/`: Folder untuk menyimpan gambar komik asli (mentahan) yang akan diedit.
*   `hasil/`: Folder tempat hasil gambar komik yang sudah diterjemahkan dan di-*export* disimpan.
*   `Font/`: Folder untuk menyimpan *font custom* (contoh: `ComicNeue-Bold.ttf`).
*   `gemini/`: Folder untuk menyimpan kunci API (`gemini_key.txt`).
*   `requirements.txt`: Daftar *library* Python yang dibutuhkan.

## Persyaratan (Requirements)

Pastikan Anda telah menginstal Python di sistem Anda (PC atau Termux di Android). Aplikasi ini membutuhkan dua pustaka Python eksternal:

*   `requests` (Untuk memanggil API Gemini)
*   `Pillow` (Untuk pemrosesan gambar resolusi tinggi)

## Cara Instalasi & Penggunaan

1.  **Klon/Unduh Repositori Ini**
2.  **Instal Dependensi:**
    Buka terminal (atau Termux), arahkan ke folder proyek ini, lalu jalankan perintah:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Siapkan API Key (Opsional, untuk fitur AI OCR):**
    *   Buat folder bernama `gemini` di dalam direktori proyek.
    *   Di dalam folder tersebut, buat file bernama `gemini_key.txt`.
    *   Masukkan API Key Google Gemini Anda ke dalam file tersebut (satu baris saja).
4.  **Jalankan Server:**
    Di terminal, jalankan perintah:
    ```bash
    python server.py
    ```
5.  **Buka Editor:**
    Buka browser web Anda (Chrome, Firefox, Safari, dll.) dan kunjungi alamat:
    `http://localhost:8080`

## Panduan Singkat Penggunaan

1.  **Mulai:** Di panel kiri, klik **Upload** untuk memilih gambar dari perangkat Anda, atau klik **Buka** untuk memilih gambar yang sudah ada di folder `bahan/`.
2.  **Translate Otomatis (Jika API Key diset):** Pilih bahasa asal dan tujuan di panel kiri, lalu klik **Terjemahkan**. Tunggu beberapa saat, kotak-kotak teks terjemahan akan muncul di pojok kiri atas.
3.  **Tambah Teks Manual:** Klik tombol **Tambah Teks** di panel kiri bawah.
4.  **Edit & Posisikan:** 
    *   Klik dua kali pada teks untuk mengubah isinya.
    *   Klik, tahan, dan seret kotak untuk memindahkannya.
    *   Tarik ujung kanan bawah kotak untuk mengubah ukurannya (teks akan menyesuaikan otomatis).
5.  **Simpan:** Jika sudah selesai, klik tombol **Export** berwana biru di pojok kanan atas. Hasil gambar HD akan tersimpan di dalam folder `hasil/`.
