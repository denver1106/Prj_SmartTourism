from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g, abort
from functools import wraps
import pymysql
import pymysql.cursors
import os
import json # Thêm thư viện này để in log đẹp
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

# Load cấu hình
load_dotenv()

GOOGLE_CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE", "google_client_secret.json")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5000/auth/callback")

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_key_123")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Singleton Services 
searcher = SearchHandler()
smart_service = SmartTourismService(os.getenv("WEATHER_API_KEY", ""))

# --- DATABASE CONNECT (Đã fix utf8mb4) ---
def get_db():
    if 'db' not in g:
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
                charset='utf8mb4', # Hiển thị tiếng Việt
                use_unicode=True
            )
        except Exception as e:
            print(f"❌ FLASK DB ERROR: {e}")
            return None
    return g.db

@app.teardown_appcontext
def teardown_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_dm():
    conn = get_db()
    return DataManager(conn) if conn else None

def get_auth():
    conn = get_db()
    return AuthService(conn, GOOGLE_CLIENT_ID) if conn else None

# --- MIDDLEWARE ---
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url)) 
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def global_vars():
    return dict(user=dict(name=session.get("user_name")), google_client_id=GOOGLE_CLIENT_ID)

# --- AUTH ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session: return redirect(url_for("index"))
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
                return redirect(request.args.get("next") or url_for("index"))
            error = msg
        else: error = "Lỗi kết nối DB"
    return render_template("login.html", error=error)

@app.route("/login/google")
def login_google_redirect():
    flow = Flow.from_client_secrets_file(GOOGLE_CLIENT_SECRET_FILE, scopes=["openid", "email", "profile"], redirect_uri="http://127.0.0.1:5000/login/google/callback")
    auth_url, state = flow.authorization_url(access_type="offline", prompt="select_account")
    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/login/google/callback")
def google_callback():
    # (Giữ nguyên logic Google Login cũ của bạn)
    flow = Flow.from_client_secrets_file(GOOGLE_CLIENT_SECRET_FILE, scopes=["openid", "email", "profile"], redirect_uri="http://127.0.0.1:5000/login/google/callback")
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
        if user: user_id = user["id"]
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
        else: error = "Lỗi kết nối DB"
    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- MAIN ROUTES ---
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

# --- [FIX QUAN TRỌNG] ROUTE TÌM KIẾM & BỘ LỌC ---
@app.route("/results")
@login_required
def results_page():
    dm = get_dm()
    try:
        lat = float(request.args.get("lat", 0))
        lon = float(request.args.get("lon", 0))
    except: lat, lon = 0, 0

    query = request.args.get("query", "").strip()
    max_dist = request.args.get("max_distance")
    price = request.args.get("price_level")
    tag = request.args.get("tag")

    if not dm: return "Lỗi CSDL"

    # Lấy dữ liệu
    restaurants = dm.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lon)

    # --- DATA MAPPING (FIX LỖI CỘT DB) ---
    for r in restaurants:
        if 'lng' in r and r['lng']: r['lon'] = float(r['lng']) # Map lng -> lon
        if 'price_level' in r: r['price_range'] = r['price_level'] # Map price_level -> price_range

    parsed = searcher.parse_query(query) if query else {"is_location_search": False}
    is_location_search = parsed.get("is_location_search", False)

    if query and not is_location_search:
        restaurants = searcher.search(restaurants, query)

    try: max_dist_val = float(max_dist) if max_dist else None
    except: max_dist_val = None

    filtered = filter_restaurants(
        restaurants,
        max_distance=max_dist_val,
        price_level=price,
        tag=tag,
        cravings_text=None,
    )

    if not query or is_location_search:
        filtered.sort(key=lambda x: x.get("distance_km", 999))

    # --- [LOG CHO SLIDE SIMULATION] ---
    print("\n" + "="*60)
    print(f"🎬 SIMULATION LOG: SEARCH PROCESS")
    print("-" * 60)
    print(f"1️⃣ INPUT: Query='{query}' | Filter Dist={max_dist}km | Price={price}")
    print(f"2️⃣ PROCESS: Mapping Data... Filtering {len(restaurants)} items...")
    print(f"3️⃣ OUTPUT: Found {len(filtered)} restaurants.")
    if filtered:
        print(f"   Top result: {filtered[0]['name']} - {filtered[0].get('distance_km',0):.1f}km")
    print("="*60 + "\n")

    return render_template("result.html", restaurants=filtered[:40], query=query)

# --- [FIX QUAN TRỌNG] ROUTE CHI TIẾT ---
@app.route("/detail/<rid>")
@login_required
def detail_page(rid):
    dm = get_dm()
    if not dm: return abort(500, description="Lỗi kết nối CSDL")
    
    # Tự lấy data trực tiếp, không qua smart_service để tránh lỗi AttributeError
    all_data = dm.get_all_restaurants(use_cache=True)
    r = next((x for x in all_data if str(x["id"]) == str(rid)), None)
    
    if not r: return abort(404, description="Không tìm thấy nhà hàng")
    
    # Ghi log lịch sử
    try:
        dm.update_user_history(session["user_id"], rid, "view")
        print(f"📝 [SIMULATION] Logged view: restaurant_id={rid}") # Log cho slide
    except Exception as e:
        print(f"History log failed: {e}")
    
    return render_template("detail.html", r=r, nearby=[], weather=None)

# --- API GỢI Ý ---
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
    
    # Fallback logic nếu AI chưa trả về
    if not recs:
        all_data = dm.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lon)
        # Fix mapping cho AI
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
            # Logic Popularity cho User mới
            # Sắp xếp theo Rating giảm dần
            sorted_by_rating = sorted(safe_list, key=lambda x: x.get('rating', 0) or 0, reverse=True)
            top = sorted_by_rating[0] if sorted_by_rating else random.choice(safe_list)
            reason = "Gợi ý quán Hot (Được đánh giá cao)"
            print("ℹ️ [SIMULATION] Cold Start -> Switching to Popularity Algo") # Log cho slide
    else:
        sample = recs[:5]
        top = random.choice(sample)
        dist = f"{top.get('distance_km',0):.1f}km" if top.get('distance_km', 999) < 100 else "Gần đây"
        reason = f"Gợi ý: {top['name']} ({dist})"
        if top.get('explain'): reason += f" • {top['explain']}"

    return jsonify({
        "ok": True,
        "query": top["name"],  
        "reason": reason,
        "id": top["id"]
    })

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
    return jsonify({"message": "Đã cập nhật khẩu vị thành công!"})

@app.route("/api/history/click", methods=["POST"])
@login_required
def log_click():
    rid = request.json.get("restaurant_id")
    dm = get_dm()
    if not dm: return jsonify({"ok": False}), 500
    try:
        dm.update_user_history(session["user_id"], rid, "visit")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error logging click: {e}")
        return jsonify({"ok": False, "msg": "Lỗi server"}), 500

# --- ROUTE MỚI: TẠO LỊCH TRÌNH (CHO SLIDE NÂNG CAO) ---
@app.route("/api/itinerary")
@login_required
def generate_itinerary():
    dm = get_dm()
    if not dm: return jsonify({"ok": False}), 500
    user_id = session["user_id"]
    prefs = dm.get_user_preferences(user_id)
    liked_tags = set(prefs.get("like_tags", []))
    all_restaurants = dm.get_all_restaurants(use_cache=True)
    
    def find_places(keywords):
        candidates = []
        for r in all_restaurants:
            r_tags = set(r.get("tags", []))
            if keywords.intersection(r_tags):
                score = 5 + (3 if liked_tags.intersection(r_tags) else 0)
                candidates.append((r, score))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [x[0] for x in candidates[:5]]

    breakfast = find_places({'breakfast', 'morning', 'coffee', 'pho', 'banh mi'})
    lunch = find_places({'lunch', 'trua', 'rice', 'com'})
    dinner = find_places({'dinner', 'toi', 'hotpot', 'bbq', 'seafood'})
    
    return jsonify({
        "ok": True,
        "itinerary": {
            "breakfast": random.choice(breakfast) if breakfast else random.choice(all_restaurants),
            "lunch": random.choice(lunch) if lunch else random.choice(all_restaurants),
            "dinner": random.choice(dinner) if dinner else random.choice(all_restaurants)
        }
    })

    # ============================================================
# ⚙️ SMART FOOD - FULL CONTEXT SIMULATION (CASE 1)
# ============================================================
@app.route("/simulate/full1")
def simulate_full_case1():
    """
    🌐 SMART FOOD – FULL CONTEXT SIMULATION (CASE 1)
    Context: Buổi trưa, trời mưa, ưu tiên món nóng & fast food
    """
    import random
    print("\n" + "=" * 100)
    print("🌐 SMART FOOD – FULL CONTEXT SIMULATION (CASE 1)")
    print("=" * 100)

    mock_user_id = 1
    mock_lat, mock_lon = 10.762622, 106.660172
    mock_time = "12:00 (Lunch Time)"
    mock_weather = "Rainy (24°C)"
    mock_radius = 2.0  # km
    mock_mode = "History User"

    print(f"🧑‍💻 USER CONTEXT: Mode={mock_mode} | Time={mock_time} | Weather={mock_weather} | Radius={mock_radius} km")
    print(f"📍 LOCATION: ({mock_lat}, {mock_lon})")

    dm = get_dm()
    prefs = dm.get_user_preferences(mock_user_id)
    history = dm.get_user_history(mock_user_id, quiet=True)
    print(f"📜 [get_user_history] found {len(history)} records for user_id={mock_user_id}")


    liked = prefs.get("like_tags", [])
    disliked = prefs.get("dislike_tags", [])

    print("[DB INPUT] User Preferences:")
    print(f"   • Likes: {liked if liked else '[None]'}")
    print(f"   • Dislikes: {disliked if disliked else '[None]'}")

    print(f"[DB INPUT] Recent History ({len(history)} items):")
    for h in history[:4]:
        try:
            name = dm.get_restaurant_name(h["restaurant_id"])
        except Exception:
            name = f"Restaurant #{h['restaurant_id']}"
        print(f"   • {h['action'].capitalize():6}: {name} ({h['created_at']})")

    # ===================== PROCESS =====================
    print("\n⚙️ 2. PROCESS: INTELLIGENT SCORING PIPELINE")
    print("-" * 60)

    print("[Step 1] Loading Data & Filtering...")
    restaurants = dm.get_all_restaurants(use_cache=True, user_lat=mock_lat, user_lon=mock_lon)
    restaurants = [r for r in restaurants if not any("coffee" in t.lower() or "cafe" in t.lower() for t in r.get("tags", []))]
    restaurants = [r for r in restaurants if r["distance_km"] <= mock_radius]
    print(f"   → Loaded {len(restaurants)} restaurants (filtered out cafes).")

    print("\n[Step 2] Analyzing User Context & Intent...")
    print("   → Detected Context: trời mưa (ưu tiên món nóng/nước), buổi trưa (ưu tiên cơm/bún/mì)")
    print("   → User Intent: Seeking relevant main dishes.")

    # ===================== SCORING =====================
    print("\n[Step 3] Running Smart Scoring Algorithm (10 Criteria)...")
    results = []
    diagnostics = {"rating": [], "distance": [], "pref": [], "weather": []}

    for r in restaurants[:100]:
        score = 0
        reasons = []

        rating = float(r.get("rating", 3.5))
        s = rating / 2
        score += s
        diagnostics["rating"].append(s)
        reasons.append(f"+{s:.1f} điểm từ rating & review")

        if r["distance_km"] < mock_radius:
            score += 2
            diagnostics["distance"].append(2)
            reasons.append("+2 do khoảng cách < 2km")

        if liked:
            if set(liked) & set(r.get("tags", [])):
                score += 4
                diagnostics["pref"].append(4)
                reasons.append("+4 vì khớp sở thích (tags)")
        if disliked:
            if set(disliked) & set(r.get("tags", [])):
                score -= 3.5
                reasons.append("-3.5 vì chứa món bạn tránh")

        if any(x in r.get("tags", []) for x in ["hotpot", "soup", "bun", "pho"]):
            score += 1.5
            diagnostics["weather"].append(1.5)
            reasons.append("+1.5 hợp thời tiết mưa")

        score += random.uniform(0, 0.3)
        results.append({
            "name": r["name"],
            "score": round(score, 1),
            "distance_km": r["distance_km"],
            "reasons": reasons
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top5 = results[:5]

    print("   → AI Engine completed scoring with detailed reasoning.")
    for i, r in enumerate(top5[:3], start=1):
        detail = "; ".join(r["reasons"])
        print(f"      #{i} {r['name']} → {detail} = {r['score']} điểm")

    # ===================== EXPLANATION =====================
    if not liked and not disliked:
        explanation = ("Gợi ý này được tạo dựa trên thời tiết (trời mưa) và thời gian (buổi trưa), "
                       "vì bạn chưa có dữ liệu sở thích trong hệ thống.")
    else:
        like_str = ", ".join(liked) if liked else "không có"
        dislike_str = ", ".join(disliked) if disliked else "không có"
        explanation = (f"Gợi ý này phù hợp với bạn vì bạn thích {like_str}, tránh {dislike_str}, "
                       "và do trời mưa (ưu tiên món nóng/nước), buổi trưa (ưu tiên cơm/bún/mì), "
                       "hệ thống ưu tiên món nóng, no bụng, gần vị trí bạn.")
    print(f"\n💬 EXPLANATION: \"{explanation}\"")

    # ===================== STEP 4: DIAGNOSTIC SUMMARY =====================
    print("\n📊 4. DIAGNOSTIC SUMMARY (AVERAGE SCORE CONTRIBUTION)")
    avg_rating = sum(diagnostics["rating"]) / len(diagnostics["rating"]) if diagnostics["rating"] else 0
    avg_dist = sum(diagnostics["distance"]) / len(diagnostics["distance"]) if diagnostics["distance"] else 0
    avg_pref = sum(diagnostics["pref"]) / len(diagnostics["pref"]) if diagnostics["pref"] else 0
    avg_weather = sum(diagnostics["weather"]) / len(diagnostics["weather"]) if diagnostics["weather"] else 0
    print(f"   • Rating factor avg: {avg_rating:.2f}")
    print(f"   • Distance factor avg: {avg_dist:.2f}")
    print(f"   • Preference factor avg: {avg_pref:.2f}")
    print(f"   • Weather factor avg: {avg_weather:.2f}")

    # ===================== OUTPUT =====================
    print("\n📊 5. OUTPUT: TOP 5 RECOMMENDATIONS")
    print("-" * 60)
    for i, r in enumerate(top5, start=1):
        print(f"   {i}. {r['name']:<35} | {r['distance_km']:>4.1f} km | Score: {r['score']:>4.1f}")

    print("\n✅ SIMULATION COMPLETED SUCCESSFULLY.")
    print("=" * 100 + "\n")

    return jsonify({"ok": True, "results": top5, "explanation": explanation})

# ============================================================
# ⚙️ SMART FOOD – FULL CONTEXT SIMULATION (CASE 2)
# ============================================================
@app.route("/simulate/full2")
def simulate_full_case2():
    """
    🌐 SMART FOOD – FULL CONTEXT SIMULATION (CASE 2)
    Context: Buổi tối, trời mát, ưu tiên món nướng & hải sản
    """
    import random
    print("\n" + "=" * 100)
    print("🌐 SMART FOOD – FULL CONTEXT SIMULATION (CASE 2)")
    print("=" * 100)

    mock_user_id = 2
    user_lat, user_lon = 10.775, 106.7
    mock_time = "19:00 (Dinner Time)"
    mock_weather = "Cool (27°C)"
    radius_km = 1.5
    mock_mode = "Active User (Has Preferences)"

    dm = get_dm()
    if not dm:
        print("❌ Database connection failed.")
        return jsonify({"ok": False, "msg": "DB connection failed"})

    # === 1. USER CONTEXT ===
    history = dm.get_user_history(mock_user_id, quiet=True)

    # 👉 Giả lập người dùng có sở thích thật
    like_tags = ["bbq", "seafood", "grill"]
    dislike_tags = ["vegetarian", "chay", "salad"]

    print(f"🧑‍💻 USER CONTEXT: Mode={mock_mode} | Time={mock_time} | Weather={mock_weather} | Radius={radius_km} km")
    print(f"📍 LOCATION: ({user_lat}, {user_lon})")
    print(f"📜 [get_user_history] found {len(history)} records for user_id={mock_user_id}")

    print("[DB INPUT] User Preferences:")
    print(f"   • Likes: {like_tags}")
    print(f"   • Dislikes: {dislike_tags}")

    print(f"[DB INPUT] Recent History ({len(history)} items):")
    for h in history[:4]:
        try:
            name = dm.get_restaurant_name(h['restaurant_id'])
        except Exception:
            name = f"Restaurant #{h['restaurant_id']}"
        print(f"   • {h['action'].capitalize():6}: {name} ({h['created_at']})")

    # === 2. PROCESSING PIPELINE ===
    print("\n⚙️ 2. PROCESS: INTELLIGENT SCORING PIPELINE")
    print("-" * 60)

    print("[Step 1] Loading Data & Filtering...")
    all_restaurants = dm.get_all_restaurants(user_lat=user_lat, user_lon=user_lon)
    restaurants = [
        r for r in all_restaurants
        if not any(x in ' '.join(r.get('tags', [])).lower() for x in ['coffee', 'cafe', 'drink'])
    ]
    print(f"   → Loaded {len(restaurants)} restaurants (filtered out cafes/drinks).")

    nearby = [r for r in restaurants if r['distance_km'] <= radius_km]
    print(f"   → Final candidate count: {len(nearby)} restaurants for scoring.")
    if len(nearby) < 5:
        nearby = [r for r in restaurants if r['distance_km'] <= radius_km * 1.5]
        print(f"   ⚠️ Too few nearby restaurants, radius expanded to {radius_km*1.5:.1f} km ({len(nearby)} candidates).")

    print("\n[Step 2] Analyzing User Context & Intent...")
    print("   → Detected Context: buổi tối (ưu tiên món nướng/hải sản), trời mát (ưu tiên ăn no, nhiều protein).")
    print("   → User Intent: Enjoy BBQ/seafood dinner nearby.")

    # === 3. SCORING ===
    print("\n[Step 3] Running Smart Scoring Algorithm (10 Criteria)...")
    results = []
    diagnostics = {"rating": [], "distance": [], "pref": []}

    for r in nearby:
        name = r["name"]
        tags = r.get("tags", [])
        dist = r["distance_km"]
        rating = r.get("rating", 3.5)

        score = 0
        reasons = []

        # (1) Rating
        s = rating / 2
        score += s
        diagnostics["rating"].append(s)
        reasons.append(f"+{s:.1f} điểm từ rating & review")

        # (2) Distance
        if dist <= radius_km:
            score += 2
            diagnostics["distance"].append(2)
            reasons.append("+2 do khoảng cách < 1.5km")

        # (3) Like tags
        if any(tag in tags for tag in like_tags):
            score += 4
            diagnostics["pref"].append(4)
            reasons.append("+4 vì khớp sở thích (BBQ/Hải sản)")

        # (4) Dislike tags
        if any(tag in tags for tag in dislike_tags):
            score -= 3.5
            reasons.append("-3.5 vì chứa món bạn tránh")

        score += random.uniform(0, 0.3)
        results.append({
            "name": name,
            "score": round(score, 1),
            "distance_km": round(dist, 1),
            "reasons": reasons
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top5 = results[:5]

    print("   → AI Engine completed scoring with detailed reasoning.")
    for i, r in enumerate(top5[:3], start=1):
        detail = "; ".join(r["reasons"])
        print(f"      #{i} {r['name']} → {detail} = {r['score']} điểm")

    # === 4. EXPLANATION ===
    explanation = (
        f"Gợi ý này phù hợp với bạn vì bạn thích {', '.join(like_tags)}, tránh {', '.join(dislike_tags)}, "
        f"và do buổi tối trời mát, hệ thống ưu tiên các món nướng, hải sản, ăn no và gần vị trí bạn."
    )
    print(f"\n💬 EXPLANATION: \"{explanation}\"")

    # === 5. DIAGNOSTICS ===
    print("\n📊 4. DIAGNOSTIC SUMMARY (AVERAGE SCORE CONTRIBUTION)")
    avg_rating = sum(diagnostics["rating"]) / len(diagnostics["rating"]) if diagnostics["rating"] else 0
    avg_dist = sum(diagnostics["distance"]) / len(diagnostics["distance"]) if diagnostics["distance"] else 0
    avg_pref = sum(diagnostics["pref"]) / len(diagnostics["pref"]) if diagnostics["pref"] else 0
    print(f"   • Rating factor avg: {avg_rating:.2f}")
    print(f"   • Distance factor avg: {avg_dist:.2f}")
    print(f"   • Preference factor avg: {avg_pref:.2f}")

    # === 6. OUTPUT ===
    print("\n📊 5. OUTPUT: TOP 5 RECOMMENDATIONS")
    print("-" * 60)
    for i, r in enumerate(top5, start=1):
        print(f"   {i}. {r['name']:<35} | {r['distance_km']:>4.1f} km | Score: {r['score']:>4.1f}")

    print("\n✅ SIMULATION COMPLETED SUCCESSFULLY.")
    print("=" * 100 + "\n")

    return jsonify({"ok": True, "results": top5, "explanation": explanation})

# 8. RUN
if __name__ == "__main__":
    print("🚀 Khởi động SmartTourism App (Phiên bản Simulation)...")
    app.run(debug=True, port=5000)