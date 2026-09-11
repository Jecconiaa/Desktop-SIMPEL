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
from pyzbar.pyzbar import decode, ZBarSymbol
import urllib3
import torch
import torch.nn as nn

# Import InsightFace
from insightface.app import FaceAnalysis

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from context.AuthContext import auth_context
    from lib.api import init_api
    from lib.api_base import get_api_base_url
except ImportError:
    print("❌ Import Error")
    sys.exit(1)


# ============================================================
# MiniFASNet V1 SE
# Arsitektur dibuat sama dengan model yang dipakai saat training.
# ============================================================
class MiniFASNetBlock(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1):
        super().__init__()
        self.conv = nn.Conv2d(
            in_ch, out_ch, 3,
            stride=stride,
            padding=1,
            bias=False
        )
        self.bn = nn.BatchNorm2d(out_ch)
        self.relu = nn.ReLU(inplace=True)

        if stride != 1 or in_ch != out_ch:
            self.down = nn.Sequential(
                nn.Conv2d(
                    in_ch, out_ch, 1,
                    stride=stride,
                    bias=False
                ),
                nn.BatchNorm2d(out_ch)
            )
        else:
            self.down = nn.Identity()

    def forward(self, x):
        return self.relu(self.bn(self.conv(x)) + self.down(x))


class SEModule(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels, channels // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(channels // reduction, channels, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        b, c, _, _ = x.size()
        y = self.avg_pool(x).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        return x * y.expand_as(x)


class MiniFASNetV1SE(nn.Module):
    def __init__(self, num_classes=2, channels=(64, 128, 128, 256, 256)):
        super().__init__()

        self.stem = nn.Sequential(
            nn.Conv2d(3, channels[0], 3, padding=1, bias=False),
            nn.BatchNorm2d(channels[0]),
            nn.ReLU(inplace=True)
        )

        blocks = []
        in_ch = channels[0]

        for i, out_ch in enumerate(channels[1:]):
            stride = 2 if i % 2 == 0 else 1
            blocks.append(
                MiniFASNetBlock(
                    in_ch,
                    out_ch,
                    stride=stride
                )
            )
            blocks.append(SEModule(out_ch))
            in_ch = out_ch

        self.blocks = nn.Sequential(*blocks)
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.drop = nn.Dropout(0.5)
        self.fc = nn.Linear(in_ch, num_classes)

    def forward(self, x):
        x = self.stem(x)
        x = self.blocks(x)
        x = self.gap(x).flatten(1)
        x = self.drop(x)
        return self.fc(x)


class AppSIMPEL(ctk.CTk):
    def __init__(self):
        super().__init__()

        # API & Auth
        self.auth = auth_context
        self.api_base_url = get_api_base_url()
        self.api = init_api(self.api_base_url)

        if not self.auth.is_authenticated():
            self.show_login_required()
            return

        self.api.set_token(self.auth.get_token())

        # Threshold Face Recognition InsightFace
        self.FR_THRESHOLD = 0.45
        self.BR_THRESHOLD = 95
        self.clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )

        # ====================================================
        # InsightFace: Detection + Recognition
        # ====================================================
        print("Loading InsightFace...")
        self.face_app = FaceAnalysis(
            name='buffalo_l',
            root=os.path.join(project_root, 'models')
        )
        self.face_app.prepare(
            ctx_id=-1,
            det_size=(640, 640)
        )

        # ====================================================
        # MiniFASNet V1 SE: Liveness / Anti-Spoofing
        # ====================================================
        self.liveness_device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.liveness_model = None
        self.liveness_classes = []
        self.real_class_index = None
        self.liveness_model_path = None

        # 3 prediksi REAL berturut-turut sebelum akses dilanjutkan.
        # Ini mencegah satu frame salah klasifikasi langsung lolos.
        self.LIVENESS_REQUIRED_STREAK = 3

        # IMPORTANT: model custom ini dilatih dari gambar dataset yang langsung
        # di-Resize(224x224), bukan dengan pipeline crop scale 2x/4x ala model
        # MiniFASNet official. Karena deployment dengan margin=0.50 membuat input
        # terlalu berbeda dan pada pengujian nyata terkunci sebagai SPOOF, gunakan
        # margin 0.20 (crop ~1.4x bbox) yang lebih dekat dengan framing sebelumnya.
        self.LIVENESS_CROP_MARGIN = 0.20

        # Setelah kepala kembali frontal, beri waktu singkat supaya motion blur
        # akibat gerakan challenge hilang sebelum frame pertama masuk MiniFASNet.
        self.LIVENESS_STABILIZE_SECONDS = 0.40
        self.liveness_ready_at = 0.0

        # Setelah challenge selesai, user WAJIB kembali frontal sebelum
        # MiniFASNet mulai menilai REAL/SPOOF.
        self.FRONT_RATIO_MIN = 0.42
        self.FRONT_RATIO_MAX = 0.58
        self.RETURN_FRONT_REQUIRED_STREAK = 2

        # Toleransi hilangnya bbox sesaat ketika user menoleh.
        # Session baru di-reset jika wajah benar-benar hilang cukup lama.
        self.NO_FACE_RESET_SECONDS = 1.5

        self.load_liveness_model()

        # Window
        self.title("SIMPEL - InsightFace + MiniFASNet V1 SE")
        self.geometry("1280x720")
        self.after(0, lambda: self.state('zoomed'))
        ctk.set_appearance_mode("dark")

        # Engines
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_known_faces()

        # Threading Flags
        self.face_data_lock = threading.Lock()
        self.is_qr_processing = False
        self.is_detecting_face = False
        self.is_identifying_face = False
        self.is_liveness_processing = False

        self.cached_face_locations = None
        self.cached_face_embedding = None
        self.cached_face_kps = None  # 5-point landmark dari InsightFace untuk challenge

        # Versi landmark bertambah setiap hasil detector baru. Ini penting agar
        # streak challenge dihitung dari sampel InsightFace yang benar-benar
        # berbeda, bukan frame UI yang memakai landmark cache yang sama.
        self.cached_kps_version = 0
        self.last_challenge_kps_version = -1
        self.last_return_front_kps_version = -1

        self.last_detect_time = 0
        self.last_identify_time = 0
        self.last_liveness_time = 0

        # ====================================================
        # ACTIVE CHALLENGE
        # Dipilih random setiap QR valid terbaca.
        # Challenge yang baru tidak mengulang challenge sebelumnya
        # supaya user berikutnya tidak selalu mendapat tugas yang sama.
        # ====================================================
        self.CHALLENGE_OPTIONS = [
            "Tengok Kiri",
            "Tengok Kanan",
            "Senyum"
        ]
        self.last_challenge = None

        self.reset_all_states()
        self.setup_ui()

        # Camera
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.update_frame()

    # ========================================================
    # LOAD MINIFASNET V1 SE
    # ========================================================
    def load_liveness_model(self):
        model_dir = os.path.join(project_root, "models")
        os.makedirs(model_dir, exist_ok=True)

        # Bisa memakai nama hasil save seperti:
        # minifasnet_v1_se_epoch37.pth
        candidates = []

        for filename in os.listdir(model_dir):
            lower = filename.lower()
            if (
                lower.startswith("minifasnet_v1_se")
                and lower.endswith(".pth")
            ):
                candidates.append(os.path.join(model_dir, filename))

        if not candidates:
            raise FileNotFoundError(
                "Model MiniFASNet V1 SE tidak ditemukan. "
                "Taruh file minifasnet_v1_se*.pth di folder models/"
            )

        # Kalau ada beberapa file, pakai yang paling baru.
        model_path = max(candidates, key=os.path.getmtime)
        self.liveness_model_path = model_path

        print(f"Loading MiniFASNet V1 SE: {model_path}")
        print(f"Liveness device: {self.liveness_device}")

        # Kompatibel dengan checkpoint lengkap maupun state_dict biasa.
        try:
            checkpoint = torch.load(
                model_path,
                map_location=self.liveness_device,
                weights_only=False
            )
        except TypeError:
            checkpoint = torch.load(
                model_path,
                map_location=self.liveness_device
            )

        if (
            isinstance(checkpoint, dict)
            and "model_state_dict" in checkpoint
        ):
            state_dict = checkpoint["model_state_dict"]
            classes = checkpoint.get("classes", ["Real", "Spoof"])
            num_classes = checkpoint.get(
                "num_classes",
                len(classes)
            )
        else:
            # Untuk file yang isinya langsung model.state_dict()
            state_dict = checkpoint
            classes = ["Real", "Spoof"]
            num_classes = 2

        self.liveness_classes = list(classes)

        self.liveness_model = MiniFASNetV1SE(
            num_classes=num_classes
        )
        self.liveness_model.load_state_dict(state_dict)
        self.liveness_model.to(self.liveness_device)
        self.liveness_model.eval()

        # Jangan hardcode index kelas. Ambil dari metadata checkpoint.
        real_names = {
            "real",
            "live",
            "genuine",
            "bonafide",
            "bona_fide",
            "bona-fide"
        }

        for idx, class_name in enumerate(self.liveness_classes):
            if str(class_name).strip().lower() in real_names:
                self.real_class_index = idx
                break

        if self.real_class_index is None:
            raise ValueError(
                "Kelas REAL tidak ditemukan pada checkpoint. "
                f"Classes yang terbaca: {self.liveness_classes}"
            )

        print("✅ MiniFASNet V1 SE Loaded")
        print(f"   Classes: {self.liveness_classes}")
        print(
            "   REAL index: "
            f"{self.real_class_index} "
            f"({self.liveness_classes[self.real_class_index]})"
        )

    def apply_enhancement(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if np.mean(gray) < self.BR_THRESHOLD:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            enhanced_l = self.clahe.apply(l)

            return (
                cv2.cvtColor(
                    cv2.merge([enhanced_l, a, b]),
                    cv2.COLOR_LAB2BGR
                ),
                True
            )

        return frame, False

    # Fungsi ngitung tingkat kemiripan embedding wajah
    def cosine_similarity(self, embedding1, embedding2):
        return np.dot(
            embedding1,
            embedding2
        ) / (
            np.linalg.norm(embedding1)
            * np.linalg.norm(embedding2)
        )

    def load_known_faces(self):
        path = os.path.join(project_root, "assets")

        if not os.path.exists(path):
            return

        for f in os.listdir(path):
            if f.lower().endswith((".jpg", ".png", ".jpeg")):
                img = cv2.imread(os.path.join(path, f))
                enhanced, _ = self.apply_enhancement(img)
                rgb = cv2.cvtColor(
                    enhanced,
                    cv2.COLOR_BGR2RGB
                )

                # Ekstrak fitur wajah pake InsightFace
                faces = self.face_app.get(rgb)

                if faces:
                    self.known_face_encodings.append(
                        faces[0].normed_embedding
                    )
                    self.known_face_names.append(
                        os.path.splitext(f)[0]
                        .replace("_", " ")
                        .title()
                    )

        print(
            f"✅ DB Loaded: "
            f"{len(self.known_face_names)} faces"
        )

    def setup_ui(self):
        self.header = ctk.CTkFrame(
            self,
            height=60,
            corner_radius=0,
            fg_color="#162032"
        )
        self.header.pack(side="top", fill="x")

        ctk.CTkButton(
            self.header,
            text="LOGOUT",
            width=100,
            fg_color="#dc2626",
            command=self.logout
        ).pack(side="left", padx=20)

        ctk.CTkLabel(
            self.header,
            text="Sistem Peminjaman Alat laboratorium P4",
            font=("Arial", 20, "bold"),
            text_color="#22d3ee"
        ).pack(pady=15)

        self.video_frame = ctk.CTkFrame(
            self,
            fg_color="black"
        )
        self.video_frame.pack(
            expand=True,
            fill="both"
        )

        self.video_label = tk.Label(
            self.video_frame,
            bg="black"
        )
        self.video_label.pack(
            expand=True,
            fill="both"
        )

    def reset_all_states(self):
        self.current_state = 'STANDBY'
        self.identified_user = None
        self.current_qr_data = None

        # Challenge baru dipilih saat QR valid berhasil dibaca.
        # Verifikasi challenge memakai 5-point landmark InsightFace.
        # MiniFASNet tetap menjadi anti-spoofing setelah challenge lolos.
        self.active_challenge = None
        self.challenge_streak = 0
        self.CHALLENGE_REQUIRED_STREAK = 2
        self.challenge_ratio = 0.5
        self.last_challenge_kps_version = -1

        # State setelah challenge: tunggu user kembali menghadap depan.
        self.return_front_streak = 0
        self.last_return_front_kps_version = -1

        # Timestamp untuk toleransi kehilangan wajah sementara.
        self.face_missing_since = None

        # State khusus challenge Senyum.
        # Rasio = lebar mulut / jarak antar mata.
        # Baseline diambil saat QR baru terbaca, sebelum user melakukan senyum.
        self.smile_baseline_ratio = None
        self.smile_ratio = 0.0

        # State liveness MiniFASNet
        self.liveness_label = None
        self.liveness_confidence = 0.0
        self.liveness_is_real = False
        self.liveness_real_streak = 0
        self.liveness_ready_at = 0.0

    # --- WORKERS (ASYNCHRONOUS) ---

    def detect_face_worker(self, frame_copy):
        try:
            # Enhancement
            processed, _ = self.apply_enhancement(frame_copy)
            rgb = cv2.cvtColor(
                processed,
                cv2.COLOR_BGR2RGB
            )

            # InsightFace nyari semua wajah di frame
            faces = self.face_app.get(rgb)

            with self.face_data_lock:
                if faces:
                    # MediaPipe sudah dihapus.
                    # Wajah utama = bbox InsightFace paling besar.
                    main_face = max(
                        faces,
                        key=lambda f: (
                            (f.bbox[2] - f.bbox[0])
                            * (f.bbox[3] - f.bbox[1])
                        )
                    )

                    self.cached_face_locations = (
                        main_face.bbox.astype(int)
                    )
                    self.cached_face_embedding = (
                        main_face.normed_embedding
                    )

                    # InsightFace detector menyediakan 5 keypoints:
                    # dua mata, hidung, dua sudut mulut.
                    self.cached_face_kps = (
                        None
                        if getattr(main_face, "kps", None) is None
                        else np.asarray(main_face.kps).copy()
                    )
                    self.cached_kps_version += 1
                else:
                    self.cached_face_locations = None
                    self.cached_face_embedding = None
                    self.cached_face_kps = None

                    # Saat belum ada session QR, hasil recognition boleh dihapus.
                    # Saat challenge/liveness aktif, identity dipertahankan selama
                    # grace period. Jika wajah hilang > NO_FACE_RESET_SECONDS,
                    # reset_all_states() akan menghapus session secara penuh.
                    if self.current_qr_data is None:
                        self.identified_user = None

                    self.liveness_label = None
                    self.liveness_confidence = 0.0
                    self.liveness_is_real = False
                    self.liveness_real_streak = 0

        finally:
            self.is_detecting_face = False

    def identify_face_worker(self):
        try:
            # Nyocokin wajah pake Cosine Similarity dari cache
            with self.face_data_lock:
                locs = self.cached_face_locations
                embedding = self.cached_face_embedding

            if locs is None or embedding is None:
                return

            if self.known_face_encodings:
                similarities = [
                    self.cosine_similarity(
                        embedding,
                        enc
                    )
                    for enc in self.known_face_encodings
                ]

                idx = np.argmax(similarities)

                with self.face_data_lock:
                    if similarities[idx] >= self.FR_THRESHOLD:
                        self.identified_user = (
                            self.known_face_names[idx]
                        )
                    else:
                        self.identified_user = "UNKNOWN"

        finally:
            self.is_identifying_face = False

    # ========================================================
    # PREPROCESSING MINIFASNET
    # Sama dengan testing transform waktu training:
    # Resize 224x224 -> ToTensor -> Normalize(0.5, 0.5)
    # ========================================================
    def preprocess_liveness_face(self, face_crop):
        rgb = cv2.cvtColor(
            face_crop,
            cv2.COLOR_BGR2RGB
        )
        rgb = cv2.resize(
            rgb,
            (224, 224),
            interpolation=cv2.INTER_LINEAR
        )

        tensor = torch.from_numpy(rgb).float() / 255.0
        tensor = tensor.permute(2, 0, 1)

        # Equivalent dengan Normalize([0.5]*3, [0.5]*3)
        tensor = (tensor - 0.5) / 0.5

        return tensor.unsqueeze(0).to(
            self.liveness_device
        )

    def crop_face_for_liveness(self, frame, bbox, margin=0.20):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        face_w = max(1, x2 - x1)
        face_h = max(1, y2 - y1)

        margin_x = int(face_w * margin)
        margin_y = int(face_h * margin)

        x1 = max(0, x1 - margin_x)
        y1 = max(0, y1 - margin_y)
        x2 = min(w, x2 + margin_x)
        y2 = min(h, y2 + margin_y)

        if x2 <= x1 or y2 <= y1:
            return None

        return frame[y1:y2, x1:x2].copy()

    def liveness_worker(self, frame_copy, bbox):
        try:
            face_crop = self.crop_face_for_liveness(
                frame_copy,
                bbox,
                margin=self.LIVENESS_CROP_MARGIN
            )

            if face_crop is None or face_crop.size == 0:
                return

            input_tensor = self.preprocess_liveness_face(
                face_crop
            )

            with torch.inference_mode():
                logits = self.liveness_model(input_tensor)
                probs = torch.softmax(logits, dim=1)[0]

                pred_index = int(
                    torch.argmax(probs).item()
                )
                confidence = float(
                    probs[pred_index].item()
                )

            pred_label = str(
                self.liveness_classes[pred_index]
            )
            is_real = (
                pred_index == self.real_class_index
            )

            with self.face_data_lock:
                self.liveness_label = pred_label
                self.liveness_confidence = confidence
                self.liveness_is_real = is_real

                if is_real:
                    self.liveness_real_streak += 1
                else:
                    self.liveness_real_streak = 0

            print(
                f"🛡️ Liveness: {pred_label} | "
                f"confidence={confidence:.4f} | "
                f"real_streak={self.liveness_real_streak}"
            )

        except Exception as e:
            print(f"❌ MiniFASNet Liveness Error: {e}")

            with self.face_data_lock:
                self.liveness_label = None
                self.liveness_confidence = 0.0
                self.liveness_is_real = False
                self.liveness_real_streak = 0

        finally:
            self.is_liveness_processing = False

    # ========================================================
    # ACTIVE CHALLENGE TANPA MEDIAPIPE
    # - Tengok Kiri/Kanan: posisi hidung terhadap kedua mata
    # - Senyum: perubahan lebar mulut relatif terhadap jarak mata
    # Semua memakai 5-point landmark InsightFace.
    # ========================================================
    def calculate_head_ratio(self, kps):
        """
        Rasio posisi hidung terhadap kedua mata.
        Nilai sekitar 0.5 = wajah relatif frontal.
        """
        if kps is None or len(kps) < 3:
            return None

        eye_x1 = float(kps[0][0])
        eye_x2 = float(kps[1][0])
        nose_x = float(kps[2][0])

        left_x = min(eye_x1, eye_x2)
        right_x = max(eye_x1, eye_x2)
        eye_distance_x = right_x - left_x

        if eye_distance_x < 1.0:
            return None

        return (nose_x - left_x) / eye_distance_x

    def calculate_smile_ratio(self, kps):
        """
        Hitung rasio lebar mulut terhadap jarak antar mata.
        InsightFace 5-point landmark:
        0 = mata, 1 = mata, 2 = hidung, 3 = sudut mulut, 4 = sudut mulut.
        Rasio dibuat relatif supaya lebih stabil terhadap jarak user ke kamera.
        """
        if kps is None or len(kps) < 5:
            return None

        eye_1 = np.asarray(kps[0], dtype=np.float32)
        eye_2 = np.asarray(kps[1], dtype=np.float32)
        mouth_1 = np.asarray(kps[3], dtype=np.float32)
        mouth_2 = np.asarray(kps[4], dtype=np.float32)

        eye_distance = float(np.linalg.norm(eye_2 - eye_1))
        mouth_width = float(np.linalg.norm(mouth_2 - mouth_1))

        if eye_distance < 1.0:
            return None

        return mouth_width / eye_distance

    def choose_random_challenge(self):
        """
        Pilih satu dari 3 challenge secara random.
        Challenge berturut-turut tidak dibuat sama supaya user berikutnya
        tidak langsung mendapat challenge yang sama dengan user sebelumnya.
        """
        choices = [
            c for c in self.CHALLENGE_OPTIONS
            if c != self.last_challenge
        ]

        # Fallback, walaupun secara normal choices selalu berisi 2 item.
        if not choices:
            choices = self.CHALLENGE_OPTIONS.copy()

        selected = random.choice(choices)
        self.last_challenge = selected
        return selected

    def check_active_challenge(self, kps, kps_version):
        if kps is None or self.active_challenge is None:
            self.challenge_streak = 0
            return False

        # Jangan hitung landmark cache yang sama berkali-kali dari loop UI.
        if kps_version == self.last_challenge_kps_version:
            return False
        self.last_challenge_kps_version = kps_version

        try:
            ratio = self.calculate_head_ratio(kps)

            if ratio is None:
                self.challenge_streak = 0
                return False

            self.challenge_ratio = ratio
            passed_now = False

            # Karena frame kamera di-mirror, jika kiri/kanan terasa kebalik
            # di perangkat, tukar operator pada dua kondisi berikut.
            if self.active_challenge == "Tengok Kiri":
                passed_now = ratio < 0.38

            elif self.active_challenge == "Tengok Kanan":
                passed_now = ratio > 0.62

            elif self.active_challenge == "Senyum":
                current_smile_ratio = self.calculate_smile_ratio(kps)

                if current_smile_ratio is None:
                    self.challenge_streak = 0
                    return False

                self.smile_ratio = current_smile_ratio

                # Kalau baseline belum sempat diambil saat QR scan,
                # ambil dari frame pertama challenge sebagai fallback.
                if self.smile_baseline_ratio is None:
                    self.smile_baseline_ratio = current_smile_ratio
                    self.challenge_streak = 0
                    return False

                # Senyum harus memperlebar jarak dua sudut mulut dibanding
                # baseline. Wajah juga harus relatif frontal saat senyum.
                required_smile_ratio = max(
                    self.smile_baseline_ratio * 1.08,
                    self.smile_baseline_ratio + 0.05
                )

                head_is_frontal = (
                    self.FRONT_RATIO_MIN
                    <= ratio
                    <= self.FRONT_RATIO_MAX
                )

                passed_now = (
                    head_is_frontal
                    and current_smile_ratio >= required_smile_ratio
                )

            if passed_now:
                self.challenge_streak += 1
            else:
                self.challenge_streak = 0

            if self.challenge_streak >= self.CHALLENGE_REQUIRED_STREAK:
                if self.active_challenge == "Senyum":
                    detail = (
                        f"smile={self.smile_ratio:.3f} | "
                        f"baseline={self.smile_baseline_ratio:.3f}"
                    )
                else:
                    detail = f"ratio={ratio:.3f}"

                print(
                    f"✅ Challenge lolos: {self.active_challenge} | "
                    f"{detail}"
                )

                # Jangan langsung jalankan MiniFASNet ketika kepala masih
                # menoleh. Minta user kembali frontal terlebih dahulu.
                self.current_state = 'RETURN_FRONT'
                self.return_front_streak = 0
                self.last_return_front_kps_version = -1

                self.liveness_label = None
                self.liveness_confidence = 0.0
                self.liveness_is_real = False
                self.liveness_real_streak = 0
                return True

        except Exception as e:
            print(f"⚠️ Challenge InsightFace Error: {e}")
            self.challenge_streak = 0

        return False

    def check_return_front(self, kps, kps_version):
        """
        Setelah challenge lolos, pastikan user sudah kembali menghadap
        kamera sebelum MiniFASNet anti-spoofing mulai bekerja.
        """
        if kps is None:
            self.return_front_streak = 0
            return False

        # Sama seperti challenge: hanya proses hasil InsightFace yang baru.
        if kps_version == self.last_return_front_kps_version:
            return False
        self.last_return_front_kps_version = kps_version

        ratio = self.calculate_head_ratio(kps)

        if ratio is None:
            self.return_front_streak = 0
            return False

        self.challenge_ratio = ratio

        is_frontal = (
            self.FRONT_RATIO_MIN
            <= ratio
            <= self.FRONT_RATIO_MAX
        )

        if is_frontal:
            self.return_front_streak += 1
        else:
            self.return_front_streak = 0

        if self.return_front_streak >= self.RETURN_FRONT_REQUIRED_STREAK:
            print(
                "✅ Wajah kembali frontal. "
                f"ratio={ratio:.3f} -> mulai MiniFASNet"
            )

            self.current_state = 'LIVENESS'
            self.liveness_label = None
            self.liveness_confidence = 0.0
            self.liveness_is_real = False
            self.liveness_real_streak = 0

            # Jangan langsung klasifikasi frame transisi setelah kepala bergerak.
            # Tunggu sebentar agar blur/pose residual dari challenge mereda.
            self.liveness_ready_at = time.time() + self.LIVENESS_STABILIZE_SECONDS
            self.last_liveness_time = 0
            return True

        return False

    def update_frame(self):
        ret, frame = self.cap.read()

        if not ret:
            return

        frame = cv2.flip(frame, 1)
        display_frame = frame.copy()
        now = time.time()

        # ====================================================
        # 1. FACE DETECTION
        # ====================================================
        if (
            not self.is_detecting_face
            and (now - self.last_detect_time > 0.5)
        ):
            self.last_detect_time = now
            self.is_detecting_face = True

            threading.Thread(
                target=self.detect_face_worker,
                args=(frame.copy(),),
                daemon=True
            ).start()

        # ====================================================
        # 2. FACE RECOGNITION
        # ====================================================
        if (
            not self.is_identifying_face
            and self.cached_face_locations is not None
            and self.current_qr_data is None
            and (now - self.last_identify_time > 1.2)
        ):
            self.last_identify_time = now
            self.is_identifying_face = True

            threading.Thread(
                target=self.identify_face_worker,
                daemon=True
            ).start()

        # ====================================================
        # 3. QR BARU BOLEH DISCAN SETELAH WAJAH DIKENALI
        # ====================================================
        if (
            self.identified_user is not None
            and self.identified_user != "UNKNOWN"
            and self.current_qr_data is None
            and self.current_state == 'STANDBY'
            and int(now * 10) % 5 == 0
            and not self.is_qr_processing
        ):
            self.is_qr_processing = True

            threading.Thread(
                target=self.qr_worker,
                args=(frame.copy(),),
                daemon=True
            ).start()

        # ====================================================
        # 4. MINIFASNET BARU JALAN SETELAH CHALLENGE LOLOS
        #    DAN WAJAH SUDAH KEMBALI FRONTAL
        # ====================================================
        if (
            not self.is_liveness_processing
            and self.cached_face_locations is not None
            and self.current_qr_data
            and self.identified_user is not None
            and self.identified_user != "UNKNOWN"
            and self.current_state == 'LIVENESS'
            and now >= self.liveness_ready_at
            and (now - self.last_liveness_time > 0.35)
        ):
            self.last_liveness_time = now
            self.is_liveness_processing = True

            with self.face_data_lock:
                bbox = self.cached_face_locations.copy()

            threading.Thread(
                target=self.liveness_worker,
                args=(frame.copy(), bbox),
                daemon=True
            ).start()

        # ====================================================
        # UI DATA
        # ====================================================
        with self.face_data_lock:
            bbox_for_ui = (
                None
                if self.cached_face_locations is None
                else self.cached_face_locations.copy()
            )

            kps_for_ui = (
                None
                if self.cached_face_kps is None
                else self.cached_face_kps.copy()
            )
            kps_version_for_ui = self.cached_kps_version

        if bbox_for_ui is not None:
            # Wajah kembali terlihat -> batalkan timer kehilangan wajah.
            self.face_missing_since = None

            self.process_ui_logic(
                display_frame,
                bbox_for_ui,
                kps_for_ui,
                kps_version_for_ui
            )
        else:
            # Jangan langsung reset ketika detector kehilangan wajah 1 frame,
            # karena hal itu bisa terjadi saat challenge tengok kiri/kanan.
            if self.current_state not in [
                'PROCESSING_API',
                'SUCCESS'
            ]:
                if self.face_missing_since is None:
                    self.face_missing_since = now

                if (
                    now - self.face_missing_since
                    >= self.NO_FACE_RESET_SECONDS
                ):
                    print("⚠️ Wajah hilang terlalu lama. Session di-reset.")
                    self.reset_all_states()

        self.render_ui(display_frame)
        self.after(33, self.update_frame)

    def process_ui_logic(self, img, bbox, kps=None, kps_version=-1):
        h, w, _ = img.shape

        x_min, y_min, x_max, y_max = [
            int(v) for v in bbox
        ]

        x_min = max(0, min(w - 1, x_min))
        y_min = max(0, min(h - 1, y_min))
        x_max = max(0, min(w - 1, x_max))
        y_max = max(0, min(h - 1, y_max))

        cx = (x_min + x_max) // 2
        text_y = max(30, y_min - 30)

        # ====================================================
        # FLOW:
        # FACE RECOGNITION -> QR -> CHALLENGE -> KEMBALI FRONTAL
        # -> MINIFASNET -> API
        # ====================================================

        # 1. Wajah belum selesai dikenali
        if self.identified_user is None:
            self.draw_text(
                img,
                "MENGENALI WAJAH...",
                cx,
                text_y,
                (255, 255, 0)
            )

        # 2. Wajah tidak dikenal: QR tidak akan diproses
        elif self.identified_user == "UNKNOWN":
            self.draw_text(
                img,
                "WAJAH TIDAK DIKENAL",
                cx,
                text_y,
                (0, 0, 255)
            )

        # 3. Face recognition lolos, tunggu QR
        elif not self.current_qr_data:
            self.draw_text(
                img,
                "SCAN QR DULU",
                cx,
                text_y,
                (50, 50, 255)
            )

        # 4. QR terbaca -> challenge aktif muncul
        elif self.current_state == 'CHALLENGE':
            self.draw_text(
                img,
                f"TASK: {self.active_challenge} "
                f"[{self.challenge_streak}/"
                f"{self.CHALLENGE_REQUIRED_STREAK}]",
                cx,
                text_y,
                (255, 150, 0)
            )

            self.check_active_challenge(kps, kps_version)

        # 5. Challenge lolos -> user harus kembali menghadap depan
        elif self.current_state == 'RETURN_FRONT':
            self.draw_text(
                img,
                f"HADAP DEPAN KEMBALI "
                f"[{self.return_front_streak}/"
                f"{self.RETURN_FRONT_REQUIRED_STREAK}]",
                cx,
                text_y,
                (255, 255, 0)
            )

            self.check_return_front(kps, kps_version)

        # 6. Sudah frontal -> MiniFASNet cek REAL/SPOOF
        elif self.current_state == 'LIVENESS':
            if self.liveness_label is None:
                self.draw_text(
                    img,
                    "CHALLENGE OK - CEK LIVENESS...",
                    cx,
                    text_y,
                    (255, 150, 0)
                )
            else:
                confidence_pct = (
                    self.liveness_confidence * 70.0
                )

                if self.liveness_is_real:
                    color = (0, 255, 0)
                    status_text = (
                        f"LIVENESS: REAL "
                        f"{confidence_pct:.1f}% "
                        f"[{self.liveness_real_streak}/"
                        f"{self.LIVENESS_REQUIRED_STREAK}]"
                    )
                else:
                    color = (0, 0, 255)
                    status_text = (
                        f"LIVENESS: SPOOF "
                        f"{confidence_pct:.1f}%"
                    )

                self.draw_text(
                    img,
                    status_text,
                    cx,
                    text_y,
                    color
                )

            # REAL harus lolos beberapa prediksi berturut-turut.
            if (
                self.liveness_is_real
                and self.liveness_real_streak
                >= self.LIVENESS_REQUIRED_STREAK
            ):
                self.current_state = 'PROCESSING_API'

                threading.Thread(
                    target=self.run_api,
                    args=(self.current_qr_data,),
                    daemon=True
                ).start()

        elif self.current_state == 'PROCESSING_API':
            self.draw_text(
                img,
                "MOHON TUNGGU...",
                cx,
                text_y,
                (255, 255, 0)
            )

        elif self.current_state == 'SUCCESS':
            self.draw_text(
                img,
                "AKSES DITERIMA",
                cx,
                text_y,
                (0, 255, 0)
            )

        # User label
        if self.identified_user:
            color = (
                (0, 255, 0)
                if self.identified_user != "UNKNOWN"
                else (0, 0, 255)
            )

            self.draw_text(
                img,
                f"USER: {self.identified_user}",
                cx,
                min(h - 10, y_max + 40),
                color
            )

        cv2.rectangle(
            img,
            (x_min, y_min),
            (x_max, y_max),
            (255, 255, 255),
            2
        )

    def render_ui(self, frame):
        try:
            w_lbl = self.video_label.winfo_width()
            h_lbl = self.video_label.winfo_height()

            if w_lbl > 100:
                img = cv2.resize(
                    frame,
                    (w_lbl, h_lbl),
                    interpolation=cv2.INTER_LINEAR
                )
                img = Image.fromarray(
                    cv2.cvtColor(
                        img,
                        cv2.COLOR_BGR2RGB
                    )
                )

                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

        except:
            pass

    def qr_worker(self, frame):
        try:
            decoded = decode(
                cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2GRAY
                ),
                symbols=[ZBarSymbol.QRCODE]
            )

            # QR hanya diterima jika wajah sudah dikenali.
            if (
                decoded
                and self.identified_user is not None
                and self.identified_user != "UNKNOWN"
                and self.current_qr_data is None
            ):
                self.current_qr_data = (
                    decoded[0].data.decode('utf-8')
                )

                # Begitu QR valid terbaca, pilih 1 dari 3 challenge
                # secara random: Tengok Kiri / Tengok Kanan / Senyum.
                self.active_challenge = self.choose_random_challenge()
                self.challenge_streak = 0
                self.last_challenge_kps_version = -1
                self.return_front_streak = 0
                self.last_return_front_kps_version = -1
                self.current_state = 'CHALLENGE'

                # Ambil baseline mulut tepat saat QR dibaca.
                # Baseline hanya digunakan jika challenge yang terpilih = Senyum.
                self.smile_baseline_ratio = None
                self.smile_ratio = 0.0

                if self.active_challenge == "Senyum":
                    with self.face_data_lock:
                        kps_snapshot = (
                            None
                            if self.cached_face_kps is None
                            else self.cached_face_kps.copy()
                        )

                    self.smile_baseline_ratio = (
                        self.calculate_smile_ratio(kps_snapshot)
                    )

                    if self.smile_baseline_ratio is not None:
                        print(
                            "🙂 Baseline senyum: "
                            f"{self.smile_baseline_ratio:.3f}"
                        )

                # Reset hasil liveness lama.
                self.liveness_label = None
                self.liveness_confidence = 0.0
                self.liveness_is_real = False
                self.liveness_real_streak = 0

                print(
                    f"📱 QR terbaca. Mulai challenge: "
                    f"{self.active_challenge}"
                )

        finally:
            self.is_qr_processing = False

    def draw_text(self, img, text, x, y, color):
        cv2.putText(
            img,
            text,
            (x - 80, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            3
        )
        cv2.putText(
            img,
            text,
            (x - 80, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2
        )

    def run_api(self, qr):
        try:
            res = self.api.get(
                f"/api/Borrowing/GetScanDataByQr/{qr}"
            )

            if not res or not res.get('peminjaman_detail'):
                print("❌ Invalid QR or no data")
                self.after(2000, self.reset_all_states)
                return

            status = res.get('status', '').lower()
            print(f"📦 Status: {status}")

            if status == 'dipinjam':
                final_res = self.api.post(
                    f"/api/Borrowing/ScanQrPengembalian/{qr}"
                )
                print("✅ POST ScanQrPengembalian called")

            elif status == 'booked':
                final_res = self.api.post(
                    f"/api/Borrowing/ScanQrPeminjaman/{qr}"
                )
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

        if hasattr(self, 'cap'):
            self.cap.release()

        self.destroy()
        sys.exit(0)

    def show_login_required(self):
        ctk.CTkLabel(
            self,
            text="🔑 LOGIN REQUIRED"
        ).pack(expand=True)
        self.after(2000, self.destroy)


if __name__ == "__main__":
    app = AppSIMPEL()
    app.mainloop()