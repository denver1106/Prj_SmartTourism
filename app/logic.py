import datetime
from firebase_admin import firestore
from google.cloud.firestore_v1.field_path import FieldPath
from haversine import haversine, Unit

# === HÀM CHUNG (KẾT NỐI) ===
# Giả định team Website sẽ import 'db' từ file __init__.py
# import_db_from_init_py = True 

# === BƯỚC 1: HÀM TÌM MÓN / TÌM QUÁN ===

def search_food(db, query_text):
    """
    Tìm món ăn theo 'normalizedName' hoặc 'tags'.
    Đây là cách tìm đơn giản, không phân biệt "ý muốn".
    """
    query_text = query_text.lower().strip()
    
    # 1. Tìm theo tên chuẩn (normalizedName)
    # Đây là truy vấn chính xác (ví dụ: "pho bo" == "pho bo")
    name_query = db.collection('foods') \
                   .where('normalizedName', '==', query_text) \
                   .stream()

    # 2. Tìm theo tag (ví dụ: query_text là 'mon_nuoc')
    # 'array_contains' dùng để tìm 1 phần tử trong 1 mảng
    tag_query = db.collection('foods') \
                  .where('tags', 'array_contains', query_text) \
                  .stream()

    # 3. Gộp kết quả (dùng dict để tránh trùng lặp)
    results = {}
    for doc in name_query:
        results[doc.id] = doc.to_dict()
    for doc in tag_query:
        results[doc.id] = doc.to_dict()
        
    return list(results.values())

def search_restaurants(db, 
                       query_text=None, 
                       tags=None, 
                       price_levels=None, 
                       user_lat=None, 
                       user_lng=None, 
                       max_distance_km=None):
    """
    Đây là hàm tìm kiếm quán ăn "thần thánh", lọc theo TẤT CẢ tiêu chí.
    Vì Firestore hạn chế truy vấn phức tạp, chúng ta sẽ TẢI VỀ 
    và LỌC BẰNG PYTHON.
    (Cách này CHỈ TỐT cho 20-30 quán, nếu 1000 quán phải dùng Algolia)
    """
    all_restaurants = db.collection('restaurants').stream()
    results = []

    for doc in all_restaurants:
        restaurant = doc.to_dict()
        restaurant['id'] = doc.id # Thêm ID vào
        
        keep = True # Giả định là giữ lại quán này

        # Lọc 1: Lọc theo Tên (Query Text)
        if keep and query_text:
            if query_text.lower() not in restaurant.get('name', '').lower():
                keep = False
        
        # Lọc 2: Lọc theo Tags (ví dụ: 'truyen_thong')
        if keep and tags and isinstance(tags, list):
            restaurant_tags = restaurant.get('tags', [])
            if not any(tag in restaurant_tags for tag in tags):
                keep = False

        # Lọc 3: Lọc theo Giá (ví dụ: ['low', 'medium'])
        if keep and price_levels and isinstance(price_levels, list):
            if restaurant.get('priceLevel') not in price_levels:
                keep = False
        
        # Lọc 4: Lọc theo Khoảng Cách (Yêu cầu của bạn)
        if keep and user_lat and user_lng and max_distance_km:
            res_lat = restaurant.get('lat')
            res_lng = restaurant.get('lng')
            if res_lat and res_lng:
                user_location = (user_lat, user_lng)
                restaurant_location = (res_lat, res_lng)
                
                # Dùng thư viện 'haversine' bạn vừa cài
                distance = haversine(user_location, restaurant_location, unit=Unit.KILOMETERS)
                
                if distance > max_distance_km:
                    keep = False
            else:
                keep = False # Ẩn quán nếu không có tọa độ

        # Nếu vượt qua tất cả, giữ lại quán này
        if keep:
            results.append(restaurant)
            
    return results

# === BƯỚC 2: HÀM LẤY ĐẶC SẢN (PLACE) ===

def get_specialties_by_place(db, place_name):
    """
    Lấy đặc sản theo place.
    (Dựa trên collection 'place_specialties' của bạn)
    """
    # 1. Chuẩn hóa tên (ví dụ: "Đà Nẵng" -> "da nang")
    normalized_place = place_name.lower().strip()
    
    try:
        # 2. Tìm document "place"
        place_query = db.collection('place_specialties') \
                        .where('normalizedPlace', '==', normalized_place) \
                        .limit(1) \
                        .stream()
        
        place_doc = next(place_query, None)
        
        if not place_doc:
            print(f"Không tìm thấy đặc sản cho: {place_name}")
            return []

        # 3. Lấy ra danh sách foodId đặc sản
        food_ids = place_doc.to_dict().get('foods', [])
        if not food_ids:
            return []

        # 4. Truy vấn CSDL để lấy thông tin các món ăn đó
        # (FieldPath.document_id() là cách truy vấn bằng ID)
        food_query = db.collection('foods') \
                       .where(FieldPath.document_id(), 'in', food_ids) \
                       .stream()
                       
        foods = [doc.to_dict() for doc in food_query]
        return foods

    except Exception as e:
        print(f"LỖI khi lấy đặc sản: {e}")
        return []

# === BƯỚC 3: HÀM LƯU / LẤY / LỌC HISTORY ===
# (Dựa trên collection 'histories' của bạn)

def save_history(db, user_id, food_id, restaurant_id, query_text=""):
    """
    Lưu 1 record mới vào 'histories'.
    (Team Website sẽ gọi hàm này)
    """
    try:
        history_data = {
            'userId': user_id,
            'foodId': food_id,
            'restaurantId': restaurant_id,
            'query': query_text, # Lưu lại user search gì
            'timestamp': firestore.SERVER_TIMESTAMP 
        }
        db.collection('histories').add(history_data)
        print(f"--- Đã lưu history cho user {user_id} ---")
    except Exception as e:
        print(f"LỖI khi lưu history: {e}")

def get_user_history_blacklist(db, user_id, limit=5):
    """
    Lấy N món ăn (foodId) mà user mới ăn gần nhất
    để cho vào "danh sách đen".
    """
    try:
        history_query = db.collection('histories') \
                          .where('userId', '==', user_id) \
                          .order_by('timestamp', direction=firestore.Query.DESCENDING) \
                          .limit(limit)
                          
        history_docs = history_query.stream()
        
        # Dùng 'set' để tự động loại bỏ trùng lặp
        blacklist_food_ids = set()
        for doc in history_docs:
            blacklist_food_ids.add(doc.to_dict().get('foodId'))
            
        print(f"--- Blacklist của user (món mới ăn): {blacklist_food_ids} ---")
        return blacklist_food_ids
        
    except Exception as e:
        print(f"LỖI khi lấy blacklist: {e}")
        return set() # Trả về set rỗng

# === BƯỚC 4: HÀM LẤY DATA CHO FILTER ===

def get_filter_options(db):
    """
    Lấy tất cả các tags độc nhất từ CSDL 'foods'
    để team Website
    hiển thị (populate) ra các ô checkbox/dropdown.
    """
    try:
        foods_docs = db.collection('foods').stream()
        
        all_tags = set()
        all_place_tags = set()
        
        for doc in foods_docs:
            food = doc.to_dict()
            all_tags.update(food.get('tags', []))
            all_place_tags.update(food.get('placeTags', []))
            
        return {
            "food_tags": sorted(list(all_tags)),
            "place_tags": sorted(list(all_place_tags)),
            "price_levels": ["low", "medium", "high"] # Hardcode
        }
    except Exception as e:
        print(f"LỖI khi lấy options filter: {e}")
        return {}