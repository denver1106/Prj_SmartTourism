from flask import Flask, render_template, request, redirect, url_for, jsonify
from core import data_manager, search_handler, service, nutrition_service
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
    bằng cách gọi hàm từ core.nutrition_service.
    """
    data = request.get_json()
    ingredients = data.get('ingredients_text') # Lấy chuỗi thành phần từ request JSON

    if not ingredients:
        return jsonify({"error": "Vui lòng cung cấp thành phần để phân tích."}), 400

    # Gọi hàm service đã được định nghĩa trong core/nutrition_service.py
    # Sử dụng nutrition_service.get_nutrition_analysis (giả định import được)
    nutrition_data = nutrition_service.get_nutrition_analysis(ingredients)

    # Kiểm tra nếu service trả về lỗi (có key "error" trong dict)
    if "error" in nutrition_data:
        # Sử dụng mã lỗi 500 nếu là lỗi nội bộ/API, hoặc mã lỗi cụ thể nếu có
        status_code = nutrition_data.get('status_code', 500)
        return jsonify(nutrition_data), status_code

    return jsonify(nutrition_data) # Trả về dữ liệu dinh dưỡng thành công
# ---------------------------------------------

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
    try: return render_template('user.html') 
    except: return "Trang User Profile"

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)