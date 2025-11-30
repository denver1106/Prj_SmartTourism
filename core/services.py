# ============================================
# core/services.py
# ============================================

import requests
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Import các module nội bộ
# Lưu ý: Import DataManager chỉ để Type Hinting (tránh circular import lúc chạy)
from core.data_manager import DataManager 
from core.context_utils import ContextUtils
from core.recommendation import Recommender

class SmartTourismService:
    def __init__(self, weather_api_key: str):
        """
        Service trung tâm điều phối logic:
        - Gọi API thời tiết (OpenWeather).
        - Tổng hợp Context (Thời gian + Thời tiết).
        - Gọi Recommender System.
        
        Args:
            weather_api_key (str): Key API lấy từ biến môi trường.
        """
        self.weather_api_key = weather_api_key
        
        # Cache thời tiết để tránh spam request API (lưu trong RAM)
        # Cấu trúc: { "lat_lon": { "timestamp": datetime, "data": dict } }
        self._weather_cache: Dict[str, Any] = {}
        self._cache_duration = timedelta(minutes=20)

    # ------------------------------------------------------
    # 1. WEATHER SERVICE
    # ------------------------------------------------------
    def get_weather_context(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Lấy thông tin thời tiết từ OpenWeatherMap.
        Có cơ chế Cache: Nếu request lại tọa độ cũ trong 20p thì trả về cache.
        """
        
        # 1. Kiểm tra Cache
        cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
        now = datetime.now()

        if cache_key in self._weather_cache:
            cached_item = self._weather_cache[cache_key]
            if now - cached_item["timestamp"] < self._cache_duration:
                # Cache còn hạn -> return luôn
                return cached_item["data"]

        # 2. Giá trị mặc định (Fallback) nếu không có API Key hoặc lỗi
        default_weather = {
            "temp": 28,
            "weather_raw": "Clear",
            "weather_type": "clear",
            "desc": "Trời quang"
        }

        if not self.weather_api_key:
            return default_weather

        # 3. Gọi API
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather?"
                f"lat={lat}&lon={lon}&appid={self.weather_api_key}&units=metric&lang=vi"
            )
            
            # Timeout 3s để không treo server nếu mạng lag
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            data = response.json()

            # 4. Parse dữ liệu
            temp = float(data["main"]["temp"])
            raw_cond = data["weather"][0]["main"].lower()
            desc = data["weather"][0]["description"] # Mô tả tiếng Việt

            # Mapping sang context của hệ thống
            weather_type = "clear"
            if "rain" in raw_cond or "drizzle" in raw_cond:
                weather_type = "rainy"
            elif "thunderstorm" in raw_cond:
                weather_type = "rainy" # Gộp bão vào mưa để gợi ý món nóng
            elif "cloud" in raw_cond:
                weather_type = "cloudy"
            elif "mist" in raw_cond or "fog" in raw_cond:
                weather_type = "cloudy"
            elif temp >= 34:
                weather_type = "hot"
            elif temp <= 18:
                weather_type = "cold"

            result = {
                "temp": temp,
                "weather_raw": raw_cond,
                "weather_type": weather_type,
                "desc": desc.capitalize()
            }

            # Lưu vào cache
            self._weather_cache[cache_key] = {
                "timestamp": now,
                "data": result
            }
            return result

        except Exception as e:
            print(f"[SmartTourismService] Weather API Error: {e}")
            # Trả về mặc định để app không crash
            return default_weather

    # ------------------------------------------------------
    # 2. MAIN PROCESS (XỬ LÝ NGỮ CẢNH & GỢI Ý)
    # ------------------------------------------------------
    def process_user_input(
        self, 
        data_manager: DataManager, 
        user_id: int, 
        user_lat: float, 
        user_lon: float,
        text_query: str = ""
    ) -> Dict[str, Any]:
        """
        Hàm xử lý chính cho tính năng Gợi ý thông minh (Smart Suggestion).
        
        QUAN TRỌNG:
        - data_manager: Phải được truyền vào từ Controller (app.py) 
          để đảm bảo dùng chung kết nối Database của request hiện tại.
        """

        # BƯỚC 1: Xây dựng Context (Ngữ cảnh)
        # -----------------------------------
        # Context thời gian
        ctx = ContextUtils.get_time_context()
        
        # Context thời tiết
        weather_info = self.get_weather_context(user_lat, user_lon)
        ctx["weather"] = weather_info["weather_type"]
        ctx["weather_temp"] = weather_info["temp"]
        ctx["user_query"] = text_query

        # Lấy lịch sử & sở thích user (Sử dụng data_manager được inject vào)
        user_history = data_manager.get_user_history(user_id)
        user_prefs = data_manager.get_user_preferences(user_id)
        
        # Bổ sung vào context để Recommender sử dụng
        # (Recommender hiện tại tự gọi DB, nhưng việc truyền context đầy đủ 
        # giúp dễ dàng mở rộng debug sau này)
        ctx["user_history_summary"] = user_history[:5] 
        ctx["user_prefs_summary"] = user_prefs

        # BƯỚC 2: Chạy thuật toán gợi ý (Recommender)
        # -----------------------------------
        recommender = Recommender(
            user_id=user_id,
            user_lat=user_lat,
            user_lon=user_lon,
            context=ctx,
            data_manager=data_manager  # Truyền DM vào Recommender
        )

        # Lấy top 10 gợi ý
        try:
            recommendations = recommender.generate(top_n=10)
        except Exception as e:
            print(f"[SmartTourismService] Recommendation Error: {e}")
            traceback.print_exc()
            recommendations = []

        # BƯỚC 3: Tự động cập nhật lịch sử (Optional)
        # -----------------------------------
        # Nếu hệ thống đưa ra 1 gợi ý rất tự tin (ví dụ trong tính năng "Ăn gì ngay?"),
        # ta có thể log lại là user đã "xem" gợi ý này.
        # Ở đây ta chỉ log nếu có kết quả trả về.
        
        suggestion_log = None
        if recommendations:
            top_item = recommendations[0]
            # Lấy tên món đầu tiên trong menu hoặc tên quán để log
            food_name = top_item["name"]
            menu = top_item.get("menu", [])
            if menu and isinstance(menu, list) and len(menu) > 0:
                food_name = str(menu[0])
            
            # Ghi nhận vào DB (ẩn danh hành động này để không spam history user quá nhiều)
            # data_manager.update_user_history(user_id, food_name)
            suggestion_log = f"Suggested: {food_name}"

        # BƯỚC 4: Trả về kết quả tổng hợp
        # -----------------------------------
        return {
            "status": "success",
            "context": {
                "time": ctx.get("time_of_day"),
                "session": ctx.get("season"),
                "weather_desc": weather_info.get("desc"),
                "temp": weather_info.get("temp")
            },
            "weather_data": weather_info,
            "recommendations": recommendations,
            "debug_log": suggestion_log
        }