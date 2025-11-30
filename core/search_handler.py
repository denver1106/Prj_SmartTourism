import unicodedata
from difflib import SequenceMatcher
from typing import List, Dict, Any

# ========================================================
# KNOWLEDGE BASE: MAPPING ĐỊA ĐIỂM -> ĐẶC SẢN
# ========================================================
PROVINCE_SPECIALTIES = {
    "hanoi": ["phở", "bún chả", "chả cá", "bún đậu", "cốm", "bánh cuốn", "bún riêu", "hà nội"],
    "hue": ["bún bò", "cơm hến", "bánh bèo", "bánh lọc", "nem lụi", "chè", "huế"],
    "danang": ["mì quảng", "bánh xèo", "bánh tráng thịt heo", "bún chả cá", "đà nẵng", "quảng"],
    "saigon": ["cơm tấm", "hủ tiếu", "bánh mì", "gỏi cuốn", "sài gòn", "tphcm", "hcm"],
    "hochiminh": ["cơm tấm", "hủ tiếu", "bánh mì", "sài gòn", "tphcm"],
    "haiphong": ["bánh đa cua", "nem cua bể", "dừa dầm", "hải phòng"],
    "hoian": ["cao lầu", "cơm gà", "bánh mì phượng", "hội an"],
    "dalat": ["bánh tráng nướng", "lẩu gà lá é", "sữa đậu nành", "kem bơ", "đà lạt"],
    "nhatrang": ["bún sứa", "nem nướng", "hải sản", "nha trang"],
    "cantho": ["lẩu mắm", "bánh xèo", "cá lóc nướng", "cần thơ", "miền tây"],
    "mientay": ["lẩu mắm", "hủ tiếu nam vang", "bánh xèo", "cá lóc", "miền tây"],
    "nghean": ["cháo lươn", "súp lươn", "nghệ an", "vinh"],
    "thanhhoa": ["nem chua", "chả tôm", "thanh hóa"]
}

# CÁC TỪ THỪA TRONG NGÔN NGỮ TỰ NHIÊN (NL)
STOP_WORDS = [
    "tôi", "muốn", "ăn", "uống", "tìm", "kiếm", "quán", "nhà hàng", 
    "ở đâu", "ngon", "gần", "đây", "có", "bán", "thèm", "đi", "review",
    "xung quanh", "chỗ", "nào", "món", "đồ", "giá", "rẻ"
]

class SearchHandler:
    
    # 1. Chuẩn hóa chuỗi (Tiếng Việt -> Latin không dấu, Lowercase)
    def normalize(self, text: str) -> str:
        if not text: return ""
        text = text.lower()
        # Chuyển về dạng unicode tổ hợp để tách dấu
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        # Xóa các ký tự đặc biệt thừa
        return text.strip()

    # 2. Xử lý NL: Loại bỏ từ thừa & Phát hiện địa danh
    def parse_query(self, raw_query: str) -> dict:
        clean_q = self.normalize(raw_query)
        tokens = clean_q.split()
        
        # Lọc bỏ từ thừa
        keywords = [w for w in tokens if w not in STOP_WORDS]
        final_query = " ".join(keywords)
        
        # Check xem user có nhập tên tỉnh thành không?
        detected_location_tags = []
        is_location_search = False
        
        for city, specialties in PROVINCE_SPECIALTIES.items():
            # Nếu tên tỉnh (đã normalize) nằm trong query của user
            if self.normalize(city) in clean_q or city in clean_q:
                # User tìm theo địa danh -> Gắn đặc sản vào
                detected_location_tags.extend(specialties)
                is_location_search = True
        
        return {
            "clean_query": final_query,  # Chuỗi query tinh gọn (để fuzzy search)
            "location_tags": detected_location_tags, # List món ăn nếu tìm theo tỉnh
            "is_location_search": is_location_search
        }

    # 3. So khớp tương đối (Fuzzy Match)
    def fuzzy_ratio(self, query, text):
        if not query or not text: return 0
        return SequenceMatcher(None, query, text).ratio()

    # ===============================================
    # MAIN SEARCH FUNCTION
    # ===============================================
    def search(self, restaurants: List[Dict[str, Any]], user_input: str) -> List[Dict[str, Any]]:
        if not user_input or not user_input.strip():
            return restaurants

        # Phân tích Input của user
        parsed = self.parse_query(user_input)
        q = parsed["clean_query"]
        loc_tags = parsed["location_tags"]
        
        results = []

        for r in restaurants:
            # Lấy data của quán & chuẩn hóa
            r_name = self.normalize(r.get("name", ""))
            
            # Xử lý tags (database trả về list hoặc str)
            r_tags_list = r.get("tags", [])
            if isinstance(r_tags_list, str): r_tags_list = [r_tags_list]
            r_tags_str = " ".join([self.normalize(t) for t in r_tags_list])
            
            # Xử lý menu (database trả về list json)
            r_menu = r.get("menu", [])
            menu_str = ""
            if isinstance(r_menu, list):
                # Gộp tên các món trong menu thành 1 chuỗi dài để search
                items = [self.normalize(str(x.get("name") if isinstance(x, dict) else x)) for x in r_menu]
                menu_str = " ".join(items)

            score = 0

            # === LOGIC 1: TÌM THEO TÊN TỈNH/ĐỊA DANH ===
            # Nếu user nhập "Hà Nội" -> Tìm quán có bán Phở, Bún chả... HOẶC tag hanoi
            if parsed["is_location_search"]:
                # 1. Check xem Tag quán có chứa đặc sản của tỉnh đó không
                # ví dụ: quán bán 'pho' thì match với đặc sản 'pho' của hanoi
                match_specialty = any(spec in r_tags_str or spec in menu_str for spec in loc_tags)
                if match_specialty:
                    score += 20 # Ưu tiên rất cao
                
                # 2. Check xem tên quán có chứa tên tỉnh không (VD: Phở Hà Nội)
                # Dùng raw input để check (VD: "ha noi" in name)
                user_geo_clean = self.normalize(user_input) 
                if user_geo_clean in r_name:
                    score += 15

            # === LOGIC 2: TÌM THEO KEYWORD TỰ NHIÊN (NL) ===
            # VD: "Cơm ngon" -> q="cơm" (đã bỏ ngon)
            if q:
                # Ưu tiên 1: Tên quán chứa từ khóa
                if q in r_name: score += 10
                elif self.fuzzy_ratio(q, r_name) > 0.65: score += 5
                
                # Ưu tiên 2: Tag quán chứa từ khóa
                if q in r_tags_str: score += 8
                
                # Ưu tiên 3: Menu chứa món đó
                if q in menu_str: score += 6

            # Nếu có điểm phù hợp thì thêm vào list
            if score > 0:
                r["search_score"] = score
                # Gán thêm nhãn lý do (để frontend hiển thị nếu cần)
                if parsed["is_location_search"]:
                    r["search_reason"] = "Đặc sản vùng miền"
                else:
                    r["search_reason"] = "Khớp từ khóa"
                results.append(r)

        # Sort theo điểm khớp (giảm dần) -> Khoảng cách (tăng dần)
        # Điểm cao nhất lên đầu, nếu điểm bằng nhau thì quán gần hơn lên đầu
        results.sort(key=lambda x: (-x.get("search_score", 0), x.get("distance_km", 999)))
        
        return results