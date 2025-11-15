import os
from flask import Flask, session
from config import Config
import firebase_admin
from firebase_admin import credentials, firestore, auth

# --- KHỞI TẠO CÁC HỆ THỐNG MỘT LẦN DUY NHẤT ---

# 1. Tải "chìa khóa" Firebase
try:
    cred = credentials.Certificate(Config.FIREBASE_KEY_PATH)
    firebase_admin.initialize_app(cred)
    print("--- Kết nối Firebase THÀNH CÔNG! ---")
except Exception as e:
    print(f"LỖI: Không thể kết nối Firebase. Kiểm tra file 'firebase-key.json'. Lỗi: {e}")

# 2. Tạo các đối tượng 'db' (Firestore) và 'auth' (Authentication)
# Đây là 2 biến chúng ta sẽ dùng trong toàn bộ ứng dụng
db = firestore.client()
auth_fb = auth # Đổi tên để tránh trùng với 'auth' của Flask

# 3. Import "Bộ quản lý dữ liệu" và "Bộ dự đoán"
# (Chúng ta vẫn giữ 2 file này như cũ)
from .data_manager import DataManager
from .prediction.predictor import Predictor

# 4. Khởi tạo các "bộ não" (Vẫn như cũ)
print("--- Khởi động DataManager (Tải JSON vào RAM)... ---")
data_manager = DataManager()

print("--- Khởi động Predictor (Tải model .h5 vào RAM)... ---")
predictor = Predictor()


# --- HÀM TẠO ỨNG DỤNG (APP FACTORY) ---
def create_app(config_class=Config):
    """
    Hàm này tạo và cấu hình ứng dụng Flask.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Đảm bảo thư mục 'instance' tồn tại
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # --- Đăng ký các file logic ---
    # <<< BẮT ĐẦU THỤT LỀ TỪ ĐÂY
    with app.app_context():
        # XÓA BỎ 'models_db' (Không cần nữa)
        from . import routes

        # Đăng ký Blueprint (Như cũ)
        from .routes import main_routes
        app.register_blueprint(main_routes)

        # (Bạn có thể XÓA db.create_all() vì không còn dùng SQLAlchemy)
    
    @app.context_processor
    def inject_user():
        """
        Hàm này tự động cung cấp biến 'current_user' cho MỌI template (giống Flask-Login).
        """
        if 'user_id' in session:
            # Nếu người dùng đã đăng nhập (có user_id trong session)
            # Chúng ta tạo một "đối tượng" giả chứa thông tin
            user_info = {
                'uid': session['user_id'],
                'email': session.get('user_email', 'Email không rõ'), # Sẽ thêm ở Bước 3
                'is_authenticated': True,
                'is_anonymous': False
            }
            return dict(current_user=user_info)
        else:
            # Nếu chưa đăng nhập, tạo một "Người dùng Vô danh"
            anonymous_user = {
                'is_authenticated': False,
                'is_anonymous': True
            }
            return dict(current_user=anonymous_user)
    # =================================================

    return app
    # <<< KẾT THÚC THỤT LỀ Ở TRÊN DÒNG NÀY