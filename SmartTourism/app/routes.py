from flask import (
    render_template, request, redirect, url_for, flash, Blueprint, 
    session, current_app
)
import requests  # <-- Thư viện mới để gọi API đăng nhập
from functools import wraps # <-- Cần cho "login_required"

# Import các hệ thống chung từ app/__init__.py
from app import db, data_manager, predictor, auth_fb 

# (Chúng ta không cần import models_db nữa, vì Firebase là NoSQL)
# from .models_db import User, History, Favorites 

from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone
from firebase_admin import auth, firestore # Import các lỗi của Firebase

# --- TẠO BLUEPRINT ---
main_routes = Blueprint('main', __name__)


# --- 1. TẠO HÀM @login_required TÙY CHỈNH ---
# (Vì chúng ta không dùng Flask-Login nữa, ta phải tự tạo)
def login_required_custom(f):
    """
    Decorator (hàm bọc) này kiểm tra xem 'user_id' có trong session không.
    Nếu không, nó sẽ chuyển hướng về trang login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để sử dụng chức năng này.', 'info')
            return redirect(url_for('main.login', next=request.path))
        
        # (Nâng cao: Bạn có thể thêm logic kiểm tra token ở đây)
        
        return f(*args, **kwargs)
    return decorated_function


# --- 2. CÁC TRANG WEB ---

@main_routes.route('/')
@main_routes.route('/index')
@login_required_custom # Dùng decorator mới
def index():
    suggestion = data_manager.get_contextual_suggestion()
    return render_template('index.html', suggestion=suggestion)


# --- 3. XÁC THỰC (ĐÃ VIẾT LẠI HOÀN TOÀN) ---

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session: # Kiểm tra xem đã đăng nhập chưa
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email') # Dùng email thay vì username
        password = request.form.get('password')
        
        # Lấy Web API Key từ file config
        api_key = current_app.config['FIREBASE_WEB_API_KEY']
        
        # Đây là API Đăng nhập Phía Client của Firebase
        login_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        try:
            # Gửi yêu cầu đăng nhập đến server Firebase
            response = requests.post(login_url, json=payload)
            response.raise_for_status() # Báo lỗi nếu Firebase trả về 4xx/5xx
            
            data = response.json()
            
            # --- ĐĂNG NHẬP THÀNH CÔNG ---
            # Lưu ID người dùng và Token vào session của Flask
            session['user_id'] = data['localId'] # Đây là UID của người dùng
            session['token'] = data['idToken']  # Đây là "chứng chỉ"
            session['user_email'] = email        # <--- THÊM DÒNG NÀY VÀO

            flash('Đăng nhập thành công!', 'success')
            
            # Chuyển hướng về trang mà họ muốn vào (vd: /upload_image)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('main.index'))

        except requests.exceptions.HTTPError as err:
            # --- ĐĂNG NHẬP THẤT BẠI ---
            error_json = err.response.json()
            error_message = error_json.get('error', {}).get('message', 'Lỗi không xác định')
            
            if "INVALID_LOGIN_CREDENTIALS" in error_message or "INVALID_EMAIL" in error_message:
                flash('Email hoặc mật khẩu không đúng.', 'danger')
            else:
                flash(f'Lỗi: {error_message}', 'danger')
            return redirect(url_for('main.login'))
            
    return render_template('login.html', title='Đăng nhập')


@main_routes.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email') # Dùng email
        password = request.form.get('password')
        
        try:
            # Dùng Admin SDK (biến 'auth_fb') để tạo user
            user_record = auth_fb.create_user(
                email=email,
                password=password
            )
            print(f"Tạo user thành công: {user_record.uid}")
            
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('main.login'))
            
        except auth.EmailAlreadyExistsError:
            flash('Email này đã được đăng ký.', 'warning')
            return redirect(url_for('main.register'))
        except auth.InvalidPasswordError:
             flash('Mật khẩu phải có ít nhất 6 ký tự.', 'warning')
             return redirect(url_for('main.register'))
        except Exception as e:
            flash(f'Lỗi khi đăng ký: {e}', 'danger')
            return redirect(url_for('main.register'))
        
    return render_template('register.html', title='Đăng ký')

@main_routes.route('/logout')
@login_required_custom # Dùng decorator mới
def logout():
    # Xóa thông tin người dùng khỏi session
    session.pop('user_id', None)
    session.pop('token', None)
    flash('Bạn đã đăng xuất.', 'info')
    return redirect(url_for('main.index'))


# --- 4. XỬ LÝ LÕI (ĐÃ VIẾT LẠI) ---
from flask import session, redirect, url_for, flash # Đảm bảo đã import đủ
# ... (các import khác của bạn)

@main_routes.route('/upload_image', methods=['POST'])
def upload_image():
    # =============== THÊM CODE BẢO VỆ TẠI ĐÂY ===============
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để sử dụng chức năng này.', 'warning')
        return redirect(url_for('main_routes.login'))
    # ========================================================

    if 'file' not in request.files:
        flash('Không có file nào được chọn', 'danger')
        return redirect(request.referrer) # Quay lại trang upload form
        
    file = request.files['file']
    if file.filename == '':
        flash('Chưa chọn file', 'danger')
        return redirect(request.referrer) # Quay lại trang upload form

    if file:
        filename = secure_filename(file.filename)
        # ... (code lưu file, dự đoán của bạn đã CHUẨN) ...
        # ...
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # --- LOGIC DỰ ĐOÁN ---
        # 👇👇 RẤT CÓ THỂ BẠN ĐÃ XÓA MẤT 3 DÒNG NÀY 👇👇
        # HÃY THÊM CHÚNG LẠI (HOẶC ĐẢM BẢO CHÚNG KHÔNG BỊ COMMENT #):
        food_result, food_score = predictor.predict_image(filepath, 'food')
        place_result, place_score = predictor.predict_image(filepath, 'place')
        print(f"Food: {food_result} ({food_score:.2f}) | Place: {place_result} ({place_score:.2f})")

        if food_score > place_score and food_result != 'unknown':
            # ...
            final_result_name = food_result
            model_used = 'food'
        elif place_score > food_score and place_result != 'unknown':
            # ...
            final_result_name = place_result
            model_used = 'place'
        else:
            flash('Không thể nhận diện hình ảnh này.', 'danger')
            return redirect(request.referrer) # Quay lại trang upload form

        # --- LẤY DỮ LIỆU TĨNH TỪ DATA MANAGER (Giữ nguyên) ---
        if model_used == 'food':
            food_item = data_manager.get_food_by_name(final_result_name)
            if not food_item:
                 flash('Tìm thấy món ăn, nhưng chưa có trong CSDL JSON.', 'warning')
                 return redirect(request.referrer) # Quay lại trang upload form
            
            # ... (code lấy restaurants, variations của bạn) ...
            
            # --- LOGIC GHI LỊCH SỬ (ĐÃ VIẾT LẠI CHO FIRESTORE) ---
            try:
                user_uid = session['user_id'] # Dòng này giờ đã an toàn
                # ... (code ghi vào Firestore của bạn đã CHUẨN) ...
                history_collection.add(history_item)
            except Exception as e:
                # ...
                print(f"LỖI: Không thể ghi lịch sử vào Firestore. Lỗi: {e}")
                flash('Đã nhận diện, nhưng lỗi khi lưu lịch sử.', 'warning')
            # CHUYỂN HƯỚNG SANG TRANG KẾT QUẢ (CHUẨN)
            return render_template('results.html', 
                                   item=food_item, 
                                   restaurants=restaurants, 
                                   variations=variations)
        else:
            # (Làm tương tự cho 'place')
            pass
            
    return redirect(url_for('main_routes.index')) # Chỗ này nên là 'main_routes.index'