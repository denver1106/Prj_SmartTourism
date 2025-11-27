import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Dict, Optional, Any
import random

class DataManager:
    """
    Quản lý kết nối Firestore, chuẩn hóa dữ liệu và tạo dữ liệu giả THÔNG MINH.
    Hỗ trợ: Mock data theo vị trí, lấy đặc sản vùng miền, context mô tả phong phú.
    CẬP NHẬT: Đã hỗ trợ lấy group_type và vibe.
    """
    def __init__(self, cred_path: str = "firebase-key.json", use_app_name: Optional[str] = None):
        # --- Logic khởi tạo Firebase an toàn ---
        if not firebase_admin._apps:
            try:
                cred = credentials.Certificate(cred_path)
                if use_app_name:
                    self.app = firebase_admin.initialize_app(cred, name=use_app_name)
                else:
                    self.app = firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"CRITICAL ERROR: Không thể khởi tạo Firebase. Lỗi: {e}")
                self.db = None
                return
        else:
            try:
                if use_app_name:
                    self.app = firebase_admin.get_app(name=use_app_name)
                else:
                    self.app = firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(cred_path)
                if use_app_name:
                    self.app = firebase_admin.initialize_app(cred, name=use_app_name)
                else:
                    self.app = firebase_admin.initialize_app(cred)

        self.db = firestore.client(app=self.app)
        
        self._cache = {
            "restaurants": None,
            "foods": None,
            "places": None
        }

    # ---------------- 1. HÀM LẤY ĐẶC SẢN TỪ FIREBASE ----------------
    def get_place_specialties(self, place_name: str) -> List[str]:
        if not self.db or not place_name:
            return []
        
        clean_name = place_name.strip().lower()
        specialties = []

        try:
            coll_ref = self.db.collection("place_specialties")
            docs = coll_ref.where("normalizedPlace", "==", clean_name).stream()
            
            found = False
            for doc in docs:
                found = True
                data = doc.to_dict()
                foods = data.get("foods", [])
                if isinstance(foods, list):
                    specialties.extend(foods)
            
            if not found:
                doc_id = clean_name.replace(" ", "_")
                doc = coll_ref.document(doc_id).get()
                if doc.exists:
                    foods = doc.to_dict().get("foods", [])
                    if isinstance(foods, list):
                        specialties.extend(foods)
                        
        except Exception as e:
            print(f"Lỗi lấy đặc sản: {e}")
            
        return specialties

    # ---------------- 2. MOCK GENERATOR (FULL CONTEXT) ----------------
    def _generate_mock_data(self, user_lat: float, user_lon: float, count: int = 10, special_foods: List[str] = None) -> List[Dict[str, Any]]:
        """
        Sinh dữ liệu giả bao gồm cả group_type và vibe để test bộ lọc.
        """
        mocks = []
        
        default_categories = [
            {"base": "Phở Bò", "menu": ["phở tái", "phở nạm", "quẩy"], "tags": ["sáng", "nóng"]},
            {"base": "Cơm Tấm", "menu": ["cơm sườn", "bì", "chả"], "tags": ["trưa", "no"]},
            {"base": "Bún Bò Huế", "menu": ["bún bò", "giò heo"], "tags": ["sáng", "cay"]},
            {"base": "Trà Sữa", "menu": ["trà sữa trân châu", "hồng trà"], "tags": ["chiều"]},
            {"base": "Bún Đậu", "menu": ["bún đậu", "mắm tôm"], "tags": ["trưa"]},
            {"base": "Pizza", "menu": ["pizza hải sản", "mỳ ý"], "tags": ["tối", "Âu"]},
            {"base": "Bánh Mì", "menu": ["bánh mì thịt", "bánh mì chảo"], "tags": ["nhanh", "sáng"]},
            {"base": "Lẩu Nướng", "menu": ["ba chỉ bò", "nầm nướng"], "tags": ["tối", "nhậu"]},
        ]
        
        suffixes = ["Gia Truyền", "Bà Ba", "Chú Tư", "Sài Gòn", "Phố Cổ", "Vỉa Hè", "Ngon", "Gốc", "Luxury"]
        
        # Danh sách các nhóm và vibe để random cho dữ liệu giả
        mock_groups = ["alone", "family", "friends", "dating", "company", "couple"]
        mock_vibes = ["street_food", "luxury", "cozy", "vintage", "modern"]

        descriptions_pool = [
            "Hương vị hài hòa, cân bằng giữa mặn — ngọt — chua.",
            "Thành phần tươi ngon, chế biến tinh tế.",
            "Món ăn đậm đà, kích thích vị giác ngay từ miếng đầu tiên.",
            "Phù hợp để chia sẻ cùng gia đình và bạn bè.",
            "Trình bày tinh tế, bắt mắt, ăn trước đã thấy ngon.",
            "Đầy đặn, ngon miệng — no lâu, bổ dưỡng.",
            "Không gian thoáng mát, phục vụ nhanh.",
            "Món ăn đường phố nổi tiếng, đậm đà bản sắc.",
        ]

        source_categories = default_categories
        
        if special_foods and len(special_foods) > 0:
            custom_categories = []
            for food in special_foods:
                food_name = food.replace("_", " ").title()
                custom_categories.append({
                    "base": food_name,
                    "menu": [food_name, food_name + " đặc biệt"],
                    "tags": ["đặc sản", "địa phương", "ngon"]
                })
            source_categories = custom_categories

        for i in range(count):
            cat = random.choice(source_categories)
            suffix = random.choice(suffixes)
            name = f"{cat['base']} {suffix}"
            
            offset_lat = (random.random() - 0.5) * 0.035 
            offset_lon = (random.random() - 0.5) * 0.035
            mock_lat = user_lat + offset_lat
            mock_lng = user_lon + offset_lon
            
            dist_approx = ((mock_lat - user_lat)**2 + (mock_lng - user_lon)**2)**0.5 * 111

            # Random 1-3 nhóm phù hợp cho mỗi quán giả
            random_groups = random.sample(mock_groups, k=random.randint(1, 3))

            mocks.append({
                "id": f"mock_special_{i}",
                "name": name,
                "address": "Vị trí đề xuất (Gần bạn)",
                "lat": mock_lat,
                "lng": mock_lng,
                "tags": ["demo", "mock"] + cat["tags"],
                "menu": cat["menu"],
                "foods": cat["menu"], 
                "price_level": random.choice(["30k", "50k", "100k"]),
                "description": random.choice(descriptions_pool),
                "distance_km": dist_approx,
                
                # 🔥 [MỚI] THÊM DỮ LIỆU GIẢ CHO GROUP VÀ VIBE
                "group_type": random_groups,
                "vibe": random.choice(mock_vibes)
            })
            
        return mocks

    # ---------------- 3. MAIN LOADER (LẤY DỮ LIỆU) ----------------
    def get_all_restaurants(self, use_cache: bool = True, user_lat: float = None, user_lon: float = None, 
                          enable_mock: bool = True, place_scope: str = None) -> List[Dict[str, Any]]:
        """
        Lấy quán ăn từ DB + Mock Data.
        """
        restaurants = []
        
        # 1. Lấy dữ liệu thật từ Firebase
        if self.db:
            try:
                # Đảm bảo lấy từ bảng 'restaurants'
                ref = self.db.collection("restaurants")
                docs = ref.stream()
                for doc in docs:
                    raw_data = doc.to_dict() or {}
                    
                    lat = raw_data.get("lat")
                    lng = raw_data.get("lng")
                    if lat is None or lng is None:
                        geo = raw_data.get("location") or raw_data.get("rental")
                        if geo and hasattr(geo, 'latitude'):
                            lat = geo.latitude
                            lng = geo.longitude
                    
                    raw_foods = raw_data.get("foods") or raw_data.get("menu") or []
                    if not isinstance(raw_foods, list): raw_foods = [str(raw_foods)]
                    clean_menu = [str(m).lower() for m in raw_foods]

                    item = {
                        "id": doc.id,
                        "name": raw_data.get("name", "Tên chưa cập nhật"),
                        "address": raw_data.get("address", ""),
                        "tags": [str(t).lower() for t in raw_data.get("tags", [])],
                        "menu": clean_menu,       
                        "foods": clean_menu,      
                        "price_level": raw_data.get("price_level", "?"),
                        "lat": float(lat) if lat is not None else None,
                        "lng": float(lng) if lng is not None else None,
                        "description": raw_data.get("description", "Chưa có mô tả."),
                        "distance_km": 0.0,
                        
                        # 🔥 [MỚI] LẤY TRƯỜNG group_type VÀ vibe TỪ DB
                        "group_type": raw_data.get("group_type", []), # Mặc định là list rỗng
                        "vibe": raw_data.get("vibe", "")              # Mặc định là chuỗi rỗng
                    }
                    restaurants.append(item)
            except Exception as e:
                print(f"ERROR loading real data: {e}")

        # 2. Xử lý Mock Data
        if enable_mock:
            target_lat = user_lat if user_lat else 10.7769 
            target_lon = user_lon if user_lon else 106.7009
            
            special_foods = []
            if place_scope:
                special_foods = self.get_place_specialties(place_scope)
            
            mock_data = self._generate_mock_data(target_lat, target_lon, count=20, special_foods=special_foods)
            restaurants.extend(mock_data)

        self._cache["restaurants"] = restaurants
        return restaurants

    def get_restaurants_near_user(self, lat: float, lng: float, radius_km: float = 10.0) -> List[Dict[str, Any]]:
        return self.get_all_restaurants(use_cache=False, user_lat=lat, user_lon=lng, enable_mock=True)
    
    # ---------------- 4. USER HELPERS ----------------
    def get_user_history(self, user_id: str) -> List[str]:
        try:
            if not self.db: return []
            doc = self.db.collection("users").document(user_id).get()
            return [str(x).lower() for x in doc.to_dict().get("history", [])] if doc.exists else []
        except: return []

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        try:
            if not self.db: return {}
            doc = self.db.collection("users").document(user_id).get()
            return doc.to_dict().get("preferences", {}) if doc.exists else {}
        except: return {}

    def update_user_history(self, user_id: str, new_food: str):
        if not self.db: return
        try:
            ref = self.db.collection("users").document(user_id)
            ref.set({"history": firestore.ArrayUnion([str(new_food).lower()])}, merge=True)
        except: pass