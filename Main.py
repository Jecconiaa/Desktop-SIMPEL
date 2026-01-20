import customtkinter as ctk
import cv2
import face_recognition
import numpy as np
import os
import sys
import time
import random
import requests
from PIL import Image
from pyzbar.pyzbar import decode
# Import class LoginFrame dari file login.py lu
from login import LoginFrame
from api_base import ApiBase
from Authcontext import AuthContext

# --- FORCE JALUR MEDIAPIPE ---
mp_path = os.path.join(os.getcwd(), "venv", "Lib", "site-packages", "mediapipe", "python")
if os.path.exists(mp_path): sys.path.append(mp_path)

try:
    from mediapipe.solutions import face_mesh as mp_face_mesh
except:
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh

# --- CONFIG API BACKEND ---
API_BASE_URL = "http://localhost:5234/api" 

class AppSIMPEL(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(" 🛡️ SIMPEL - Scanner Desktop ")
        self.geometry("1200x750")

        # --- DATA TRANSAKSI & AUTH ---
        self.transaksi_id = None 
        self.api_headers = {"Content-Type": "application/json"}
        self.is_logged_in = False
        
        # --- ENGINE CONFIG ---
        self.assets_path = "assets"
        self.known_encodings = []
        self.known_names = []
        self.current_user = "Unknown"
        self.is_verified = False
        self.frame_count = 0 
        self.face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True)
        
        # Liveness Config
        self.LEFT_EYE = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE = [33, 160, 158, 133, 153, 144]
        self.blink_count = 0
        self.eye_closed = False
        self.standby_start_time = None
        self.standby_duration = 2
        self.is_ready_for_challenge = False
        self.pool_challenges = ["Tengok Kanan", "Tengok Kiri", "Kedip 2x", "Buka Mulut"]
        self.active_challenges = random.sample(self.pool_challenges, 4)
        self.current_step = 0
        self.challenge_verified = False

        # --- STEP 1: TAMPILKAN LOGIN FRAME ---
        # Begitu aplikasi buka, munculin login dulu bro
        self.show_login_screen()

    def show_login_screen(self):
        """Menampilkan frame login di tengah layar"""
        self.login_view = LoginFrame(self, self.handle_login_success, API_BASE_URL)
        self.login_view.pack(expand=True, pady=20)

    def handle_login_success(self, token):
        """Callback saat login di login.py berhasil"""
        self.is_logged_in = True
        self.api_headers["Authorization"] = f"Bearer {token}"
        
        # Hapus layar login
        self.login_view.destroy()
        
        # --- STEP 2: SETUP SCANNER UI & START ENGINES ---
        print("✅ Login Sukses! Memulai Scanner...")
        self.load_known_faces()
        self.setup_ui()
        
        # Start Kamera
        self.cap = cv2.VideoCapture(0)
        self.update_frame()

    # ================================================================
    # API INTEGRATION LOGIC
    # ================================================================

    def api_process_scan(self, qr_code):
        try:
            url_scan = f"{API_BASE_URL}/Borrowing/ScanQrPeminjaman/{qr_code}"
            res_scan = requests.post(url_scan, headers=self.api_headers, verify=False, timeout=5)
            
            if res_scan.status_code == 200:
                data_res = res_scan.json()
                self.transaksi_id = data_res.get("data", {}).get("id")
                
                url_detail = f"{API_BASE_URL}/Borrowing/GetScanDataByQr/{qr_code}"
                res_detail = requests.get(url_detail, headers=self.api_headers, verify=False)
                return res_detail.json() if res_detail.status_code == 200 else f"Error: {res_detail.status_code}"
            
            return f"Error Scan BE: {res_scan.status_code}"
        except Exception as e:
            return f"Koneksi Gagal: {str(e)}"

    def api_verify_final(self, is_face_ok):
        if not self.transaksi_id: return False
        try:
            url = f"{API_BASE_URL}/Borrowing/VerifyPeminjaman/{self.transaksi_id}"
            payload = {
                "isQrVerified": True,
                "isFaceVerified": is_face_ok,
                "verifiedBy": f"Desktop-{self.current_user}"[:30]
            }
            res = requests.post(url, json=payload, headers=self.api_headers, verify=False)
            return res.status_code == 200
        except: return False

    # ================================================================
    # UI & ENGINE LOGIC
    # ================================================================

    def load_known_faces(self):
        if not os.path.exists(self.assets_path): os.makedirs(self.assets_path)
        for file in os.listdir(self.assets_path):
            if file.lower().endswith((".jpg", ".png", ".jpeg")):
                img = face_recognition.load_image_file(os.path.join(self.assets_path, file))
                encs = face_recognition.face_encodings(img)
                if encs:
                    self.known_encodings.append(encs[0])
                    self.known_names.append(os.path.splitext(file)[0])

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, height=60, fg_color="#162032")
        self.header.pack(side="top", fill="x")
        ctk.CTkLabel(self.header, text="🛡️ SIMPEL SCANNER ", font=("Arial", 20, "bold"), text_color="#22d3ee").pack(pady=15)
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(expand=True, fill="both", padx=20, pady=20)
        
        self.video_label = ctk.CTkLabel(self.container, text="", corner_radius=20, fg_color="black")
        self.video_label.pack(side="left", expand=True, fill="both", padx=(0, 15))
        
        self.panel = ctk.CTkFrame(self.container, width=350, corner_radius=20, fg_color="#162032")
        self.panel.pack(side="right", fill="y")
        
        self.welcome_label = ctk.CTkLabel(self.panel, text="MENCARI WAJAH...", font=("Arial", 20, "bold"), text_color="#22d3ee")
        self.welcome_label.pack(pady=(40, 5))
        self.status_label = ctk.CTkLabel(self.panel, text="Standby Mode", font=("Arial", 14), text_color="gray")
        self.status_label.pack(pady=5)
        self.progress_bar = ctk.CTkProgressBar(self.panel, width=280)
        self.progress_bar.pack(pady=10); self.progress_bar.set(0)
        self.qr_info_box = ctk.CTkTextbox(self.panel, width=300, height=280, corner_radius=15, fg_color="#0d1b2a")
        self.qr_info_box.pack(pady=20, padx=20)

    def calculate_ear(self, landmarks, eye_indices):
        def dist(p1, p2): return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
        v1 = dist(landmarks[eye_indices[1]], landmarks[eye_indices[5]])
        v2 = dist(landmarks[eye_indices[2]], landmarks[eye_indices[4]])
        h = dist(landmarks[eye_indices[0]], landmarks[eye_indices[3]])
        return (v1 + v2) / (2.0 * h)

    def check_liveness_features(self, landmarks):
        nose = landmarks[4].x
        re, le = landmarks[234].x, landmarks[454].x
        ratio = (nose - re) / (le - re)
        res = []
        if ratio < 0.38: res.append("Tengok Kiri")
        elif ratio > 0.62: res.append("Tengok Kanan")
        if abs(landmarks[13].y - landmarks[14].y) > 0.05: res.append("Buka Mulut")
        return res

    def draw_fancy_border(self, img, pt1, pt2, color):
        x1, y1 = pt1; x2, y2 = pt2
        r = 20
        for p in [(x1,y1,1,1), (x2,y1,-1,1), (x1,y2,1,-1), (x2,y2,-1,-1)]:
            cv2.line(img, (p[0], p[1]), (p[0] + p[2]*r, p[1]), color, 3)
            cv2.line(img, (p[0], p[1]), (p[0], p[1] + p[3]*r), color, 3)

    def update_frame(self):
        if not self.is_logged_in: return # Jangan jalanin kamera kalo belum login
        
        ret, frame = self.cap.read()
        if not ret: return
        self.frame_count += 1
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 1. Face Recognition
        if self.current_user == "Unknown" and self.frame_count % 30 == 0:
            small_rgb = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
            f_locs = face_recognition.face_locations(small_rgb)
            f_encs = face_recognition.face_encodings(small_rgb, f_locs)
            if f_encs:
                matches = face_recognition.compare_faces(self.known_encodings, f_encs[0], tolerance=0.5)
                if True in matches:
                    self.current_user = self.known_names[matches.index(True)]
                    self.welcome_label.configure(text=f"Hi, {self.current_user.title()}")

        # 2. Face Mesh & Liveness
        res = self.face_mesh.process(rgb_frame)
        if res.multi_face_landmarks:
            lms = res.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]
            x_min, y_min = int(lms[234].x * w), int(lms[10].y * h)
            x_max, y_max = int(lms[454].x * w), int(lms[152].y * h)
            color = (74, 222, 128) if self.challenge_verified else (0, 211, 238)
            self.draw_fancy_border(frame, (x_min, y_min), (x_max, y_max), color)

            if self.current_user != "Unknown":
                ear = (self.calculate_ear(lms, self.LEFT_EYE) + self.calculate_ear(lms, self.RIGHT_EYE)) / 2.0
                if ear < 0.23: self.eye_closed = True
                elif self.eye_closed and ear > 0.25:
                    self.blink_count += 1
                    self.eye_closed = False

                if not self.is_ready_for_challenge and not self.challenge_verified:
                    if self.standby_start_time is None: self.standby_start_time = time.time()
                    elapsed = time.time() - self.standby_start_time
                    countdown = max(0, int(self.standby_duration - elapsed))
                    if countdown > 0:
                        cv2.putText(frame, f"Bersiap: {countdown}s", (x_min, y_min-20), 1, 2, (255, 255, 0), 2)
                    else: self.is_ready_for_challenge = True

                if self.is_ready_for_challenge and not self.challenge_verified:
                    detected = self.check_liveness_features(lms)
                    if self.blink_count >= 2: detected.append("Kedip 2x")
                    target = self.active_challenges[self.current_step]
                    self.status_label.configure(text=f"TAHAP {self.current_step+1}/4: {target}", text_color="#fbbf24")
                    self.progress_bar.set(self.current_step / 4)
                    cv2.putText(frame, f"Ikuti: {target}", (x_min, y_min-20), 1, 2, (0, 255, 255), 2)
                    if target in detected:
                        self.current_step += 1
                        self.blink_count = 0
                        if self.current_step == 4: self.challenge_verified = True

        # 3. QR & Verification
        if self.challenge_verified and not self.is_verified:
            for barcode in decode(frame):
                qr_data = barcode.data.decode('utf-8')
                self.status_label.configure(text="SINKRONISASI BE...", text_color="#fbbf24")
                res_data = self.api_process_scan(qr_data)
                
                if isinstance(res_data, dict):
                    self.is_verified = True
                    mhs = res_data.get('mahasiswa', {})
                    info = f"👤 {mhs.get('nama')} ({mhs.get('nim')})\n📦 DAFTAR ALAT:\n"
                    for item in res_data.get('peminjaman_detail', []):
                        info += f"- {item.get('nama_alat')} [{item.get('status')}]\n"
                    
                    self.qr_info_box.delete("0.0", "end")
                    self.qr_info_box.insert("0.0", info)
                    
                    if self.api_verify_final(is_face_ok=True):
                        self.status_label.configure(text="VERIFIKASI SUKSES ✅", text_color="#4ade80")
                    else:
                        self.status_label.configure(text="VERIFIKASI GAGAL BE ❌", text_color="#f87171")
                else:
                    self.status_label.configure(text=f"ERROR: {res_data}", text_color="#f87171")

        img_tk = ctk.CTkImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), size=(750, 500))
        self.video_label.configure(image=img_tk)
        self.after(10, self.update_frame)

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    app = AppSIMPEL()
    app.mainloop()