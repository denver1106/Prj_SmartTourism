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

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# 1. SETUP ENV & APP
load_dotenv()

app = Flask(__name__)
# Thiết lập Secret Key
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_key_123")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Singleton Services
searcher = SearchHandler()
smart_service = SmartTourismService(os.getenv("WEATHER_API_KEY", ""))


# 2. DATABASE CONNECT
def get_db():
    if "db" not in g:
        try:
            g.db = pymysql.connect(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_DATABASE", "smarttourism"),
                port=int(os.getenv("DB_PORT", 3306)),
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
                autocommit=True,
                # --- [FIX QUAN TRỌNG] Hỗ trợ tiếng Việt ---
                charset='utf8mb4',
                use_unicode=True
            )
        except Exception as e:
            print(f"❌ FLASK DB ERROR: {e}")
            return None
    return g.db


@app.teardown_appcontext
def teardown_db(error):
    """Đóng kết nối DB khi request kết thúc."""
    db = g.pop("db", None)
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
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def global_vars():
    return dict(
        user=dict(name=session.get("user_name")),
        google_client_id=GOOGLE_CLIENT_ID,
    )


# 4. AUTH ROUTES
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
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE,
        scopes=["openid", "email", "profile"],
        redirect_uri="http://127.0.0.1:5000/login/google/callback",
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes=False,
        prompt="select_account",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/login/google/callback")
def google_callback():
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE,
        scopes=["openid", "email", "profile"],
        redirect_uri="http://127.0.0.1:5000/login/google/callback",
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    token = credentials.id_token

    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    idinfo = id_token.verify_oauth2_token(token, google_requests.Request())
    email = idinfo["email"]
    name = idinfo.get("name", email.split("@")[0])

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        if user:
            user_id = user["id"]
        else:
            cur.execute("INSERT INTO users(email, username) VALUES(%s, %s)", (email, name))
            conn.commit()
            user_id = cur.lastrowid

    session["user_id"] = user_id
    session["user_name"] = name
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session: return redirect(url_for("index"))
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


# 5. MAIN ROUTES
@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/user")
@login_required
def user_page():
    uid = session["user_id"]
    conn = get_db()
    with conn.cursor() as c:
        c.execute("SELECT username, email, id FROM users WHERE id=%s", (uid,))
        u = c.fetchone()
    dm = get_dm()
    prefs = dm.get_user_preferences(uid)
    if hasattr(dm, "get_user_history_full"):
        history = dm.get_user_history_full(uid)
    else:
        history = dm.get_user_history(uid)
    return render_template("user.html", user=u, likes=prefs.get("like_tags", []), dislikes=prefs.get("dislike_tags", []), history=history)


@app.route("/results")
@login_required
def results_page():
    dm = get_dm()
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except Exception:
        lat, lon = 0, 0

    query = request.args.get("query", "").strip()
    max_dist = request.args.get("max_distance")
    price = request.args.get("price_level")
    tag = request.args.get("tag")

    if not dm: return "Lỗi CSDL"

    print(f"\n======== START SEARCH ========")
    print(f"🔎 Query: '{query}' | Filter Dist: {max_dist}")

    # Lấy dữ liệu thô
    restaurants = dm.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lon)
    print(f"📊 [1] Lấy được: {len(restaurants)} quán")

    # --- [FIX QUAN TRỌNG: CẦU NỐI DỮ LIỆU] ---
    # Database dùng 'lng' và 'price_level', nhưng Code cần 'lon' và 'price_range'.
    # Đoạn này copy dữ liệu sang tên đúng để bộ lọc hiểu.
    for r in restaurants:
        # 1. Fix GPS (lng -> lon)
        if 'lng' in r and r['lng'] is not None: 
            r['lon'] = float(r['lng']) 
        
        # 2. Fix Giá (price_level -> price_range)
        if 'price_level' in r: 
            r['price_range'] = r['price_level']

    # Phân tích query
    parsed = searcher.parse_query(query) if query else {"is_location_search": False}
    is_location_search = parsed.get("is_location_search", False)

    # 1. Search Text
    if query and not is_location_search:
        restaurants = searcher.search(restaurants, query)
        print(f"🕵️ [2] Sau khi search text: còn {len(restaurants)} quán")

    # 2. Filter
    try:
        max_dist_val = float(max_dist) if max_dist else None
    except Exception:
        max_dist_val = None

    cravings_for_filter = None
    
    # Gọi bộ lọc (Giờ nó đã hiểu 'lon' và 'price_range' nhờ đoạn fix ở trên)
    filtered = filter_restaurants(
        restaurants,
        max_distance=max_dist_val,
        price_level=price,
        tag=tag,
        cravings_text=cravings_for_filter,
    )
    print(f"🏁 [3] Kết quả cuối cùng: {len(filtered)} quán\n")

    if not query or is_location_search:
        filtered.sort(key=lambda x: x.get("distance_km", 999))

    return render_template("result.html", restaurants=filtered[:40], query=query)


@app.route("/detail/<int:rid>")
@login_required
def detail_page(rid: int):
    dm = get_dm()
    if not dm: return abort(500, description="Lỗi DB")
    try:
        user_lat = float(request.args.get("lat")) if request.args.get("lat") else None
        user_lon = float(request.args.get("lon")) if request.args.get("lon") else None
    except: user_lat = user_lon = None

    ctx = smart_service.build_detail_page_context(
        data_manager=dm, restaurant_id=rid, user_id=session.get("user_id"),
        user_lat=user_lat, user_lon=user_lon,
    )
    if ctx.get("status") == "not_found" or not ctx.get("restaurant"):
        return abort(404, description="Không tìm thấy")

    return render_template("detail.html", r=ctx["restaurant"], nearby=ctx.get("nearby", []), weather=ctx.get("weather"))


# 6. AI FEATURES
@app.route("/api/suggestion")
@login_required
def api_suggestion():
    dm = get_dm()
    if not dm: return jsonify({"ok": False, "msg": "DB Error"}), 500
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except: lat, lon = 0, 0

    user_id = session["user_id"]
    prefs = dm.get_user_preferences(user_id)
    liked_set = set(prefs.get("like_tags", []))
    disliked_set = set(prefs.get("dislike_tags", []))

    recs = []
    try:
        result = smart_service.process_user_input(dm, user_id, lat, lon)
        recs = result.get("recommendations", [])
    except Exception as e: print(f"❌ AI Error: {e}")

    top = None
    reason = ""
    if recs:
        sample = recs[:5]
        top = random.choice(sample)
        dist = f"{top.get('distance_km', 0):.1f}km" if top.get("distance_km", 999) < 100 else "Gần đây"
        reason = f"Gợi ý: {top['name']} ({dist})"
        if top.get("explain"): reason += f" • {top['explain']}"
    else:
        # Fallback thủ công
        all_data = dm.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lon)
        if not all_data: return jsonify({"ok": False, "msg": "Data trống"}), 200
        
        # --- FIX DATA CHO AI (Quan trọng) ---
        for r in all_data:
            if 'lng' in r and r['lng']: r['lon'] = float(r['lng'])

        safe_list = [r for r in all_data if not disliked_set.intersection(set(r.get("tags", [])))]
        if not safe_list: safe_list = all_data
        preferred_list = [r for r in safe_list if liked_set.intersection(set(r.get("tags", [])))]

        if preferred_list:
            top = random.choice(preferred_list)
            matched = list(liked_set.intersection(set(top["tags"])))[:1]
            tag_name = matched[0] if matched else "sở thích"
            reason = f"Gợi ý vì bạn thích '{tag_name}'"
        elif safe_list:
            top = random.choice(safe_list)
            reason = "Gợi ý thông minh phù hợp"
        else:
            top = random.choice(all_data)
            reason = "Thử vận may!"

    return jsonify({"ok": True, "query": top["name"], "reason": reason, "id": top["id"]})


@app.route("/recommend")
@login_required
def recommend_page():
    dm = get_dm()
    if not dm: return abort(500)
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except: lat, lon = 0, 0
    res = smart_service.process_user_input(dm, session["user_id"], lat, lon)
    recs = res.get("recommendations", [])
    for r in recs: r["smart_score"] = r.get("score", 0)
    return render_template("result.html", restaurants=recs, query="Gợi ý dành riêng cho bạn")


@app.route("/api/user/preferences", methods=["POST"])
@login_required
def save_preferences():
    data = request.json
    liked = [str(x).lower().strip() for x in data.get("liked", []) if x]
    disliked = [str(x).lower().strip() for x in data.get("disliked", []) if x]
    dm = get_dm()
    dm.save_user_preferences(session["user_id"], liked, disliked)
    return jsonify({"message": "Đã cập nhật!"})


@app.route("/api/history/click", methods=["POST"])
@login_required
def log_click():
    rid = request.json.get("restaurant_id")
    dm = get_dm()
    if not dm: return jsonify({"ok": False}), 500
    try:
        dm.update_user_history(session["user_id"], rid, "visit")
        return jsonify({"ok": True})
    except: return jsonify({"ok": False}), 500


if __name__ == "__main__":
    print("🚀 Khởi động SmartTourism App (Đã Fix Lỗi Cột)...")
    app.run(debug=True, port=5000)