# core/nutrition_service.py

import requests
from typing import Dict, Any, Optional # Thêm imports

# THÔNG TIN API BẠN CUNG CẤP ĐÃ ĐƯỢC THAY THẾ Ở ĐÂY
# Sử dụng API Edamam Nutrition Analysis làm ví dụ.
NUTRITION_API_URL = "https://api.edamam.com/api/nutrition-data"
API_KEY = "b55c3e332d765b8cdc7e4965b3fcfd53" 
APP_ID = "56f598f8" 

def get_nutrition_analysis(ingredients_text: str) -> Dict[str, Any]:
    """
    Gọi API bên ngoài để phân tích dinh dưỡng cho một chuỗi thành phần (sử dụng Edamam API).

    Args:
        ingredients_text (str): Chuỗi các thành phần (ví dụ: "1 apple, 100g chicken breast")

    Returns:
        dict: Kết quả phân tích dinh dưỡng hoặc thông báo lỗi (sẽ chứa khóa 'error' nếu có lỗi).
"""
    try:
        # Edamam yêu cầu thành phần được gửi qua query parameter 'ingr'
        params = {
            'ingr': ingredients_text,
            'app_id': APP_ID,
            'app_key': API_KEY
        }
        print(f"Đang gửi yêu cầu phân tích API cho: {ingredients_text}")
         # Gửi request GET
        response = requests.get(NUTRITION_API_URL, params=params)
        response.raise_for_status() # Raise exception cho status code lỗi (4xx hoặc 5xx)

        # API Edamam trả về 'totalWeight' = 0.0 nếu không tìm thấy thành phần nào
        api_data = response.json()
        if api_data.get('totalWeight', 0.0) == 0.0 and 'ingredients' in api_data:
        # Đây là lỗi API logic, không phải lỗi HTTP 
            raise ValueError("API không thể phân tích các thành phần đã cung cấp (Total weight = 0).")
        return api_data 
    except requests.exceptions.HTTPError as e:
         # Xử lý lỗi HTTP (401, 404, 422, v.v.)
        status_code = response.status_code if 'response' in locals() else 'N/A'
        print(f"Lỗi HTTP {status_code} khi gọi API: {e}")
        return {
             "error": "Lỗi khi gọi API dinh dưỡng. Vui lòng kiểm tra chuỗi thành phần và API Key/ID.", 
            "status_code": status_code,
            "details": str(e)
        }
    except (requests.exceptions.RequestException, ValueError) as e:
         # Xử lý lỗi kết nối hoặc lỗi logic API
        print(f"Lỗi xử lý API dinh dưỡng: {e}")
        return {"error": "Lỗi xử lý API hoặc kết nối.", "details": str(e)}
    except Exception as e:
        print(f"Lỗi không xác định trong phân tích dinh dưỡng: {e}")
    return {"error": "Đã xảy ra lỗi nội bộ không xác định.", "details": str(e)}

# ---------------- BỔ SUNG LOGIC CACHING ----------------
def get_nutrition_with_caching(ingredients_text: str, data_manager: Any) -> Optional[Dict[str, Any]]:
    """
    Sử dụng DataManager để:
    1. Tìm kiếm trong cache Firestore.
    2. Nếu không có (Cache Miss), gọi API.
    3. Nếu gọi API thành công, lưu kết quả vào cache.
    
    Args:
        ingredients_text: Chuỗi thành phần cần phân tích.
        data_manager: Instance của DataManager (cần có các method get_nutrition_cache, set_nutrition_cache).
        
    Returns:
        Dict: Kết quả phân tích dinh dưỡng (HOẶC None nếu thất bại hoàn toàn).
    """
    # Chuẩn hóa query để truy cập cache nhất quán (vd: "1 cup rice" -> "1 cup rice")
    normalized_query = ingredients_text.strip().lower()
    
    # 1. TÌM TRONG CACHE (Firestore)
    cached_result = data_manager.get_nutrition_cache(normalized_query)
    if cached_result:
        print(f"CACHE HIT: Trả về kết quả dinh dưỡng cho '{normalized_query}' từ Firestore.")
        return cached_result
    
    # 2. CACHE MISS: Gọi API
    api_result = get_nutrition_analysis(ingredients_text)
    
    # 3. LƯU KẾT QUẢ VÀO CACHE (Firestore)
    # Kiểm tra: kết quả có tồn tại và không chứa khóa 'error' (chỉ lưu kết quả thành công)
    if api_result and not api_result.get("error"):
        print(f"CACHE WRITE: Lưu kết quả cho '{normalized_query}' vào Firestore.")
        data_manager.set_nutrition_cache(normalized_query, api_result)
        return api_result
        
    # Nếu gọi API thất bại, trả về None hoặc kết quả lỗi (tùy vào cách bạn muốn xử lý ở app.py)
    # Trong trường hợp này, trả về kết quả lỗi để thông báo cho người dùng
    if api_result and api_result.get("error"):
        return api_result # Trả về dictionary có chứa lỗi
        
    return None