from flask import Flask, render_template, request, redirect, url_for
from core import data_manager, search_handler, service
import os

app = Flask(__name__)
# Key giả định, sau này thay bằng key thật nếu cần
WEATHER_API_KEY = "DUMMY_API_KEY_FOR_NOW"

# Khởi tạo các module xử lý
db_manager = data_manager.DataManager()
search_engine = search_handler.SearchHandler()
tourism_service = service.SmartTourismService(weather_api_key=WEATHER_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results')
def results_page():
    """
    Hàm này xử lý tất cả: Tìm kiếm từ khóa, Lọc khoảng cách, Lọc nhóm (Ăn cùng ai), Lọc Vibe.
    """
    # 1. LẤY DỮ LIỆU TỪ GIAO DIỆN
    query = request.args.get('query', '').strip().lower()
    group_filter = request.args.get('group_filter') # Lấy filter Ăn cùng ai
    vibe_filter = request.args.get('vibe_filter')   # Lấy filter Vibe
    
    # Lấy tham số lọc khoảng cách
    try:
        max_distance_str = request.args.get('max_distance')
        max_distance = float(max_distance_str) if max_distance_str else None
    except ValueError:
        max_distance = None

    # Lấy tọa độ user
    try:
        user_lat = float(request.args.get('lat'))
        user_lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        user_lat = None
        user_lon = None

    # 2. LẤY DANH SÁCH QUÁN ĂN (Từ Database thông qua DataManager)
    all_restaurants = db_manager.get_all_restaurants(
        use_cache=False, 
        user_lat=user_lat, 
        user_lon=user_lon
    )
    
    # 3. TÌM KIẾM THEO TÊN/MÓN (Dùng module search cũ của bạn)
    # Bước này lọc sơ bộ những quán khớp từ khóa tìm kiếm
    if query:
        # Nếu có nhập từ khóa -> Lọc theo tên
        temp_results = search_engine.search(all_restaurants, query)
    else:
        # Nếu để trống -> Lấy tất cả quán (để sau đó lọc theo Tag)
        temp_results = all_restaurants

    # 4. ÁP DỤNG CÁC BỘ LỌC NÂNG CAO (LOGIC MỚI)
    final_results = []
    
    for r in temp_results:
        # --- A. LỌC KHOẢNG CÁCH ---
        if user_lat and user_lon:
            # Tính khoảng cách (nếu chưa có sẵn trong data)
            if r.get("distance_km", 0) == 0 and r.get('lat') and r.get('lng'):
                try:
                    r["distance_km"] = ((r['lat'] - user_lat)**2 + (r['lng'] - user_lon)**2)**0.5 * 111
                except:
                    r["distance_km"] = 999 
            
            # Nếu quán xa hơn mức user chọn -> Bỏ qua
            if max_distance is not None and r.get("distance_km", 0) > max_distance:
                continue 
        
        # --- B. LỌC THEO NHÓM (ĂN CÙNG AI) ---
        # Logic: Nếu user chọn filter, kiểm tra xem quán có tag đó trong mảng 'group_type' không
        if group_filter and group_filter not in ["", "all"]:
            # Lấy danh sách group của quán (nếu không có thì trả về list rỗng)
            res_groups = r.get('group_type', [])
            
            # Nếu quán không có tag này -> Bỏ qua
            # (Ví dụ: Tìm 'alone' mà quán chỉ có ['family'] -> Bị loại)
            if not isinstance(res_groups, list) or group_filter not in res_groups:
                continue 

        # --- C. LỌC THEO VIBE ---
        # Logic: Nếu user chọn filter, kiểm tra xem 'vibe' của quán có khớp không
        if vibe_filter and vibe_filter not in ["", "all"]:
            res_vibe = r.get('vibe', '')
            if res_vibe != vibe_filter:
                continue

        # Nếu vượt qua mọi bài test -> Thêm vào kết quả cuối cùng
        final_results.append(r)

    # 5. TRẢ VỀ GIAO DIỆN
    return render_template('results.html', 
                           restaurants=final_results, 
                           query=query,
                           group_filter=group_filter, 
                           vibe_filter=vibe_filter)

@app.route('/recommend')
def recommend_page():
    # Giữ nguyên logic gợi ý thông minh
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return "Lỗi: Không nhận được tọa độ vị trí hợp lệ!", 400

    user_id = "guest_user_001"
    service_output = tourism_service.process_user_input(user_id, lat, lon)

    context_data = service_output.get('context', {})
    recommendations = service_output.get('recommendations', [])
    
    time_of_day = context_data.get('time_of_day', 'Unknown')
    season = context_data.get('season', 'Unknown')
    context_desc = f"Buổi {time_of_day}, Mùa {season}"

    return render_template(
        'results.html', 
        restaurants=recommendations, 
        context=context_desc,
        query="Gợi ý thông minh"
    )

@app.route('/user')
def user_page():
    try: return render_template('user.html') 
    except: return "Trang User Profile"

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Chạy ở chế độ debug
    app.run(debug=True)