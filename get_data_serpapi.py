from serpapi import GoogleSearch
import json
import time

# === CẤU HÌNH ===
# 1. Dán cái Key trong ảnh của bạn vào đây (trong dấu ngoặc kép)
YOUR_API_KEY = "54f66d2ad514fc3d893f3cb36b23dc9365cdf36f93fb519488361cea1c3a9f7e" 

# 2. Danh sách các quán bạn muốn tìm (Bạn có thể sửa/thêm tùy ý)
ds_quan_an = [
    # --- HÀ NỘI (MIỀN BẮC) ---
    "Phở Thìn Lò Đúc Hà Nội",
    "Phở Lý Quốc Sư Hàng Vôi",
    "Bún Chả Hương Liên Lê Văn Hưu",
    "Chả Cá Lã Vọng Hà Nội",
    "Bún Đậu Mắm Tôm Hàng Khay",
    "Xôi Yến Nguyễn Hữu Huân",
    "Bánh Cuốn Bà Hoành Tô Hiến Thành",
    "Bún Thang Bà Đức Cầu Gỗ",
    "Phở Bát Đàn Hà Nội",
    "Bún Ốc Cô Huệ Nguyễn Siêu",
    "Kem Tràng Tiền Hà Nội",
    "Cà Phê Giảng Nguyễn Hữu Huân",
    "Bánh Mì Dân Tổ Hà Nội",
    "Mỳ Vằn Thắn Bình Tây Phố Huế",
    "Bún Riêu Cua Hàng Bạc",

    # --- HUẾ - ĐÀ NẴNG - HỘI AN (MIỀN TRUNG) ---
    "Bún Bò Huế Đông Ba",
    "Cơm Hến Bà Cam Huế",
    "Chè Hẻm Huế",
    "Bánh Bèo Nậm Lọc Bà Đỏ Huế",
    "Bánh Mì Phượng Hội An",
    "Cơm Gà Bà Buội Hội An",
    "Cao Lầu Thanh Hội An",
    "Mì Quảng Ếch Bếp Trang Đà Nẵng",
    "Bánh Xèo Bà Dưỡng Đà Nẵng",
    "Bánh Tráng Thịt Heo Trần Đà Nẵng",
    "Bún Chả Cá Ông Tạ Đà Nẵng",
    "Hải Sản Bé Mặn Đà Nẵng",
    "Bún Mắm Nêm Bà Thuyên Đà Nẵng",
    "Nem Lụi Bà Trai Huế",
    "Bánh Canh Ruộng Đà Nẵng",

    # --- SÀI GÒN - MIỀN TÂY (MIỀN NAM) ---
    "Cơm Tấm Ba Ghiền Sài Gòn",
    "Cơm Tấm Phúc Lộc Thọ",
    "Hủ Tiếu Nam Vang Nhân Quán",
    "Phở Lệ Nguyễn Trãi",
    "Bánh Mì Huỳnh Hoa Quận 1",
    "Dim Tu Tac Saigon",
    "Ốc Đào Nguyễn Trãi",
    "Lẩu Cá Kèo Bà Huyện Thanh Quan",
    "Sủi Cảo Hà Tôn Quyền",
    "Bún Mắm Cô Ba VN Hiệu",
    "Bánh Canh Ghẹ Muối Ớt Xanh Sài Gòn",
    "Chè Khúc Bạch Đỗ Ngọc",
    "Bún Bò Gánh Lý Chính Thắng",
    "Bánh Xèo 46A Đinh Công Tráng",
    "Cua Dì Ba Chợ Thái Bình",
    "Hủ Tiếu Mì Cật 62 Trương Định",
    "Pizza 4P's Bến Thành",
    "Bún Quậy Phú Quốc Kiến Xây",
    "Lẩu Mắm Dạ Lý Cần Thơ",
    "Bánh Xèo Mười Xiềm Cần Thơ"
]

ket_qua_thu_thap = []

print(f"🚀 Đang bắt đầu tìm kiếm thông tin cho {len(ds_quan_an)} quán ăn...")
print("-" * 50)

for ten_quan in ds_quan_an:
    print(f"🔎 Đang tìm: {ten_quan}...")
    
    params = {
        "engine": "google_maps",  # Dùng engine Google Maps
        "q": ten_quan,            # Từ khóa tìm kiếm
        "api_key": YOUR_API_KEY,  # Key của bạn
        "type": "search",
        "hl": "vi"                # Ngôn ngữ Tiếng Việt
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Kiểm tra xem có kết quả trả về không
        if "local_results" in results and len(results["local_results"]) > 0:
            # Lấy kết quả đầu tiên (chính xác nhất)
            place = results["local_results"][0]
            
            # Tạo cấu trúc dữ liệu JSON giống project của bạn
            restaurant_info = {
                "name": place.get("title"),
                "address": place.get("address"),
                "rating": place.get("rating", 0),
                "user_ratings_total": place.get("reviews", 0),
                # Lấy ảnh đại diện (nếu có), không thì dùng ảnh mẫu
                "image_url": place.get("thumbnail", "https://via.placeholder.com/300"),
                "place_id": place.get("place_id"),
                "description": f"Địa điểm ẩm thực nổi tiếng tại {place.get('address', 'Việt Nam')}. Được đánh giá {place.get('rating', 0)} sao trên Google Maps.",
                # Giả lập thêm giá cả (vì Google Maps ít khi để giá cụ thể)
                "price_range": "30.000đ - 60.000đ" 
            }
            
            ket_qua_thu_thap.append(restaurant_info)
            print(f"✅ Đã thấy: {restaurant_info['name']} ({restaurant_info['rating']}⭐)")
        else:
            print(f"❌ Không tìm thấy quán này: {ten_quan}")

    except Exception as e:
        print(f"⚠️ Lỗi khi tìm {ten_quan}: {e}")
    
    # Nghỉ 1 giây để server không chặn
    time.sleep(1)

# === LƯU FILE ===
output_file = 'data/real_restaurants_serpapi.json'

# Đảm bảo thư mục data tồn tại
import os
if not os.path.exists('data'):
    os.makedirs('data')

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(ket_qua_thu_thap, f, ensure_ascii=False, indent=4)

print("-" * 50)
print(f"🎉 HOÀN TẤT! Đã lưu dữ liệu vào file: {output_file}")
print(f"👉 Bạn hãy mở file đó lên và copy nội dung vào 'restaurants.json' nhé!")