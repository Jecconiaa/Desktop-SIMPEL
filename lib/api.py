# lib/api.py
import json
import logging
import sys
import os
from typing import Dict, Any, Optional


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import middleware kita
try:
    from middleware import middleware
    print("✅ Middleware imported successfully")
except ImportError:
    print("⚠️ Middleware not found, creating simple fallback")
    import requests
    
    class SimpleMiddleware:
        def __init__(self):
            self.session = requests.Session()
            self.session.verify = True
            self.session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "SIMPEL-Desktop/1.0",
                "X-Application-Type": "Desktop",
                "Origin": "http://desktop.simpel.local"
            })
        
        def post(self, url, data=None, **kwargs):
            return self.session.post(url, json=data, timeout=10, **kwargs)
        
        def get(self, url, **kwargs):
            return self.session.get(url, timeout=10, **kwargs)
        
        def add_header(self, key, value):
            self.session.headers[key] = value

        def configure_base_url(self, base_url):
            self.add_header("X-Base-URL", base_url.rstrip("/"))
        
        def remove_header(self, key):
            self.session.headers.pop(key, None)
    
    middleware = SimpleMiddleware()

# Setup logger
logger = logging.getLogger(__name__)

class ApiClient:
    def __init__(self, base_url: str, timeout: int = 10):
        """
        Initialize API client dengan middleware.
        
        Args:
            base_url: Base URL API (contoh: "https://api.simpel-p4.tech")
            timeout: Timeout dalam detik
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._token: Optional[str] = None
        
        # Setup middleware dengan base URL yang benar
        middleware.configure_base_url(self.base_url)
        
        print(f"🔧 API Client initialized: {self.base_url}")
        
    def set_token(self, token: str):
        """Set JWT token untuk authorization"""
        self._token = token
        middleware.add_header("Authorization", f"Bearer {token}")
        print("🔑 Token set di middleware")
        
    def clear_token(self):
        """Clear token (logout)"""
        self._token = None
        middleware.remove_header("Authorization")
        print("🔑 Token cleared dari middleware")
        
    def get_token(self) -> Optional[str]:
        """Get current token"""
        return self._token
        
    def _make_url(self, endpoint: str) -> str:
        """Construct full URL"""
        endpoint = endpoint.lstrip('/')
        return f"{self.base_url}/{endpoint}"
    
    def post(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        POST request dengan middleware.
        
        Returns:
            Dict: JSON response dari server
        """
        url = self._make_url(endpoint)
        logger.debug(f"POST {url}")
        
        try:
            response = middleware.post(url, data=data)
            response.raise_for_status()  # Raise exception untuk status 4xx/5xx
            return response.json()
            
        except Exception as e:
            logger.error(f"POST failed: {str(e)}")
            # Coba parse error message
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', str(e))
                except:
                    error_msg = e.response.text or str(e)
            else:
                error_msg = str(e)
                
            raise Exception(f"API request failed: {error_msg}")
    
    def get(self, endpoint: str) -> Dict[str, Any]:
        """
        GET request dengan middleware.
        
        Returns:
            Dict: JSON response dari server
        """
        url = self._make_url(endpoint)
        logger.debug(f"GET {url}")
        
        try:
            response = middleware.get(url)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"GET failed: {str(e)}")
            raise Exception(f"API request failed: {str(e)}")
    
    def login(self, username: str, password: str, jenis_aplikasi: str = "public") -> Dict[str, Any]:
        print(f"🔐 Attempting login: {username}")
    
        # ⚠️ PAYLOAD HARUS PASCALCASE! ⚠️
        payload = {
            "Username": username,        # ← Huruf besar 'U'
            "Password": password,        # ← Huruf besar 'P'  
            "JenisAplikasi": jenis_aplikasi  # ← Huruf besar 'J'
        }
    
        print(f"📦 Payload: {json.dumps(payload)}")
    
        try:
            response_data = self.post("/api/Auth/login", payload)
            
            token = response_data.get("token")
            if token:
                self.set_token(token)
                print(f"✅ Login successful, token received")
            else:
                print("⚠️ Login successful but no token in response")
                
            return response_data
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            raise
    
    def get_permission(self, username: str, app_id: str, role_id: str) -> Dict[str, Any]:
        """
        Helper method untuk get permission.
        
        Args:
            username: Username
            app_id: Application ID
            role_id: Role ID
            
        Returns:
            Dict: Permission response data
        """
        print(f"🔑 Getting permissions for: {username}, App: {app_id}, Role: {role_id}")
        
        payload = {
            "username": username,
            "appId": app_id,
            "roleId": role_id
        }
        
        try:
            response_data = self.post("/api/Auth/getpermission", payload)
            
            token = response_data.get("token")
            if token:
                self.set_token(token)  # Update dengan final token
                print(f"✅ Permissions received, final token set")
            else:
                print("⚠️ Permissions received but no token in response")
                
            return response_data
            
        except Exception as e:
            print(f"❌ Get permission failed: {e}")
            raise

# Global instance (sama kayak di mobile)
# Base URL akan di-set di api_base.py
api = None

def init_api(base_url: str):
    """Initialize global api instance"""
    global api
    api = ApiClient(base_url)
    return api

__all__ = ['ApiClient', 'api', 'init_api']
