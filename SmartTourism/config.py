import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ban-phai-thay-doi-chuoi-nay-bang-mot-thu-bi-mat'
    
    # SỬA DÒNG NÀY:
    # Sai: os.path.join(BASE_DIR, 'instance', 'firebase-key.json')
    # Đúng:
    FIREBASE_KEY_PATH = os.path.join(basedir, 'instance', 'firebase-key.json')

    # === THÊM DÒNG NÀY VÀO ===
    FIREBASE_WEB_API_KEY = "AIzaSyBBKfYYAzfXNUddkrQSQzV7xgomKn7DH-Y"
    
    # Dòng này bạn đã viết đúng
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')