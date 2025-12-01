from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, abort
from functools import wraps
import pymysql
import pymysql.cursors
import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
import google.auth.transport.requests
import requests
import random
from core.data_manager import DataManager
from core.auth_service import AuthService
from core.search_handler import SearchHandler
from core.manual_filters import filter_restaurants
from core.services import SmartTourismService

GOOGLE_CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "google_client_secret.json")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/callback")

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'


# 1. SETUP ENV & APP
load_dotenv()

app = Flask(__name__)
# Thiết lập Secret Key từ biến môi trường (Bảo mật)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_key_123")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Singleton Services 
searcher = SearchHandler()
smart_service = SmartTourismService(os.getenv("WEATHER_API_KEY", ""))

# 2. DATABASE CONNECT
def get_db():
    if 'db' not in g:
        try:
            g.db = pymysql.connect(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_DATABASE", "smarttourism"),
                port=int(os.getenv("DB_PORT", 3306)),  #
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                autocommit=True
            )
            # Thêm dòng test này, nó sẽ in ra console của PyCharm/VSCode mỗi khi refresh trang
            # print("✅ Flask đã kết nối DB thành công!") 
        except Exception as e:
            print(f"❌ FLASK DB ERROR: {e}")
            return None
    return g.db

@app.teardown_appcontext
def teardown_db(error):
    """Đóng kết nối DB khi request kết thúc."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Factory Functions
def get_dm():
    conn = get_db()

    return DataManager(conn) if conn else None

def get_auth():
    conn = get_db()
    return AuthService(conn, GOOGLE_CLIENT_ID) if conn else None

# 3. MIDDLEWARE
def login_required(f):
    """Decorator yêu cầu đăng nhập trước khi truy cập route."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            # Chuyển hướng về login và lưu URL hiện tại để quay lại sau
            return redirect(url_for("login", next=request.url)) 
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def global_vars():
    """Tiêm biến toàn cục vào mọi template."""
    return dict(
        user=dict(
            name=session.get("user_name")
        ),
        google_client_id=GOOGLE_CLIENT_ID
    )

# 4. AUTH ROUTES (Đăng nhập, Đăng ký, Đăng xuất)
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        auth = get_auth()
        
        if auth:
            uid, msg = auth.login(email, password)
            if uid:
                session["user_id"] = uid
                # Lấy tên hiển thị sau khi login thành công
                conn = get_db()
                if conn:
                    with conn.cursor() as c:
                        c.execute("SELECT username FROM users WHERE id=%s", (uid,))
                        u = c.fetchone()
                        session["user_name"] = u["username"] if u else email
                
                next_url = request.args.get("next")
                return redirect(next_url or url_for("index"))
            error = msg
        else:
            error = "Lỗi kết nối DB"

    return render_template("login.html", error=error)

@app.route("/login/google")
def login_google_redirect():
    """Redirect user to Google OAuth page"""
    flow = Flow.from_client_secrets_file(
        "google_client_secret.json",
        scopes=["openid", "email", "profile"],
        redirect_uri="http://127.0.0.1:5000/login/google/callback"
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes=False,   
        prompt="select_account"
    )

    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/login/google/callback")
def google_callback():
    flow = Flow.from_client_secrets_file(
        "google_client_secret.json",
        scopes=["openid", "email", "profile"],
        redirect_uri="http://127.0.0.1:5000/login/google/callback"
    )

    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    token = credentials.id_token

    from google.oauth2 import id_token
    from google.auth.transport import requests

    idinfo = id_token.verify_oauth2_token(token, requests.Request())

    email = idinfo["email"]
    name = idinfo.get("name", email.split("@")[0])

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:
            user_id = user["id"]
        else:
            cur.execute(
                "INSERT INTO users(email, username) VALUES(%s, %s)",
                (email, name)
            )
            conn.commit()
            user_id = cur.lastrowid

    session["user_id"] = user_id
    session["user_name"] = name
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        auth = get_auth()

        if auth:
            uid, msg = auth.register(email, username, password)
            if uid:
                session["user_id"] = uid
                session["user_name"] = username
                return redirect(url_for("index"))
            error = msg
        else:
            error = "Lỗi kết nối DB"
            
    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# 5. MAIN ROUTES (Trang Chủ, Kết Quả Tìm Kiếm, Chi Tiết)
@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/user")
@login_required
def user_page():
    uid = session["user_id"]
    conn = get_db()
    
    # Thông tin user
    with conn.cursor() as c:
        c.execute("SELECT username, email, id FROM users WHERE id=%s", (uid,))
        u = c.fetchone()
    
    dm = get_dm()
    prefs = dm.get_user_preferences(uid)

    # Lịch sử nâng cấp (full object)
    if hasattr(dm, "get_user_history_full"):
        history = dm.get_user_history_full(uid)
    else:
        history = dm.get_user_history(uid)

    return render_template(
        "user.html",
        user=u,
        likes=prefs.get("like_tags", []),
        dislikes=prefs.get("dislike_tags", []),
        history=history
    )

@app.route("/results")
@login_required
def results_page():
    dm = get_dm()

    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except:
        lat, lon = 0, 0

    query = request.args.get("query", "").strip()
    max_dist = request.args.get("max_distance")
    price = request.args.get("price_level")
    tag = request.args.get("tag")

    if not dm:
        return "Lỗi CSDL"

    # Phân tích query để biết đây là search món ăn hay search tỉnh/thành
    parsed = searcher.parse_query(query) if query else {"is_location_search": False}
    is_location_search = parsed.get("is_location_search", False)
    print("DEBUG_RESULT_PAGE: query =", query, "| is_location_search =", is_location_search)

    # Lấy toàn bộ quán (đã tính distance_km)
    restaurants = dm.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lon)
    print("DEBUG_RESULT_PAGE: len(all_restaurants) =", len(restaurants))

    # 1. SEARCH
    # - Nếu là search món ăn / từ khóa -> dùng SearchHandler như cũ
    # - Nếu là search tỉnh/thành -> KHÔNG search theo text nữa (giữ nguyên danh sách)
    if query and not is_location_search:
        restaurants = searcher.search(restaurants, query)
        print("DEBUG_RESULT_PAGE: len(after search) =", len(restaurants))

    # 2. FILTER
    try:
        max_dist_val = float(max_dist) if max_dist else None
    except:
        max_dist_val = None

    # Nếu là search tỉnh/thành -> không dùng cravings_text để lọc nữa
    cravings_for_filter = None

    filtered = filter_restaurants(
        restaurants,
        max_distance=max_dist_val,
        price_level=price,
        tag=tag,
        cravings_text=cravings_for_filter,
    )

    print("DEBUG_RESULT_PAGE: len(after filter) =", len(filtered))

    # Nếu không có query hoặc là search tỉnh/thành -> sort theo khoảng cách
    if not query or is_location_search:
        filtered.sort(key=lambda x: x.get("distance_km", 999))

    return render_template("result.html", restaurants=filtered[:40], query=query)


@app.route("/detail/<rid>")
@login_required
def detail_page(rid):
    dm = get_dm()
    if not dm: return abort(500, description="Lỗi kết nối CSDL")
    
    # Tìm chi tiết nhà hàng
    data = dm.get_all_restaurants(use_cache=True)
    r = next((x for x in data if str(x["id"]) == str(rid)), None)
    if not r: return abort(404, description="Không tìm thấy nhà hàng")
    
    # Ghi nhật ký lịch sử xem
    try:
        dm.update_user_history(session["user_id"], rid, "view")
    except Exception as e:
        print(f"History log failed: {e}")
        pass
    
    return render_template("detail.html", r=r)

# 6. AI FEATURES (Gợi ý thông minh)
# app.py

@app.route("/api/suggestion")
@login_required
def api_suggestion():
    dm = get_dm()
    if not dm: return jsonify({"ok": False, "msg": "DB Error"}), 500

    # 1. GET GPS
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except:
        lat, lon = 0, 0

    user_id = session["user_id"]

    # 2. LẤY PREFERENCES
    # Hàm này trả về {'like_tags': [...], 'dislike_tags': [...]} (theo data_manager cũ)
    prefs = dm.get_user_preferences(user_id)
    
    # Chuẩn hóa về set để so sánh nhanh hơn
    liked_set = set(prefs.get("like_tags", []))
    disliked_set = set(prefs.get("dislike_tags", []))

    # 3. GỌI AI / SMART SERVICE
    recs = []
    try:
        # Hàm này đã được viết ở core/services.py
        result = smart_service.process_user_input(dm, user_id, lat, lon)
        recs = result.get("recommendations", [])
    except Exception as e:
        print(f"❌ AI Error: {e}")

    top = None
    reason = ""

    # 4. LOGIC CHỌN QUÁN
    if recs:
        # --- TRƯỜNG HỢP 1: AI TÌM THẤY ---
        # Lấy random trong Top 5 để đổi vị (như đã bàn ở turn trước)
        sample = recs[:5]
        top = random.choice(sample)
        dist = f"{top.get('distance_km',0):.1f}km" if top.get('distance_km', 999) < 100 else "Gần đây"
        
        reason = f"Gợi ý: {top['name']} ({dist})"
        if top.get('explain'):
            reason += f" • {top['explain']}"
    
    else:
        # --- TRƯỜNG HỢP 2: FALLBACK (THỦ CÔNG) ---
        print("⚡ AI trả về rỗng → Chạy lọc thủ công")
        
        # Lấy tất cả quán từ DB
        all_data = dm.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lon)
        
        if not all_data:
            return jsonify({"ok": False, "msg": "Dữ liệu quán ăn đang trống"}), 200

        # Lọc bỏ quán chứa tag user ghét
        # (Nếu bất kỳ tag nào của quán nằm trong disliked_set -> Loại)
        safe_list = [
            r for r in all_data 
            if not disliked_set.intersection(set(r.get("tags", [])))
        ]
        
        # Nếu lọc ghét xong mà hết quán -> Dùng lại all_data
        if not safe_list: 
            safe_list = all_data

        # Tìm quán chứa tag user thích
        # (Nếu quán có ít nhất 1 tag nằm trong liked_set)
        preferred_list = [
            r for r in safe_list 
            if liked_set.intersection(set(r.get("tags", [])))
        ]

        if preferred_list:
            top = random.choice(preferred_list)
            # Tìm ra tag nào trùng để hiện lý do
            matched = list(liked_set.intersection(set(top["tags"])))[:1]
            tag_name = matched[0] if matched else "sở thích"
            reason = f"Gợi ý quán này vì bạn thích '{tag_name}'"
        elif safe_list:
            top = random.choice(safe_list)
            reason = "Gợi ý thông minh phù hợp với bạn"
        else:
            top = random.choice(all_data)
            reason = "Thử vận may xem sao!"
            
    return jsonify({
        "ok": True,
        "query": top["name"],  
        "reason": reason,
        "id": top["id"] # Trả thêm ID để nếu cần frontend redirect thẳng
    })
@app.route("/recommend")
@login_required
def recommend_page():
    """Trang hiển thị kết quả gợi ý thông minh (Smart Recommendation)"""
    dm = get_dm()
    if not dm: return abort(500, description="Lỗi kết nối CSDL")
    
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except: lat, lon = 0, 0
    
    res = smart_service.process_user_input(dm, session["user_id"], lat, lon)
    recs = res.get("recommendations", [])
    
    # Thêm smart_score để hiển thị
    for r in recs: r["smart_score"] = r.get("score", 0)

    return render_template("result.html", restaurants=recs, query="Gợi ý dành riêng cho bạn")

# 7. USER PROFILE API (Thông tin người dùng và lịch sử)
# @app.route("/user")
# @login_required
# def user_page():
#     uid = session["user_id"]
#     conn = get_db()
#     with conn.cursor() as c:
#         c.execute("SELECT username, email, id FROM users WHERE id=%s", (uid,))
#         u = c.fetchone()
    
#     dm = get_dm()
#     prefs = dm.get_user_preferences(uid) # Lấy cả Like và Dislike
    
#     return render_template("user.html", 
#                            user=u, 
#                            likes=prefs.get("like_tags", []), 
#                            dislikes=prefs.get("dislike_tags", []), # Truyền dislikes xuống HTML
#                            history=dm.get_user_history(uid))


@app.route("/api/user/preferences", methods=["POST"])
@login_required
def save_preferences():
    data = request.json
    liked = data.get("liked", [])     # Danh sách Thích
    disliked = data.get("disliked", []) # Danh sách Không thích
    
    # Clean input
    liked = [str(x).lower().strip() for x in liked if x]
    disliked = [str(x).lower().strip() for x in disliked if x]
    
    dm = get_dm()
    dm.save_user_preferences(session["user_id"], liked, disliked)
    
    return jsonify({"message": "Đã cập nhật khẩu vị thành công!"})

@app.route("/api/history/click", methods=["POST"])
@login_required
def log_click():
    """Ghi nhật ký 'Check-in' hoặc 'Đã đến'."""
    rid = request.json.get("restaurant_id")
    dm = get_dm()
    if not dm: return jsonify({"ok": False, "msg": "Lỗi kết nối CSDL"}), 500
    
    try:
        dm.update_user_history(session["user_id"], rid, "visit")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error logging click: {e}")
        return jsonify({"ok": False, "msg": "Lỗi server khi ghi nhật ký."}), 500

# 8. RUN
if __name__ == "__main__":
    print("🚀 Khởi động SmartTourism App...")
    # Chạy Flask App ở chế độ debug
    app.run(debug=True, port=5000)