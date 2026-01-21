# run_login.py
import sys
import os

# Setup path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import customtkinter as ctk
from tkinter import messagebox
from app.auth.login import LoginFrame

def main():
    """Main entry point"""
    print("\n" + "="*50)
    print("🛡️  SIMPEL - Desktop Scanner Application")
    print("="*50)
    
    # Setup CTk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Create window
    root = ctk.CTk()
    root.title("🔐 SIMPEL - Login")
    root.geometry("500x650")
    
    # Center window
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    window_width = 500
    window_height = 650
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def on_login_success(token):
        """Callback ketika login berhasil"""
        print(f"\n" + "="*50)
        print(f"✅ LOGIN BERHASIL!")
        print(f"🔑 Token: {token[:50]}...")
        print("="*50)
        
        # Import AuthContext untuk cek state
        try:
            from context.AuthContext import auth_context
            print(f"👤 User: {auth_context.get_username()}")
            print(f"📋 Permissions: {len(auth_context.get_permissions())} items")
        except:
            pass
        
        # Close login window
        root.destroy()
        
        # Launch main application
        launch_main_app()
    
    # Create login frame
    login_frame = LoginFrame(root, on_login_success)
    login_frame.pack(expand=True, fill="both", padx=20, pady=20)
    
    print("\n🚀 Login screen ready!")
    print("📡 API URL: http://127.0.0.1:5234")
    print("👤 Default: admin / asd")
    print("="*50 + "\n")
    
    # Start main loop
    root.mainloop()

def launch_main_app():
    """Launch main application setelah login berhasil"""
    print("\n🚀 Launching main application...")
    
    try:
        # Import main.py
        import importlib.util
        main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        
        if not os.path.exists(main_path):
            raise FileNotFoundError(f"main.py tidak ditemukan: {main_path}")
        
        # Load main module
        spec = importlib.util.spec_from_file_location("main_app", main_path)
        main_module = importlib.util.module_from_spec(spec)
        sys.modules["main_app"] = main_module
        spec.loader.exec_module(main_module)
        
        # Check which method to call
        if hasattr(main_module, 'start_main_app'):
            print("✅ Found start_main_app() method")
            main_module.start_main_app()
        elif hasattr(main_module, 'AppSIMPEL'):
            print("✅ Found AppSIMPEL class")
            app = main_module.AppSIMPEL()
            app.mainloop()
        else:
            raise AttributeError("No start_main_app() or AppSIMPEL class found")
            
        print("\n👋 Main application closed.")
        
    except Exception as e:
        print(f"❌ Failed to launch main app: {e}")
        import traceback
        traceback.print_exc()
        
        # Show error message
        messagebox.showerror(
            "Launch Error",
            f"Gagal membuka aplikasi utama:\n\n{str(e)}\n\nSilakan run main.py secara manual."
        )
        
        # Option to run main.py directly
        if messagebox.askyesno("Run Manual", "Jalankan main.py secara manual?"):
            import subprocess
            subprocess.run([sys.executable, "main.py"])

if __name__ == "__main__":
    main()