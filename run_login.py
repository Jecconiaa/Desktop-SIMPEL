# run_login.py
import sys
import os
import subprocess
import customtkinter as ctk
from tkinter import messagebox

# 🔥 PENTING: Setup Path Root Project 🔥
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import komponen lokal
try:
    from app.auth.login import LoginFrame
    from context.AuthContext import auth_context
    print("✅ Module Auth & Login berhasil di-load")
except ImportError as e:
    print(f"❌ Gagal load module: {e}")
    sys.exit(1)

class LoginApp:
    def __init__(self):
        # Setup UI Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Inisialisasi Root Window
        self.root = ctk.CTk()
        self.root.title("🔐 SIMPEL - Secure Login")
        self.root.geometry("500x650")
        
        # Bikin window di tengah layar
        self._center_window(500, 650)
        
        # Cek apakah sudah ada session aktif (Auto-login logic)
        if auth_context.is_authenticated():
            print(f"⚡ Session ditemukan untuk {auth_context.get_username()}, langsung gaskeun!")
            self.root.after(100, self.launch_main_app)
            return

        # Tampilkan Frame Login
        self.login_frame = LoginFrame(self.root, on_login_success=self.handle_login_success)
        self.login_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        print("\n🚀 SIMPEL Login System Ready!")
        print("📡 Server Target: http://127.0.0.1:5234")
        print("="*50)

    def _center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def handle_login_success(self, token):
        """
        Dijalankan pas LoginFrame manggil callback success.
        AuthContext udah otomatis nyimpen token ke session.json di dalem LoginFrame.
        """
        print("\n" + "="*50)
        print(f"🎉 LOGIN BERHASIL!")
        print(f"👤 User: {auth_context.get_username()}")
        print(f"🔑 Token persistent sudah aman di session.json")
        print("="*50)
        
        # Tutup window login dan buka app utama
        self.root.destroy()
        self.launch_main_app()

    def launch_main_app(self):
        """Membuka main.py sebagai proses baru biar fresh"""
        print("\n🚀 Launching main application...")
        
        main_path = os.path.join(project_root, "main.py")
        
        if not os.path.exists(main_path):
            messagebox.showerror("Error", f"File {main_path} tidak ditemukan!")
            return

        try:
            # Kita pake subprocess.Popen supaya script ini (run_login) bisa beneran close
            # dan script main.py jalan di environment Python yang sama (venv)
            python_executable = sys.executable
            subprocess.Popen([python_executable, main_path])
            
            print("✅ Main scanner app started. Closing login process...")
            sys.exit(0)
            
        except Exception as e:
            print(f"❌ Gagal buka main app: {e}")
            messagebox.showerror("Launch Error", f"Gagal buka scanner:\n{str(e)}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    try:
        app = LoginApp()
        # Kalo root masih ada (gak langsung auto-login), jalanin mainloop
        if hasattr(app, 'root') and app.root.winfo_exists():
            app.run()
    except KeyboardInterrupt:
        print("\n👋 App closed by user")