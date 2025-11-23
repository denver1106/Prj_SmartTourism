from core.data_manager import DataManager
from math import radians, cos, sin, sqrt, atan2

class Recommender:
    def __init__(self, user_id, user_lat, user_lon, context, data_manager: DataManager):
        self.dm = data_manager
        self.user_id = user_id
        self.user_lat = user_lat
        self.user_lon = user_lon
        self.context = context
        self.user_history = self.dm.get_user_history(user_id)
        self.user_preferences = self.dm.get_user_preferences(user_id)

    # --- Haversine Distance ---
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return 9999.0 

        R = 6371 
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    # --- Filters ---
    def filter_unwanted(self, restaurants):
        disliked_tags = self.user_preferences.get("dislike_tags", [])
        return [r for r in restaurants if not any(tag in disliked_tags for tag in r.get("tags", []))]

    def filter_recent_foods(self, restaurants):
        return [r for r in restaurants if not any(food in self.user_history for food in r.get("foods", []))]

    def matches_context(self, restaurant):
        tags = restaurant.get("tags", [])
        time_tag = self.context.get("time_of_day")
        season_tag = self.context.get("season")
        weekday_tag = self.context.get("weekday")

        if not tags: return True
        
        # Luôn match cho các quán demo/mock để đảm bảo hiển thị
        if "demo" in tags or "mock" in tags:
            return True

        context_values = [v for v in [time_tag, season_tag, weekday_tag] if v]
        return any(tag in tags for tag in context_values)

    # --- Compute score ---
    def compute_score(self, restaurant):
        score = 0
        preferred_tags = self.user_preferences.get("like_tags", [])
        if any(tag in preferred_tags for tag in restaurant.get("tags", [])):
            score += 2
        if not any(food in self.user_history for food in restaurant.get("foods", [])):
            score += 1
        if self.matches_context(restaurant):
            score += 3
        return score

    # --- Generate ---
    def generate(self, top_n=10):
        # QUAN TRỌNG: Gọi hàm lấy quán gần user (đã bao gồm mock data nếu thiếu quán thật)
        restaurants = self.dm.get_restaurants_near_user(self.user_lat, self.user_lon)

        # 1. Filter
        restaurants = self.filter_unwanted(restaurants)
        restaurants = self.filter_recent_foods(restaurants)

        # 2. Score & Distance
        for r in restaurants:
            r["score"] = self.compute_score(r)
            
            r_lat = r.get("lat")
            r_lon = r.get("lon") if r.get("lon") is not None else r.get("lng")
            
            # Tính lại khoảng cách chính xác
            dist = self.haversine_distance(self.user_lat, self.user_lon, r_lat, r_lon)
            r["distance_km"] = dist

        # 3. Sort (Ưu tiên điểm cao -> khoảng cách gần)
        restaurants.sort(key=lambda x: (-x["score"], x["distance_km"]))

        return restaurants[:top_n]