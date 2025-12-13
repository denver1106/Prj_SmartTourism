import bcrypt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

class AuthService:
    def __init__(self, db_conn, google_client_id=None):
        self.db = db_conn
        self.GOOGLE_CLIENT_ID = google_client_id

    def register(self, email, username, password):
        try:
            with self.db.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                if cur.fetchone(): return None, "Email đã tồn tại"
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                cur.execute("INSERT INTO users (email, username, password, provider, created_at) VALUES (%s, %s, %s, 'local', NOW())", (email, username, hashed))
                uid = cur.lastrowid
            self.db.commit()
            return uid, None
        except Exception as e:
            self.db.rollback()
            return None, str(e)

    def login(self, email, password):
        try:
            with self.db.cursor() as cur:
                cur.execute("SELECT id, username, password FROM users WHERE email=%s AND provider='local'", (email,))
                user = cur.fetchone()
            if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
                return user["id"], None
            return None, "Sai email hoặc mật khẩu"
        except: return None, "Lỗi Server"

    def login_with_google(self, token):
        try:
            req = google_requests.Request()
            info = id_token.verify_oauth2_token(token, req, self.GOOGLE_CLIENT_ID)
            email, name, sub = info.get("email"), info.get("name"), info.get("sub")

            with self.db.cursor() as cur:
                cur.execute("SELECT id, username FROM users WHERE email=%s", (email,))
                user = cur.fetchone()
                if user: return user["id"], None
                
                # Register new Google User
                cur.execute("INSERT INTO users (email, username, google_id, provider, created_at) VALUES (%s, %s, %s, 'google', NOW())", (email, name, sub))
                uid = cur.lastrowid
            self.db.commit()
            return uid, None
        except ValueError: return None, "Token Google không hợp lệ"
        except Exception as e:
            self.db.rollback()
            return None, str(e)