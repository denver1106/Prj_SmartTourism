# core/nutrition_service.py

import requests

# THÔNG TIN API BẠN CUNG CẤP ĐÃ ĐƯỢC THAY THẾ Ở ĐÂY
# Sử dụng API Edamam Nutrition Analysis làm ví dụ.
NUTRITION_API_URL = "https://api.edamam.com/api/nutrition-data"
API_KEY = "b55c3e332d765b8cdc7e4965b3fcfd53"  # Đã cập nhật Key
APP_ID = "56f598f8"  # Đã cập nhật ID

def get_nutrition_analysis(ingredients_text):
    """
    Gọi API bên ngoài để phân tích dinh dưỡng cho một chuỗi thành phần (sử dụng Edamam API).

    Args:
        ingredients_text (str): Chuỗi các thành phần (ví dụ: "1 apple, 100g chicken breast")

    Returns:
        dict: Kết quả phân tích dinh dưỡng hoặc thông báo lỗi.
    """
    try:
        # Edamam yêu cầu thành phần được gửi qua query parameter 'ingr'
        params = {
            'ingr': ingredients_text,
            'app_id': APP_ID,
            'app_key': API_KEY
        }
        
        print(f"Đang gửi yêu cầu phân tích cho: {ingredients_text}")
        
        # Gửi request GET
        response = requests.get(NUTRITION_API_URL, params=params)
        response.raise_for_status() # Raise exception cho status code lỗi (4xx hoặc 5xx)
        
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        # Xử lý các lỗi cụ thể từ API (ví dụ: 401 Unauthorized, 404 Not Found, 422 Unprocessable Entity - lỗi dữ liệu đầu vào)
        error_details = response.json() if response.content else {}
        print(f"Lỗi HTTP {response.status_code} khi gọi API: {e}")
        return {
            "error": "Lỗi khi gọi API dinh dưỡng. Vui lòng kiểm tra chuỗi thành phần.", 
            "status_code": response.status_code,
            "details": error_details.get("error", str(e))
        }
    except requests.exceptions.RequestException as e:
        print(f"Lỗi kết nối API dinh dưỡng: {e}")
        return {"error": "Không thể kết nối với dịch vụ phân tích dinh dưỡng.", "details": str(e)}
    except Exception as e:
        print(f"Lỗi không xác định trong phân tích dinh dưỡng: {e}")
        return {"error": "Đã xảy ra lỗi nội bộ.", "details": str(e)}