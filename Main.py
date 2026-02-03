import customtkinter as ctk
import cv2
import face_recognition
import numpy as np
import os
import sys
import time
import random
import threading
from PIL import Image
from pyzbar.pyzbar import decode
import urllib3

# Nonaktifkan peringatan SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. SETUP PATH ---
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from context.AuthContext import auth_context
    from lib.api import init_api 
    from lib.api_base import get_api_base_url
except ImportError as e:
    print(f"❌ Main: Import error: {e}")
    sys.exit(1)

try:
    from mediapipe.solutions import face_mesh as mp_face_mesh
except:
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh

class AppSIMPEL(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.api_base_url = get_api_base_url()
        self.api = init_api(self.api_base_url) 
        
        if not auth_context.is_authenticated():
            self.show_login_required(); return
        
        self.api.set_token(auth_context.get_token())

        # Window Config
        self.title("🛡️ SIMPEL - High Performance Clean UI")
        self.geometry("1280x720")
        self.after(0, lambda: self.state('zoomed')) 
        ctk.set_appearance_mode("dark")

        # Database & Engines
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces() 
        self.face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True, min_detection_confidence=0.6, min_tracking_confidence=0.6)
        
        # --- Performance Flags (Secret Sauce integrated) ---
        self.is_face_processing = False
        self.last_face_scan_time = 0
        self.face_scan_interval = 1.5  # Cooldown 1 detik biar CPU gak meledak
        self.FR_TOLERANCE = 0.55       # ✅ Lebih toleran buat low-light       
        
        self.is_qr_processing = False  # 🚀 Flag buat QR thread
        
        # 🔥 PIPELINE THREADING FLAGS
        self.is_detecting_face = False       # Thread A (lightweight)
        self.is_identifying_face = False     # Thread B (heavy)
        self.last_detect_time = 0
        self.last_identify_time = 0
        self.detect_interval = 0.3           # Deteksi cepet (300ms)
        self.identify_interval = 1.5         # Identifikasi lambat (1.5s)
        
        # 🛡️ RACE CONDITION PROTECTION
        self.face_data_lock = threading.Lock()
        self.cached_face_locations = None    # Thread A simpan kesini
        self.cached_frame_for_encoding = None
        
        self.frame_count = 0
        self.last_known_lms = None 
        self.no_face_counter = 0    
        self.face_buffer_limit = 3  
        
        self.reset_all_states()
        self.setup_ui() 
        
        # Camera Setup (HD)
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        self.update_frame()

    def load_known_faces(self):
        path = os.path.join(project_root, "assets")
        if not os.path.exists(path): return
        for filename in os.listdir(path):
            if filename.lower().endswith((".jpg", ".png", ".jpeg")):
                try:
                    img = face_recognition.load_image_file(os.path.join(path, filename))
                    encs = face_recognition.face_encodings(img)
                    if encs:
                        self.known_face_encodings.append(encs[0])
                        self.known_face_names.append(os.path.splitext(filename)[0].replace("_", " ").title())
                except: pass
        print(f"✅ Database Loaded: {len(self.known_face_names)} faces")

    def reset_all_states(self):
        self.current_state = 'STANDBY' 
        self.identified_user = None 
        self.current_qr_data = None
        self.blink_count = 0
        self.eye_closed = False
        self.active_challenge = random.choice(["Tengok Kanan", "Tengok Kiri", "Kedip 2x", "Buka Mulut"])
        self.face_detected_start_time = 0

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#162032")
        self.header.pack(side="top", fill="x")
        
        self.btn_logout = ctk.CTkButton(self.header, text="🚪 LOGOUT", width=100, height=35, 
                                        fg_color="#dc2626", hover_color="#b91c1c", 
                                        font=("Arial", 12, "bold"), command=self.logout)
        self.btn_logout.pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(self.header, text="🛡️ SIMPEL SCANNER SYSTEM", font=("Arial", 18, "bold"), text_color="#22d3ee").pack(pady=15)
        
        self.video_label = ctk.CTkLabel(self, text="", fg_color="black")
        self.video_label.pack(expand=True, fill="both")

    # --- DRAWING HELPERS (DROP SHADOW - NO BOX/BORDER) ---
    def draw_floating_text(self, img, text, pos_x, pos_y, color):
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.9; thickness = 2
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        tx = pos_x - (text_size[0] // 2)
        
        # Shadow effect (geser 2 pixel hitam)
        cv2.putText(img, text, (tx + 2, pos_y + 2), font, font_scale, (0, 0, 0), thickness + 1)
        # Main text
        cv2.putText(img, text, (tx, pos_y), font, font_scale, color, thickness)

    def draw_fancy_border(self, img, pt1, pt2, color):
        x1, y1, x2, y2, r = pt1[0], pt1[1], pt2[0], pt2[1], 35
        for p in [(x1,y1,1,1), (x2,y1,-1,1), (x1,y2,1,-1), (x2,y2,-1,-1)]:
            cv2.line(img, (p[0]+2, p[1]+2), (p[0] + p[2]*r + 2, p[1]+2), (0,0,0), 6) # Shadow
            cv2.line(img, (p[0]+2, p[1]+2), (p[0], p[1] + p[3]*r + 2), (0,0,0), 6) # Shadow
            cv2.line(img, (p[0], p[1]), (p[0] + p[2]*r, p[1]), color, 5) # Main
            cv2.line(img, (p[0], p[1]), (p[0], p[1] + p[3]*r), color, 5) # Main

    def update_frame(self):
        if not self.cap.isOpened(): return
        ret, frame = self.cap.read()
        if not ret: return
        
        self.frame_count += 1
        frame = cv2.flip(frame, 1)
        display_frame = frame.copy()

        # 1. SCAN QR (Background Thread - Paralel dengan Face Recognition)
        if self.frame_count % 5 == 0 and self.current_state in ['STANDBY', 'LOCKING']:
            if not self.is_qr_processing:
                self.is_qr_processing = True
                threading.Thread(target=self.detect_qr_worker, args=(frame.copy(),), daemon=True).start()

        # 2. PIPELINE FACE RECOGNITION (2 Thread Terpisah)
        now = time.time()
        
        # 🔹 THREAD A: Deteksi Ada Wajah Ga (Lightweight - 300ms interval)
        if not self.is_detecting_face and now - self.last_detect_time > self.detect_interval:
            self.last_detect_time = now
            self.is_detecting_face = True
            threading.Thread(target=self.detect_face_worker, args=(frame.copy(),), daemon=True).start()
        
        # 🔹 THREAD B: Identifikasi Siapa (Heavy - 1.5s interval, cuma jalan kalau ada wajah)
        if not self.is_identifying_face and now - self.last_identify_time > self.identify_interval:
            # Cek apakah Thread A udah deteksi ada wajah
            with self.face_data_lock:
                if self.cached_face_locations is not None:
                    self.last_identify_time = now
                    self.is_identifying_face = True
                    # Pass data aman pake lock
                    threading.Thread(target=self.identify_face_worker, daemon=True).start()

        # 3. MEDIAPIPE (UI/Liveness)
        res = self.face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if res.multi_face_landmarks:
            self.last_known_lms = res.multi_face_landmarks[0].landmark
            self.no_face_counter = 0
            if self.face_detected_start_time == 0: self.face_detected_start_time = time.time()
        else:
            self.no_face_counter += 1
        
        # Auto-reset UI
        if self.no_face_counter >= self.face_buffer_limit:
            if self.current_state not in ['PROCESSING_API', 'SUCCESS']: self.reset_all_states()
            self.last_known_lms = None

        if self.last_known_lms:
            self.process_logic_ui(display_frame, self.last_known_lms)

        self.render_to_ui(display_frame)
        self.after(16, self.update_frame)  # 16ms = ~60 FPS (lebih smooth)

    # 🔹 THREAD A: Deteksi Wajah (Lightweight)
    def detect_face_worker(self, frame_copy):
        try:
            # Resize kecil biar cepet
            small = cv2.resize(frame_copy, (0, 0), fx=0.15, fy=0.15)  # Lebih kecil dari encode
            
            # 🌟 AUTO BRIGHTNESS ENHANCEMENT (Low-light fix)
            # Convert ke LAB color space (L = Lightness, A = Green-Red, B = Blue-Yellow)
            lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) ke channel L
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
            l_enhanced = clahe.apply(l)
            # Merge balik
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
            
            # Convert RGB & Contiguous
            rgb_small = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
            rgb_small = np.ascontiguousarray(rgb_small.astype(np.uint8))
            
            # Deteksi lokasi wajah (cepet)
            face_locs = face_recognition.face_locations(rgb_small, model="hog")
            
            # Simpan hasil ke cache (AMAN pake Lock)
            with self.face_data_lock:
                if face_locs:
                    self.cached_face_locations = face_locs
                    self.cached_frame_for_encoding = frame_copy  # Simpan frame asli buat Thread B
                else:
                    self.cached_face_locations = None
                    # Reset status kalau gak ada wajah
                    if self.identified_user and self.identified_user != "UNKNOWN":
                        self.after(0, lambda: setattr(self, 'identified_user', None))
        except Exception as e:
            print(f"⚠️ Face detection error: {e}")
        finally:
            self.is_detecting_face = False
    
    # 🔹 THREAD B: Identifikasi Wajah (Heavy)
    def identify_face_worker(self):
        try:
            # Ambil data dari Thread A (AMAN pake Lock)
            with self.face_data_lock:
                face_locs = self.cached_face_locations
                frame_copy = self.cached_frame_for_encoding
            
            if face_locs is None or frame_copy is None:
                return
            
            # Resize untuk encoding
            small = cv2.resize(frame_copy, (0, 0), fx=0.2, fy=0.2)
            
            # 🌟 AUTO BRIGHTNESS ENHANCEMENT (Low-light fix)
            lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
            l_enhanced = clahe.apply(l)
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
            
            # Convert RGB & Contiguous
            rgb_small = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
            rgb_small = np.ascontiguousarray(rgb_small.astype(np.uint8))
            
            # Encode wajah (berat)
            encs = face_recognition.face_encodings(rgb_small, face_locs)
            
            if encs and self.known_face_encodings:
                dist = face_recognition.face_distance(self.known_face_encodings, encs[0])
                if len(dist) > 0 and np.min(dist) <= self.FR_TOLERANCE:
                    name = self.known_face_names[np.argmin(dist)]
                    self.after(0, lambda n=name: setattr(self, 'identified_user', n))
                    return
            
            # Kalau gak kenal
            if self.known_face_encodings:
                self.after(0, lambda: setattr(self, 'identified_user', "UNKNOWN"))
        except Exception as e:
            print(f"⚠️ Face identification error: {e}")
        finally:
            self.is_identifying_face = False

    def process_logic_ui(self, display_frame, lms):
        h, w, _ = display_frame.shape
        x_min, y_min = int(lms[234].x * w), int(lms[10].y * h)
        x_max, y_max = int(lms[454].x * w), int(lms[152].y * h)
        cx = (x_min + x_max) // 2

        # Teks Atas
        top_txt = ""
        if not self.current_qr_data:
            if time.time() - self.face_detected_start_time > 2.5: top_txt = "QR TIDAK TERBACA"
        elif self.current_state == 'CHALLENGE': top_txt = f"TUGAS: {self.active_challenge.upper()}"
        if top_txt: self.draw_floating_text(display_frame, top_txt, cx, y_min - 35, (71, 71, 248)) 

        # Teks Bawah
        bot_txt = ""
        if self.identified_user == "UNKNOWN": bot_txt = "WAJAH ASING!"
        elif self.identified_user: bot_txt = f"USER: {self.identified_user}"
        if bot_txt: self.draw_floating_text(display_frame, bot_txt, cx, y_max + 55, (74, 222, 128))

        # Border
        clr = (251, 191, 36) if self.current_state == 'CHALLENGE' else (238, 211, 0)
        if self.current_state == 'SUCCESS': clr = (74, 222, 128)
        self.draw_fancy_border(display_frame, (x_min, y_min), (x_max, y_max), clr)

        # State transitions
        if self.current_state == 'STANDBY': self.current_state = 'LOCKING'
        elif self.current_state == 'LOCKING' and self.identified_user and self.identified_user != "UNKNOWN" and self.current_qr_data:
            self.current_state = 'CHALLENGE'
        elif self.current_state == 'CHALLENGE':
            self.handle_liveness_check(lms)

    def handle_liveness_check(self, lms):
        nose = lms[4].x; re = lms[234].x; le = lms[454].x
        ratio = (nose - re) / (le - re) if (le - re) != 0 else 0.5
        moves = []
        if ratio < 0.35: moves.append("Tengok Kiri")
        elif ratio > 0.65: moves.append("Tengok Kanan")
        if abs(lms[13].y - lms[14].y) > 0.05: moves.append("Buka Mulut")
        
        # Blink Check
        def d(p1, p2): return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
        ear = ( (d(lms[385], lms[380]) + d(lms[387], lms[373])) / (2 * d(lms[362], lms[263])) +
                (d(lms[160], lms[144]) + d(lms[158], lms[153])) / (2 * d(lms[33], lms[133])) ) / 2
        if ear < 0.20: self.eye_closed = True
        elif self.eye_closed and ear > 0.25:
            self.blink_count += 1; self.eye_closed = False
        if self.blink_count >= 2: moves.append("Kedip 2x")

        if self.active_challenge in moves:
            self.current_state = 'PROCESSING_API'
            threading.Thread(target=self.run_api_background, args=(self.current_qr_data,), daemon=True).start()

    def detect_qr(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        qrs = decode(gray)
        return qrs[0].data.decode('utf-8') if qrs else None

    # 🚀 WORKER: QR DETECTION (Background Thread)
    def detect_qr_worker(self, frame_copy):
        try:
            qr = self.detect_qr(frame_copy)
            if qr:
                self.after(0, lambda q=qr: setattr(self, 'current_qr_data', q))
        except Exception as e:
            print(f"⚠️ QR detection error: {e}")
        finally:
            self.is_qr_processing = False

    def render_to_ui(self, frame):
        try:
            w_lbl, h_lbl = self.video_label.winfo_width(), self.video_label.winfo_height()
            if w_lbl > 100 and h_lbl > 100:
                h_f, w_f = frame.shape[:2]
                ratio = max(w_lbl/w_f, h_lbl/h_f)
                new_w, new_h = int(w_f * ratio), int(h_f * ratio)
                frame_res = cv2.resize(frame, (new_w, new_h))
                sx = (new_w - w_lbl) // 2; sy = (new_h - h_lbl) // 2
                crop = frame_res[sy:sy+h_lbl, sx:sx+w_lbl]
                img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                self.video_label.configure(image=ctk.CTkImage(img, size=(w_lbl, h_lbl)))
        except: pass

    def run_api_background(self, qr):
        try:
            res = self.api.get(f"/api/Borrowing/GetScanDataByQr/{qr}")
            if res and isinstance(res, dict) and res.get('peminjaman_detail'):
                self.after(0, self.handle_scan_success)
            else:
                print(f"⚠️ API response invalid or empty")
                self.after(3000, self.reset_all_states)
        except Exception as e:
            print(f"⚠️ API error: {e}")
            self.after(3000, self.reset_all_states)

    def handle_scan_success(self):
        self.current_state = 'SUCCESS'; self.after(5000, self.reset_all_states)

    def logout(self):
        auth_context.sign_out()
        if hasattr(self, 'cap'): self.cap.release()
        self.destroy(); sys.exit(0)

    def show_login_required(self):
        ctk.CTkLabel(self, text="🔐 HARAP LOGIN").pack(expand=True); self.after(2000, self.destroy)

if __name__ == "__main__":
    app = AppSIMPEL(); app.mainloop()