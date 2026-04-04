import http.server
import socketserver
import os
import json
import urllib.parse
import base64
import requests
import mimetypes
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PORT = 8080
UPLOAD_DIR = 'bahan'
OUTPUT_DIR = 'hasil'
FONT_PATH = 'Font/ComicNeue-Bold.ttf'
KEY_FILE = 'gemini/gemini_key.txt'

# Ambil READ_DIR dari argumen command line jika ada, jika tidak gunakan 'bahan'
if len(sys.argv) > 1:
    READ_DIR = sys.argv[1]
else:
    READ_DIR = 'bahan'

# Pastikan folder ada
os.makedirs(UPLOAD_DIR, exist_ok=True)
if READ_DIR != UPLOAD_DIR:
    os.makedirs(READ_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Lokasi history sekarang mengikuti READ_DIR (folder yang sedang dibuka)
HISTORY_FILE = os.path.join(READ_DIR, 'history.json')

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history_data):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Gagal menyimpan history: {e}")

class ApiKeyManager:
    def __init__(self, key_file):
        self.key_file = key_file
        self.keys = self._read_keys()
        
    def _read_keys(self):
        try:
            with open(self.key_file, "r") as f: 
                return [l.strip() for l in f if l.strip()]
        except: return []
        
    def get_current_key(self):
        return self.keys[0] if self.keys else None
        
    def rotate_key(self):
        if self.keys: self.keys.append(self.keys.pop(0))

key_manager = ApiKeyManager(KEY_FILE)

def call_gemini_api(payload):
    models = ["gemini-2.5-flash"]

    for _ in range(len(key_manager.keys) or 1):
        api_key = key_manager.get_current_key()
        if not api_key:
            return {"error": "API Key tidak ditemukan di gemini_key.txt"}

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                print(f"DEBUG: Mengirim ke {model}...")
                res = requests.post(url, json=payload, timeout=60)

                if res.status_code == 200:
                    data = res.json()
                    candidate = data.get("candidates", [{}])[0]
                    content = candidate.get("content", {}).get("parts", [])

                    if not content:
                        return {"error": "Respon kosong dari Gemini"}

                    text = content[0].get("text", "")
                    clean = text.replace("```json", "").replace("```", "").strip()

                    try:
                        return json.loads(clean)
                    except:
                        return {"translations": [clean]}

                if res.status_code == 429:
                    print(f"⚠️ Quota habis: {model}, mencoba fallback...")
                    continue

                print(f"❌ Gemini error {res.status_code}: {res.text}")

            except Exception as e:
                print(f"❌ Request gagal {model}: {e}")

        key_manager.rotate_key()

    return {"error": "Semua model Gemini gagal dihubungi."}

def call_gemini_vision(image_path, target_lang="Indonesian", source_lang="Auto"):
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type: mime_type = "image/jpeg"
    
    try:
        with open(image_path, "rb") as f: 
            img_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return {"error": f"Gagal membaca gambar: {e}"}
        
    source_instruction = f"The source text is in {source_lang}." if source_lang != "Auto" else "Auto-detect the source language of the text."
    prompt = f"Extract all text from this comic page. {source_instruction} Translate it to {target_lang}. IMPORTANT: Maintain the original tone and context. Adapt the language, idioms, and expressions so they sound completely natural and localized for native speakers of {target_lang}. Based on the context and translated text, suggest a short, catchy, and highly relevant title for this comic page in {target_lang}. Return JSON: {{'translations': ['text1', 'text2'], 'detected_language': 'language name', 'title': 'Suggested Title'}}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt}, 
                {"inline_data": {"mime_type": mime_type, "data": img_b64}}
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    return call_gemini_api(payload)

def call_gemini_text(texts, target_lang):
    prompt = f"Translate the following list of comic text bubbles to {target_lang}. Keep the exact same order, meaning, and tone. Return ONLY JSON format: {{'translations': ['translated text 1', 'translated text 2', ...]}}\n\nTexts:\n{json.dumps(texts, ensure_ascii=False)}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    return call_gemini_api(payload)

def wrap_text_pil(text, font, max_width, draw):
    """Fungsi untuk memecah teks menjadi beberapa baris sesuai lebar kotak"""
    lines = []
    # Pecah berdasarkan newline manual dulu
    paragraphs = text.split('\n')
    for p in paragraphs:
        words = p.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
    return lines

class KomikServerHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/upload':
            try:
                # Dapatkan nama file dari header custom
                file_name = self.headers.get('X-File-Name', 'uploaded_image.png')
                file_name = urllib.parse.unquote(file_name)
                # Dapatkan ukuran file
                file_length = int(self.headers.get('Content-Length', 0))
                
                if file_length > 0:
                    # Baca data file
                    file_data = self.rfile.read(file_length)
                    
                    # Simpan ke folder bahan
                    filepath = os.path.join(UPLOAD_DIR, os.path.basename(file_name))
                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    
                    # Kirim respons sukses
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'status': 'success', 'message': f'File berhasil diupload ke folder bahan.', 'url': f'/{filepath}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
            except Exception as e:
                print(f"Error handling upload: {e}")
                
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Gagal mengupload file"}')
            return

        elif self.path == '/process_ocr':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                filename = data.get('filename')
                target_lang = data.get('target_lang', 'Indonesian')
                source_lang = data.get('source_lang', 'Auto')
                
                if not filename:
                    raise ValueError("Filename tidak ditemukan")
                    
                source_path = os.path.join(UPLOAD_DIR, filename)
                if not os.path.exists(source_path):
                    source_path = os.path.join(READ_DIR, filename)
                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"File {filename} tidak ditemukan di bahan maupun {READ_DIR}.")

                # Panggil Gemini API
                result = call_gemini_vision(source_path, target_lang, source_lang)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                return
                
            except Exception as e:
                print(f"Error OCR: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
                return

        elif self.path == '/translate_texts':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                texts = data.get('texts', [])
                target_lang = data.get('target_lang', 'English')
                
                if not texts:
                    raise ValueError("Tidak ada teks yang dikirim")

                result = call_gemini_text(texts, target_lang)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                return
                
            except Exception as e:
                print(f"Error translate texts: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
                return

        elif self.path == '/export':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                # Gunakan relative path asli
                rel_filename = data['fileName']
                source_path = os.path.join(UPLOAD_DIR, rel_filename)
                if not os.path.exists(source_path):
                    source_path = os.path.join(READ_DIR, rel_filename)
                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"File {rel_filename} tidak ditemukan di bahan maupun {READ_DIR}.")

                # Buka gambar HD asli
                img = Image.open(source_path).convert('RGB')
                draw = ImageDraw.Draw(img)
                
                for el in data['elements']:
                    # 1. Gambar Background Box (Menutup teks asli)
                    # Parsing warna 'rgb(r, g, b)'
                    bg_color = el['bgColor'].replace('rgb(', '').replace(')', '').split(',')
                    bg_tuple = (int(bg_color[0]), int(bg_color[1]), int(bg_color[2]))
                    
                    x, y, w, h = el['x'], el['y'], el['w'], el['h']
                    draw.rectangle([x, y, x + w, y + h], fill=bg_tuple)
                    
                    # 2. Gambar Teks Custom
                    # Parsing warna teks
                    text_color = el['textColor'].replace('rgb(', '').replace(')', '').split(',')
                    text_tuple = (int(text_color[0]), int(text_color[1]), int(text_color[2]))
                    
                    try:
                        font = ImageFont.truetype(FONT_PATH, int(el['fontSize']))
                    except:
                        font = ImageFont.load_default()
                    
                    x, y, w, h = el['x'], el['y'], el['w'], el['h']
                    
                    # LOGIKA BARU: Paksa teks jadi huruf kapital dan gunakan wrap_text_pil
                    text_upper = el['text'].upper()
                    # Kurangi lebar sedikit (padding internal 10px) agar teks tidak mepet garis
                    lines = wrap_text_pil(text_upper, font, w - 10, draw)
                    
                    # Hitung total tinggi blok teks untuk pemusatan vertikal
                    line_heights = []
                    for line in lines:
                        if not line: # baris kosong
                            line_heights.append(int(el['fontSize']))
                            continue
                        bbox = draw.textbbox((0, 0), line, font=font)
                        line_heights.append(bbox[3] - bbox[1] if bbox[3] > bbox[1] else int(el['fontSize']))
                    
                    line_spacing = 4
                    total_text_height = sum(line_heights) + (max(0, len(lines) - 1)) * line_spacing
                    
                    # Mulai menggambar dari posisi Y agar teks di tengah secara vertikal
                    # Jika teks lebih tinggi dari box, mulai dari atas box (y) agar tidak meleber ke atas
                    if total_text_height > h:
                        current_y = y
                    else:
                        current_y = y + (h - total_text_height) / 2
                    
                    for i, line in enumerate(lines):
                        if not line:
                            current_y += int(el['fontSize']) + line_spacing
                            continue
                            
                        bbox = draw.textbbox((0, 0), line, font=font)
                        line_width = bbox[2] - bbox[0]
                        
                        # Hitung posisi X agar teks di tengah secara horizontal
                        current_x = x + (w - line_width) / 2
                        
                        draw.text((current_x, current_y), line, font=font, fill=text_tuple)
                        current_y += line_heights[i] + line_spacing
                
                # Simpan Hasil HD
                target_lang = data.get('target_lang')
                if not target_lang or target_lang.strip() == "":
                    target_lang = "Hasil_Export"
                
                # Ubah jadi Capitalize (Contoh: jawa -> Jawa)
                target_lang = target_lang.strip().capitalize()
                
                # Pastikan nama folder aman (hanya alfanumerik, spasi, dash, underscore)
                safe_lang = "".join([c for c in target_lang if c.isalnum() or c in (' ', '_', '-')]).strip()
                if not safe_lang: safe_lang = "Hasil_Export"
                
                # Struktur Output menyesuaikan subfolder sumber
                sub_dir = os.path.dirname(rel_filename)
                lang_dir = os.path.join(OUTPUT_DIR, safe_lang, sub_dir)
                os.makedirs(lang_dir, exist_ok=True)

                original_ext = os.path.splitext(rel_filename)[1]
                base_name = os.path.splitext(os.path.basename(rel_filename))[0]
                
                # LOGIKA PINTAR: Tentukan apakah ini One-shot atau Slide/Series
                parent_dir = os.path.dirname(source_path)
                # Cek apakah folder ini adalah folder utama (Root)
                is_root = (os.path.abspath(parent_dir) == os.path.abspath(READ_DIR) or 
                           os.path.abspath(parent_dir) == os.path.abspath(UPLOAD_DIR))
                
                image_in_folder = [f for f in os.listdir(parent_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif'))]
                
                comic_title = data.get('comicTitle', '').strip()
                
                # Gunakan Judul Gemini sebagai nama file jika:
                # 1. Berada langsung di folder utama (Root) -> Anggap koleksi One-shot
                # 2. Atau jika hanya ada 1 gambar di dalam subfolder tersebut
                if comic_title and (is_root or len(image_in_folder) == 1):
                    safe_title = "".join([c for c in comic_title if c.isalnum() or c in (' ', '_', '-')]).strip()
                    safe_title = safe_title.replace(' ', '_')
                    output_filename = f"{safe_title}{original_ext}"
                else:
                    # Jika di dalam subfolder dan ada banyak gambar -> Anggap Slide/Series, jaga urutan
                    output_filename = f"{base_name}{original_ext}"
                    
                output_path = os.path.join(lang_dir, output_filename)
                img.save(output_path, quality=95)
                
                # Simpan Riwayat Export ke File history.json
                history = load_history()
                if rel_filename not in history:
                    history[rel_filename] = []
                if safe_lang not in history[rel_filename]:
                    history[rel_filename].append(safe_lang)
                save_history(history)
                
                # Respon Sukses
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'status': 'success', 
                    'message': 'Gambar HD berhasil diproses!', 
                    'url': f'/{output_path}'
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                print(f"Error Exporting: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
                return

        elif self.path == '/skip_translation':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                rel_filename = data['fileName']
                source_path = os.path.join(UPLOAD_DIR, rel_filename)
                if not os.path.exists(source_path):
                    source_path = os.path.join(READ_DIR, rel_filename)
                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"File {rel_filename} tidak ditemukan di bahan maupun {READ_DIR}.")

                import shutil
                # Ambil daftar bahasa dari folder hasil/
                languages = []
                if os.path.exists(OUTPUT_DIR):
                    languages = [d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))]
                
                if not languages:
                    languages = ["Indonesia"] # Default jika kosong

                history = load_history()
                if rel_filename not in history:
                    history[rel_filename] = []

                sub_dir = os.path.dirname(rel_filename)
                base_name = os.path.basename(rel_filename)

                for lang in languages:
                    lang_dir = os.path.join(OUTPUT_DIR, lang, sub_dir)
                    os.makedirs(lang_dir, exist_ok=True)
                    output_path = os.path.join(lang_dir, base_name)
                    
                    shutil.copy2(source_path, output_path)
                    
                    if lang not in history[rel_filename]:
                        history[rel_filename].append(lang)
                        
                save_history(history)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'status': 'success', 
                    'message': f'Berhasil disalin ke {len(languages)} bahasa.', 
                    'languages': languages
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                print(f"Error Skip Translation: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
                return

    def translate_path(self, path):
        # Tangani request gambar dari /bahan/ agar bisa membaca dari READ_DIR jika tidak ada di UPLOAD_DIR
        if path.startswith('/bahan/'):
            # Ambil rel_path setelah /bahan/
            rel_path = urllib.parse.unquote(path[len('/bahan/'):])
            upload_path = os.path.join(UPLOAD_DIR, rel_path)
            if os.path.exists(upload_path):
                return os.path.abspath(upload_path)
            read_path = os.path.join(READ_DIR, rel_path)
            if os.path.exists(read_path):
                return os.path.abspath(read_path)
            return os.path.abspath(upload_path)
        return super().translate_path(path)

    def do_GET(self):
        # API Endpoint untuk mengambil daftar file di folder bahan/READ_DIR
        if self.path == '/list-bahan':
            files_data = []
            seen = set()
            history = load_history()
            
            def scan_dir(base_path):
                if not os.path.exists(base_path):
                    return
                for root, dirs, files in os.walk(base_path):
                    for f in files:
                        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                            # Dapatkan path relatif dari base_path
                            rel_path = os.path.relpath(os.path.join(root, f), base_path)
                            if rel_path not in seen:
                                files_data.append({
                                    "name": rel_path,
                                    "translated": rel_path in history and len(history[rel_path]) > 0,
                                    "languages": history.get(rel_path, [])
                                })
                                seen.add(rel_path)
            
            # 1. Ambil dari READ_DIR
            scan_dir(READ_DIR)
            
            # 2. Ambil dari UPLOAD_DIR (bahan) jika berbeda dengan READ_DIR
            if READ_DIR != UPLOAD_DIR:
                scan_dir(UPLOAD_DIR)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files_data).encode('utf-8'))
            return

        elif self.path == '/get_history':
            history = load_history()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(history).encode('utf-8'))
            return
            
        # Panggil default handler untuk serve index.html, bahan/..., hasil/...
        return super().do_GET()

# Izinkan reuse address agar tidak error "Address already in use" saat direstart
socketserver.TCPServer.allow_reuse_address = True

if __name__ == '__main__':
    with socketserver.TCPServer(('', PORT), KomikServerHandler) as httpd:
        print("=" * 40)
        print(f" SERVER HD BERJALAN DI http://localhost:{PORT}")
        print("=" * 40)
        print("Tekan Ctrl+C untuk menghentikan server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        print("\nServer berhenti.")