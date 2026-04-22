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
    try:
        os.makedirs(READ_DIR, exist_ok=True)
    except OSError as e:
        print(f"Warning: Tidak dapat membuat direktori READ_DIR '{READ_DIR}'. Detail: {e}")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Cek apakah bisa menulis di READ_DIR, jika tidak, simpan history di UPLOAD_DIR
HISTORY_FILE = os.path.join(READ_DIR, 'history.json')
try:
    # Coba tes tulis file
    test_file = os.path.join(READ_DIR, '.test_write')
    with open(test_file, 'w') as f:
        f.write('')
    os.remove(test_file)
except OSError:
    HISTORY_FILE = os.path.join(UPLOAD_DIR, 'history.json')
    print(f"Warning: Tidak dapat menulis di '{READ_DIR}'. History disimpan di '{HISTORY_FILE}'.")

# Lokasi stats global
STATS_FILE = 'bahan/stats.json'

def track_progress(filename):
    import datetime
    today = datetime.date.today().isoformat()
    stats = {}
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        except: pass
    
    if today not in stats:
        stats[today] = []
    
    if filename not in stats[today]:
        stats[today].append(filename)
        try:
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=4)
        except: pass

def get_today_count():
    import datetime
    today = datetime.date.today().isoformat()
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                return len(stats.get(today, []))
        except: pass
    return 0

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # MIGRASI GLOBAL: Pastikan semua data lama mengikuti format baru {lang: {filename, title}}
                modified = False
                for file_key in data:
                    if isinstance(data[file_key], list):
                        data[file_key] = {l: {"filename": os.path.basename(file_key), "title": ""} for l in data[file_key]}
                        modified = True
                    elif isinstance(data[file_key], dict):
                        for lang in data[file_key]:
                            if isinstance(data[file_key][lang], str):
                                data[file_key][lang] = {"filename": data[file_key][lang], "title": ""}
                                modified = True
                
                if modified:
                    save_history(data)
                return data
        except Exception as e:
            print(f"Error loading history: {e}")
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
    models = [
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash"
    ]

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

                    # pastikan JSON valid
                    if not clean.startswith("{"):
                        return {"translations": [clean]}

                    try:
                        return json.loads(clean)
                    except:
                        return {"translations": [clean]}

                # 🔥 fallback semua error umum
                if res.status_code in [429, 500, 503]:
                    print(f"⚠️ Error {res.status_code}: {model}, mencoba fallback...")
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
    prompt = f"Extract all text from this comic page. {source_instruction} Translate it to {target_lang}. IMPORTANT: Maintain the original tone and context. Adapt the language, idioms, and expressions so they sound completely natural and localized for native speakers of {target_lang}. Based on the context and translated text, suggest a short, catchy, and highly relevant title for this comic page in {target_lang}. Return ONLY valid JSON:\n{{\"translations\": [\"text1\", \"text2\"], \"detected_language\": \"language name\", \"title\": \"Suggested Title\"}}\nDo not include markdown or backticks."
    
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
                selected_langs = data.get('selected_langs', ["Indonesian", "English", "Tagalog", "Spanish"])
                
                if not filename:
                    raise ValueError("Filename tidak ditemukan")
                    
                source_path = os.path.join(UPLOAD_DIR, filename)
                if not os.path.exists(source_path):
                    source_path = os.path.join(READ_DIR, filename)
                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"File {filename} tidak ditemukan di bahan maupun {READ_DIR}.")

                # Panggil Gemini API (Hanya 1 bahasa utama agar Vision tidak berat)
                result = call_gemini_vision(source_path, target_lang, source_lang)
                
                # Jika sukses, lanjut panggil Gemini Text untuk bahasa lainnya
                if "error" not in result and "translations" in result:
                    main_translations = result["translations"]
                    main_title = result.get("title", "")
                    
                    multi_result = {
                        "translations": {target_lang: main_translations},
                        "titles": {target_lang: main_title},
                        "detected_language": result.get("detected_language", "Auto")
                    }
                    
                    extra_langs = [l for l in selected_langs if l.lower() != target_lang.lower()]
                    
                    if extra_langs and main_translations:
                        langs_str = ", ".join(extra_langs)
                        json_translations_format = ", ".join([f'"{l}": ["text1", "text2"]' for l in extra_langs])
                        json_titles_format = ", ".join([f'"{l}": "Title"' for l in extra_langs])
                        
                        prompt = f"Translate the following comic text bubbles and title into ALL of these languages: {langs_str}.\n\nOriginal Title: {main_title}\nTexts:\n{json.dumps(main_translations, ensure_ascii=False)}\n\nReturn ONLY JSON format EXACTLY like this: {{\"translations\": {{{json_translations_format}}}, \"titles\": {{{json_titles_format}}}}}"
                        
                        payload = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"response_mime_type": "application/json"}
                        }
                        
                        print(f"DEBUG: Memanggil Gemini Text untuk bahasa tambahan: {langs_str}")
                        extra_result = call_gemini_api(payload)
                        if "error" not in extra_result:
                            # Gabungkan
                            if "translations" in extra_result and isinstance(extra_result["translations"], dict):
                                multi_result["translations"].update(extra_result["translations"])
                            if "titles" in extra_result and isinstance(extra_result["titles"], dict):
                                multi_result["titles"].update(extra_result["titles"])
                    
                    result = multi_result
                
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
                    bg_color_str = el.get('bgColor', 'rgb(255, 255, 255)')
                    bg_tuple = None
                    if 'rgba(' in bg_color_str:
                        parts = bg_color_str.replace('rgba(', '').replace(')', '').split(',')
                        if len(parts) >= 4 and float(parts[3]) > 0:
                            bg_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
                    elif 'rgb(' in bg_color_str:
                        parts = bg_color_str.replace('rgb(', '').replace(')', '').split(',')
                        bg_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
                    elif bg_color_str == 'transparent':
                        pass
                    
                    x, y, w, h = el['x'], el['y'], el['w'], el['h']
                    if bg_tuple:
                        draw.rectangle([x, y, x + w, y + h], fill=bg_tuple)
                    
                    # 2. Gambar Teks Custom
                    # Parsing warna teks
                    text_color_str = el.get('textColor', 'rgb(0, 0, 0)')
                    if 'rgba(' in text_color_str:
                        parts = text_color_str.replace('rgba(', '').replace(')', '').split(',')
                        text_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
                    elif 'rgb(' in text_color_str:
                        parts = text_color_str.replace('rgb(', '').replace(')', '').split(',')
                        text_tuple = (int(parts[0]), int(parts[1]), int(parts[2]))
                    else:
                        text_tuple = (0, 0, 0)
                    
                    # LOGIKA RENDER HD: Shrink-to-fit (Pastikan teks tidak nembus box HD)
                    current_font_size = int(el['fontSize'])
                    text_upper = el['text'].upper()
                    
                    while current_font_size > 6:
                        try:
                            font = ImageFont.truetype(FONT_PATH, current_font_size)
                        except:
                            font = ImageFont.load_default()
                        
                        # Bungkus teks berdasarkan lebar box (padding 10px)
                        lines = wrap_text_pil(text_upper, font, w - 10, draw)
                        
                        # Hitung total tinggi blok teks
                        line_heights = []
                        for line in lines:
                            if not line:
                                line_heights.append(current_font_size)
                                continue
                            bbox = draw.textbbox((0, 0), line, font=font)
                            line_heights.append(bbox[3] - bbox[1] if bbox[3] > bbox[1] else current_font_size)
                        
                        line_spacing = 4
                        total_text_height = sum(line_heights) + (max(0, len(lines) - 1)) * line_spacing
                        
                        # Jika sudah cukup (tinggi teks <= tinggi box), berhenti mengecilkan
                        if total_text_height <= h:
                            break
                        
                        # Jika masih nembus, kurangi ukuran font dan ulangi pembungkusan
                        current_font_size -= 1

                    # Mulai menggambar dari posisi Y agar teks di tengah secara vertikal
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
                
                # Simpan Riwayat Export ke File history.json (Format Baru: {ori: {lang: {filename, title}}})
                history = load_history()
                if rel_filename not in history:
                    history[rel_filename] = {}
                
                # Migrasi jika masih format lama (List atau Dict of strings)
                if isinstance(history[rel_filename], list):
                    history[rel_filename] = {l: {"filename": os.path.basename(rel_filename), "title": ""} for l in history[rel_filename]}
                
                # Pastikan setiap entry adalah dict
                for lang_key in list(history[rel_filename].keys()):
                    if isinstance(history[rel_filename][lang_key], str):
                        history[rel_filename][lang_key] = {"filename": history[rel_filename][lang_key], "title": ""}

                history[rel_filename][safe_lang] = {
                    "filename": output_filename,
                    "title": comic_title
                }
                save_history(history)
                
                # Catat progres harian
                track_progress(rel_filename)
                
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
                # Ambil daftar bahasa yang VALID (Pernah ada di folder hasil)
                languages = []
                if os.path.exists(OUTPUT_DIR):
                    # Filter: Hanya ambil folder yang benar-benar berisi hasil terjemahan (Bukan Jawa)
                    languages = [d for d in os.listdir(OUTPUT_DIR) 
                                if os.path.isdir(os.path.join(OUTPUT_DIR, d)) and d not in ["Jawa", ".git", "__pycache__"]]
                
                if not languages:
                    languages = ["Indonesia"] # Default jika kosong

                history = load_history()
                if rel_filename not in history:
                    history[rel_filename] = {}
                
                # Migrasi jika format lama
                if isinstance(history[rel_filename], list):
                    history[rel_filename] = {l: {"filename": os.path.basename(rel_filename), "title": ""} for l in history[rel_filename]}

                sub_dir = os.path.dirname(rel_filename)
                base_name = os.path.basename(rel_filename)

                for lang in languages:
                    lang_dir = os.path.join(OUTPUT_DIR, lang, sub_dir)
                    os.makedirs(lang_dir, exist_ok=True)
                    output_path = os.path.join(lang_dir, base_name)
                    
                    shutil.copy2(source_path, output_path)
                    
                    # Simpan dalam format baru (dict)
                    history[rel_filename][lang] = {
                        "filename": base_name,
                        "title": ""
                    }
                        
                save_history(history)
                track_progress(rel_filename)
                
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

        elif self.path == '/delete-file':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                rel_filename = data['fileName']
                source_path = os.path.join(UPLOAD_DIR, rel_filename)
                if not os.path.exists(source_path):
                    source_path = os.path.join(READ_DIR, rel_filename)
                
                if os.path.exists(source_path):
                    os.remove(source_path)
                    
                    # Bersihkan Riwayat
                    history = load_history()
                    if rel_filename in history:
                        del history[rel_filename]
                        save_history(history)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'success', 'message': 'File berhasil dihapus'}).encode('utf-8'))
                else:
                    raise FileNotFoundError("File tidak ditemukan")

            except Exception as e:
                print(f"Error Deleting File: {e}")
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
                                langs = history.get(rel_path, [])
                                if isinstance(langs, dict):
                                    langs = list(langs.keys())
                                    
                                files_data.append({
                                    "name": rel_path,
                                    "translated": len(langs) > 0,
                                    "languages": langs
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

        elif self.path == '/get_stats':
            count = get_today_count()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'today_count': count}).encode('utf-8'))
            return

        elif self.path == '/get_history':
            history = load_history()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(history).encode('utf-8'))
            return

        elif self.path == '/list-output-categories':
            categories = []
            if os.path.exists(OUTPUT_DIR):
                categories = [d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(categories).encode('utf-8'))
            return

        elif self.path.startswith('/list-hasil'):
            # Parsing query params: ?lang=Indonesia&subfolder=path/to/dir&limit=12&offset=0
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            lang = params.get('lang', [''])[0]
            subfolder = params.get('subfolder', [''])[0]
            limit = int(params.get('limit', [12])[0])
            offset = int(params.get('offset', [0])[0])
            
            folders = []
            items = []
            total_items = 0
            
            if lang:
                target_base = os.path.join(OUTPUT_DIR, lang, subfolder)
                if os.path.exists(target_base) and os.path.isdir(target_base):
                    # List directory contents
                    try:
                        entries = os.listdir(target_base)
                        # Filter folders and files
                        for entry in entries:
                            full_entry_path = os.path.join(target_base, entry)
                            if os.path.isdir(full_entry_path):
                                if entry not in [".git", "__pycache__"]:
                                    folders.append(entry)
                            elif entry.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                                mtime = os.path.getmtime(full_entry_path)
                                # URL safe path
                                rel_path_from_lang = os.path.relpath(full_entry_path, os.path.join(OUTPUT_DIR, lang))
                                items.append({
                                    "filename": entry,
                                    "url": f"/hasil/{lang}/{rel_path_from_lang}",
                                    "mtime": mtime
                                })
                    except Exception as e:
                        print(f"Error reading dir: {e}")

            # Sort items by newest first
            items.sort(key=lambda x: x['mtime'], reverse=True)
            folders.sort() # Folders alphabetical
            
            total_items = len(items)
            paginated_items = items[offset : offset + limit] if limit > 0 else items[offset:]
            
            response_data = {
                "folders": folders,
                "items": paginated_items,
                "total": total_items,
                "has_more": (offset + len(paginated_items)) < total_items
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
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