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

    # --- haversine distance ---
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371  # km
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

    def filter_by_context(self, restaurants):
        return [r for r in restaurants if self.matches_context(r)]

    def matches_context(self, restaurant):
        tags = restaurant.get("tags", [])
        time = self.context.get("time")
        season = self.context.get("season")
        weather = self.context.get("weather")

        # Nếu trùng bất kỳ tag nào → match
        return any(tag in tags for tag in [time, season, weather]) or not tags

    # --- Compute score ---
    def compute_score(self, restaurant):
        score = 0
        # like_tags
        preferred_tags = self.user_preferences.get("like_tags", [])
        if any(tag in preferred_tags for tag in restaurant.get("tags", [])):
            score += 1
        # chưa ăn gần đây
        if not any(food in self.user_history for food in restaurant.get("foods", [])):
            score += 1
        # context match
        if self.matches_context(restaurant):
            score += 1
        return score

    # --- Generate recommendation ---
    def generate(self, top_n=10):
        restaurants = self.dm.get_all_restaurants()

        # 1. Auto filter
        restaurants = self.filter_unwanted(restaurants)
        restaurants = self.filter_recent_foods(restaurants)
        restaurants = self.filter_by_context(restaurants)

        # 2. Compute score + distance
        for r in restaurants:
            r["score"] = self.compute_score(r)
            r["distance_km"] = self.haversine_distance(
                self.user_lat, self.user_lon, r["lat"], r["lon"]
            )

        # 3. Sort: score giảm, distance tăng
        restaurants.sort(key=lambda x: (-x["score"], x["distance_km"]))

        # 4. Return top_n
        return restaurants[:top_n]
