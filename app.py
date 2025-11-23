from flask import Flask, render_template, request, redirect, url_for, session
from core import data_manager, search_handler, service
import os

app = Flask(__name__)

# SECRET KEY để dùng session (bắt buộc phải có)
app.secret_key = "smartfood-secret-key-demo"

WEATHER_API_KEY = "DUMMY_API_KEY_FOR_NOW"

# Khởi tạo các "Data Res" layer
db_manager = data_manager.DataManager()
search_engine = search_handler.SearchHandler()
tourism_service = service.SmartTourismService(weather_api_key=WEATHER_API_KEY)


# ================== HÀM CHUẨN HÓA DỮ LIỆU -> FRONT ==================

def normalize_restaurants(raw_list):
    """
    Chuẩn hoá dữ liệu quán ăn từ DataManager / SmartTourismService
    về cùng một format mà results.html có thể hiển thị:

    {
        "id": ...,
        "name": ...,
        "address": ...,
        "place": ...,
        "price_level": ...,
        "distance_km": ...,
        "tags": [...],
        "dishes": [...],
        "lat": ...,
        "lng": ...,
        "description": ...
    }
    """
    normalized = []

    for r in raw_list:
        if not isinstance(r, dict):
            continue

        name = r.get("name", "Tên chưa cập nhật")
        address = r.get("address", "Địa chỉ đang cập nhật")
        place = r.get("place") or r.get("area") or address
        price_level = r.get("price_level", "?")

        try:
            distance_km = float(r.get("distance_km", 0.0))
        except (TypeError, ValueError):
            distance_km = 0.0

        tags = r.get("tags") or []
        dishes = r.get("foods") or r.get("menu") or []

        lat = r.get("lat")
        lng = r.get("lng")
        description = r.get("description", "Chưa có mô tả.")

        normalized.append({
            "id": r.get("id"),
            "name": name,
            "address": address,
            "place": place,
            "price_level": price_level,
            "distance_km": distance_km,
            "tags": tags,
            "dishes": dishes,
            "lat": lat,
            "lng": lng,
            "description": description
        })

    return normalized


# ================== AUTH / ACCOUNT (ĐĂNG NHẬP / ĐĂNG KÝ) ==================

@app.route("/account", methods=["GET", "POST"])
def account():
    """
    Trang đăng ký / đăng nhập (account.html).
    - GET  : hiển thị form
    - POST : nhận dữ liệu form, lưu vào session và chuyển sang trang chủ
    """
    if request.method == "POST":
        user_name = request.form.get("user_name") or "Bạn"
        email = request.form.get("email") or ""
        # Ở đây chưa kiểm tra mật khẩu, vì phần này thuộc backend / bảo mật

        # Lưu thông tin cơ bản vào session
        session["user_name"] = user_name
        session["email"] = email

        # Đăng nhập xong -> vào trang chủ
        return redirect(url_for("index"))

    # Nếu đã đăng nhập rồi mà vẫn gõ /account -> cho về trang chủ
    if "user_name" in session:
        return redirect(url_for("index"))

    # Lần đầu hoặc chưa đăng nhập -> hiển thị form account
    return render_template("account.html")


# ================== ROUTES FRONTEND CHÍNH ==================

@app.route("/")
def index():
    """
    Trang chủ SmartFood (index.html).
    Bắt buộc phải đăng nhập trước:
    - Nếu chưa có session["user_name"] -> chuyển về /account
    - Nếu có rồi -> render trang chủ
    """
    if "user_name" not in session:
        return redirect(url_for("account"))

    return render_template("index.html", user_name=session.get("user_name"))


@app.route("/results")
def results_page():
    """
    Route xử lý tìm kiếm và lọc khoảng cách.
    Connect Data Res - Front:
    - Gọi DataManager + SearchHandler để lấy dữ liệu (Data Res)
    - Chuẩn hoá => normalize_restaurants
    - Truyền vào results.html để hiển thị (Front)
    """
    if "user_name" not in session:
        return redirect(url_for("account"))

    query = request.args.get("query", "").strip()

    # Lấy tham số lọc khoảng cách (nếu có)
    try:
        max_distance_str = request.args.get("max_distance")
        max_distance = float(max_distance_str) if max_distance_str else None
    except ValueError:
        max_distance = None

    # Lấy toạ độ user (nếu front có truyền)
    try:
        user_lat = float(request.args.get("lat"))
        user_lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        user_lat = None
        user_lon = None

    # 1. Lấy dữ liệu (bao gồm Mock Data gần user_lat/lon nếu DataManager hỗ trợ)
    all_restaurants = db_manager.get_all_restaurants(
        use_cache=False,
        user_lat=user_lat,
        user_lon=user_lon
    )

    # 2. Tìm kiếm theo từ khóa
    results = search_engine.search(all_restaurants, query)

    # 3. Tính khoảng cách và LỌC THEO MAX DISTANCE
    final_results = []
    if user_lat is not None and user_lon is not None:
        for r in results:
            if r.get("distance_km", 0) == 0 and r.get("lat") is not None and r.get("lng") is not None:
                dist = ((r["lat"] - user_lat) ** 2 + (r["lng"] - user_lon) ** 2) ** 0.5 * 111
                r["distance_km"] = dist

            current_dist = r.get("distance_km", 0) or 0
            if max_distance is not None and current_dist > max_distance:
                continue

            final_results.append(r)
    else:
        final_results = results

    # 4. Chuẩn hoá data trước khi gửi ra giao diện
    restaurants_for_front = normalize_restaurants(final_results)

    # 5. Truyền sang template
    return render_template(
        "results.html",
        restaurants=restaurants_for_front,
        query=query
    )


@app.route("/recommend")
def recommend_page():
    """
    Route demo gợi ý thông minh (SmartTourismService).
    Cũng connect Data Res -> Front qua normalize_restaurants.
    """
    if "user_name" not in session:
        return redirect(url_for("account"))

    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return "Lỗi: Không nhận được tọa độ vị trí hợp lệ!", 400

    user_id = "guest_user_001"
    service_output = tourism_service.process_user_input(user_id, lat, lon)

    context_data = service_output["context"]
    recommendations = service_output["recommendations"]

    restaurants_for_front = normalize_restaurants(recommendations)
    context_desc = f"Buổi {context_data.get('time_of_day')}, Mùa {context_data.get('season')}"

    return render_template(
        "results.html",
        restaurants=restaurants_for_front,
        context=context_desc,
        query="Gợi ý thông minh"
    )


@app.route("/user")
def user_page():
    """
    Trang người dùng (user.html).
    Cũng yêu cầu đăng nhập để xem.
    """
    if "user_name" not in session:
        return redirect(url_for("account"))

    # Tạm thời chỉ render UI demo, chưa nối data thật
    return render_template("user.html")


@app.route("/logout")
def logout():
    """
    Đăng xuất:
    - Xoá session
    - Quay lại trang đăng nhập (account.html)
    """
    session.clear()
    return redirect(url_for("account"))


if __name__ == "__main__":
    app.run(debug=True)
