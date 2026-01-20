# api_base.py
import requests

class ApiBase:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        # verify=False karena localhost biasanya nggak punya SSL
        self.session.verify = False 
        self.session.headers.update({"Content-Type": "application/json"})

    def set_token(self, token):
        """Masukin token JWT ke header otomatis"""
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def post(self, endpoint, data=None):
        return self.session.post(f"{self.base_url}{endpoint}", json=data, timeout=10)

    def get(self, endpoint):
        return self.session.get(f"{self.base_url}{endpoint}", timeout=10)