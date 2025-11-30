from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from core import data_manager, search_handler, service, ai_service
import os

app = Flask(__name__)
# Key giả định, sau này thay bằng key thật
WEATHER_API_KEY = "DUMMY_API_KEY_FOR_NOW"

# --- CẤU HÌNH UPLOAD ẢNH ---
# Nơi lưu ảnh tạm thời khi người dùng upload lên
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# Tự động tạo thư mục nếu chưa có
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- KHỞI TẠO CÁC MODULE (Bao gồm cả AI) ---
db_manager = data_manager.DataManager()
search_engine = search_handler.SearchHandler()
tourism_service = service.SmartTourismService(weather_api_key=WEATHER_API_KEY)

# Khởi động AI Engine (Load model 1 lần duy nhất lúc chạy server)
print("⏳ Đang tải Model AI... Vui lòng đợi...")
ai_engine = ai_service.AIService(model_dir='ml_models')
print("✅ Model AI đã sẵn sàng!")

@app.route('/')
def index():
    return render_template('index.html')

# --- ROUTE XỬ LÝ NHẬN DIỆN ẢNH (MỚI) ---
@app.route('/predict', methods=['POST'])
def predict_route():
    """
    Nhận file ảnh từ người dùng -> Đưa qua AI -> Lấy tên món -> Tìm kiếm quán bán món đó.
    """
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)

    if file:
        try:
            # 1. Lưu ảnh tạm
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # 2. Gọi AI nhận diện
            label, score = ai_engine.predict_image(filepath)
            
            # Xóa ảnh sau khi dùng xong để tiết kiệm dung lượng (Tùy chọn)
            # os.remove(filepath)

            # 3. Xử lý kết quả
            if label and label != "Không nhận diện được":
                print(f"🤖 AI Nhận diện: {label} ({score*100:.1f}%)")
                # Chuyển hướng sang trang kết quả với từ khóa là tên món vừa đoán được
                # Ví dụ: Đoán ra "Phở bò" -> Tự động tìm quán "Phở bò"
                return redirect(url_for('results_page', query=label))
            else:
                # Nếu AI bó tay
                return render_template('index.html', error="AI không nhận diện được món này. Thử ảnh khác nhé!")
                
        except Exception as e:
            print(f"Lỗi xử lý ảnh: {e}")
            return render_template('index.html', error="Có lỗi xảy ra khi xử lý ảnh.")

    return redirect(url_for('index'))

# --- CÁC ROUTE CŨ (GIỮ NGUYÊN) ---
@app.route('/results')
def results_page():
    # 1. LẤY DỮ LIỆU TỪ GIAO DIỆN
    query = request.args.get('query', '').strip().lower()
    group_filter = request.args.get('group_filter')
    vibe_filter = request.args.get('vibe_filter')
    
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

    # 2. LẤY DỮ LIỆU
    all_restaurants = db_manager.get_all_restaurants(
        use_cache=False, 
        user_lat=user_lat, 
        user_lon=user_lon,
        enable_mock=False
    )
    
    # 3. TÌM KIẾM
    if query:
        temp_results = search_engine.search(all_restaurants, query)
    else:
        temp_results = all_restaurants

    # 4. LỌC NÂNG CAO
    final_results = []
    for r in temp_results:
        # Lọc khoảng cách
        if user_lat and user_lon:
            if r.get("distance_km", 0) == 0 and r.get('lat') and r.get('lng'):
                try:
                    r["distance_km"] = ((r['lat'] - user_lat)**2 + (r['lng'] - user_lon)**2)**0.5 * 111
                except:
                    r["distance_km"] = 999 
            if max_distance is not None and r.get("distance_km", 0) > max_distance:
                continue 
        
        # Lọc nhóm
        if group_filter and group_filter not in ["", "all"]:
            res_groups = r.get('group_type', [])
            if not isinstance(res_groups, list) or group_filter not in res_groups:
                continue 

        # Lọc vibe
        if vibe_filter and vibe_filter not in ["", "all"]:
            res_vibe = r.get('vibe', '')
            if res_vibe != vibe_filter:
                continue

        final_results.append(r)

    return render_template('results.html', 
                           restaurants=final_results, 
                           query=query,
                           group_filter=group_filter, 
                           vibe_filter=vibe_filter)

@app.route('/recommend')
def recommend_page():
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

    return render_template('results.html', restaurants=recommendations, context=context_desc, query="Gợi ý thông minh")

@app.route('/user')
def user_page():
    try: return render_template('user.html') 
    except: return "Trang User Profile"

@app.route('/logout')
def logout():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)