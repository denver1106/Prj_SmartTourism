from flask import Flask, render_template, request, redirect, url_for, session
from core import data_manager, search_handler, service
import os

app = Flask(__name__)
# Secret key để dùng session (lưu tên user, v.v.)
app.secret_key = os.environ.get("SMARTFOOD_SECRET_KEY", "dev-secret-smartfood")

# API key thời tiết (demo)
WEATHER_API_KEY = "DUMMY_API_KEY_FOR_NOW"

# Khởi tạo các lớp xử lý dữ liệu / tìm kiếm / auto filter
db_manager = data_manager.DataManager()
search_engine = search_handler.SearchHandler()
tourism_service = service.SmartTourismService(weather_api_key=WEATHER_API_KEY)


# ========================= TRANG CHỦ =========================
@app.route("/")
def index():
    """
    Trang chủ: hiển thị UI tìm kiếm + bộ lọc.
    Nếu đã có user_name trong session thì show lên, không thì để trống.
    """
    user_name = session.get("user_name")  # có thể được set từ trang account/login
    return render_template("index.html", user_name=user_name)


# ========================= KẾT QUẢ TÌM KIẾM THỦ CÔNG =========================
@app.route("/results")
def results_page():
    """
    Route xử lý tìm kiếm & lọc thủ công.
    - Nhận query (tên món / địa điểm)
    - Nhận các filter: max_distance, price_level, tag, cravings_text
    - Lấy dữ liệu từ DataManager + SearchHandler
    - Tính khoảng cách, lọc theo khoảng cách, trả về results.html
    """
    query = request.args.get("query", "").strip()

    # Lọc khoảng cách (km)
    try:
        max_distance_str = request.args.get("max_distance")
        max_distance = float(max_distance_str) if max_distance_str else None
    except ValueError:
        max_distance = None

    # Các filter khác (chưa dùng nhiều nhưng vẫn đọc để sau này có backend xử lý)
    price_level = request.args.get("price_level") or ""
    tag = request.args.get("tag") or ""
    cravings_text = request.args.get("cravings_text") or ""

    # Toạ độ user (nếu có từ index.html gửi lên)
    try:
        user_lat = float(request.args.get("lat"))
        user_lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        user_lat = None
        user_lon = None

    # 1. Lấy dữ liệu quán ăn (bao gồm Mock Data gần user_lat/lon)
    all_restaurants = db_manager.get_all_restaurants(
        use_cache=False,
        user_lat=user_lat,
        user_lon=user_lon
    )

    # 2. Tìm kiếm theo từ khóa (SearchHandler có thể dùng query + cravings_text, tag, ...)
    results = search_engine.search(all_restaurants, query)

    # 3. Tính khoảng cách và LỌC THEO MAX DISTANCE (nếu có toạ độ)
    final_results = []
    if user_lat is not None and user_lon is not None:
        for r in results:
            # Tính khoảng cách nếu chưa có
            if r.get("distance_km", 0) == 0 and r.get("lat") and r.get("lng"):
                r["distance_km"] = (
                    (r["lat"] - user_lat) ** 2 + (r["lng"] - user_lon) ** 2
                ) ** 0.5 * 111  # xấp xỉ km

            current_dist = r.get("distance_km", 0)

            # Nếu có max_distance và khoảng cách > max thì bỏ
            if max_distance is not None and current_dist > max_distance:
                continue

            final_results.append(r)

        # Sắp xếp kết quả theo khoảng cách tăng dần cho đẹp
        final_results.sort(key=lambda x: x.get("distance_km", 0))
    else:
        # Không có toạ độ -> không lọc theo khoảng cách
        final_results = results

    # Render ra template
    return render_template(
        "results.html",
        restaurants=final_results,
        query=query,
        # gửi thêm info filter nếu bạn muốn show lại trên UI
        max_distance=max_distance,
        price_level=price_level,
        tag=tag,
        cravings_text=cravings_text,
        context=None,  # context chỉ dùng cho auto-filter
    )


# ========================= GỢI Ý TỰ ĐỘNG (AUTO FILTER) =========================
@app.route("/recommend")
def recommend_page():
    """
    Route LỌC MẶC ĐỊNH (auto filters):
    - Được gọi khi user bấm nút "✨ Gợi ý thông minh theo vị trí & thời tiết".
    - Nhận lat, lon từ query string (JS trên index.html gửi sang).
    - Gọi SmartTourismService để:
        + Xác định context (thời gian trong ngày, mùa, thời tiết, lịch sử dùng...)
        + Sinh ra danh sách recommendations đã được sắp xếp & lọc.
    - Trả về results.html với 'context' để giải thích lý do gợi ý.
    """
    # Lấy toạ độ từ query; nếu lỗi thì dùng default HCM
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        # Fallback: nếu không có toạ độ hợp lệ thì dùng toạ độ mặc định
        lat = 10.7769
        lon = 106.7009

    # Trong demo, user_id cứng; sau có thể lấy từ session
    user_id = "guest_user_001"

    # Gọi tầng dịch vụ thông minh (SmartTourismService)
    service_output = tourism_service.process_user_input(user_id, lat, lon)

    context_data = service_output.get("context", {})
    recommendations = service_output.get("recommendations", [])

    # (Optionally) bạn có thể chuẩn hoá lại fields cho frontend ở đây
    auto_results = recommendations

    # Chuẩn bị câu mô tả context hiển thị lên giao diện
    context_desc = f"Buổi {context_data.get('time_of_day', '?')}, mùa {context_data.get('season', '?')}"

    return render_template(
        "results.html",
        restaurants=auto_results,
        context=context_desc,
        query="Gợi ý tự động",
    )


# ========================= TRANG NGƯỜI DÙNG =========================
@app.route("/user")
def user_page():
    """
    Trang hồ sơ / lịch sử gợi ý của người dùng (UI demo).
    """
    try:
        return render_template("user.html")
    except:
        return "Trang User Profile"


# ========================= ĐĂNG XUẤT =========================
@app.route("/logout")
def logout():
    """
    Đăng xuất đơn giản: xoá tên user trong session rồi quay về trang chủ.
    (Nếu nhóm bạn có login thật thì route này có thể xoá thêm token, v.v.)
    """
    session.pop("user_name", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
