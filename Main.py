import customtkinter as ctk
import cv2
import numpy as np
import os
import sys
import time
import random
import threading
from PIL import Image, ImageTk
import tkinter as tk
from pyzbar.pyzbar import decode
import urllib3

#Import InsightFace 
from insightface.app import FaceAnalysis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path: sys.path.insert(0, project_root)

try:
    from context.AuthContext import auth_context
    from lib.api import init_api 
    from lib.api_base import get_api_base_url
except ImportError:
    print("❌ Import Error"); sys.exit(1)

import mediapipe as mp

class AppSIMPEL(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # API & Auth
        self.auth = auth_context  # Store auth context reference
        self.api_base_url = get_api_base_url()
        self.api = init_api(self.api_base_url) 
        if not self.auth.is_authenticated(): self.show_login_required(); return
        self.api.set_token(self.auth.get_token())

        #  ganti pake Threshold Cosine Similarity InsightFace
        self.FR_THRESHOLD = 0.45 
        self.BR_THRESHOLD = 95
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        
        #  Inisialisasi Model InsightFace
        print(" Loading InsightFace...")
        self.face_app = FaceAnalysis(name='buffalo_l', root=os.path.join(project_root, 'models'))
        self.face_app.prepare(ctx_id=-1, det_size=(640, 640)) # ctx_id=-1 biar jalan aman di CPU
        
        # Window
        self.title(" SIMPEL - Ultra Performance (InsightFace)")
        self.geometry("1280x720")
        self.after(0, lambda: self.state('zoomed'))
        ctk.set_appearance_mode("dark")

        # Engines
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces()
        
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5)

        # Threading Flags
        self.face_data_lock = threading.Lock()
        self.is_qr_processing = False
        self.is_detecting_face = False
        self.is_identifying_face = False
        self.is_mesh_processing = False 
        
        self.cached_face_locations = None
        # Ganti cache gambar dengan cache embedding wajah
        self.cached_face_embedding = None 
        self.last_known_lms = None
        
        self.last_detect_time = 0
        self.last_identify_time = 0
        
        self.reset_all_states()
        self.setup_ui()
        
        # Camera
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30) # Lock camera ke 30 FPS
        
        self.update_frame()

    def apply_enhancement(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if np.mean(gray) < self.BR_THRESHOLD:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            enhanced_l = self.clahe.apply(l)
            return cv2.cvtColor(cv2.merge([enhanced_l, a, b]), cv2.COLOR_LAB2BGR), True
        return frame, False

    # 🔥Fungsi ngitung tingkat kemiripan embedding wajah
    def cosine_similarity(self, embedding1, embedding2):
        return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))

    def load_known_faces(self):
        path = os.path.join(project_root, "assets")
        if not os.path.exists(path): return
        for f in os.listdir(path):
            if f.lower().endswith((".jpg", ".png", ".jpeg")):
                img = cv2.imread(os.path.join(path, f))
                enhanced, _ = self.apply_enhancement(img)
                rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
                
                # Ekstrak fitur wajah pake InsightFace
                faces = self.face_app.get(rgb)
                if faces:
                    self.known_face_encodings.append(faces[0].normed_embedding)
                    self.known_face_names.append(os.path.splitext(f)[0].replace("_", " ").title())
        print(f"✅ DB Loaded: {len(self.known_face_names)} faces")

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#162032")
        self.header.pack(side="top", fill="x")
        ctk.CTkButton(self.header, text="LOGOUT", width=100, fg_color="#dc2626", command=self.logout).pack(side="left", padx=20)
        ctk.CTkLabel(self.header, text="Sistem Peminjaman Alat laboratorium P4", font=("Arial", 20, "bold"), text_color="#22d3ee").pack(pady=15)
        
        self.video_frame = ctk.CTkFrame(self, fg_color="black")
        self.video_frame.pack(expand=True, fill="both")
        self.video_label = tk.Label(self.video_frame, bg="black")
        self.video_label.pack(expand=True, fill="both")

    def reset_all_states(self):
        self.current_state = 'STANDBY'
        self.identified_user = None
        self.current_qr_data = None
        self.blink_count = 0
        self.eye_closed = False
        self.active_challenge = random.choice(["Tengok Kanan", "Tengok Kiri", "Buka Mulut"])
        self.face_detected_start_time = 0
        self.no_face_counter = 0

    # --- 🚀 WORKERS (ASYNCHRONOUS) ---

    def mediapipe_worker(self, frame_rgb):
        try:
            res = self.face_mesh.process(frame_rgb)
            if res.multi_face_landmarks:
                self.last_known_lms = res.multi_face_landmarks[0].landmark
                self.no_face_counter = 0
                if self.face_detected_start_time == 0: self.face_detected_start_time = time.time()
            else:
                self.no_face_counter += 1
                if self.no_face_counter > 5: self.last_known_lms = None
        finally:
            self.is_mesh_processing = False

    def detect_face_worker(self, frame_copy):
        try:
            # Enhancement
            processed, _ = self.apply_enhancement(frame_copy)
            rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            
            # InsightFace nyari semua wajah di frame
            faces = self.face_app.get(rgb)
            
            with self.face_data_lock:
                if faces:
                    #  FIX SPLIT-BRAIN: Sinkronisasi dengan MediaPipe 
                    if self.last_known_lms:
                        # 1. Ambil koordinat MediaPipe
                        lms = self.last_known_lms
                        h, w = rgb.shape[:2]
                        
                        # 2. Cari titik tengah muka (Center X & Y) versi MediaPipe
                        mp_cx = ((lms[234].x + lms[454].x) / 2) * w
                        mp_cy = ((lms[10].y + lms[152].y) / 2) * h
                        
                        # 3. Fungsi hitung jarak Muka InsightFace ke Kotak MediaPipe
                        def distance_to_mp(f):
                            x1, y1, x2, y2 = f.bbox
                            f_cx = (x1 + x2) / 2
                            f_cy = (y1 + y2) / 2
                            # Rumus jarak Euclidean (Phytagoras)
                            return (f_cx - mp_cx)**2 + (f_cy - mp_cy)**2
                        
                        # 4. Pilih wajah yang posisinya paling nempel/sama dengan MediaPipe
                        main_face = min(faces, key=distance_to_mp)
                    
                    else:
                        # Kalo MediaPipe lagi blank, balik ke rule "Muka Paling Gede"
                        main_face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                    
                    # Simpan data buat fungsi identifikasi
                    self.cached_face_locations = main_face.bbox.astype(int)
                    self.cached_face_embedding = main_face.normed_embedding
                else:
                    self.cached_face_locations = None
                    self.cached_face_embedding = None
                    self.identified_user = None
        finally: 
            self.is_detecting_face = False

    def identify_face_worker(self):
        try:
            #  Nyocokin wajah pake perhitungan Cosine Similarity dari cache
            with self.face_data_lock:
                locs = self.cached_face_locations
                embedding = self.cached_face_embedding
            
            if locs is None or embedding is None: return
            
            if self.known_face_encodings:
                similarities = [self.cosine_similarity(embedding, enc) for enc in self.known_face_encodings]
                idx = np.argmax(similarities)
                
                with self.face_data_lock:
                    if similarities[idx] >= self.FR_THRESHOLD:
                        self.identified_user = self.known_face_names[idx]
                    else:
                        self.identified_user = "UNKNOWN"
        finally: 
            self.is_identifying_face = False

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret: return

        frame = cv2.flip(frame, 1)
        display_frame = frame.copy()
        now = time.time()

        if not self.is_mesh_processing:
            self.is_mesh_processing = True
            mini_mp = cv2.cvtColor(cv2.resize(frame, (640, 360)), cv2.COLOR_BGR2RGB)
            threading.Thread(target=self.mediapipe_worker, args=(mini_mp,), daemon=True).start()

        if int(now * 10) % 5 == 0 and not self.is_qr_processing:
            self.is_qr_processing = True
            threading.Thread(target=self.qr_worker, args=(frame.copy(),), daemon=True).start()

        if not self.is_detecting_face and (now - self.last_detect_time > 0.5):
            self.last_detect_time = now
            self.is_detecting_face = True
            threading.Thread(target=self.detect_face_worker, args=(frame.copy(),), daemon=True).start()

        # 🔥 Perbaikan logic "is not None" buat numpy array InsightFace
        if not self.is_identifying_face and self.cached_face_locations is not None and (now - self.last_identify_time > 1.2):
            self.last_identify_time = now
            self.is_identifying_face = True
            threading.Thread(target=self.identify_face_worker, daemon=True).start()

        if self.last_known_lms:
            self.process_ui_logic(display_frame, self.last_known_lms)
        else:
            if self.current_state not in ['PROCESSING_API', 'SUCCESS']: self.reset_all_states()

        self.render_ui(display_frame)
        self.after(33, self.update_frame)

    def process_ui_logic(self, img, lms):
        h, w, _ = img.shape
        x_min = int(lms[234].x * w); y_min = int(lms[10].y * h)
        x_max = int(lms[454].x * w); y_max = int(lms[152].y * h)
        cx = (x_min + x_max) // 2

        if not self.current_qr_data:
            self.draw_text(img, "SCAN QR DULU", cx, y_min-30, (50, 50, 255))
        else:
            if self.current_state == 'STANDBY':
                self.current_state = 'CHALLENGE'
            
            if self.current_state == 'CHALLENGE':
                self.draw_text(img, f"TASK: {self.active_challenge}", cx, y_min-30, (255, 150, 0))
                self.check_liveness(lms)
            elif self.current_state == 'PROCESSING_API':
                self.draw_text(img, "MOHON TUNGGU...", cx, y_min-30, (255, 255, 0))
            elif self.current_state == 'SUCCESS':
                self.draw_text(img, "AKSES DITERIMA", cx, y_min-30, (0, 255, 0))
        
        if self.identified_user:
            color = (0, 255, 0) if self.identified_user != "UNKNOWN" else (0, 0, 255)
            self.draw_text(img, f"USER: {self.identified_user}", cx, y_max+40, color)
        
        cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (255, 255, 255), 2)

    def check_liveness(self, lms):
        nose = lms[4].x; re = lms[234].x; le = lms[454].x
        ratio = (nose - re) / (le - re) if (le - re) != 0 else 0.5
        
        moves = []
        if ratio < 0.35: moves.append("Tengok Kiri")
        elif ratio > 0.65: moves.append("Tengok Kanan")
        if abs(lms[13].y - lms[14].y) > 0.05: moves.append("Buka Mulut")

        if self.active_challenge in moves:
            self.current_state = 'PROCESSING_API'
            threading.Thread(target=self.run_api, args=(self.current_qr_data,), daemon=True).start()

    def render_ui(self, frame):
        try:
            w_lbl, h_lbl = self.video_label.winfo_width(), self.video_label.winfo_height()
            if w_lbl > 100:
                img = cv2.resize(frame, (w_lbl, h_lbl), interpolation=cv2.INTER_LINEAR)
                img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk 
                self.video_label.configure(image=imgtk)
        except: pass

    def qr_worker(self, frame):
        try:
            decoded = decode(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            if decoded: self.current_qr_data = decoded[0].data.decode('utf-8')
        finally: self.is_qr_processing = False

    def draw_text(self, img, text, x, y, color):
        cv2.putText(img, text, (x - 80, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 3)
        cv2.putText(img, text, (x - 80, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def run_api(self, qr):
        try:
            res = self.api.get(f"/api/Borrowing/GetScanDataByQr/{qr}")
            
            if not res or not res.get('peminjaman_detail'):
                print("❌ Invalid QR or no data")
                self.after(2000, self.reset_all_states)
                return
            
            status = res.get('status', '').lower()  
            print(f"📦 Status: {status}")
            
            if status == 'dipinjam':
                final_res = self.api.post(f"/api/Borrowing/ScanQrPengembalian/{qr}")
                print("✅ POST ScanQrPengembalian called")
            elif status == 'booked':
                final_res = self.api.post(f"/api/Borrowing/ScanQrPeminjaman/{qr}")
                print("✅ POST ScanQrPeminjaman called")
            else:
                print(f"⚠️ Unknown status: {status}")
                self.after(2000, self.reset_all_states)
                return
            
            if final_res:
                self.current_state = 'SUCCESS'
                self.after(3000, self.reset_all_states)
            else:
                print("⚠️ POST endpoint failed")
                self.after(2000, self.reset_all_states)
                
        except Exception as e:
            print(f"❌ API Error: {e}")
            self.after(2000, self.reset_all_states)

    def logout(self):
        self.auth.sign_out()
        self.api.clear_token()
        if hasattr(self, 'cap'): self.cap.release()
        self.destroy()
        sys.exit(0)

    def show_login_required(self):
        ctk.CTkLabel(self, text="🔑 LOGIN REQUIRED").pack(expand=True)
        self.after(2000, self.destroy)

if __name__ == "__main__":
    app = AppSIMPEL()
    app.mainloop()