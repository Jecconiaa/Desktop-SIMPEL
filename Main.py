import customtkinter as ctk
import cv2
import face_recognition
import numpy as np
import os
import sys
import time
import random
from PIL import Image
from pyzbar.pyzbar import decode
import urllib3

# Nonaktifkan peringatan SSL buat lokal
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
        self.admin_session = auth_context.get_username()

        # --- WINDOW CONFIG ---
        self.title(" 🛡️ SIMPEL - Scanner Desktop ")
        self.geometry("1200x800")
        self.after(0, lambda: self.state('zoomed')) 
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- FACE DATABASE ---
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces() 

        # --- ENGINES ---
        self.face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True, min_detection_confidence=0.6)
        self.list_pilihan_challenge = ["Tengok Kanan", "Tengok Kiri", "Kedip 2x", "Buka Mulut"]
        
        self.reset_all_states()
        self.setup_ui() 
        
        # Init Camera
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
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
                        name = os.path.splitext(filename)[0].replace("_", " ").title()
                        self.known_face_names.append(name)
                except: pass
        print(f"✅ Database Loaded: {self.known_face_names}")

    def reset_all_states(self):
        self.current_state = 'STANDBY_FACE' 
        self.state_start_time = None
        self.identified_user = None 
        self.blink_count = 0
        self.eye_closed = False
        self.active_challenge = random.choice(self.list_pilihan_challenge)
        self.EYE_AR_THRESH = 0.20
        self.LEFT_EYE = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE = [33, 160, 158, 133, 153, 144]

    def setup_ui(self):
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#162032")
        self.header.pack(side="top", fill="x")
        ctk.CTkLabel(self.header, text="🛡️ SIMPEL SCANNER SYSTEM", font=("Arial", 22, "bold"), text_color="#22d3ee").pack(pady=15)
        
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(expand=True, fill="both", padx=20, pady=20)

        self.right_panel = ctk.CTkFrame(self.main_container, width=380, corner_radius=20, fg_color="#162032")
        self.right_panel.pack(side="right", fill="y", padx=(20, 0))
        self.right_panel.pack_propagate(False)

        self.welcome_label = ctk.CTkLabel(self.right_panel, text="MENGENALI WAJAH...", font=("Arial", 20, "bold"), text_color="#22d3ee")
        self.welcome_label.pack(pady=(60, 5))
        
        self.status_label = ctk.CTkLabel(self.right_panel, text="SISTEM STANDBY", font=("Arial", 14), text_color="gray")
        self.status_label.pack(pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(self.right_panel, width=300); self.progress_bar.pack(pady=20); self.progress_bar.set(0)
        
        self.qr_info_box = ctk.CTkTextbox(self.right_panel, width=320, height=350, corner_radius=15, fg_color="#0d1b2a", font=("Arial", 13))
        self.qr_info_box.pack(pady=10, padx=20); self.qr_info_box.insert("0.0", "📦 STATUS: READY"); self.qr_info_box.configure(state="disabled")

        self.btn_logout = ctk.CTkButton(self.right_panel, text="LOGOUT & EXIT", command=self.logout, fg_color="#dc2626", hover_color="#b91c1c", height=45, font=("Arial", 13, "bold"))
        self.btn_logout.pack(side="bottom", pady=30)

        self.video_container = ctk.CTkFrame(self.main_container, corner_radius=20, fg_color="black")
        self.video_container.pack(side="left", expand=True, fill="both")
        self.video_label = ctk.CTkLabel(self.video_container, text="")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

    def update_frame(self):
        if not self.cap.isOpened(): return
        ret, frame = self.cap.read()
        if not ret: return
        frame = cv2.flip(frame, 1)
        display_frame = frame.copy()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self.face_mesh.process(rgb_frame)
        
        if res.multi_face_landmarks:
            lms = res.multi_face_landmarks[0].landmark
            self.process_logic(display_frame, lms, frame)
        else:
            if self.current_state not in ['SCAN_QR', 'SUCCESS']:
                self.reset_ui_to_idle()

        self.render_to_ui(display_frame)
        self.after(10, self.update_frame)

    def reset_ui_to_idle(self):
        self.reset_all_states()
        self.welcome_label.configure(text="MENGENALI WAJAH...", text_color="#22d3ee")
        self.status_label.configure(text="SISTEM STANDBY", text_color="gray")
        self.progress_bar.set(0)

    def process_logic(self, display_frame, lms, raw_frame):
        h, w, _ = display_frame.shape
        x_min, y_min = int(lms[234].x * w), int(lms[10].y * h)
        x_max, y_max = int(lms[454].x * w), int(lms[152].y * h)

        if self.current_state == 'STANDBY_FACE':
            self.draw_fancy_border(display_frame, (x_min, y_min), (x_max, y_max), (0, 211, 238))
            self.state_start_time = time.time()
            self.current_state = 'LOCKING_FACE'

        elif self.current_state == 'LOCKING_FACE':
            self.draw_fancy_border(display_frame, (x_min, y_min), (x_max, y_max), (0, 211, 238))
            elapsed = time.time() - self.state_start_time
            if elapsed < 2.5:
                self.progress_bar.set(elapsed / 2.5)
            if elapsed > 1.0 and self.identified_user is None:
                # Resize frame
                small = cv2.resize(raw_frame, (0, 0), fx=0.25, fy=0.25)

                # ===== DETEKSI (GRAYSCALE, PALING STABIL) =====
                gray_small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                gray_small = np.ascontiguousarray(gray_small, dtype=np.uint8)

                face_locs = face_recognition.face_locations(
                    gray_small,
                    number_of_times_to_upsample=0,
                    model="hog"
                )

                # ===== ENCODING (RGB) =====
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                rgb_small = np.ascontiguousarray(rgb_small, dtype=np.uint8)

                face_encs = face_recognition.face_encodings(rgb_small, face_locs)

                for face_encoding in face_encs:
                    matches = face_recognition.compare_faces(
                        self.known_face_encodings,
                        face_encoding,
                        tolerance=0.5
                    )

                    if True in matches:
                        idx = matches.index(True)
                        self.identified_user = self.known_face_names[idx]
                        self.welcome_label.configure(
                            text=f"Hi, {self.identified_user}!",
                            text_color="#4ade80"
                        )
                    else:
                        self.welcome_label.configure(
                            text="WAJAH TIDAK DIKENAL",
                            text_color="#f87171"
                        )

            else:
                if self.identified_user is not None:
                    self.state_start_time = time.time()
                    self.current_state = 'STANDBY_CHALLENGE'
                else:
                    self.status_label.configure(text="AKSES DITOLAK: WAJAH ASING", text_color="#f87171")
                    if elapsed > 5.0: self.reset_ui_to_idle()

        elif self.current_state == 'STANDBY_CHALLENGE':
            self.draw_fancy_border(display_frame, (x_min, y_min), (x_max, y_max), (251, 191, 36))
            elapsed = time.time() - self.state_start_time
            countdown = 3 - int(elapsed)
            if countdown > 0:
                self.status_label.configure(text=f"SIAP-SIAP! ({countdown})", text_color="#fbbf24")
                cv2.putText(display_frame, str(countdown), (w//2-40, h//2+50), cv2.FONT_HERSHEY_DUPLEX, 5, (255, 255, 255), 10)
                self.progress_bar.set(elapsed / 3.0)
            else:
                self.current_state = 'CHALLENGE'
                self.progress_bar.set(0)

        elif self.current_state == 'CHALLENGE':
            self.draw_fancy_border(display_frame, (x_min, y_min), (x_max, y_max), (251, 191, 36))
            target = self.active_challenge
            self.status_label.configure(text=f"TUGAS: {target.upper()}", text_color="#fbbf24")
            detected = self.check_liveness_features(lms)
            self.handle_blink(lms)
            if self.blink_count >= 2: detected.append("Kedip 2x")
            if target in detected:
                self.current_state = 'SCAN_QR'
                self.progress_bar.set(1.0)

        elif self.current_state == 'SCAN_QR':
            self.draw_fancy_border(display_frame, (x_min, y_min), (x_max, y_max), (74, 222, 128))
            self.status_label.configure(text="WAJAH OK! SILAKAN SCAN QR", text_color="#4ade80")
            qr_data = self.detect_qr(raw_frame)
            if qr_data:
                res_data = self.api_process_scan(qr_data)
                if res_data:
                    self.handle_scan_success(res_data)
                    self.current_state = 'SUCCESS'

    def handle_blink(self, lms):
        ear = (self.calculate_ear(lms, self.LEFT_EYE) + self.calculate_ear(lms, self.RIGHT_EYE)) / 2.0
        if ear < self.EYE_AR_THRESH: self.eye_closed = True
        elif self.eye_closed and ear > (self.EYE_AR_THRESH + 0.05):
            self.blink_count += 1
            self.eye_closed = False

    def detect_qr(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        processed = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        qrs = decode(processed) or decode(gray)
        return qrs[0].data.decode('utf-8') if qrs else None

    # ⭐ UPDATED LOGIC: Partial Return & Finalization
    def api_process_scan(self, qr_code):
        try:
            # 1. Ambil data status barang terkini
            res_data = self.api.get(f"/api/Borrowing/GetScanDataByQr/{qr_code}")
            
            if not res_data or not res_data.get('peminjaman_detail'):
                self.status_label.configure(text="QR TIDAK TERDAFTAR!", text_color="#f87171")
                return None

            items = res_data.get('peminjaman_detail', [])
            # Ambil status sampel dari item pertama
            first_status = items[0].get('status', '').lower()
            
            mode = "INFO"
            action_res = None
            
            # --- LOGIC DECISION ---
            
            # A. FASE PEMINJAMAN (Serah Terima Awal)
            if first_status == "booked":
                action_res = self.api.post(f"/api/Borrowing/ScanQrPeminjaman/{qr_code}")
                mode = "PEMINJAMAN"

            # B. FASE PENGEMBALIAN / VERIFIKASI
            # Status bisa 'dipinjam' atau 'dikembalikan' (campur)
            elif first_status in ["dipinjam", "dikembalikan"]:
                # Cek apakah SEMUA item sudah dikembalikan via Mobile?
                all_returned = all(item.get('status', '').lower() == 'dikembalikan' for item in items)
                
                if all_returned:
                    # ✅ FINALISASI: Semua alat sudah balik, Administrator 'tutup' transaksi
                    action_res = self.api.post(f"/api/Borrowing/ScanQrPengembalian/{qr_code}")
                    mode = "SELESAI"
                else:
                    # ⚠️ PARTIAL: Belum semua balik, cuma verifikasi status fisik
                    # Kita set 'action_res' dummy success agar UI tetap update data
                    action_res = {"success": True, "message": "Verification Only"}
                    mode = "VERIFIKASI"

            else:
                 # Status lain: 'selesai', 'hilang', dll -> Cuma tampilkan info
                 action_res = {"success": True}
                 mode = "INFO"

            # ----------------------

            # 4. Handle Unauthorized (401)
            if action_res == 401 or (isinstance(action_res, dict) and action_res.get("status") == 401):
                self.welcome_label.configure(text="SESI HABIS!", text_color="#f87171")
                return None

            # 5. Jika sukses (atau sekedar verifikasi), ambil data terbaru untuk UI
            if action_res and (isinstance(action_res, dict) and action_res.get("success") or True):
                # Fetch ulang biar dapat status paling fresh (misal setelah POST)
                updated_data = self.api.get(f"/api/Borrowing/GetScanDataByQr/{qr_code}")
                if updated_data:
                    updated_data['current_mode'] = mode
                    return updated_data
            return None

        except Exception as e:
            print(f"API Error: {e}"); return None

    # ⭐ UPDATED UI: Dynamic Display
    def handle_scan_success(self, res_data):
        mhs = res_data.get('mahasiswa', {})
        items = res_data.get('peminjaman_detail', [])
        mode = res_data.get('current_mode', 'INFO')
        
        # Header Text Logic
        if mode == "PEMINJAMAN":
            header = "✅ PEMINJAMAN SUKSES"
        elif mode == "SELESAI":
            header = "🏁 TRANSAKSI SELESAI"
        elif mode == "VERIFIKASI":
            header = "📋 CEK STATUS BARANG"
        else:
            header = "ℹ️ INFO TRANSAKSI"
        
        info = (f"{header}\n👤 {mhs.get('nama')}\n🆔 NIM: {mhs.get('nim')}\n"
                f"--------------------------\n📦 DETAIL STATUS:\n")
        
        if items:
            for i, item in enumerate(items, 1):
                raw_status = item.get('status', '').lower()
                status_icon = "✅" if raw_status == 'dikembalikan' else "⏳" if raw_status == 'dipinjam' else "📦"
                info += f" {i}. {item.get('nama_alat')} [{status_icon} {raw_status.upper()}]\n"
        else:
            info += " (Tidak ada data alat)\n"
            
        info += (f"--------------------------\n📢 MODE: {mode}")
        
        self.qr_info_box.configure(state="normal")
        self.qr_info_box.delete("0.0", "end")
        self.qr_info_box.insert("0.0", info)
        self.qr_info_box.configure(state="disabled")
        self.after(10000, self.reset_total)

    def reset_total(self):
        self.reset_ui_to_idle()
        self.qr_info_box.configure(state="normal")
        self.qr_info_box.delete("0.0", "end")
        self.qr_info_box.insert("0.0", "📦 STATUS: READY")
        self.qr_info_box.configure(state="disabled")

    def calculate_ear(self, lms, idx):
        def d(p1, p2): return ((p1.x - p2.x)**2 + (p1.y - p2.y)**2)**0.5
        return (d(lms[idx[1]], lms[idx[5]]) + d(lms[idx[2]], lms[idx[4]])) / (2.0 * d(lms[idx[0]], lms[idx[3]]))

    def check_liveness_features(self, lms):
        nose, re, le = lms[4].x, lms[234].x, lms[454].x
        ratio = (nose - re) / (le - re) if (le - re) != 0 else 0.5
        res = []
        if ratio < 0.35: res.append("Tengok Kiri")
        elif ratio > 0.65: res.append("Tengok Kanan")
        if abs(lms[13].y - lms[14].y) > 0.05: res.append("Buka Mulut")
        return res

    def draw_fancy_border(self, img, pt1, pt2, color):
        x1, y1, x2, y2, r = pt1[0], pt1[1], pt2[0], pt2[1], 25
        for p in [(x1,y1,1,1), (x2,y1,-1,1), (x1,y2,1,-1), (x2,y2,-1,-1)]:
            cv2.line(img, (p[0], p[1]), (p[0] + p[2]*r, p[1]), color, 4)
            cv2.line(img, (p[0], p[1]), (p[0], p[1] + p[3]*r), color, 4)

    def render_to_ui(self, frame):
        try:
            w, h = self.video_label.winfo_width(), self.video_label.winfo_height()
            if w > 100 and h > 100:
                img = ctk.CTkImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), size=(w, h))
                self.video_label.configure(image=img)
        except: pass

    def logout(self):
        auth_context.sign_out()
        if hasattr(self, 'cap'): self.cap.release()
        self.destroy(); sys.exit(0)

    def show_login_required(self):
        ctk.CTkLabel(self, text="🔐 HARAP LOGIN").pack(expand=True)
        self.after(2000, self.destroy)

if __name__ == "__main__":
    app = AppSIMPEL(); app.mainloop()