# lib/api_base.py
import os


"""Konfigurasi endpoint backend untuk aplikasi Desktop SIMPEL."""

PRODUCTION_API_BASE_URL = "https://api.simpel-p4.tech"
DEVELOPMENT_API_BASE_URL = "http://10.1.4.93:5234"


def _normalize_base_url(value: str) -> str:
    """Hapus slash akhir agar URL endpoint tidak menjadi ``//api/...``."""
    return value.strip().rstrip("/")

def get_api_base_url() -> str:
    """
    Fungsi untuk mendapatkan base URL API.
    Sama konsepnya dengan getApiBaseUrl() di React Native.
    
    Returns:
        str: Base URL API (contoh: "http://192.168.100.4:5234")
    """
    # **EDIT IP DI SINI SAJA!** - Ganti sesuai IP server BE lu
    # Pilihan IP (uncomment salah satu sesuai network lu)
    
    # DEFAULT_IP = '192.168.100.4'  # WiFi kampus/lab
    # DEFAULT_IP = '10.1.6.125'     # WiFi alternatif 1
    # DEFAULT_IP = '10.1.14.15'     # WiFi alternatif 2
    # DEFAULT_IP = '192.168.207.1'  # Hotspot
    # DEFAULT_IP = '172.31.16.1'    # WiFi lainnya
    
    # === IP Histori Lu ===
    # DEFAULT_IP = '172.30.241.95'  # IP Wi-Fi dari konfigurasi user
    # DEFAULT_IP = '192.168.100.3'
    
    # === IP Histori Temen Lu ===
    # IP laptop yang menjalankan backend.
    # DEFAULT_IP = '10.1.4.93'
    
    # === IP KAMPUS LU YANG AKTIF SEKARANG ===
    DEFAULT_IP = '10.1.4.93'
    
    PORT = 5234
    
    # Untuk development (bisa detect otomatis)
    # Tapi karena desktop app, biasanya fixed IP
    return f"http://{DEFAULT_IP}:{PORT}"
    Mengembalikan origin API tanpa suffix ``/api``.

    Prioritas konfigurasi:
    1. ``SIMPEL_API_BASE_URL`` untuk server development/LAN khusus.
    2. ``SIMPEL_ENV=development`` untuk backend laptop default.
    3. API production untuk rilis desktop.
    """
    configured_url = os.getenv("SIMPEL_API_BASE_URL")
    if configured_url and configured_url.strip():
        return _normalize_base_url(configured_url)

    environment = os.getenv("SIMPEL_ENV", "production").strip().lower()
    if environment in {"dev", "development", "local"}:
        return DEVELOPMENT_API_BASE_URL

    return PRODUCTION_API_BASE_URL


def get_api_endpoint(endpoint: str) -> str:
    """
    Helper untuk mendapatkan full URL endpoint.
    
    Args:
        endpoint (str): Endpoint path (contoh: "/api/Auth/login")
        
    Returns:
        str: Full URL endpoint
    """
    base_url = get_api_base_url()
    endpoint = endpoint.lstrip('/')
    return f"{base_url}/{endpoint}"


# Contoh penggunaan:
if __name__ == "__main__":
    print("Base URL:", get_api_base_url())
    print("Login URL:", get_api_endpoint("/api/Auth/login"))
    print("Permission URL:", get_api_endpoint("/api/Auth/getpermission"))