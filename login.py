# login.py
import customtkinter as ctk
import requests

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login_success, api_base_url):
        super().__init__(master, corner_radius=20, fg_color="#162032")
        self.on_login_success = on_login_success
        self.api_base_url = api_base_url
        
        # Setup UI biar __init__ gak kepanjangan
        self.setup_ui()

    def setup_ui(self):
        ctk.CTkLabel(self, text="SIMPEL LOGIN", font=("Arial", 20, "bold"), text_color="#22d3ee").pack(pady=(30, 20))
        
        # Entry Username sesuai field 'Username' di DTO
        self.entry_user = ctk.CTkEntry(self, placeholder_text="Username", width=250, height=40)
        self.entry_user.pack(pady=10, padx=30)
        
        # Entry Password sesuai field 'Password' di DTO
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=250, height=40)
        self.entry_pass.pack(pady=10, padx=30)
        
        self.btn_login = ctk.CTkButton(self, text="LOGIN", command=self.handle_login, fg_color="#5B4DBC", width=250, height=40)
        self.btn_login.pack(pady=(20, 30))
        
        self.error_label = ctk.CTkLabel(self, text="", text_color="#f87171", font=("Arial", 12))
        self.error_label.pack()

    def handle_login(self):
        # Payload WAJIB lengkap sesuai LoginRequestDto.cs
        payload = {
            "Username": self.entry_user.get(),
            "Password": self.entry_pass.get(),
            "JenisAplikasi": "Desktop" # Wajib diisi agar tidak error 400
        }
        
        try:
            # Tembak endpoint Auth/login di BE lu
            url = f"{self.api_base_url}/Auth/login"
            res = requests.post(url, json=payload, verify=False, timeout=5)
            
            if res.status_code == 200:
                token = res.json().get("token") # Ambil token dari response
                print("✅ Login Berhasil!")
                self.on_login_success(token) # Lempar token ke Main.py
            else:
                # Kalo error 400 atau 401, tampilin pesan dari BE
                self.error_label.configure(text=f"Login Gagal ({res.status_code})")
        except Exception as e:
            self.error_label.configure(text="Gagal konek ke Server BE!")