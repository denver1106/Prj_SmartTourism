import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Dict, Optional, Any
import random

class DataManager:
    """
    Quản lý kết nối Firestore, chuẩn hóa dữ liệu và tạo dữ liệu giả THÔNG MINH.
    Hỗ trợ: Mock data theo vị trí, lấy đặc sản vùng miền, context mô tả phong phú.
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
        # --- KHẮC PHỤC LỖI Attribute ERROR: Khởi tạo dữ liệu quán ăn ---
        # Gọi hàm tải dữ liệu để đảm bảo self._cache["restaurants"] có giá trị 
        # (và nó được dùng trong get_restaurant_by_id)
        # Tắt mock data khi tải ban đầu để tránh tạo quá nhiều mock mỗi lần khởi động
        self.restaurants_data = self.get_all_restaurants(
            use_cache=False, 
            enable_mock=False
        )
        # Lưu ý: Vì get_all_restaurants lưu vào self._cache["restaurants"], 
        # nên nếu bạn muốn dùng self.restaurants_data, phải gán lại như trên.
        # Hoặc bạn có thể dùng thẳng self._cache["restaurants"] trong get_restaurant_by_id.
        # Tôi sẽ gán vào cả hai để đảm bảo các hàm sau hoạt động:
        # self.restaurants_data = self._cache["restaurants"] 
        # (Dòng trên không cần thiết vì get_all_restaurants đã làm)

    # ---------------- 1. HÀM LẤY ĐẶC SẢN TỪ FIREBASE ----------------
    def get_place_specialties(self, place_name: str) -> List[str]:
        """
        Tra cứu đặc sản của địa phương từ collection 'place_specialties'.
        VD: input "An Giang" -> return ["lẩu mắm", "cá linh kho"...]
        """
        if not self.db or not place_name:
            return []
        
        clean_name = place_name.strip().lower()
        specialties = []

        try:
            # Cách 1: Query theo normalizedPlace
            coll_ref = self.db.collection("place_specialties")
            docs = coll_ref.where("normalizedPlace", "==", clean_name).stream()
            
            found = False
            for doc in docs:
                found = True
                data = doc.to_dict()
                foods = data.get("foods", [])
                if isinstance(foods, list):
                    specialties.extend(foods)
            
            # Cách 2: Nếu query không ra, thử tìm theo ID (ví dụ: an_giang)
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
        Sinh dữ liệu giả. 
        Nếu có special_foods (đặc sản), sẽ ưu tiên tạo quán bán các món đó.
        """
        mocks = []
        
        # Danh sách mặc định (dùng khi không có đặc sản)
        default_categories = [
            {"base": "Phở Bò", "menu": ["phở tái", "phở nạm", "quẩy", "trứng trần"], "tags": ["sáng", "nóng"]},
            {"base": "Cơm Tấm", "menu": ["cơm sườn", "bì", "chả", "trứng ốp la"], "tags": ["trưa", "no"]},
            {"base": "Bún Bò Huế", "menu": ["bún bò", "giò heo", "chả cua"], "tags": ["sáng", "cay"]},
            {"base": "Trà Sữa", "menu": ["trà sữa trân châu", "hồng trà", "flan"], "tags": ["chiều"]},
            {"base": "Bún Đậu", "menu": ["bún đậu", "mắm tôm", "dồi sụn"], "tags": ["trưa"]},
            {"base": "Pizza", "menu": ["pizza hải sản", "mỳ ý", "salad"], "tags": ["tối", "Âu"]},
            {"base": "Bánh Mì", "menu": ["bánh mì thịt", "bánh mì chảo", "xíu mại"], "tags": ["nhanh", "sáng"]},
            {"base": "Lẩu Nướng", "menu": ["ba chỉ bò", "nầm nướng", "lẩu thái"], "tags": ["tối", "nhậu"]},
        ]
        
        suffixes = ["Gia Truyền", "Bà Ba", "Chú Tư", "Sài Gòn", "Phố Cổ", "Vỉa Hè", "Ngon", "Gốc", "Luxury"]
        
        # DANH SÁCH 30 CONTEXT MÔ TẢ PHONG PHÚ
        descriptions_pool = [
            "Hương vị hài hòa, cân bằng giữa mặn — ngọt — chua.",
            "Thành phần tươi ngon, chế biến tinh tế.",
            "Món ăn đậm đà, kích thích vị giác ngay từ miếng đầu tiên.",
            "Cách nêm nếm truyền thống kết hợp phong cách hiện đại.",
            "Textures phong phú: mềm — giòn — béo hài hòa.",
            "Phục vụ nóng hổi, giữ nguyên hương thơm tự nhiên.",
            "Thành phần từ nguồn địa phương, an toàn và sạch.",
            "Món nhẹ nhàng, thích hợp cho mọi bữa ăn.",
            "Phù hợp để chia sẻ cùng gia đình và bạn bè.",
            "Trình bày tinh tế, bắt mắt, ăn trước đã thấy ngon.",
            "Đầy đặn, ngon miệng — no lâu, bổ dưỡng.",
            "Hương thơm thoang thoảng, đánh thức khứu giác.",
            "Chế biến cầu kỳ nhưng vẫn giữ được vị nguyên bản.",
            "Sự hòa quyện của gia vị tạo nên điểm nhấn riêng.",
            "Phù hợp với người ăn chay/ăn mặn (ghi chú khi cần).",
            "Món ăn cân bằng dinh dưỡng — phù hợp cho mọi lứa tuổi.",
            "Vị nhẹ nhàng, dễ ăn, phù hợp cho cả trẻ em.",
            "Một lựa chọn tinh tế cho bữa trưa vội hay tối ấm cúng.",
            "Cảm giác ấm áp, quen thuộc như bữa cơm nhà.",
            "Món ăn tươi sống, chế biến nhanh, giữ vitamin.",
            "Vị cay/không cay có thể điều chỉnh theo yêu cầu.",
            "Phù hợp kết hợp với nhiều loại đồ uống.",
            "Hương vị phong phú, mỗi miếng là một trải nghiệm.",
            "Món ăn truyền cảm hứng từ ẩm thực địa phương.",
            "Độ mặn vừa phải, không lấn át nguyên liệu chính.",
            "Món cổ điển được làm mới bằng kỹ thuật hiện đại.",
            "Hương vị nhẹ nhàng nhưng ấn tượng, dễ nhớ.",
            "Tinh tế trong cách cân gia vị và xử lý nguyên liệu.",
            "Được chế biến theo tiêu chuẩn vệ sinh thực phẩm nghiêm ngặt.",
            "Một lựa chọn hoàn hảo cho những ai yêu ẩm thực tinh tế."
        ]

        # --- XỬ LÝ LOGIC ĐẶC SẢN ---
        source_categories = default_categories
        
        if special_foods and len(special_foods) > 0:
            # Nếu có đặc sản, tạo category mới từ đặc sản đó
            custom_categories = []
            for food in special_foods:
                food_name = food.replace("_", " ").title() # vd: "lau_mam" -> "Lau Mam"
                custom_categories.append({
                    "base": food_name, # Tên quán sẽ là "Lau Mam Bà Ba"
                    "menu": [food_name, food_name + " đặc biệt", "Món ngon " + food_name],
                    "tags": ["đặc sản", "địa phương", "ngon"]
                })
            source_categories = custom_categories # Ghi đè danh sách nguồn

        for i in range(count):
            cat = random.choice(source_categories)
            suffix = random.choice(suffixes)
            
            # Ghép tên quán
            name = f"{cat['base']} {suffix}"
            
            # Random vị trí gần user (1-2km) để map chỉ đường đẹp
            # Hệ số 0.035 tương đương bán kính ~1.5km - 2km
            offset_lat = (random.random() - 0.5) * 0.035 
            offset_lon = (random.random() - 0.5) * 0.035
            
            mock_lat = user_lat + offset_lat
            mock_lng = user_lon + offset_lon
            
            # Tính khoảng cách sơ bộ (Pythagore)
            dist_approx = ((mock_lat - user_lat)**2 + (mock_lng - user_lon)**2)**0.5 * 111

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
                "distance_km": dist_approx
            })
            
        return mocks

    # ---------------- 3. MAIN LOADER (LẤY DỮ LIỆU) ----------------
    def get_all_restaurants(self, use_cache: bool = True, user_lat: float = None, user_lon: float = None, 
                          enable_mock: bool = True, place_scope: str = None) -> List[Dict[str, Any]]:
        """
        Lấy quán ăn từ DB + Mock Data.
        place_scope: Tên địa điểm user đang tìm (VD: 'an giang'). Nếu có, sẽ lấy đặc sản vùng đó.
        enable_mock: True/False để bật tắt chế độ dữ liệu giả.
        """
        restaurants = []
        
        # 1. Lấy dữ liệu thật từ Firebase
        if self.db:
            try:
                ref = self.db.collection("restaurants")
                docs = ref.stream()
                for doc in docs:
                    raw_data = doc.to_dict() or {}
                    
                    # --- Chuẩn hóa Tọa độ ---
                    lat = raw_data.get("lat")
                    lng = raw_data.get("lng")
                    if lat is None or lng is None:
                        geo = raw_data.get("location") or raw_data.get("rental")
                        if geo and hasattr(geo, 'latitude'):
                            lat = geo.latitude
                            lng = geo.longitude
                    
                    # --- Chuẩn hóa Menu ---
                    # Ưu tiên 'foods' rồi đến 'menu'
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
                        "distance_km": 0.0 
                    }
                    restaurants.append(item)
            except Exception as e:
                print(f"ERROR loading real data: {e}")

        # 2. Xử lý Mock Data thông minh
        if enable_mock:
            # Nếu user truyền tọa độ -> dùng tọa độ đó. 
            # Nếu không -> dùng mặc định TP.HCM (thay vì Hà Nội để phù hợp context bạn test)
            target_lat = user_lat if user_lat else 10.7769 
            target_lon = user_lon if user_lon else 106.7009
            
            # --- KEY POINT: Lấy đặc sản nếu đang tìm theo địa điểm ---
            special_foods = []
            if place_scope:
                # print(f"DEBUG: Đang tìm đặc sản cho vùng: {place_scope}")
                special_foods = self.get_place_specialties(place_scope)
            
            # Truyền danh sách đặc sản vào hàm tạo mock
            # Luôn tạo 20 quán giả để đảm bảo kết quả tìm kiếm không bị trống
            mock_data = self._generate_mock_data(target_lat, target_lon, count=20, special_foods=special_foods)
            restaurants.extend(mock_data)

        self._cache["restaurants"] = restaurants
        return restaurants

    def get_restaurants_near_user(self, lat: float, lng: float, radius_km: float = 10.0) -> List[Dict[str, Any]]:
        """Wrapper cho chức năng Gợi ý (Luôn bật Mock)"""
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
    # --- THÊM PHƯƠNG THỨC MỚI NÀY ---
    def get_restaurant_by_id(self, restaurant_id):
        """
        Tìm và trả về dữ liệu quán ăn dựa trên ID.
        """
        for r in self.restaurants_data:
            if r.get("id") == restaurant_id:
                return r  # Trả về đối tượng quán ăn khi tìm thấy
        return None  # Trả về None nếu không tìm thấy quán ăn nào
    
    def get_similar_restaurants(self, restaurant_id):
        # Hàm giả định để tránh lỗi ở app.py, bạn có thể implement logic thật sau
        return [r for r in self.restaurants_data if r['id'] != restaurant_id][:2]
    # ---------------------------------