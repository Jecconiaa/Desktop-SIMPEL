# middleware.py
"""
Middleware untuk handle CORS dan headers khusus desktop app.
"""
import functools
import requests
from typing import Dict, Any, Callable, Optional
import json

class DesktopMiddleware:
    """Middleware untuk desktop app dengan headers khusus"""
    
    def __init__(self):
        self.session = requests.Session()
        # Production memakai HTTPS valid. Jangan menonaktifkan pemeriksaan
        # sertifikat secara global karena itu membuat koneksi rentan MITM.
        self.session.verify = True
        self._setup_headers()
        
        # Setup hooks untuk debugging
        self.request_hook = None
        self.response_hook = None

    def _setup_headers(self):
        """Setup headers dengan Host yang sesuai"""
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SIMPEL-Desktop/1.0",
            #"Host": "localhost:5234",  # ⚠️ INI YANG PENTING! ⚠️
        })
    
    def set_request_hook(self, hook: Callable):
        """Set hook sebelum request dikirim"""
        self.request_hook = hook
    
    def set_response_hook(self, hook: Callable):
        """Set hook setelah response diterima"""
        self.response_hook = hook
    
    def add_header(self, key: str, value: str):
        """Tambah custom header"""
        self.session.headers[key] = value
        print(f"➕ Added header: {key}: {value}")

    def configure_base_url(self, base_url: str):
        """Simpan base URL diagnostik tanpa mengubah verifikasi HTTPS."""
        self.add_header("X-Base-URL", base_url.rstrip("/"))
    
    def remove_header(self, key: str):
        """Hapus header"""
        if key in self.session.headers:
            self.session.headers.pop(key)
            print(f"➖ Removed header: {key}")
    
    def clear_headers(self):
        """Clear semua headers kecuali yang essential"""
        essential = ["Content-Type", "Accept", "User-Agent"]
        new_headers = {}
        for key in essential:
            if key in self.session.headers:
                new_headers[key] = self.session.headers[key]
        self.session.headers.clear()
        self.session.headers.update(new_headers)
        print("🧹 Cleared non-essential headers")
    
    def copy_mobile_headers(self):
        """Copy headers dari mobile app React Native"""
        mobile_headers = {
            "User-Agent": "SIMPEL-Mobile/1.0",
            "X-Platform": "desktop",
            "X-Device-ID": "desktop-scanner",
            "X-App-Version": "1.0.0",
            "Origin": "http://mobile.simpel.local",
            "Referer": "http://mobile.simpel.local/"
        }
        self.session.headers.update(mobile_headers)
        print("📱 Applied mobile-like headers")
    
    def copy_web_headers(self):
        """Copy headers dari web app Next.js"""
        web_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/auth/login",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty"
        }
        self.session.headers.update(web_headers)
        print("🌐 Applied web-like headers")
    
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Wrapper untuk requests dengan middleware"""
        print(f"\n{'='*50}")
        print(f"🌐 {method} {url}")
        
        # Log headers sebelum request
        print("📤 Request Headers:")
        for key, value in self.session.headers.items():
            if key not in ['Authorization']:  # Jangan log token
                print(f"  {key}: {value}")
        
        # Log payload kalo ada
        if 'json' in kwargs:
            print(f"📦 Payload: {json.dumps(kwargs['json'], indent=2)}")
        
        # Call request hook
        if self.request_hook:
            self.request_hook(method, url, kwargs)
        
        # Auto tambah timeout kalo ga ada
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 15
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            print(f"\n📥 Response Status: {response.status_code}")
            print(f"📋 Response Headers:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
            
            # Log response body (partial)
            try:
                if response.text:
                    if len(response.text) > 500:
                        print(f"📄 Response (first 500 chars): {response.text[:500]}...")
                    else:
                        print(f"📄 Response: {response.text}")
            except:
                pass
            
            # Call response hook
            if self.response_hook:
                self.response_hook(response)
            
            # Auto-raise untuk error status
            if response.status_code >= 400:
                print(f"❌ HTTP Error {response.status_code}")
                response.raise_for_status()
            
            return response
            
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout untuk {url} (timeout: {kwargs.get('timeout', 15)}s)")
            raise
        except requests.exceptions.ConnectionError as e:
            print(f"🔌 Connection error: {e}")
            raise
        except requests.exceptions.HTTPError as e:
            print(f"🚫 HTTP Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    print(f"📋 Error details: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"📋 Error text: {e.response.text[:200]}")
            raise
        except Exception as e:
            print(f"⚠️ Unexpected error: {type(e).__name__}: {e}")
            raise
    
    def post(self, url: str, data: Dict = None, **kwargs) -> requests.Response:
        """POST request dengan middleware"""
        return self.request('POST', url, json=data, **kwargs)
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET request dengan middleware"""
        return self.request('GET', url, **kwargs)
    
    def test_connection(self, base_url: str) -> bool:
        """Test koneksi ke server"""
        test_url = f"{base_url.rstrip('/')}/"
        try:
            response = self.get(test_url, timeout=5)
            print(f"✅ Connection test: {response.status_code}")
            return response.status_code < 400
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False

# Global instance
middleware = DesktopMiddleware()

# Decorator untuk auto-pake middleware
def with_middleware(func: Callable):
    """Decorator untuk pake middleware otomatis"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Inject middleware ke function yang butuh
        if 'middleware' not in kwargs:
            kwargs['middleware'] = middleware
        return func(*args, **kwargs)
    return wrapper

# Test function untuk debugging
def test_middleware():
    """Test middleware dengan berbagai konfigurasi"""
    print("🧪 Testing middleware configurations...")
    
    test_cases = [
        ("Default headers", None),
        ("Mobile-like headers", lambda m: m.copy_mobile_headers()),
        ("Web-like headers", lambda m: m.copy_web_headers()),
        ("Cleared headers", lambda m: m.clear_headers()),
    ]
    
    from lib.api_base import get_api_endpoint

    test_url = get_api_endpoint("/api/Auth/login")
    payload = {
        "username": "admin",
        "password": "asd",
        "jenisAplikasi": "public"
    }
    
    for test_name, setup_func in test_cases:
        print(f"\n{'='*60}")
        print(f"🧪 TEST: {test_name}")
        print('='*60)
        
        # Reset middleware
        middleware = DesktopMiddleware()
        
        # Apply setup
        if setup_func:
            setup_func(middleware)
        
        try:
            response = middleware.post(test_url, data=payload)
            print(f"✅ {test_name}: Status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"🔑 Token received: {data.get('token', '')[:50]}...")
                return middleware  # Return successful middleware
        except Exception as e:
            print(f"❌ {test_name}: {type(e).__name__}: {e}")
    
    return None

if __name__ == "__main__":
    # Test middleware
    successful_middleware = test_middleware()
    
    if successful_middleware:
        print("\n🎉 Found working middleware configuration!")
        print("Headers that worked:")
        for key, value in successful_middleware.session.headers.items():
            print(f"  {key}: {value}")
    else:
        print("\n❌ No configuration worked. Check BE restrictions.")
