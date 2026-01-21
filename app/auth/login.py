# app/auth/login.py
import customtkinter as ctk
from tkinter import messagebox
import threading
import sys
import os

# 🔥 FIX IMPORT PATH 🔥
# Dapetin project root path
current_file = os.path.abspath(__file__)  # C:\College\WEB P4\Desktop-SIMPEL\app\auth\login.py
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))  # C:\College\WEB P4\Desktop-SIMPEL

# Tambah project_root ke sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"🔍 Project root: {project_root}")

# Import module kita
try:
    from context.AuthContext import auth_context
    from lib.api import init_api
    from lib.api_base import get_api_base_url
    print("✅ Import berhasil!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    # Coba import dengan cara lain
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
        
        # Initialize API
        from lib.api import init_api
        
        print("✅ Import berhasil dengan cara manual!")
    except Exception as e2:
        print(f"❌ Manual import juga gagal: {e2}")
        sys.exit(1)

# Initialize API dengan base URL
api_base_url = get_api_base_url()
print(f"🌐 API Base URL: {api_base_url}")
api = init_api(api_base_url)


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        """
        Frame login untuk desktop app.
        
        Args:
            master: Parent window (ctk.CTk)
            on_login_success: Callback function ketika login berhasil
        """
        super().__init__(master, corner_radius=20, fg_color="#162032")
        
        self.master = master
        self.on_login_success = on_login_success
        
        # Setup UI
        self.setup_ui()
        
        # Bind Enter key untuk login
        self.master.bind('<Return>', lambda e: self.handle_login())
    
    def setup_ui(self):
        """Setup semua UI components"""
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(40, 20))
        
        ctk.CTkLabel(
            self.header_frame,
            text="🔐 SIMPEL LOGIN",
            font=("Arial", 24, "bold"),
            text_color="#22d3ee"
        ).pack()
        
        ctk.CTkLabel(
            self.header_frame,
            text="Desktop Scanner Application",
            font=("Arial", 12),
            text_color="gray"
        ).pack(pady=(5, 0))
        
        # Form container
        self.form_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.form_frame.pack(pady=20, padx=40)
        
        # Username field
        ctk.CTkLabel(
            self.form_frame,
            text="Username",
            font=("Arial", 14, "bold"),
            text_color="white"
        ).pack(anchor="w", pady=(10, 5))
        
        self.entry_user = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="admin",
            width=300,
            height=45,
            corner_radius=10,
            font=("Arial", 14)
        )
        self.entry_user.pack(pady=(0, 15))
        self.entry_user.insert(0, "admin")  # Default value untuk testing
        
        # Password field
        ctk.CTkLabel(
            self.form_frame,
            text="Password",
            font=("Arial", 14, "bold"),
            text_color="white"
        ).pack(anchor="w", pady=(10, 5))
        
        self.entry_pass = ctk.CTkEntry(
            self.form_frame,
            placeholder_text="••••••",
            show="•",
            width=300,
            height=45,
            corner_radius=10,
            font=("Arial", 14)
        )
        self.entry_pass.pack(pady=(0, 20))
        self.entry_pass.insert(0, "asd")  # ⚠️ Password sesuai BE
        
        # Jenis Aplikasi (hidden field)
        self.jenis_aplikasi = "Public"  # ⚠️ Sesuai BE
        
        # Login button
        self.btn_login = ctk.CTkButton(
            self.form_frame,
            text="SIGN IN",
            command=self.handle_login,
            fg_color="#5B4DBC",
            hover_color="#4A3D9C",
            width=300,
            height=50,
            corner_radius=10,
            font=("Arial", 16, "bold")
        )
        self.btn_login.pack(pady=(10, 5))
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.form_frame,
            text="",
            font=("Arial", 12),
            text_color="gray"
        )
        self.status_label.pack(pady=10)
        
        # Error label
        self.error_label = ctk.CTkLabel(
            self.form_frame,
            text="",
            font=("Arial", 12),
            text_color="#f87171"
        )
        self.error_label.pack()
        
        # API Info
        api_url = get_api_base_url() + "/api/Auth/login"
        ctk.CTkLabel(
            self,
            text=f"API: {api_url}",
            font=("Arial", 10),
            text_color="gray"
        ).pack(pady=(20, 30))
    
    def handle_login(self):
        """Handle login button click"""
        # Get input values
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        
        # Validation
        if not username or not password:
            self.show_error("Username dan password harus diisi")
            return
        
        # Disable button dan show loading
        self.btn_login.configure(
            text="MEMPROSES...",
            state="disabled",
            fg_color="gray"
        )
        self.status_label.configure(text="Menghubungi server...")
        self.error_label.configure(text="")
        
        # Run login in background thread (biar UI tidak freeze)
        threading.Thread(target=self._perform_login, args=(username, password), daemon=True).start()
    
    def _perform_login(self, username: str, password: str):
        """Perform login in background thread"""
        try:
            # Step 1: Login ke API
            self._update_status("Login ke server...")
            
            print(f"🔐 Login dengan: username={username}, jenis_aplikasi={self.jenis_aplikasi}")
            
            login_data = api.login(
                username=username,
                password=password,
                jenis_aplikasi=self.jenis_aplikasi
            )
            
            token = login_data.get("token")
            if not token:
                raise Exception("Token tidak ditemukan dalam response")
            
            print(f"✅ Token diterima: {token[:50]}...")
            
            # Step 2: Get permissions
            self._update_status("Mengambil permissions...")
            
            # Cari appId dan roleId dari listAplikasi
            list_aplikasi = login_data.get("listAplikasi", [])
            if not list_aplikasi:
                raise Exception("Tidak ada aplikasi yang tersedia")
            
            # Ambil app pertama (APP01) - adjust sesuai kebutuhan
            app_info = list_aplikasi[0]
            app_id = app_info.get("appId", "APP01")
            role_id = app_info.get("roleId", "ROL23")
            
            print(f"📱 App ID: {app_id}, Role ID: {role_id}")
            
            permission_data = api.get_permission(
                username=username,
                app_id=app_id,
                role_id=role_id
            )
            
            final_token = permission_data.get("token")
            permissions = permission_data.get("listPermission", [])
            
            if not final_token:
                raise Exception("Final token tidak ditemukan")
            
            print(f"✅ Final token: {final_token[:50]}...")
            print(f"✅ Permissions: {len(permissions)} items")
            
            # Step 3: Save to auth context
            self._update_status("Menyimpan session...")
            
            auth_context.sign_in(
                token=final_token,
                permissions=permissions,
                user_info={
                    "username": username,
                    "nama": login_data.get("nama", ""),
                    "app_id": app_id,
                    "role_id": role_id,
                    "expires_at": permission_data.get("expiresAt", ""),
                    "list_aplikasi": list_aplikasi
                }
            )
            
            # Step 4: Success - call callback di main thread
            self.master.after(0, self._login_success, final_token)
            
        except Exception as e:
            # Show error di main thread
            print(f"❌ Error detail: {type(e).__name__}: {str(e)}")
            self.master.after(0, self._login_failed, str(e))
    
    def _update_status(self, message: str):
        """Update status label from background thread"""
        self.master.after(0, lambda: self.status_label.configure(text=message))
    
    def _login_success(self, token: str):
        """Handle successful login"""
        self.status_label.configure(text="Login berhasil!", text_color="#4ade80")
        
        # Reset button
        self.btn_login.configure(
            text="SIGN IN",
            state="normal",
            fg_color="#5B4DBC"
        )
        
        # Call callback
        if self.on_login_success:
            self.on_login_success(token)
    
    def _login_failed(self, error_message: str):
        """Handle failed login"""
        self.error_label.configure(text=f"Error: {error_message}")
        self.status_label.configure(text="Login gagal", text_color="#f87171")
        
        # Reset button
        self.btn_login.configure(
            text="SIGN IN",
            state="normal",
            fg_color="#5B4DBC"
        )
        
        # Show detailed error untuk debugging
        print(f"❌ Login error: {error_message}")
    
    def show_error(self, message: str):
        """Show error message"""
        self.error_label.configure(text=message)
        self.error_label.after(5000, lambda: self.error_label.configure(text=""))


# Test function
if __name__ == "__main__":
    # Untuk testing standalone
    app = ctk.CTk()
    app.title("Login Test")
    app.geometry("500x600")
    
    def on_login_success(token):
        print(f"Login berhasil! Token: {token[:50]}...")
        messagebox.showinfo("Success", "Login berhasil!")
    
    login_frame = LoginFrame(app, on_login_success)
    login_frame.pack(expand=True, fill="both", padx=20, pady=20)
    
    app.mainloop() 