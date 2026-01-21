# main.py
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
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- IMPORT MODULE BARU ---
import sys
import os

# Setup path untuk import module kita
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from context.AuthContext import auth_context
    from lib.api import api
    from lib.api_base import get_api_base_url
    print("✅ Main: Import module berhasil")
except ImportError as e:
    print(f"❌ Main: Import error: {e}")
    # Fallback import
    try:
        import importlib.util
        # Import AuthContext
        auth_context_path = os.path.join(project_root, "context", "AuthContext.py")
        spec = importlib.util.spec_from_file_location("AuthContext", auth_context_path)
        auth_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(auth_module)
        auth_context = auth_module.auth_context
        
        # Import api_base
        api_base_path = os.path.join(project_root, "lib", "api_base.py")
        spec = importlib.util.spec_from_file_location("api_base", api_base_path)
        api_base_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api_base_module)
        get_api_base_url = api_base_module.get_api_base_url
        
        from lib.api import api
        
        print("✅ Main: Import berhasil dengan cara manual")
    except Exception as e2:
        print(f"❌ Main: Manual import juga gagal: {e2}")
        sys.exit(1)

# --- FORCE JALUR MEDIAPIPE ---
mp_path = os.path.join(os.getcwd(), "venv", "Lib", "site-packages", "mediapipe", "python")
if os.path.exists(mp_path): 
    sys.path.append(mp_path)

try:
    from mediapipe.solutions import face_mesh as mp_face_mesh
except:
    import mediapipe as mp
    mp_face_mesh = mp.solutions.face_mesh

# --- CONFIG ---
API_BASE_URL = get_api_base_url() + "/api"

class AppSIMPEL(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(" 🛡️ SIMPEL - Scanner Desktop ")
        self.geometry("1200x750")
        
        # Setup theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # --- CEK AUTH DULU ---
        print("\n" + "="*50)
        print("🔍 Main: Checking authentication...")
        if not auth_context.is_authenticated():
            print("❌ Main: User not authenticated!")
            print("⚠️  Please login first via run_login.py")
            self.show_login_required()
            return
        
        # User sudah login, ambil info dari AuthContext
        self.current_user = auth_context.get_username()
        self.user_permissions = auth_context.get_permissions()
        self.user_token = auth_context.get_token()
        
        print(f"✅ Main: User '{self.current_user}' authenticated")
        print(f"📋 Permissions: {len(self.user_permissions)} items")
        print("="*50 + "\n")
        
        # --- DATA TRANSAKSI & AUTH ---
        self.transaksi_id = None 
        self.api_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.user_token}"
        }
        self.is_logged_in = True
        
        # --- ENGINE CONFIG ---
        self.assets_path = "assets"
        self.known_encodings = []
        self.known_names = []
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
        
        # --- LOAD FACES & SETUP UI ---
        self.load_known_faces()
        self.setup_ui()
        
        # Start Kamera
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("❌ Main: Camera not accessible")
            self.show_camera_error()
        else:
            self.update_frame()
    
    def show_login_required(self):
        """Tampilkan pesan login required"""
        self.login_frame = ctk.CTkFrame(self, corner_radius=20, fg_color="#162032")
        self.login_frame.pack(expand=True, fill="both", padx=50, pady=50)
        
        ctk.CTkLabel(
            self.login_frame,
            text="🔐 LOGIN REQUIRED",
            font=("Arial", 28, "bold"),
            text_color="#f87171"
        ).pack(pady=40)
        
        ctk.CTkLabel(
            self.login_frame,
            text="Please login first using the login application.",
            font=("Arial", 16),
            text_color="gray"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            self.login_frame,
            text="Run: python run_login.py",
            font=("Arial", 14, "bold"),
            text_color="#22d3ee"
        ).pack(pady=20)
        
        btn_close = ctk.CTkButton(
            self.login_frame,
            text="CLOSE APPLICATION",
            command=self.destroy,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            width=200,
            height=40
        )
        btn_close.pack(pady=30)
    
    def show_camera_error(self):
        """Tampilkan error kamera tidak bisa diakses"""
        self.camera_frame = ctk.CTkFrame(self, corner_radius=20, fg_color="#162032")
        self.camera_frame.pack(expand=True, fill="both", padx=50, pady=50)
        
        ctk.CTkLabel(
            self.camera_frame,
            text="📷 CAMERA ERROR",
            font=("Arial", 28, "bold"),
            text_color="#f87171"
        ).pack(pady=40)
        
        ctk.CTkLabel(
            self.camera_frame,
            text="Cannot access camera. Please check:\n1. Camera is connected\n2. No other app using camera\n3. Camera permissions",
            font=("Arial", 16),
            text_color="gray"
        ).pack(pady=10)
        
        btn_retry = ctk.CTkButton(
            self.camera_frame,
            text="RETRY CAMERA",
            command=self.retry_camera,
            fg_color="#5B4DBC",
            width=200,
            height=40
        )
        btn_retry.pack(pady=20)
        
        btn_close = ctk.CTkButton(
            self.camera_frame,
            text="CLOSE",
            command=self.destroy,
            fg_color="#dc2626",
            width=200,
            height=40
        )
        btn_close.pack(pady=10)
    
    def retry_camera(self):
        """Coba lagi akses kamera"""
        self.camera_frame.destroy()
        self.cap = cv2.VideoCapture(0)
        if self.cap.isOpened():
            self.setup_ui()
            self.update_frame()
        else:
            self.show_camera_error()
    
    # ================================================================
    # API INTEGRATION LOGIC
    # ================================================================
    
    def api_process_scan(self, qr_code):
        try:
            print(f"🔍 Processing QR: {qr_code}")
            
            # Gunakan API instance yang sudah ada
            response = api.post(f"/Borrowing/ScanQrPeminjaman/{qr_code}")
            
            if isinstance(response, dict):
                self.transaksi_id = response.get("data", {}).get("id")
                
                # Get detail
                detail_response = api.get(f"/Borrowing/GetScanDataByQr/{qr_code}")
                return detail_response
            else:
                return f"Error: Invalid response"
                
        except Exception as e:
            print(f"❌ API Process Scan Error: {e}")
            return f"Connection Error: {str(e)}"
    
    def api_verify_final(self, is_face_ok):
        if not self.transaksi_id: 
            return False
            
        try:
            print(f"✅ Verifying transaction: {self.transaksi_id}")
            
            payload = {
                "isQrVerified": True,
                "isFaceVerified": is_face_ok,
                "verifiedBy": f"Desktop-{self.current_user}"[:30]
            }
            
            response = api.post(f"/Borrowing/VerifyPeminjaman/{self.transaksi_id}", payload)
            return isinstance(response, dict)
            
        except Exception as e:
            print(f"❌ API Verify Error: {e}")
            return False
    
    # ================================================================
    # UI & ENGINE LOGIC
    # ================================================================
    
    def load_known_faces(self):
        """Load known faces from assets folder"""
        if not os.path.exists(self.assets_path): 
            os.makedirs(self.assets_path)
            print(f"📁 Created assets folder: {self.assets_path}")
        
        face_files = [f for f in os.listdir(self.assets_path) 
                     if f.lower().endswith((".jpg", ".png", ".jpeg"))]
        
        if not face_files:
            print("⚠️  No face images found in assets folder")
            return
        
        print(f"📸 Loading {len(face_files)} face images...")
        
        for file in face_files:
            img_path = os.path.join(self.assets_path, file)
            try:
                img = face_recognition.load_image_file(img_path)
                encs = face_recognition.face_encodings(img)
                if encs:
                    self.known_encodings.append(encs[0])
                    self.known_names.append(os.path.splitext(file)[0])
                    print(f"  ✅ Loaded: {file}")
                else:
                    print(f"  ⚠️  No face found in: {file}")
            except Exception as e:
                print(f"  ❌ Error loading {file}: {e}")
        
        print(f"✅ Loaded {len(self.known_encodings)} known faces")
    
    def setup_ui(self):
        """Setup user interface"""
        # Header
        self.header = ctk.CTkFrame(self, height=60, fg_color="#162032")
        self.header.pack(side="top", fill="x")
        
        header_text = ctk.CTkLabel(
            self.header, 
            text=f"🛡️ SIMPEL SCANNER - {self.current_user.upper()}", 
            font=("Arial", 20, "bold"), 
            text_color="#22d3ee"
        )
        header_text.pack(pady=15)
        
        # Container utama
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Video panel (kiri)
        self.video_label = ctk.CTkLabel(
            self.container, 
            text="", 
            corner_radius=20, 
            fg_color="black"
        )
        self.video_label.pack(side="left", expand=True, fill="both", padx=(0, 15))
        
        # Info panel (kanan)
        self.panel = ctk.CTkFrame(
            self.container, 
            width=350, 
            corner_radius=20, 
            fg_color="#162032"
        )
        self.panel.pack(side="right", fill="y")
        
        # User info
        self.welcome_label = ctk.CTkLabel(
            self.panel, 
            text=f"Welcome, {self.current_user.title()}! 👋", 
            font=("Arial", 20, "bold"), 
            text_color="#22d3ee"
        )
        self.welcome_label.pack(pady=(40, 5))
        
        # Status
        self.status_label = ctk.CTkLabel(
            self.panel, 
            text="🔍 Looking for face...", 
            font=("Arial", 14), 
            text_color="gray"
        )
        self.status_label.pack(pady=5)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.panel, width=280)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # QR Info box
        self.qr_info_box = ctk.CTkTextbox(
            self.panel, 
            width=300, 
            height=280, 
            corner_radius=15, 
            fg_color="#0d1b2a",
            text_color="white",
            font=("Arial", 12)
        )
        self.qr_info_box.pack(pady=20, padx=20)
        self.qr_info_box.insert("0.0", "📦 QR Scanner Ready\n\nScan QR code after face verification")
        self.qr_info_box.configure(state="disabled")
        
        # Logout button
        self.btn_logout = ctk.CTkButton(
            self.panel,
            text="LOGOUT",
            command=self.logout,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            width=120,
            height=35
        )
        self.btn_logout.pack(pady=20)
    
    def logout(self):
        """Logout user"""
        print("🔒 Logging out...")
        auth_context.sign_out()
        self.destroy()
        print("👋 Application closed")
    
    def calculate_ear(self, landmarks, eye_indices):
        """Calculate Eye Aspect Ratio"""
        def dist(p1, p2): 
            return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
        
        v1 = dist(landmarks[eye_indices[1]], landmarks[eye_indices[5]])
        v2 = dist(landmarks[eye_indices[2]], landmarks[eye_indices[4]])
        h = dist(landmarks[eye_indices[0]], landmarks[eye_indices[3]])
        
        if h == 0:
            return 0.0
        return (v1 + v2) / (2.0 * h)
    
    def check_liveness_features(self, landmarks):
        """Check liveness features from face landmarks"""
        nose = landmarks[4].x
        re, le = landmarks[234].x, landmarks[454].x
        
        if le - re == 0:
            return []
        
        ratio = (nose - re) / (le - re)
        res = []
        
        if ratio < 0.38: 
            res.append("Tengok Kiri")
        elif ratio > 0.62: 
            res.append("Tengok Kanan")
        
        if abs(landmarks[13].y - landmarks[14].y) > 0.05: 
            res.append("Buka Mulut")
        
        return res
    
    def draw_fancy_border(self, img, pt1, pt2, color):
        """Draw fancy rounded border"""
        x1, y1 = pt1
        x2, y2 = pt2
        r = 20
        
        corners = [
            (x1, y1, 1, 1),    # Top-left
            (x2, y1, -1, 1),   # Top-right
            (x1, y2, 1, -1),   # Bottom-left
            (x2, y2, -1, -1)   # Bottom-right
        ]
        
        for x, y, dx, dy in corners:
            cv2.line(img, (x, y), (x + dx*r, y), color, 3)
            cv2.line(img, (x, y), (x, y + dy*r), color, 3)
    
    def update_frame(self):
        """Main frame update loop"""
        if not self.is_logged_in or not self.cap.isOpened():
            return
        
        ret, frame = self.cap.read()
        if not ret:
            return
        
        self.frame_count += 1
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 1. Face Recognition (every 30 frames)
        if self.frame_count % 30 == 0 and self.known_encodings:
            small_rgb = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
            f_locs = face_recognition.face_locations(small_rgb)
            f_encs = face_recognition.face_encodings(small_rgb, f_locs)
            
            if f_encs:
                matches = face_recognition.compare_faces(
                    self.known_encodings, 
                    f_encs[0], 
                    tolerance=0.5
                )
                
                if True in matches:
                    match_index = matches.index(True)
                    detected_name = self.known_names[match_index]
                    
                    if detected_name != self.current_user:
                        self.current_user = detected_name
                        self.welcome_label.configure(
                            text=f"Hi, {self.current_user.title()}! 👋"
                        )
                        print(f"👤 Face recognized: {self.current_user}")
        
        # 2. Face Mesh & Liveness Detection
        res = self.face_mesh.process(rgb_frame)
        
        if res.multi_face_landmarks:
            lms = res.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]
            
            # Calculate face bounding box
            x_min = int(min([lm.x for lm in lms]) * w)
            y_min = int(min([lm.y for lm in lms]) * h)
            x_max = int(max([lm.x for lm in lms]) * w)
            y_max = int(max([lm.y for lm in lms]) * h)
            
            # Draw border
            border_color = (74, 222, 128) if self.challenge_verified else (0, 211, 238)
            self.draw_fancy_border(frame, (x_min, y_min), (x_max, y_max), border_color)
            
            # Liveness challenge logic
            ear = (self.calculate_ear(lms, self.LEFT_EYE) + 
                   self.calculate_ear(lms, self.RIGHT_EYE)) / 2.0
            
            if ear < 0.23:
                self.eye_closed = True
            elif self.eye_closed and ear > 0.25:
                self.blink_count += 1
                self.eye_closed = False
            
            # Standby countdown
            if not self.is_ready_for_challenge and not self.challenge_verified:
                if self.standby_start_time is None:
                    self.standby_start_time = time.time()
                
                elapsed = time.time() - self.standby_start_time
                countdown = max(0, int(self.standby_duration - elapsed))
                
                if countdown > 0:
                    cv2.putText(
                        frame, f"Ready in: {countdown}s", 
                        (x_min, y_min-30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, 
                        (255, 255, 0), 2
                    )
                    self.status_label.configure(
                        text=f"Bersiap: {countdown}s", 
                        text_color="#fbbf24"
                    )
                else:
                    self.is_ready_for_challenge = True
                    self.status_label.configure(text="Ikuti instruksi!", text_color="#22d3ee")
            
            # Liveness challenge
            if self.is_ready_for_challenge and not self.challenge_verified:
                detected = self.check_liveness_features(lms)
                
                if self.blink_count >= 2:
                    detected.append("Kedip 2x")
                
                target = self.active_challenges[self.current_step]
                
                self.status_label.configure(
                    text=f"Tahap {self.current_step+1}/4: {target}", 
                    text_color="#fbbf24"
                )
                self.progress_bar.set(self.current_step / 4)
                
                cv2.putText(
                    frame, f"Ikuti: {target}", 
                    (x_min, y_min-30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, 
                    (0, 255, 255), 2
                )
                
                if target in detected:
                    self.current_step += 1
                    self.blink_count = 0
                    
                    if self.current_step == 4:
                        self.challenge_verified = True
                        self.status_label.configure(
                            text="✅ Liveness Verified!", 
                            text_color="#4ade80"
                        )
                        self.progress_bar.set(1.0)
                        print("✅ Liveness challenge completed!")
        
        # 3. QR Code Scanning (after liveness verified)
        if self.challenge_verified and not self.is_verified:
            for barcode in decode(frame):
                qr_data = barcode.data.decode('utf-8')
                
                self.status_label.configure(
                    text="🔍 Scanning QR...", 
                    text_color="#fbbf24"
                )
                
                # Decode QR and process
                (x, y, w, h) = barcode.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    frame, "QR Detected", 
                    (x, y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                    (0, 255, 0), 2
                )
                
                res_data = self.api_process_scan(qr_data)
                
                if isinstance(res_data, dict):
                    self.is_verified = True
                    
                    # Display transaction info
                    mhs = res_data.get('mahasiswa', {})
                    info = f"✅ VERIFIKASI BERHASIL\n\n"
                    info += f"👤 Mahasiswa:\n"
                    info += f"   Nama: {mhs.get('nama', 'N/A')}\n"
                    info += f"   NIM: {mhs.get('nim', 'N/A')}\n\n"
                    info += f"📦 Daftar Alat:\n"
                    
                    for item in res_data.get('peminjaman_detail', []):
                        info += f"   - {item.get('nama_alat', 'N/A')}"
                        info += f" [{item.get('status', 'N/A')}]\n"
                    
                    self.qr_info_box.configure(state="normal")
                    self.qr_info_box.delete("0.0", "end")
                    self.qr_info_box.insert("0.0", info)
                    self.qr_info_box.configure(state="disabled")
                    
                    # Final verification
                    if self.api_verify_final(is_face_ok=True):
                        self.status_label.configure(
                            text="✅ Verifikasi Sukses!", 
                            text_color="#4ade80"
                        )
                        print("✅ Transaction verified successfully!")
                    else:
                        self.status_label.configure(
                            text="❌ Verifikasi Gagal", 
                            text_color="#f87171"
                        )
                else:
                    self.status_label.configure(
                        text=f"Error: {str(res_data)[:30]}...", 
                        text_color="#f87171"
                    )
        
        # Convert frame to CTkImage and update display
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        img_ctk = ctk.CTkImage(img_pil, size=(750, 500))
        self.video_label.configure(image=img_ctk)
        
        # Schedule next frame
        self.after(10, self.update_frame)
    
    def on_closing(self):
        """Handle window closing"""
        print("🔒 Cleaning up resources...")
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        self.destroy()

# ================================================================
# MAIN ENTRY POINT
# ================================================================

def start_main_app():
    """Start main application"""
    print("\n" + "="*50)
    print("🚀 LAUNCHING SIMPEL SCANNER")
    print("="*50)
    
    # Disable requests warnings
    requests.packages.urllib3.disable_warnings()
    
    # Create and run app
    app = AppSIMPEL()
    
    # Handle window close
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    app.mainloop()

if __name__ == "__main__":
    # Untuk running langsung (testing mode)
    print("⚠️ Running in direct mode (bypassing login)")
    
    # Simulasi login untuk testing
    try:
        from context.AuthContext import auth_context
        auth_context.sign_in(
            token="dummy_token_for_testing",
            permissions=[
                "dashboard.baca", "dashboard.tulis",
                "master.baca", "master.tulis",
                "alat.baca", "alat.tulis",
                "transaksi.baca", "transaksi.tulis"
            ],
            user_info={
                "username": "admin",
                "nama": "Administrator",
                "app_id": "APP01",
                "role_id": "ROL23"
            }
        )
        print("✅ Test authentication set")
    except Exception as e:
        print(f"⚠️ Failed to set test auth: {e}")
    
    start_main_app()