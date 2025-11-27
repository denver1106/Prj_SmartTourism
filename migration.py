import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

# --- KHỞI TẠO FIREBASE (Làm 1 lần) ---
try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cred_path = os.path.join(base_dir, 'instance', 'firebase-key.json')
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("--- KẾT NỐI FIREBASE THÀNH CÔNG! ---")
except Exception as e:
    if "already exists" not in str(e): # Bỏ qua lỗi "đã kết nối"
        print(f"LỖI: Không thể kết nối Firebase. Lỗi: {e}")
        exit()
    else:
        db = firestore.client() # Lấy client đã kết nối
        print("--- Đã kết nối Firebase (sử dụng app có sẵn) ---")

def read_json_file(filename):
    """Hàm phụ để đọc file JSON (với utf-8-sig cho an toàn)"""
    try:
        filepath = os.path.join('data', filename)
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"LỖI: Không thể mở file 'data/{filename}'. Lỗi: {e}")
        return None

# === HÀM 1: ĐẨY DỮ LIỆU 'foods' ===
def migrate_foods(batch):
    print("\n--- Bắt đầu đẩy 'foods' ---")
    foods_data = read_json_file('foods.json')
    if not foods_data: return 0
    
    count = 0
    for item in foods_data:
        doc_id = item['id']
        # ĐẶC BIỆT: Chuyển 'createdAt' thành timestamp thật của server
        item['createdAt'] = firestore.SERVER_TIMESTAMP
        doc_ref = db.collection('foods').document(doc_id)
        batch.set(doc_ref, item)
        count += 1
    print(f"Đã chuẩn bị {count} 'foods'")
    return count

# === HÀM 2: ĐẨY DỮ LIỆU 'restaurants' ===
def migrate_restaurants(batch):
    print("\n--- Bắt đầu đẩy 'restaurants' ---")
    restaurants_data = read_json_file('restaurants.json')
    if not restaurants_data: return 0
    
    count = 0
    for item in restaurants_data:
        doc_id = item['id']
        
        # ĐẶC BIỆT: Chuyển 'createdAt' thành timestamp thật
        item['createdAt'] = firestore.SERVER_TIMESTAMP
        
        # ĐẶC BIỆT: Chuyển lat/lng thành Geopoint
        # (Lưu ý: Chúng ta vẫn giữ lat, lng riêng lẻ như kế hoạch của bạn
        # nhưng thêm 'location' (Geopoint) để team Location có thể truy vấn)
        if 'lat' in item and 'lng' in item:
            item['location'] = firestore.GeoPoint(item['lat'], item['lng'])
        
        doc_ref = db.collection('restaurants').document(doc_id)
        batch.set(doc_ref, item)
        count += 1
    print(f"Đã chuẩn bị {count} 'restaurants'")
    return count

# === HÀM 3: ĐẨY DỮ LIỆU 'users' ===
def migrate_users(batch):
    print("\n--- Bắt đầu đẩy 'users' ---")
    users_data = read_json_file('users.json')
    if not users_data: return 0
    
    count = 0
    for item in users_data:
        doc_id = item['id'] # Dùng ID 'demo_user'
        doc_ref = db.collection('users').document(doc_id)
        batch.set(doc_ref, item)
        count += 1
    print(f"Đã chuẩn bị {count} 'users' (mẫu)")
    return count

# === HÀM 4: ĐẨY DỮ LIỆU 'histories' ===
def migrate_histories(batch):
    print("\n--- Bắt đầu đẩy 'histories' ---")
    histories_data = read_json_file('histories.json')
    if not histories_data: return 0
    
    count = 0
    for item in histories_data:
        doc_id = item['id']
        
        # ĐẶC BIỆT: Chuyển string 'timestamp' thành Timestamp thật
        try:
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
        except Exception:
            item['timestamp'] = firestore.SERVER_TIMESTAMP
            
        doc_ref = db.collection('histories').document(doc_id)
        batch.set(doc_ref, item)
        count += 1
    print(f"Đã chuẩn bị {count} 'histories' (mẫu)")
    return count

# === HÀM 5: ĐẨY DỮ LIỆU 'place_specialties' ===
def migrate_place_specialties(batch):
    print("\n--- Bắt đầu đẩy 'place_specialties' ---")
    places_data = read_json_file('place_specialties.json')
    if not places_data: return 0
    
    count = 0
    for item in places_data:
        doc_id = item['id']
        doc_ref = db.collection('place_specialties').document(doc_id)
        batch.set(doc_ref, item)
        count += 1
    print(f"Đã chuẩn bị {count} 'place_specialties'")
    return count

# === CHẠY SCRIPT ===
def run_migration():
    print("Đang chạy script di trú dữ liệu (theo 5 collections)...")
    
    # Tạo 1 'batch' để đẩy 1 lần cho nhanh
    batch = db.batch()
    
    total_count = 0
    total_count += migrate_foods(batch)
    total_count += migrate_restaurants(batch)
    total_count += migrate_histories(batch)
    total_count += migrate_place_specialties(batch)
    
    # Đẩy 1 lần lên server
    try:
        batch.commit()
        print(f"\n--- THÀNH CÔNG! ---")
        print(f"Đã đẩy/cập nhật tổng cộng {total_count} documents.")
        print("LÊN FIREBASE CONSOLE KIỂM TRA LẠI DỮ LIỆU.")
    except Exception as e:
        print(f"\n--- LỖI KHI ĐẨY DỮ LIỆU LÊN SERVER: {e} ---")

# Chạy hàm chính
run_migration()