from app.user_service import (
    get_user_profile,
    update_user_basic,
    update_user_preferences,
    add_favorite_food,
    remove_favorite_food,
    add_favorite_restaurant,
    remove_favorite_restaurant,
    get_recent_history,
)

from flask import (
    render_template, request, redirect, url_for, flash, Blueprint,
    session, current_app
)
import requests
from functools import wraps

# Import các hệ thống chung từ app/__init__.py
from app import db, data_manager, predictor, auth_fb

from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone
from firebase_admin import auth, firestore

# Nếu bạn đã có file logic.py với hàm save_history thì import:
from app.logic import save_history   # <-- quan trọng

# --- TẠO BLUEPRINT ---
main_routes = Blueprint('main', __name__)


# --- 1. TẠO HÀM @login_required TÙY CHỈNH ---
def login_required_custom(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để sử dụng chức năng này.', 'info')
            return redirect(url_for('main.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


# --- 2. CÁC TRANG WEB ---

@main_routes.route('/')
@main_routes.route('/index')
@login_required_custom
def index():
    suggestion = data_manager.get_contextual_suggestion()
    return render_template('index.html', suggestion=suggestion)


# --- 3. XÁC THỰC ---

@main_routes.route('/login', methods=['GET', 'POST'])
def login():
    # Nếu đã đăng nhập rồi thì vào thẳng trang chủ
    if 'user_id' in session:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        api_key = current_app.config['FIREBASE_WEB_API_KEY']
        login_url = (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            f"?key={api_key}"
        )

        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        try:
            # Gửi request đăng nhập lên Firebase Auth
            response = requests.post(login_url, json=payload)
            response.raise_for_status()

            data = response.json()
            uid = data['localId']

            # Lưu thông tin đăng nhập vào session
            session['user_id'] = uid
            session['token'] = data['idToken']
            session['user_email'] = email

            # Cập nhật lastActiveAt trên Firestore
            db.collection('users').document(uid).set(
                {
                    "email": email,
                    "lastActiveAt": firestore.SERVER_TIMESTAMP,
                },
                merge=True
            )

            flash('Đăng nhập thành công!', 'success')

            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))

        except requests.exceptions.HTTPError as err:
            error_json = err.response.json()
            error_message = error_json.get('error', {}).get('message', 'Lỗi không xác định')

            if ("INVALID_LOGIN_CREDENTIALS" in error_message
                    or "INVALID_EMAIL" in error_message):
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
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Tạo tài khoản trên Firebase Auth
            user_record = auth_fb.create_user(
                email=email,
                password=password
            )
            uid = user_record.uid
            print(f"Tạo user thành công: {uid}")

            # Tạo document hồ sơ user trên Firestore
            db.collection('users').document(uid).set({
                "email": email,
                "displayName": email.split("@")[0],
                "createdAt": firestore.SERVER_TIMESTAMP,
                "lastActiveAt": firestore.SERVER_TIMESTAMP,
                "preferences": {
                    "favoriteTags": [],
                    "dislikedTags": [],
                    "maxDistanceKm": 5,
                    "priceLevels": ["low", "medium", "high"],
                    "timePreferences": []
                },
                "favoriteFoodIds": [],
                "favoriteRestaurantIds": []
            })

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
@login_required_custom
def logout():
    session.pop('user_id', None)
    session.pop('token', None)
    session.pop('user_email', None)
    flash('Bạn đã đăng xuất.', 'info')
    return redirect(url_for('main.index'))


# --- 4. UPLOAD ẢNH & LƯU HISTORY ---

@main_routes.route('/upload_image', methods=['POST'])
def upload_image():
    # Bắt buộc phải đăng nhập
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để sử dụng chức năng này.', 'warning')
        return redirect(url_for('main.login'))

    if 'file' not in request.files:
        flash('Không có file nào được chọn', 'danger')
        return redirect(request.referrer)

    file = request.files['file']
    if file.filename == '':
        flash('Chưa chọn file', 'danger')
        return redirect(request.referrer)

    if not file:
        return redirect(url_for('main.index'))

    # Lưu file
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # --- DỰ ĐOÁN MÓN / ĐỊA ĐIỂM ---
    food_result, food_score = predictor.predict_image(filepath, 'food')
    place_result, place_score = predictor.predict_image(filepath, 'place')
    print(f"Food: {food_result} ({food_score:.2f}) | Place: {place_result} ({place_score:.2f})")

    if food_score > place_score and food_result != 'unknown':
        final_result_name = food_result
        model_used = 'food'
    elif place_score > food_score and place_result != 'unknown':
        final_result_name = place_result
        model_used = 'place'
    else:
        flash('Không thể nhận diện hình ảnh này.', 'danger')
        return redirect(request.referrer)

    # --- LẤY DỮ LIỆU TỪ DATA_MANAGER ---
    if model_used == 'food':
        food_item = data_manager.get_food_by_name(final_result_name)
        if not food_item:
            flash('Tìm thấy món ăn, nhưng chưa có trong CSDL.', 'warning')
            return redirect(request.referrer)

        # Lấy danh sách quán & biến thể (giữ theo code cũ của bạn)
        restaurants = data_manager.get_restaurants_for_food(food_item['id'])
        variations = data_manager.get_variations(food_item['id'])

        # --- GHI LỊCH SỬ LÊN FIRESTORE ---
        try:
            user_uid = session['user_id']
            food_id = food_item['id']

            # Tạm thời lấy quán đầu tiên trong danh sách (nếu có) để ghi history.
            restaurant_id = restaurants[0]['id'] if restaurants else None

            save_history(
                db=db,
                user_id=user_uid,
                food_id=food_id,
                restaurant_id=restaurant_id,
                query_text=final_result_name
            )
        except Exception as e:
            print(f"LỖI: Không thể ghi lịch sử vào Firestore. Lỗi: {e}")
            flash('Đã nhận diện, nhưng lỗi khi lưu lịch sử.', 'warning')

        return render_template(
            'results.html',
            item=food_item,
            restaurants=restaurants,
            variations=variations
        )

    else:
        # TODO: xử lý trường hợp model_used == 'place'
        flash('Nhận diện địa điểm chưa được cài đặt.', 'info')
        return redirect(request.referrer)


@main_routes.route('/profile', methods=['GET', 'POST'])
@login_required_custom
def profile():
    user_id = session['user_id']

    if request.method == 'POST':
        # ví dụ form có input name="displayName"
        display_name = request.form.get('displayName', '').strip()

        # form checkbox/ select cho preferences
        favorite_tags = request.form.getlist('favoriteTags')       # dạng list
        disliked_tags = request.form.getlist('dislikedTags')
        price_levels = request.form.getlist('priceLevels')         # ["low", "medium"]
        max_distance = request.form.get('maxDistanceKm') or 5
        time_preferences = request.form.getlist('timePreferences')

        try:
            update_user_basic(db, user_id, display_name=display_name)
            update_user_preferences(
                db,
                user_id,
                favorite_tags=favorite_tags,
                disliked_tags=disliked_tags,
                max_distance_km=float(max_distance),
                price_levels=price_levels,
                time_preferences=time_preferences,
            )
            flash('Cập nhật thông tin thành công.', 'success')
        except Exception as e:
            print("Lỗi khi cập nhật profile:", e)
            flash('Có lỗi khi lưu thông tin. Vui lòng thử lại.', 'danger')

        return redirect(url_for('main.profile'))

    # GET: hiển thị form
    profile_data = get_user_profile(db, user_id)
    recent_history = get_recent_history(db, user_id, limit=10)

    return render_template(
        'profile.html',
        user=profile_data,
        history=recent_history
    )


@main_routes.route('/favorite/food/<food_id>', methods=['POST'])
@login_required_custom
def toggle_favorite_food(food_id):
    user_id = session['user_id']
    action = request.form.get('action', 'add')  # "add" hoặc "remove"

    try:
        if action == 'remove':
            remove_favorite_food(db, user_id, food_id)
            flash('Đã bỏ khỏi danh sách món yêu thích.', 'info')
        else:
            add_favorite_food(db, user_id, food_id)
            flash('Đã thêm vào món yêu thích.', 'success')
    except Exception as e:
        print("Lỗi khi cập nhật favorite food:", e)
        flash('Không thể cập nhật món yêu thích.', 'danger')

    return redirect(request.referrer or url_for('main.index'))


@main_routes.route('/favorite/restaurant/<restaurant_id>', methods=['POST'])
@login_required_custom
def toggle_favorite_restaurant(restaurant_id):
    user_id = session['user_id']
    action = request.form.get('action', 'add')

    try:
        if action == 'remove':
            remove_favorite_restaurant(db, user_id, restaurant_id)
            flash('Đã bỏ khỏi quán yêu thích.', 'info')
        else:
            add_favorite_restaurant(db, user_id, restaurant_id)
            flash('Đã thêm vào quán yêu thích.', 'success')
    except Exception as e:
        print("Lỗi khi cập nhật favorite restaurant:", e)
        flash('Không thể cập nhật quán yêu thích.', 'danger')

    return redirect(request.referrer or url_for('main.index'))
