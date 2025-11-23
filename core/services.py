from core.data_manager import DataManager
from core.context_utils import ContextUtils 
from core.recommendation import Recommender

class SmartTourismService:
    def __init__(self, weather_api_key: str):
        # DataManager tự quản lý kết nối DB
        self.dm = DataManager()
        
        # --- ĐÃ SỬA: Xóa dòng self.context_utils = ... ---
        # ContextUtils bây giờ là static class, không cần khởi tạo.
        
        # Lưu api key dự phòng (nếu sau này cần dùng)
        self.weather_api_key = weather_api_key

    def process_user_input(self, user_id, user_lat, user_lon):
        """
        Hàm này nhận đầu vào là User + Vị trí, 
        Trả về: Context (Thời gian) + List quán ăn gợi ý
        """
        # 1. Xây dựng ngữ cảnh (Context) - Gọi trực tiếp từ Class (Static Method)
        # SỬA: Dùng get_time_context() thay vì get_full_context()
        context = ContextUtils.get_time_context()

        # 2. Gọi thuật toán gợi ý (Recommender)
        recommender = Recommender(
            user_id=user_id,
            user_lat=user_lat,
            user_lon=user_lon,
            context=context,
            data_manager=self.dm
        )
        
        # Lấy top 10 quán gợi ý
        result = recommender.generate(top_n=10)

        # 3. Cập nhật lịch sử (Optional)
        if result and len(result) > 0:
            first_place = result[0]
            # Kiểm tra an toàn để tránh lỗi nếu quán không có menu/foods
            foods_list = first_place.get("menu") or first_place.get("foods", [])
            
            if foods_list:
                # Lưu món đầu tiên vào lịch sử người dùng để lần sau gợi ý tốt hơn
                self.dm.update_user_history(user_id, foods_list[0])

        return {
            "context": context,
            "recommendations": result
        }