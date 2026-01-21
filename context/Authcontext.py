# context/AuthContext.py
import json
import threading
from typing import Optional, List, Dict, Any, Callable


class AuthContext:
    """
    AuthContext singleton untuk manage authentication state.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize dengan default values"""
        self._token: Optional[str] = None
        self._permissions: List[str] = []
        self._user_info: Dict[str, Any] = {}
        self._is_authenticated = False
        self._listeners: List[Callable] = []
        print("🔧 AuthContext initialized")
    
    # ============ PUBLIC METHODS ============
    
    def sign_in(self, token: str, permissions: List[str] = None, user_info: Dict = None):
        """
        Sign in user dan simpan state.
        
        Args:
            token: JWT token dari API
            permissions: List permission dari getpermission endpoint
            user_info: User info dari login response
        """
        with self._lock:
            self._token = token
            self._permissions = permissions or []
            self._user_info = user_info or {}
            self._is_authenticated = True
            
            print(f"✅ AuthContext: User signed in")
            print(f"   Username: {self._user_info.get('username', 'Unknown')}")
            print(f"   Token: {'***' + token[-10:] if token else 'None'}")
            print(f"   Permissions: {len(self._permissions)} items")
            
            self._notify_listeners()
    
    def sign_out(self):
        """Clear semua auth data"""
        with self._lock:
            username = self._user_info.get('username', 'Unknown')
            self._token = None
            self._permissions = []
            self._user_info = {}
            self._is_authenticated = False
            
            print(f"✅ AuthContext: User '{username}' signed out")
            self._notify_listeners()
    
    def has_permission(self, permission: str) -> bool:
        """
        Cek apakah user punya permission tertentu.
        
        Args:
            permission: Permission string (contoh: "dashboard.baca")
            
        Returns:
            True jika punya permission
        """
        return permission in self._permissions
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """
        Cek apakah user punya minimal satu dari list permission.
        """
        return any(self.has_permission(p) for p in permissions)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """
        Cek apakah user punya semua permission dalam list.
        """
        return all(self.has_permission(p) for p in permissions)
    
    def get_token(self) -> Optional[str]:
        """Ambil current token"""
        return self._token
    
    def get_permissions(self) -> List[str]:
        """Ambil semua permissions (copy)"""
        return self._permissions.copy()
    
    def get_user_info(self) -> Dict[str, Any]:
        """Ambil user info (copy)"""
        return self._user_info.copy()
    
    def get_username(self) -> str:
        """Ambil username"""
        return self._user_info.get('username', '')
    
    def get_nama(self) -> str:
        """Ambil nama user"""
        return self._user_info.get('nama', '')
    
    def get_app_id(self) -> str:
        """Ambil app ID"""
        return self._user_info.get('app_id', '')
    
    def get_role_id(self) -> str:
        """Ambil role ID"""
        return self._user_info.get('role_id', '')
    
    def is_authenticated(self) -> bool:
        """Cek apakah user sudah login"""
        return self._is_authenticated
    
    # ============ LISTENER MANAGEMENT ============
    
    def add_listener(self, callback: Callable):
        """Tambah listener untuk auth state changes"""
        if callback not in self._listeners:
            self._listeners.append(callback)
            print(f"👂 Listener added, total: {len(self._listeners)}")
    
    def remove_listener(self, callback: Callable):
        """Hapus listener"""
        if callback in self._listeners:
            self._listeners.remove(callback)
            print(f"👂 Listener removed, total: {len(self._listeners)}")
    
    def _notify_listeners(self):
        """Notify semua listeners bahwa auth state berubah"""
        for listener in self._listeners:
            try:
                listener()
            except Exception as e:
                print(f"⚠️ Error notifying listener: {e}")
    
    # ============ DEBUG & UTILITY ============
    
    def print_state(self):
        """Print current auth state untuk debugging"""
        print("\n" + "="*50)
        print("🧾 AUTH CONTEXT STATE")
        print("="*50)
        print(f"Authenticated: {self._is_authenticated}")
        print(f"Username: {self.get_username()}")
        print(f"Nama: {self.get_nama()}")
        print(f"App ID: {self.get_app_id()}")
        print(f"Role ID: {self.get_role_id()}")
        print(f"Token: {'***' + self._token[-10:] if self._token else 'None'}")
        print(f"Permissions: {len(self._permissions)} items")
        if self._permissions:
            print(f"Sample permissions: {self._permissions[:5]}...")
        print("="*50 + "\n")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert auth state to dictionary"""
        return {
            "is_authenticated": self._is_authenticated,
            "username": self.get_username(),
            "nama": self.get_nama(),
            "app_id": self.get_app_id(),
            "role_id": self.get_role_id(),
            "has_token": bool(self._token),
            "permissions_count": len(self._permissions),
            "permissions_sample": self._permissions[:3] if self._permissions else []
        }
    
    def save_to_file(self, filepath: str = "auth_state.json"):
        """Save auth state to file (for debugging)"""
        try:
            data = {
                "token": self._token,
                "permissions": self._permissions,
                "user_info": self._user_info,
                "is_authenticated": self._is_authenticated
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Auth state saved to {filepath}")
        except Exception as e:
            print(f"❌ Failed to save auth state: {e}")


# ============ GLOBAL SINGLETON INSTANCE ============

# Create singleton instance
_auth_context_singleton = AuthContext()

# Alias untuk mudah di-import
auth_context = _auth_context_singleton

# Export juga class-nya kalau perlu
__all__ = ['AuthContext', 'auth_context']


# ============ TEST CODE ============

if __name__ == "__main__":
    print("🧪 Testing AuthContext...")
    
    # Get instance
    auth1 = AuthContext()
    auth2 = auth_context  # Harusnya sama instance
    
    print(f"Same instance? {auth1 is auth2}")
    
    # Test sign in
    auth1.sign_in(
        token="test_token_123",
        permissions=["dashboard.read", "users.write"],
        user_info={"username": "testuser", "nama": "Test User"}
    )
    
    # Check state
    auth1.print_state()
    
    # Test methods
    print(f"Has 'dashboard.read': {auth1.has_permission('dashboard.read')}")
    print(f"Has 'admin.super': {auth1.has_permission('admin.super')}")
    print(f"Username: {auth1.get_username()}")
    
    # Test sign out
    auth1.sign_out()
    print(f"Authenticated after logout: {auth1.is_authenticated()}")