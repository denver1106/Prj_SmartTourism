import random
import math
from core.data_manager import DataManager

# -------------------------------------------------------------------
# CONFIGURATION & WEIGHTS (Dễ dàng tinh chỉnh tại đây)
# -------------------------------------------------------------------
SCORING_WEIGHTS = {
    "preference_match": 4.0,   # Trùng sở thích user
    "intent_match": 5.0,       # Trùng ý định tìm kiếm (query)
    "time_match": 2.0,         # Phù hợp bữa (sáng/trưa/tối)
    "weather_match": 3.0,      # Phù hợp thời tiết
    "distance_bonus": 2.0,     # Rất gần (<2km)
    "novelty_bonus": 1.0,      # Món chưa từng ăn (khám phá)
    "similarity_bonus": 1.5,   # Giống món từng ăn
    "rating_weight": 1.0,      # Hệ số nhân với rating gốc
    "popularity_boost": 0.5    # Hệ số boost dựa trên số review
}

# -------------------------------------------------------------------
# KNOWLEDGE BASE
# -------------------------------------------------------------------
FOOD_CLUSTERS = {
    "pho": ["pho", "phở", "nam dinh", "hanoi"],
    "bun": ["bún", "bun", "hue", "cha"],
    "com": ["cơm", "com", "tam", "ga", "nieu"],
    "lau": ["lẩu", "lau", "hotpot", "manwah", "kichi"],
    "bbq": ["nướng", "bbq", "grill", "sumo", "gogi"],
    "fast": ["pizza", "burger", "gà rán", "banh mi", "kfc", "mcdonald", "lotteria"],
    "drink": ["trà", "coffee", "cafe", "juice", "tea", "phuc long", "highlands", "starbucks", "kem", "chè"],
    "seafood": ["ốc", "sò", "nghêu", "hải sản", "cua", "ghẹ"],
    "healthy": ["salad", "eat clean", "chay", "vegan"]
}

WEATHER_FOOD_MAP = {
    "rainy": ["pho", "bun", "lau", "hotpot", "soup", "bbq", "spicy"],
    "hot": ["drink", "tea", "ice", "kem", "cool"],
    "cold": ["bbq", "lau", "spicy", "hotpot", "grill"],
    "cloudy": ["coffee", "cafe", "snack"],
    "clear": []
}

class Recommender:
    def __init__(self, user_id, user_lat, user_lon, context, data_manager: DataManager):
        self.dm = data_manager
        self.user_id = user_id
        self.user_lat = float(user_lat or 0)
        self.user_lon = float(user_lon or 0)
        self.context = context
        
        # Load dữ liệu User
        self.history_items = set(self.dm.get_user_history(user_id))
        prefs = self.dm.get_user_preferences(user_id)
        self.liked_tags = set(prefs.get("like_tags", []))
        
        # Parse Intent từ Query của User (nếu có)
        # Query: "đang đói, muốn ăn phở" -> user_intents = {"pho", "noodle"}
        q = context.get("user_query", "").lower()
        self.user_query_tokens = set(q.split()) if q else set()

    # --- 1. ENRICH DATA ---
    def _detect_cluster(self, r):
        """Xác định nhóm món ăn (Phở, Cơm, Cafe...) dựa trên Tên và Tags"""
        text_source = f"{r.get('name', '')} {' '.join(r.get('tags', []))}".lower()
        
        for cluster, keywords in FOOD_CLUSTERS.items():
            if any(kw in text_source for kw in keywords):
                return cluster
        return "other"

    # --- 2. COMPUTE SCORES ---
    def _compute_single_score(self, r):
        score = 0.0
        details = [] # Lưu log để debug lý do gợi ý

        # Dữ liệu từ DB (đã clean)
        tags = set(r.get("tags", []))
        cluster = r.get("cluster")
        dist_km = r.get("distance_km", 999.0)
        
        # 2.1. BASE SCORE (Rating)
        rating = r.get("rating", 0) or 3.0 # Default rating nếu chưa có là 3
        # Lấy số lượng review: Nếu là list json -> lấy len(), nếu int -> lấy value
        raw_revs = r.get("reviews")
        review_count = len(raw_revs) if isinstance(raw_revs, list) else int(raw_revs or 0)
        
        # Công thức: Rating + Logarit(review count) để tránh rating 5.0 mà chỉ có 1 review
        popularity = rating * SCORING_WEIGHTS["rating_weight"] 
        if review_count > 0:
            popularity += math.log10(review_count + 1) * SCORING_WEIGHTS["popularity_boost"]
        
        score += popularity

        # 2.2. DISTANCE (Chỉ tính nếu có GPS)
        # Ưu tiên quán rất gần (< 2km)
        if self.user_lat != 0 and dist_km < 2.0:
            score += SCORING_WEIGHTS["distance_bonus"]
            details.append("Gần bạn")

        # 2.3. USER PREFERENCES (Sở thích)
        # Nếu quán có tag trùng với like_tags
        if not self.liked_tags.isdisjoint(tags): # Kiểm tra giao nhau nhanh
            score += SCORING_WEIGHTS["preference_match"]
            details.append("Đúng gu")
        
        # 2.4. CONTEXT: TIME (Bữa sáng/trưa/tối)
        # DataManager hoặc DB cần có tags như: 'breakfast', 'lunch'
        current_meal = self.context.get("time_of_day") # VD: 'noon' (trưa) maps với tags lunch
        time_map = {
            "morning": ["breakfast", "pho", "bun", "coffee"],
            "noon": ["lunch", "rice", "com", "bento"],
            "afternoon": ["snack", "drink", "tea"],
            "evening": ["dinner", "bbq", "hotpot", "lau"],
            "late": ["night_food"]
        }
        target_tags = time_map.get(current_meal, [])
        # Check if tag/cluster matches context
        if cluster in target_tags or any(t in target_tags for t in tags):
            score += SCORING_WEIGHTS["time_match"]
            # Không append detail để tránh rối, nhưng cộng điểm ngầm

        # 2.5. CONTEXT: WEATHER (Thời tiết)
        current_weather = self.context.get("weather") # rainy, hot, cold...
        weather_foods = WEATHER_FOOD_MAP.get(current_weather, [])
        if cluster in weather_foods or any(t in weather_foods for t in tags):
            score += SCORING_WEIGHTS["weather_match"]
            details.append(f"Hợp trời {current_weather}")

        # 2.6. NOVELTY vs SIMILARITY (Lịch sử)
        # Lấy tên món và cluster so với lịch sử
        if r.get("name", "").lower() in self.history_items:
             # Đã từng ăn quán này -> Cộng ít điểm (re-order)
             pass 
        else:
             # Chưa ăn -> Khám phá
             score += SCORING_WEIGHTS["novelty_bonus"]

        # 2.7. INTENT (Query Search)
        # User đang gõ: "món nước", "phở"...
        if self.user_query_tokens:
            combined_text = (r["name"] + " " + " ".join(tags) + " " + cluster).lower()
            if any(token in combined_text for token in self.user_query_tokens):
                score += SCORING_WEIGHTS["intent_match"]
                details.append("Khớp tìm kiếm")

        return score, details

    # --- 3. MAIN FUNCTION ---
    def generate(self, top_n=10):
        # A. Lấy Data
        # Nếu có GPS -> Lấy gần. Nếu không -> Lấy hết
        if self.user_lat != 0 and self.user_lon != 0:
            # Lấy bán kính 15km
            restaurants = self.dm.get_restaurants_near_user(self.user_lat, self.user_lon, radius_km=15)
        else:
            restaurants = self.dm.get_all_restaurants(use_cache=True)
            
        if not restaurants:
            print("⚠️ Không có quán gần hoặc mất GPS -> Lấy toàn bộ DB")
            restaurants = self.dm.get_all_restaurants(use_cache=True)
        # B. Chấm điểm (Scoring)
        candidates = []
        for r in restaurants:
            # 1. Detect Cluster (Enrich Data)
            r["cluster"] = self._detect_cluster(r)
            
            # 2. Compute Score
            score, explain_tags = self._compute_single_score(r)
            
            # Gắn kết quả tạm vào object (copy nhẹ để không ảnh hưởng cache gốc nếu cần)
            # Ở đây ta gắn trực tiếp cho nhanh, vì mỗi request DataManager tạo obj mới
            r["score"] = score
            r["explain"] = ", ".join(explain_tags) # Chuỗi lý do gợi ý
            
            candidates.append(r)

        # C. Sắp xếp sơ bộ (Primary Sort)
        # Điểm cao nhất -> Gần nhất -> Rating cao nhất
        candidates.sort(key=lambda x: (-x["score"], x.get("distance_km", 999), -x.get("rating", 0)))
        
        # D. Đa dạng hóa (Diversification - Re-Ranking)
        # Logic: Không gợi ý quá 2 quán cùng cluster liên tiếp
        final_list = []
        seen_clusters = {} # đếm số lượng cluster đã thêm
        
        # Vòng 1: Lấy các món ngon nhất, bỏ qua nếu bị trùng lặp quá nhiều
        buffer_list = [] # Những món bị skip sẽ cho vào đây để vớt vát sau
        
        for r in candidates:
            c = r["cluster"]
            if seen_clusters.get(c, 0) < 2:
                final_list.append(r)
                seen_clusters[c] = seen_clusters.get(c, 0) + 1
            else:
                # Nếu cluster này xuất hiện >= 2 lần rồi, đẩy xuống danh sách dự phòng
                buffer_list.append(r)
            
            if len(final_list) >= top_n:
                break
        
        # Nếu chưa đủ Top N, lấy thêm từ buffer
        missing = top_n - len(final_list)
        if missing > 0:
            final_list.extend(buffer_list[:missing])

        return final_list