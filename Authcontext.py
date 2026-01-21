# auth_context.py
class AuthContext:
    def __init__(self, api_instance):
        self.api = api_instance
        self.is_authenticated = False
        self.user_info = None

    def login(self, username, password):
        """Proses login ke BE"""
        payload = {
            "Username": username,
            "Password": password, # Password LDAP lu bro
            "JenisAplikasi": "APP01" # Sesuai isi app_id di DB lu
        }
        
        try:
            # Tembak endpoint login sesuai AuthController
            res = self.api.post("/Auth/login", payload)
            
            if res.status_code == 200:
                data = res.json()
                token = data.get("token")
                # Simpan token ke apiBase biar request selanjutnya otomatis bawa token
                self.api.set_token(token)
                self.user_info = data
                self.is_authenticated = True
                return True, "Sukses"
            else:
                return False, res.json().get("message", "Login Gagal")
        except Exception as e:
            return False, str(e)

    def logout(self):
        self.is_authenticated = False
        self.user_info = None
        self.api.session.headers.pop("Authorization", None)