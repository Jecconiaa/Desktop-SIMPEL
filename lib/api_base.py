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