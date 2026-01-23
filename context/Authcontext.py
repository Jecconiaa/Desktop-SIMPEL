# context/AuthContext.py
import json
import threading
import os
from typing import Optional, List, Dict, Any, Callable

class AuthContext:
    """
    AuthContext singleton untuk manage authentication state dengan fitur Persistence.
    Biar token nggak ilang pas pindah script atau aplikasi di-restart.
    """
    
    _instance = None
    _lock = threading.Lock()
    # Nama file buat nyimpen session (disimpen di root project)
    _session_file = "session.json"
    
    def __new__(cls):
        """Singleton pattern biar instance-nya cuma satu di seluruh app"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize dengan default values dan coba load session lama"""
        self._token: Optional[str] = None
        self._permissions: List[str] = []
        self._user_info: Dict[str, Any] = {}
        self._is_authenticated = False
        self._listeners: List[Callable] = []
        
        # 🔥 Langsung coba load data pas app baru jalan
        self._load_session_from_file()
        print("🔧 AuthContext initialized (Persistent Mode)")
    
    # ============ PERSISTENCE LOGIC (FILE SYSTEM) ============

    def _save_session_to_file(self):
        """Simpan state saat ini ke file JSON"""
        try:
            data = {
                "token": self._token,
                "permissions": self._permissions,
                "user_info": self._user_info,
                "is_authenticated": self._is_authenticated
            }
            with open(self._session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            # print(f"💾 Session saved to {self._session_file}")
        except Exception as e:
            print(f"❌ Gagal simpan session ke file: {e}")

    def _load_session_from_file(self):
        """Load data dari file JSON pas startup"""
        if os.path.exists(self._session_file):
            try:
                with open(self._session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._token = data.get("token")
                    self._permissions = data.get("permissions", [])
                    self._user_info = data.get("user_info", {})
                    self._is_authenticated = data.get("is_authenticated", False)
                if self._is_authenticated:
                    print(f"✅ Session restored for: {self.get_username()}")
            except Exception as e:
                print(f"⚠️ Gagal load session file: {e}")

    # ============ PUBLIC METHODS ============
    
    def sign_in(self, token: str, permissions: List[str] = None, user_info: Dict = None):
        """Sign in user, simpan state, dan tulis ke file"""
        with self._lock:
            self._token = token
            self._permissions = permissions or []
            self._user_info = user_info or {}
            self._is_authenticated = True
            
            # Simpan ke file biar permanen
            self._save_session_to_file()
            
            print(f"✅ AuthContext: User signed in")
            print(f"   Username: {self.get_username()}")
            print(f"   Permissions: {len(self._permissions)} items")
            
            self._notify_listeners()
    
    def sign_out(self):
        """Clear semua data dan hapus file session"""
        with self._lock:
            username = self.get_username()
            self._token = None
            self._permissions = []
            self._user_info = {}
            self._is_authenticated = False
            
            # Hapus file session pas logout
            if os.path.exists(self._session_file):
                try:
                    os.remove(self._session_file)
                except:
                    pass
            
            print(f"✅ AuthContext: User '{username}' signed out")
            self._notify_listeners()
    
    def is_authenticated(self) -> bool:
        """Cek apakah user sudah login (cek variable & token)"""
        return self._is_authenticated and self._token is not None

    def get_token(self) -> Optional[str]:
        return self._token
    
    def get_permissions(self) -> List[str]:
        return self._permissions.copy()
    
    def get_user_info(self) -> Dict[str, Any]:
        return self._user_info.copy()
    
    def get_username(self) -> str:
        return self._user_info.get('username', '')
    
    def get_nama(self) -> str:
        return self._user_info.get('nama', '')

    def has_permission(self, permission: str) -> bool:
        return permission in self._permissions

    # ============ LISTENER MANAGEMENT ============
    
    def add_listener(self, callback: Callable):
        if callback not in self._listeners:
            self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable):
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        for listener in self._listeners:
            try:
                listener()
            except Exception as e:
                print(f"⚠️ Error notifying listener: {e}")

# ============ GLOBAL SINGLETON INSTANCE ============

# Export instance tunggal
auth_context = AuthContext()

__all__ = ['AuthContext', 'auth_context']