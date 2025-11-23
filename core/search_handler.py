# core/search_handler.py
from typing import Dict, Any, List

class SearchHandler:

    def parse(self, text_query: str) -> Dict[str, Any]:
        """Phân tích ý định người dùng (Logic của bạn)"""
        if not text_query:
            return {}

        q = text_query.strip().lower()

        # Heuristic simple:
        # Bổ sung thêm vài từ khóa phổ biến
        if any(tok in q for tok in ["ăn", "món", "thức ăn", "phở", "bún", "cơm", "pizza", "mỳ", "lẩu", "nướng"]):
            return {"type": "food", "q": q}
        if any(tok in q for tok in ["tỉnh", "thành phố", "địa điểm", "ở", "near", "gần", "quận", "đường"]):
            return {"type": "place", "q": q}
        
        # Default -> intent / mood / mixed
        return {"type": "intent", "q": q}

    def search(self, data_list: List[Dict[str, Any]], text_query: str) -> List[Dict[str, Any]]:
        """
        Lọc danh sách nhà hàng dựa trên query đã được parse.
        data_list: Danh sách lấy từ DataManager.get_all_restaurants()
        """
        parsed = self.parse(text_query)
        if not parsed:
            return data_list # Trả về hết nếu không nhập gì

        q = parsed["q"]
        intent_type = parsed.get("type", "mixed")
        results = []

        for item in data_list:
            # Chuẩn bị dữ liệu để so sánh (đảm bảo lowercase)
            name = item.get("name", "").lower()
            address = item.get("address", "").lower()
            
            # Menu và tags là list, cần join lại để tìm string
            menu_str = " ".join(item.get("menu", [])).lower() 
            tags_str = " ".join(item.get("tags", [])).lower()

            match = False
            
            # LOGIC TÌM KIẾM THÔNG MINH HƠN DỰA VÀO INTENT
            if intent_type == "food":
                # Nếu tìm đồ ăn -> Ưu tiên quét Menu và Tags trước, rồi mới tới Tên quán
                if q in menu_str or q in tags_str or q in name:
                    match = True
            
            elif intent_type == "place":
                # Nếu tìm địa điểm -> Ưu tiên quét Địa chỉ
                if q in address or q in name:
                    match = True
            
            else:
                # Mặc định (mixed/intent) -> Quét tất cả các trường
                if (q in name or 
                    q in address or 
                    q in menu_str or 
                    q in tags_str):
                    match = True

            if match:
                results.append(item)

        return results