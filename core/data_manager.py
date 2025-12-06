import pymysql
import json
import math
from typing import List, Dict, Any

class DataManager:
    def __init__(self, db_connection):
        if db_connection is None: raise ValueError("DB Connection Lost")
        self.db = db_connection
        self._cache = {"restaurants": None}

    def _safe_float(self, val, default=0.0):
        try: return float(val) if val is not None else default
        except: return default

    def _parse_json(self, raw_data: Any) -> Any:
        if raw_data is None: return []
        if isinstance(raw_data, (dict, list)): return raw_data
        if isinstance(raw_data, str):
            try: return json.loads(raw_data)
            except: pass
        return []

    def _parse_tags(self, tags_raw: Any) -> List[str]:
        """Làm sạch tag, lọc bỏ các tag kỹ thuật rác (addr, source, phone...)"""
        if not tags_raw: return []
        
        # Chuyển đổi về List Python
        parsed_list = []
        if isinstance(tags_raw, list): 
            parsed_list = tags_raw
        elif isinstance(tags_raw, str):
            clean = tags_raw.strip()
            # Xử lý nếu là JSON String
            if clean.startswith("{") or clean.startswith("["):
                try: 
                    loaded = json.loads(clean)
                    # Nếu là Dict (OSM tags), chỉ lấy giá trị cuisine hoặc diet
                    if isinstance(loaded, dict):
                        target_keys = ["cuisine", "diet", "amenity"]
                        parsed_list = [v for k,v in loaded.items() if k in target_keys or (not ":" in k and not "source" in k)]
                    elif isinstance(loaded, list):
                        parsed_list = loaded
                except: pass
            else:
                # Nếu là chuỗi "pho, bun"
                parsed_list = clean.split(",")
        
        # Lọc lần cuối: Loại bỏ các tag rác
        final_tags = []
        garbage_prefixes = ["addr:", "source:", "phone:", "website:", "ref:", "opening_hours", "u'", "'"]
        
        for t in parsed_list:
            t_str = str(t).lower().strip().replace('"', '').replace("'", "")
            # Chỉ lấy tag hợp lệ (không chứa ký tự lạ, không phải tag kỹ thuật)
            if len(t_str) > 2 and not any(t_str.startswith(p) for p in garbage_prefixes):
                final_tags.append(t_str)
                
        return list(set(final_tags))

    def get_all_restaurants(self, use_cache=True, user_lat=None, user_lon=None):
        try:
            with self.db.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, address, lat, lng, tags, menu, reviews,
                           price_level, rating, description, image_url, province_name
                    FROM restaurants
                """)
                rows = cursor.fetchall()

            results = []
            for r in rows:
                item = {
                    "id": r["id"],
                    "name": r["name"] or "Quán chưa đặt tên",
                    "address": r["address"] or "",
                    "lat": self._safe_float(r["lat"]),
                    "lng": self._safe_float(r["lng"]),
                    "tags": self._parse_tags(r["tags"]),
                    "menu": self._parse_json(r["menu"]),
                    "reviews": self._parse_json(r["reviews"]),
                    "price_level": r["price_level"] or "",
                    "rating": self._safe_float(r["rating"], 3.0),
                    "description": r["description"] or "",
                    "image_url": r["image_url"] or "",
                    "province_name": r.get("province_name") or "",
                    "distance_km": 0.0
                }
                if user_lat and user_lon and item["lat"]:
                    item["distance_km"] = self._haversine(user_lat, user_lon, item["lat"], item["lng"])
                elif user_lat == 0:
                    item["distance_km"] = 999.0
                
                results.append(item)
            return results
        except Exception as e:
            print(f"❌ DM Error: {e}")
            return []
    
    def get_restaurants_near_user(self, lat, lng, radius_km=20):
        all_r = self.get_all_restaurants(use_cache=True, user_lat=lat, user_lon=lng)
        return [r for r in all_r if r["distance_km"] <= radius_km]

    def get_user_history_full(self, user_id):
        try:
            with self.db.cursor() as cur:
                # SỬA TẠI ĐÂY: Bỏ DISTINCT, thêm điều kiện lọc action, thêm h.created_at
                sql = """
                    SELECT 
                        r.id, r.name, r.address, r.image_url, 
                        r.lat, r.lng, r.rating, r.price_level,
                        MAX(h.created_at) AS latest_viewed_at, -- Lấy thời gian hoạt động mới nhất
                        SUBSTRING_INDEX(GROUP_CONCAT(h.action ORDER BY h.created_at DESC), ',', 1) AS last_action -- Lấy hành động gần nhất
                    FROM user_history h
                    JOIN restaurants r ON h.restaurant_id = r.id
                    WHERE h.user_id = %s
                        AND h.action IN ('view', 'visit') -- Chỉ lấy các hoạt động xem và ghé thăm
                    GROUP BY 
                        r.id, r.name, r.address, r.image_url, r.lat, r.lng, r.rating, r.price_level
                    ORDER BY 
                        latest_viewed_at DESC
                    LIMIT 20
                """
                cur.execute(sql, (user_id,))
                rows = cur.fetchall()
            
            # Xử lý data (Tính khoảng cách placeholder nếu cần)
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "name": r["name"],
                    "address": r.get("address", ""),
                    "image_url": r.get("image_url", ""),
                    "rating": r.get("rating", 0),
                    "price": r.get("price_level", ""),
                    # Sử dụng thời gian hoạt động mới nhất
                    "created_at": r["latest_viewed_at"], 
                    # (Tùy chọn) Thêm hành động gần nhất để bạn có thể hiển thị trong template
                    "last_action": r["last_action"]
             })
            return results
        except Exception as e:
            print(f"History Error: {e}")
            return []

    def get_user_preferences(self, user_id) -> Dict[str, Any]:
        """Lấy thông tin sở thích người dùng, sắp xếp theo thời gian mới nhất"""
        try:
            with self.db.cursor() as cur:
                # Sắp xếp DESC limit 1 để luôn lấy dòng mới nhất nếu lỡ có nhiều dòng trùng
                sql = """
                    SELECT liked_tags, disliked_tags 
                    FROM user_preferences 
                    WHERE user_id = %s 
                    ORDER BY id DESC LIMIT 1
                """
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
            
            if row: 
                # Parse JSON và trả về list
                likes = self._parse_json(row.get("liked_tags"))
                dislikes = self._parse_json(row.get("disliked_tags"))
                
                # Đảm bảo kết quả là list (đề phòng _parse_json trả về null)
                if not isinstance(likes, list): likes = []
                if not isinstance(dislikes, list): dislikes = []

                return {
                    "like_tags": [str(t).lower().strip() for t in likes],
                    "dislike_tags": [str(t).lower().strip() for t in dislikes]
                }
        except Exception as e: 
            print(f"❌ Get Prefs Error: {e}")
        
        return {"like_tags": [], "dislike_tags": []}

    def save_user_preferences(self, user_id, liked_list, disliked_list):
        """Lưu sở thích: Tự động kiểm tra đã có hay chưa để Insert hoặc Update"""
        try:
            # 1. Chuyển List thành JSON string để lưu DB
            val_like = json.dumps(liked_list, ensure_ascii=False)
            val_dislike = json.dumps(disliked_list, ensure_ascii=False)

            with self.db.cursor() as cur:
                # 2. Kiểm tra xem user này đã có record chưa
                cur.execute("SELECT id FROM user_preferences WHERE user_id = %s", (user_id,))
                existing_row = cur.fetchone()

                if existing_row:
                    # 3A. Nếu có rồi -> UPDATE
                    sql = """
                        UPDATE user_preferences 
                        SET liked_tags = %s, disliked_tags = %s 
                        WHERE user_id = %s
                    """
                    cur.execute(sql, (val_like, val_dislike, user_id))
                else:
                    # 3B. Nếu chưa có -> INSERT
                    sql = """
                        INSERT INTO user_preferences (user_id, liked_tags, disliked_tags) 
                        VALUES (%s, %s, %s)
                    """
                    cur.execute(sql, (user_id, val_like, val_dislike))
            
            # 4. Commit thay đổi
            self.db.commit()
            return True

        except Exception as e: 
            print("Save Pref Error:", e)
            self.db.rollback()
            return False

    def update_user_history(self, user_id, rid, action='view'):
        try:
            with self.db.cursor() as cur:
                cur.execute("INSERT INTO user_history (user_id, restaurant_id, action, created_at) VALUES (%s, %s, %s, NOW())", (user_id, rid, action))
            self.db.commit()
        except: self.db.rollback()

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        if not lat1 or not lon1 or not lat2 or not lon2: return 9999
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))