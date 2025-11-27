import json
import os
import firebase_admin
from firebase_admin import credentials, firestore

# --- KẾT NỐI FIREBASE (Giống hệt app/__init__.py) ---
print("Đang kết nối tới Firebase...")
try:
    cred_path = os.path.join(os.path.dirname(__file__), 'instance', 'firebase-key.json')
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Kết nối thành công.")
except Exception as e:
    print(f"Lỗi kết nối: {e}")
    exit()

# --- HÀM ĐỂ ĐỌC JSON ---
def load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Lỗi đọc file {file_path}: {e}")
        return None

# --- BẮT ĐẦU IMPORT ---

# 1. Import FOODS.JSON
print("\nBắt đầu import 'foods.json'...")
foods_list = load_json('data/foods.json')
if foods_list:
    # Lấy 'collection' (giống như 'bảng') tên là 'foods'
    food_collection = db.collection('foods')
    for food in foods_list:
        # Dùng 'id' của món ăn (vd: 'pho_bo') làm 'document_id'
        doc_id = food['id']
        food_collection.document(doc_id).set(food)
        print(f"Đã thêm: {doc_id}")
    print("Import 'foods' hoàn tất!")

# 2. Import RESTAURANTS.JSON
print("\nBắt đầu import 'restaurants.json'...")
restaurants_list = load_json('data/restaurants.json')
if restaurants_list:
    restaurant_collection = db.collection('restaurants')
    for restaurant in restaurants_list:
        doc_id = restaurant['id']
        restaurant_collection.document(doc_id).set(restaurant)
        print(f"Đã thêm: {doc_id}")
    print("Import 'restaurants' hoàn tất!")

# (Bạn có thể làm tương tự cho 'context_rules.json')