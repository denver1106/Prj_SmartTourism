import json
import os
from datetime import datetime

# Giả định thư mục /data/ nằm ở thư mục gốc của dự án
# (cùng cấp với /app/, run.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data')

class DataManager:
    def __init__(self):
        print("--- Đang tải dữ liệu JSON vào bộ nhớ... ---")
        
        # 1. Tải 3 file JSON tĩnh
        self.foods_list = self._load_json(os.path.join(DATA_PATH, 'foods.json'))
        self.restaurants_list = self._load_json(os.path.join(DATA_PATH, 'restaurants.json'))
        self.context_rules = self._load_json(os.path.join(DATA_PATH, 'context_rules.json'))

        # 2. Tối ưu dữ liệu (Đây là bước QUAN TRỌNG NHẤT)
        print("--- Đang tối ưu (pre-processing) dữ liệu... ---")
        
        # Chuyển list thành dict (hash map) để truy cập O(1)
        # Thay vì phải lặp (loop) qua list để tìm, ta truy cập thẳng
        # 
        
        # Tối ưu 'foods.json'
        self.foods_by_id = {food['id']: food for food in self.foods_list}
        self.foods_by_name = {food['name'].lower(): food for food in self.foods_list}

        # Tối ưu 'restaurants.json'
        self.restaurants_by_id = {r['id']: r for r in self.restaurants_list}
        
        # Tối ưu liên kết giữa Món ăn và Nhà hàng
        # Ví dụ: { 'pho_bo_id': ['res_1_id', 'res_2_id'], ... }
        self.restaurants_by_food_id = {} 
        for r in self.restaurants_list:
            for food_id in r.get('menu', []): # Giả sử nhà hàng có 'menu' là list các food_id
                if food_id not in self.restaurants_by_food_id:
                    self.restaurants_by_food_id[food_id] = []
                self.restaurants_by_food_id[food_id].append(r['id'])
        
        print("--- Tải dữ liệu hoàn tất! ---")

    def _load_json(self, file_path):
        """Hàm nội bộ để đọc 1 file JSON."""
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"LỖI: Không tìm thấy file {file_path}. Trả về list rỗng.")
            return []
        except json.JSONDecodeError:
            print(f"LỖI: File {file_path} bị sai cú pháp JSON. Trả về list rỗng.")
            return []

    # --- CÁC HÀM TIỆN ÍCH ĐỂ LOGIC WEB GỌI ---
    
    def get_food_by_name(self, name):
        """Tìm món ăn bằng tên (rất nhanh)."""
        return self.foods_by_name.get(name.lower())

    def get_food_by_id(self, food_id):
        """Lấy món ăn bằng ID (rất nhanh)."""
        return self.foods_by_id.get(food_id)

    def get_variations(self, food_id):
        """Lấy các biến thể của món ăn."""
        food = self.get_food_by_id(food_id)
        if not food:
            return []
        
        variation_ids = food.get('variations', [])
        return [self.get_food_by_id(vid) for vid in variation_ids]

    def get_restaurants_for_food(self, food_id):
        """Lấy danh sách nhà hàng bán món ăn này (rất nhanh)."""
        restaurant_ids = self.restaurants_by_food_id.get(food_id, [])
        return [self.restaurants_by_id.get(rid) for rid in restaurant_ids]

    def get_contextual_suggestion(self):
        """
        Logic gợi ý dựa trên ngữ cảnh (thời gian, mùa...).
        Đây là một ví dụ đơn giản.
        """
        current_hour = datetime.now().hour
        # Đọc từ context_rules (ví dụ)
        if 6 <= current_hour < 10:
            rule_key = self.context_rules.get('morning', 'default_breakfast_id')
            return self.get_food_by_id(rule_key)
        # (Thêm logic cho trưa, tối, mùa hè...)
        
        return None