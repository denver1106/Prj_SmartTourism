from flask import Flask, render_template, request, redirect, url_for, jsonify
from core import data_manager, search_handler, service, nutrition_service
from core.nutrition_service import get_nutrition_with_caching # <--- IMPORT HÀM CACHING
import os

app = Flask(__name__)
WEATHER_API_KEY = "DUMMY_API_KEY_FOR_NOW"

db_manager = data_manager.DataManager()
search_engine = search_handler.SearchHandler()
tourism_service = service.SmartTourismService(weather_api_key=WEATHER_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/detail/<restaurant_id>') # <-- Thêm route này
def detail_page(restaurant_id):
    """
    Hiển thị trang chi tiết của một quán ăn.
    """
    # Lấy thông tin quán ăn dựa trên ID
    restaurant = db_manager.get_restaurant_by_id(restaurant_id) 
    
    if not restaurant:
        return "Không tìm thấy quán ăn này.", 404
        
    # Giả định bạn có thể lấy thêm các quán tương tự (optional)
    similar_restaurants = db_manager.get_similar_restaurants(restaurant_id) 

    # Render template detail.html và truyền dữ liệu quán ăn vào
    return render_template(
        'detail.html', 
        restaurant=restaurant, 
        similar_restaurants=similar_restaurants
    )

# --- ROUTE MỚI: API PHÂN TÍCH DINH DƯỠNG ---
@app.route('/api/analyze_nutrition', methods=['POST'])
def analyze_nutrition_endpoint():
    """
    Endpoint nhận dữ liệu thành phần và trả về kết quả phân tích dinh dưỡng 
    Sử dụng hàm get_nutrition_with_caching để kiểm tra cache trước khi gọi API.
    """
    data = request.get_json()
    ingredients = data.get('ingredients_text') # Lấy chuỗi thành phần từ request JSON

    if not ingredients:
        return jsonify({"error": "Vui lòng cung cấp thành phần để phân tích."}), 400

    # GỌI HÀM CÓ CACHING VÀ TRUYỀN DB_MANAGER VÀO
    nutrition_data = get_nutrition_with_caching(ingredients, db_manager)

    # Kiểm tra nếu service trả về lỗi (có key "error" trong dict hoặc là None)
    if not nutrition_data or "error" in nutrition_data:
        # Lấy mã lỗi nếu có, mặc định là 500
        status_code = nutrition_data.get('status_code', 500) if nutrition_data else 500
        error_message = nutrition_data.get('error', "Lỗi không xác định khi phân tích dinh dưỡng.") if nutrition_data else "Lỗi service trả về rỗng."
        
        # In log để debug
        print(f"Lỗi phân tích dinh dưỡng: {error_message}")
        
        # Trả về kết quả lỗi
        return jsonify(nutrition_data if nutrition_data else {"error": error_message}), status_code

    # Trả về dữ liệu dinh dưỡng thành công
    return jsonify(nutrition_data)

@app.route('/results')
def results_page():
    """
    Route xử lý tìm kiếm và lọc khoảng cách.
    """
    query = request.args.get('query', '')
    
    # Lấy tham số lọc khoảng cách (nếu có)
    try:
        max_distance_str = request.args.get('max_distance')
        max_distance = float(max_distance_str) if max_distance_str else None
    except ValueError:
        max_distance = None

    try:
        user_lat = float(request.args.get('lat'))
        user_lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        user_lat = None
        user_lon = None

    # 1. Lấy dữ liệu (bao gồm Mock Data gần user_lat/lon)
    all_restaurants = db_manager.get_all_restaurants(
        use_cache=False, 
        user_lat=user_lat, 
        user_lon=user_lon
    )
    
    # 2. Tìm kiếm theo từ khóa
    results = search_engine.search(all_restaurants, query)

    # 3. Tính khoảng cách và LỌC THEO MAX DISTANCE
    final_results = []
    if user_lat and user_lon:
        for r in results:
            # Tính khoảng cách nếu chưa có
            if r.get("distance_km", 0) == 0 and r.get('lat') and r.get('lng'):
                r["distance_km"] = ((r['lat'] - user_lat)**2 + (r['lng'] - user_lon)**2)**0.5 * 111
            
            # --- LOGIC LỌC MỚI ---
            # Nếu user có nhập max_distance VÀ khoảng cách > max -> Loại bỏ
            current_dist = r.get("distance_km", 0)
            if max_distance is not None and current_dist > max_distance:
                continue # Bỏ qua quán này
            
            final_results.append(r)
    else:
        # Nếu không có tọa độ user thì không tính được khoảng cách -> lấy hết
        final_results = results

    return render_template('results.html', restaurants=final_results, query=query)

@app.route('/recommend')
def recommend_page():
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return "Lỗi: Không nhận được tọa độ vị trí hợp lệ!", 400

    user_id = "guest_user_001"
    service_output = tourism_service.process_user_input(user_id, lat, lon)

    context_data = service_output['context']
    recommendations = service_output['recommendations']
    context_desc = f"Buổi {context_data.get('time_of_day')}, Mùa {context_data.get('season')}"

    return render_template(
        'results.html', 
        restaurants=recommendations, 
        context=context_desc,
        query="Gợi ý thông minh"
    )

@app.route('/user')
def user_page():
    # try: return render_template('user.html') 
    # except: return "Trang User Profile"
    # Giả định ID user là cố định 'guest_user_001'
    user_id = "guest_user_001" 
    
    # 1. Lấy toàn bộ profile user (chứa các mảng ID)
    profile = db_manager.get_user_full_profile(user_id) 
    
    # 2. Lấy danh sách ID
    fav_ids = profile.get('favorites', [])
    purchased_ids = profile.get('purchased', [])
    history_ids = profile.get('history', [])
    
    # 3. Chuyển ID thành đối tượng quán ăn đầy đủ để hiển thị
    # Ghi chú: get_restaurants_by_ids sẽ tự động giới hạn 10 quán đầu tiên
    favorites = db_manager.get_restaurants_by_ids(fav_ids)
    purchased = db_manager.get_restaurants_by_ids(purchased_ids)
    history = db_manager.get_restaurants_by_ids(history_ids) 
    
    # 4. Render và truyền dữ liệu vào template
    return render_template(
        'user.html', 
        user=profile, 
        history=history,
        favorites=favorites,
        purchased=purchased,
        # Giữ lại các biến demo tags cũ nếu cần
        liked_tags=["noodle", "spicy"],
        disliked_tags=["vegan"]
    )

@app.route('/logout')
def logout():
    return redirect(url_for('index'))
@app.route('/api/user_action', methods=['POST'])
def user_action_endpoint():
    data = request.get_json()
    user_id = "guest_user_001" # Tạm thời fix cứng, sau này bạn lấy từ session
    action_type = data.get('type') # 'favorites', 'history', 'purchased'
    res_id = data.get('restaurant_id')

    if not action_type or not res_id:
        return jsonify({"error": "Thiếu thông tin"}), 400

    success = db_manager.update_user_list(user_id, action_type, res_id)
    
    if success:
        return jsonify({"message": "Đã cập nhật thành công!"})
    else:
        return jsonify({"error": "Lỗi hệ thống"}), 500

if __name__ == '__main__':
    app.run(debug=True)