# lib/api_base.py
import sys
import os
from typing import Optional

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
    
    #DEFAULT_IP = '127.0.0.1'  # Default untuk local development
    #DEFAULT_IP = '192.168.100.3'
    DEFAULT_IP = '10.1.14.15'
    PORT = 5234
    
    # Untuk development (bisa detect otomatis)
    # Tapi karena desktop app, biasanya fixed IP
    return f"http://{DEFAULT_IP}:{PORT}"


def get_api_endpoint(endpoint: str) -> str:
    """
    Helper untuk mendapatkan full URL endpoint.
    
    Args:
        endpoint (str): Endpoint path (contoh: "/api/Auth/login")
        
    Returns:
        str: Full URL (contoh: "http://192.168.100.4:5234/api/Auth/login")
    """
    base_url = get_api_base_url()
    endpoint = endpoint.lstrip('/')
    return f"{base_url}/{endpoint}"


# Contoh penggunaan:
if __name__ == "__main__":
    print("Base URL:", get_api_base_url())
    print("Login URL:", get_api_endpoint("/api/Auth/login"))
    print("Permission URL:", get_api_endpoint("/api/Auth/getpermission"))