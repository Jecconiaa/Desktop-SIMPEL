import customtkinter as ctk
import cv2
import face_recognition
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

        # --- Performance Config ---
        self.FR_SCALING = 0.2
        self.FR_TOLERANCE = 0.60
        self.BR_THRESHOLD = 95
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        
        # Window
        self.title("🛡️ SIMPEL - Ultra Performance")
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
        self.is_mesh_processing = False # 🔥 New Flag for MediaPipe
        
        self.cached_face_locations = None
        self.cached_rgb_small = None
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

    def load_known_faces(self):
        path = os.path.join(project_root, "assets")
        if not os.path.exists(path): return
        for f in os.listdir(path):
            if f.lower().endswith((".jpg", ".png", ".jpeg")):
                img = cv2.imread(os.path.join(path, f))
                enhanced, _ = self.apply_enhancement(img)
                rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
                encs = face_recognition.face_encodings(rgb)
                if encs:
                    self.known_face_encodings.append(encs[0])
                    self.known_face_names.append(os.path.splitext(f)[0].replace("_", " ").title())
        print(f"✅ DB Loaded: {len(self.known_face_names)} faces")

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#162032")
        self.header.pack(side="top", fill="x")
        ctk.CTkButton(self.header, text="🚪 LOGOUT", width=100, fg_color="#dc2626", command=self.logout).pack(side="left", padx=20)
        ctk.CTkLabel(self.header, text="🛡️ SIMPEL SCANNER SYSTEM", font=("Arial", 20, "bold"), text_color="#22d3ee").pack(pady=15)
        
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
        self.active_challenge = random.choice(["Tengok Kanan", "Tengok Kiri", "Kedip 2x", "Buka Mulut"])
        self.face_detected_start_time = 0
        self.no_face_counter = 0

    # --- 🚀 WORKERS (ASYNCHRONOUS) ---

    def mediapipe_worker(self, frame_rgb):
        """Thread khusus MediaPipe biar UI gak freezing"""
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
            small = cv2.resize(frame_copy, (0, 0), fx=self.FR_SCALING, fy=self.FR_SCALING)
            processed, _ = self.apply_enhancement(small)
            rgb_small = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb_small, model="hog")
            with self.face_data_lock:
                self.cached_face_locations = locs if locs else None
                self.cached_rgb_small = rgb_small
                if not locs: self.identified_user = None
        finally: self.is_detecting_face = False

    def identify_face_worker(self):
        try:
            with self.face_data_lock:
                locs, rgb = self.cached_face_locations, self.cached_rgb_small
            if not locs or rgb is None: return
            encs = face_recognition.face_encodings(rgb, locs)
            if encs and self.known_face_encodings:
                dist = face_recognition.face_distance(self.known_face_encodings, encs[0])
                idx = np.argmin(dist)
                if dist[idx] <= self.FR_TOLERANCE:
                    self.identified_user = self.known_face_names[idx]
                    return
            self.identified_user = "UNKNOWN"
        finally: self.is_identifying_face = False

    # --- 🎥 MAIN LOOP ---

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret: return

        frame = cv2.flip(frame, 1)
        display_frame = frame.copy()
        now = time.time()

        # 1. MediaPipe Thread (Liveness) - Paling Penting!
        if not self.is_mesh_processing:
            self.is_mesh_processing = True
            # Pake frame resize biar MediaPipe makin enteng
            mini_mp = cv2.cvtColor(cv2.resize(frame, (640, 360)), cv2.COLOR_BGR2RGB)
            threading.Thread(target=self.mediapipe_worker, args=(mini_mp,), daemon=True).start()

        # 2. QR Thread
        if int(now * 10) % 5 == 0 and not self.is_qr_processing:
            self.is_qr_processing = True
            threading.Thread(target=self.qr_worker, args=(frame.copy(),), daemon=True).start()

        # 3. FR Pipeline
        if not self.is_detecting_face and (now - self.last_detect_time > 0.5):
            self.last_detect_time = now
            self.is_detecting_face = True
            threading.Thread(target=self.detect_face_worker, args=(frame.copy(),), daemon=True).start()

        if not self.is_identifying_face and self.cached_face_locations and (now - self.last_identify_time > 1.2):
            self.last_identify_time = now
            self.is_identifying_face = True
            threading.Thread(target=self.identify_face_worker, daemon=True).start()

        # 4. Logic UI & Render
        if self.last_known_lms:
            self.process_ui_logic(display_frame, self.last_known_lms)
        else:
            if self.current_state not in ['PROCESSING_API', 'SUCCESS']: self.reset_all_states()

        self.render_ui(display_frame)
        # Lock di 30 FPS (33ms) biar CPU gak panas
        self.after(33, self.update_frame)

    def process_ui_logic(self, img, lms):
        h, w, _ = img.shape
        # Landmark mapping (MediaPipe)
        x_min = int(lms[234].x * w); y_min = int(lms[10].y * h)
        x_max = int(lms[454].x * w); y_max = int(lms[152].y * h)
        cx = (x_min + x_max) // 2

        # Draw UI
        # Draw UI
        if not self.current_qr_data:
            self.draw_text(img, "SCAN QR DULU", cx, y_min-30, (50, 50, 255))
        else:
            # FIX: If QR found & state is STANDBY, switch to CHALLENGE automatically
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
        
        # Fancy Border
        cv2.rectangle(img, (x_min, y_min), (x_max, y_max), (255, 255, 255), 2)

    def check_liveness(self, lms):
        # Pose & Blink detection
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
                # Resize cuma sekali pas mau ditampilin
                img = cv2.resize(frame, (w_lbl, h_lbl), interpolation=cv2.INTER_LINEAR)
                img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                
                # OPTIMIZATION: Use ImageTk instead of CTkImage for speed
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk # Keep reference!
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
            # Step 1: GET data peminjaman
            res = self.api.get(f"/api/Borrowing/GetScanDataByQr/{qr}")
            
            if not res or not res.get('peminjaman_detail'):
                print("❌ Invalid QR or no data")
                self.after(2000, self.reset_all_states)
                return
            
            # Step 2: Check status (booked vs dipinjam)
            status = res.get('status', '').lower()  # "booked" atau "dipinjam"
            
            print(f"📦 Status: {status}")
            
            # Step 3: Call endpoint yang sesuai
            if status == 'dipinjam':
                # PENGEMBALIAN (barang lagi dipinjam, mau dikembaliin)
                final_res = self.api.post(f"/api/Borrowing/ScanQrPengembalian/{qr}")
                print("✅ POST ScanQrPengembalian called")
            elif status == 'booked':
                # PEMINJAMAN (barang udah dibook, mau diambil)
                final_res = self.api.post(f"/api/Borrowing/ScanQrPeminjaman/{qr}")
                print("✅ POST ScanQrPeminjaman called")
            else:
                # Status tidak dikenal
                print(f"⚠️ Unknown status: {status}")
                self.after(2000, self.reset_all_states)
                return
            
            # Step 4: Handle response
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
        # Clear token dari auth context & hapus session file
        self.auth.sign_out()
        
        # Clear token dari API client
        self.api.clear_token()
        
        # Release camera
        if hasattr(self, 'cap'): self.cap.release()
        
        # Destroy & exit
        self.destroy()
        sys.exit(0)

    def show_login_required(self):
        ctk.CTkLabel(self, text="🔑 LOGIN REQUIRED").pack(expand=True)
        self.after(2000, self.destroy)

if __name__ == "__main__":
    app = AppSIMPEL()
    app.mainloop()