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
        """
        Tách query thành 2 phần:
        - clean_query: từ khoá món ăn / nhu cầu (KHÔNG chứa địa danh)
        - thông tin địa danh (TP.HCM / Hà Nội / ...)
        Hỗ trợ:
            - "phở"
            - "Thành Phố Hồ Chí Minh"
            - "phở Hà Nội"
        """
        if not raw_query:
            return {
                "clean_query": "",
                "location_tags": [],
                "is_location_search": False,
                "raw_location_query": "",
            }

        raw_lower = raw_query.lower()
        clean_q = self.normalize(raw_query)          # bỏ dấu, lowercase
        tokens = clean_q.split()

        # ----- 1. Nhận diện địa danh -----
        LOCATION_KEYWORDS = {
            "hanoi": [
                "hà nội", "ha noi", "hanoi",
                "thành phố hà nội", "thanh pho ha noi",
            ],
            "hochiminh": [
                "thành phố hồ chí minh", "thanh pho ho chi minh",
                "ho chi minh", "tp.hcm", "tp hcm", "tphcm",
                "sài gòn", "sai gon",
            ],
            # Sau này muốn thêm Đà Nẵng, Huế,... thì bổ sung ở đây
        }

        location_key = None
        location_phrase_norm = ""

        for city_key, patterns in LOCATION_KEYWORDS.items():
            for pat in patterns:
                norm_pat = self.normalize(pat)
                if norm_pat and norm_pat in clean_q:
                    location_key = city_key
                    location_phrase_norm = norm_pat      # ví dụ: "ho chi minh", "ha noi"
                    break
            if location_key:
                break

        is_location_search = location_key is not None

        detected_location_tags = []
        if is_location_search:
            detected_location_tags.extend(
                PROVINCE_SPECIALTIES.get(location_key, [])
            )

        # ----- 2. Xem query có nhắc tới món ăn không -----
        FOOD_KEYWORDS = [
            "phở", "pho",
            "bún", "mì", "mi ", "mì quảng", "hu tieu", "hủ tiếu",
            "cơm", "com", "cơm tấm", "com tam",
            "bánh mì", "banh mi",
            "lẩu", "lau",
            "pizza", "burger", "kfc",
        ]
        has_food_word = any(word in raw_lower for word in FOOD_KEYWORDS)

        # ----- 3. Tạo clean_query (chỉ phần món ăn / nhu cầu) -----
        keywords = tokens.copy()

        # Bỏ cụm từ địa danh ra khỏi tokens (nếu có)
        if location_phrase_norm:
            loc_tokens = location_phrase_norm.split()
            keywords = [w for w in keywords if w not in loc_tokens]

        # Bỏ stop words chung
        keywords = [w for w in keywords if w not in STOP_WORDS]

        final_query = " ".join(keywords).strip()

        # Nếu query chỉ để chọn địa danh (không có món ăn)
        if is_location_search and not has_food_word:
            final_query = ""   # để phân biệt location-only

        return {
            "clean_query": final_query,               # vd: "pho"
            "location_tags": detected_location_tags,  # list đặc sản của tỉnh
            "is_location_search": is_location_search,
            "raw_location_query": location_phrase_norm,  # vd: "ho chi minh", "ha noi"
        }


    # 3. So khớp tương đối (Fuzzy Match)
    def fuzzy_ratio(self, query, text):
        if not query or not text: return 0
        return SequenceMatcher(None, query, text).ratio()

    # ===============================================
    # MAIN SEARCH FUNCTION
    # ===============================================
    def search(self, restaurants: List[Dict[str, Any]], user_input: str) -> List[Dict[str, Any]]:
        """
        Tìm kiếm theo:
        - q (món ăn / từ khoá)
        - địa danh (nếu có)
        Hỗ trợ:
            + "phở"
            + "Thành Phố Hồ Chí Minh"
            + "phở Hà Nội"  -> bắt buộc match cả phở lẫn Hà Nội
        """
        if not user_input or not user_input.strip():
            return restaurants

        parsed = self.parse_query(user_input)
        q = self.normalize(parsed.get("clean_query", "")).strip()
        loc_tags = parsed.get("location_tags", [])
        is_location_search = parsed.get("is_location_search", False)
        raw_loc = parsed.get("raw_location_query") or ""
        loc_query_norm = self.normalize(raw_loc)

        results: List[Dict[str, Any]] = []

        for r in restaurants:
            # Chuẩn hoá các field text
            name_norm = self.normalize(str(r.get("name", "")))
            addr_norm = self.normalize(str(r.get("address", "")))

            tags = r.get("tags", []) or []
            if isinstance(tags, str):
                tags = [tags]
            tags_norm = [self.normalize(str(t)) for t in tags]
            tags_str = " ".join(tags_norm)

            menu = r.get("menu", []) or []
            if isinstance(menu, list):
                menu_items = []
                for m in menu:
                    if isinstance(m, dict):
                        menu_items.append(self.normalize(str(m.get("name", ""))))
                    else:
                        menu_items.append(self.normalize(str(m)))
                menu_str = " ".join(menu_items)
            else:
                menu_str = self.normalize(str(menu))

            # ----- Kiểm tra match LOCATION -----
            loc_match = True
            if is_location_search and loc_query_norm:
                loc_match = (
                    (loc_query_norm in addr_norm) or
                    (loc_query_norm in name_norm)
                )

            # ----- Kiểm tra match MÓN ĂN / KEYWORD -----
            dish_match = True
            if q:
                in_name = (q in name_norm) or (self.fuzzy_ratio(q, name_norm) > 0.65)
                in_tags = q in tags_str
                in_menu = q in menu_str
                dish_match = in_name or in_tags or in_menu

            # Nếu có địa danh thì phải match địa danh.
            # Nếu có q thì phải match q.
            if not loc_match or not dish_match:
                continue

            # ----- TÍNH ĐIỂM -----
            score = 0

            # Ưu tiên đúng địa danh
            if is_location_search and loc_query_norm:
                if loc_query_norm in addr_norm:
                    score += 20
                if loc_query_norm in name_norm:
                    score += 5

                # Bonus nếu menu/tags có món đặc sản vùng đó
                for tag in loc_tags:
                    t_norm = self.normalize(str(tag))
                    if t_norm and (t_norm in tags_str or t_norm in menu_str):
                        score += 3

            # Ưu tiên match món ăn
            if q:
                if q in name_norm:
                    score += 10
                elif self.fuzzy_ratio(q, name_norm) > 0.65:
                    score += 6

                if q in tags_str:
                    score += 4
                if q in menu_str:
                    score += 4

            if score <= 0:
                score = 1

            r["search_score"] = score
            results.append(r)

        results.sort(
            key=lambda x: (-x.get("search_score", 0), x.get("distance_km", 999))
        )
        return results
    
