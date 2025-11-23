from datetime import datetime
from typing import Dict, Optional

class ContextUtils:

    @staticmethod
    def get_time_context(now: Optional[datetime] = None) -> Dict[str, str]:
        if now is None:
            now = datetime.now()

        hour = now.hour
        if 5 <= hour < 10:
            time_of_day = "morning"
        elif 10 <= hour < 14: # Điều chỉnh nhẹ: 10h-14h là trưa (noon)
            time_of_day = "noon"
        elif 14 <= hour < 18: # 14h-18h là chiều (afternoon - hoặc gộp vào evening tùy logic)
            time_of_day = "afternoon" 
        elif 18 <= hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "late"

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
            "weekday": weekday
        }

    @staticmethod
    def merge_context(search_filters: dict, user_history: list, user_pref: dict) -> dict:
        """Hàm tiện ích để gộp thông tin nếu cần mở rộng sau này"""
        ctx = ContextUtils.get_time_context()
        ctx.update({
            "search_filters": search_filters or {},
            "user_history": user_history or [],
            "user_preferences": user_pref or {}
        })
        return ctx