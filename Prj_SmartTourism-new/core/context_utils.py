# core/context_utils.py
from datetime import datetime
from typing import Dict, Optional
import re


class ContextUtils:

    # -----------------------------
    # 1. TIME CONTEXT
    # -----------------------------
    @staticmethod
    def get_time_context(now: Optional[datetime] = None) -> Dict[str, str]:
        if now is None:
            now = datetime.now()

        hour = now.hour
        if 5 <= hour < 10:
            time_of_day = "morning"
        elif 10 <= hour < 14:
            time_of_day = "noon"
        elif 14 <= hour < 18:
            time_of_day = "afternoon"
        elif 18 <= hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "late"

        # Season
        month = now.month
        if month in (12, 1, 2):
            season = "winter"
        elif month in (3, 4, 5):
            season = "spring"
        elif month in (6, 7, 8):
            season = "summer"
        else:
            season = "autumn"

        weekday = now.strftime("%A").lower()

        return {
            "time_of_day": time_of_day,
            "season": season,
            "weekday": weekday,
            "hour": hour
        }

    # -----------------------------
    # 2. WEATHER CONTEXT (from API)
    # -----------------------------
    @staticmethod
    def get_weather_context(weather_raw: dict) -> Dict[str, str]:
        """
        Đầu vào là JSON từ API thời tiết – chỉ cần convert về semantic tags.
        Example weather_raw:
        {
            "main": {"temp": 30},
            "weather": [{"main": "Rain"}]
        }
        """

        if not weather_raw:
            return {
                "weather": "clear",
                "weather_temp": None
            }

        condition = weather_raw.get("weather", [{}])[0].get("main", "").lower()
        temp = weather_raw.get("main", {}).get("temp")

        if "rain" in condition:
            weather = "rainy"
        elif "cloud" in condition:
            weather = "cloudy"
        elif "storm" in condition:
            weather = "storm"
        elif "mist" in condition or "fog" in condition:
            weather = "fog"
        else:
            weather = "clear"

        return {
            "weather": weather,
            "weather_temp": temp
        }

    # -----------------------------
    # 3. TEXT CONTEXT (NLP KEYWORD)
    # -----------------------------
    @staticmethod
    def extract_text_intent(text: str) -> Dict[str, any]:
        """
        Phân tích câu user nhập:
            - mood: happy / bored / sad …
            - hunger level: hungry / very_hungry
            - craving: spicy / sweet / drink / noodle …
            - price intent: cheap / mid / high
        """

        if not text:
            return {}

        tx = text.lower()
        intent = {}

        # Mood
        if any(k in tx for k in ["mệt", "buồn", "chán"]):
            intent["mood"] = "low"
        elif any(k in tx for k in ["vui", "phấn khởi"]):
            intent["mood"] = "high"

        # Hunger level
        if "đói quá" in tx or "đói vl" in tx:
            intent["hunger"] = "very_hungry"
        elif "đói" in tx:
            intent["hunger"] = "hungry"

        # Craving / dish intent
        craving_map = {
            "cay": "spicy",
            "ngọt": "sweet",
            "trà sữa": "drink",
            "món nước": "noodle",
            "ăn nhanh": "fast",
            "ăn sáng": "breakfast",
            "ăn trưa": "lunch",
            "ăn tối": "dinner"
        }
        for k, v in craving_map.items():
            if k in tx:
                intent.setdefault("craving", []).append(v)

        # Price intent
        if any(k in tx for k in ["rẻ", "giá thấp", "tiết kiệm"]):
            intent["price_range"] = "cheap"
        elif any(k in tx for k in ["tầm trung", "vừa"]):
            intent["price_range"] = "mid"
        elif any(k in tx for k in ["sang", "đắt", "cao cấp"]):
            intent["price_range"] = "high"

        return intent

    # -----------------------------
    # 4. TRAFFIC CONTEXT (OPTIONAL)
    # -----------------------------
    @staticmethod
    def traffic_context(level: str = None) -> Dict[str, str]:
        """
        level:
            - heavy
            - medium
            - light
        """
        if not level:
            return {"traffic": "unknown"}

        return {"traffic": level}

    # -----------------------------
    # 5. EVENT CONTEXT (WEEKEND / HOLIDAY)
    # -----------------------------
    @staticmethod
    def event_context() -> Dict[str, str]:
        weekday = datetime.now().weekday()  # 0=Mon ... 6=Sun
        if weekday >= 5:
            return {"event": "weekend"}   # Thứ 7 – Chủ nhật
        return {"event": "normal"}

    # -----------------------------
    # 6. FINAL MERGER
    # -----------------------------
    @staticmethod
    def merge_all_context(
        search_filters: dict,
        user_history: list,
        user_pref: dict,
        text_query: str,
        weather_raw: dict = None,
        traffic: str = None
    ) -> dict:

        ctx = {}

        # Time
        ctx.update(ContextUtils.get_time_context())

        # Weather
        ctx.update(ContextUtils.get_weather_context(weather_raw))

        # Traffic
        ctx.update(ContextUtils.traffic_context(traffic))

        # Weekend / holiday
        ctx.update(ContextUtils.event_context())

        # Search filters
        ctx["search_filters"] = search_filters or {}

        # History & preferences
        ctx["user_history"] = [str(x).lower() for x in (user_history or [])]
        ctx["user_preferences"] = user_pref or {}

        # NLP intent
        ctx["nlp_intent"] = ContextUtils.extract_text_intent(text_query)

        # Raw query
        ctx["user_query"] = text_query or ""

        return ctx
