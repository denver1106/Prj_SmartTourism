import json
import random

# 1. Đọc dữ liệu thật vừa cào được
input_file = 'data/real_restaurants_serpapi.json'
output_file = 'data/restaurants.json'

try:
    with open(input_file, 'r', encoding='utf-8') as f:
        real_data = json.load(f)
    
    print(f"✅ Đã đọc được {len(real_data)} quán ăn thật.")
except FileNotFoundError:
    print("❌ Lỗi: Không tìm thấy file real_restaurants_serpapi.json")
    real_data = []

# 2. Nhân bản dữ liệu (Mục tiêu: tạo khoảng 200 quán)
final_list = []
so_lan_nhan_ban = 12  # Nhân 12 lần lên

count = 1
for i in range(so_lan_nhan_ban):
    for quan in real_data:
        # Tạo bản sao của quán ăn
        new_quan = quan.copy()
        
        # Sửa ID để không bị trùng
        new_quan['id'] = f"res_{count:03d}"  # Ví dụ: res_001, res_002
        
        # Sửa tên một chút để nhìn cho đa dạng (trừ lần đầu tiên)
        if i > 0:
            new_quan['name'] = f"{quan['name']} (Chi nhánh {i})"
            # Random rating một chút cho tự nhiên
            new_quan['rating'] = round(random.uniform(3.5, 5.0), 1)
            new_quan['user_ratings_total'] = random.randint(50, 500)
        
        final_list.append(new_quan)
        count += 1

# 3. Lưu vào file chính restaurants.json
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(final_list, f, ensure_ascii=False, indent=4)

print("-" * 50)
print(f"🎉 THÀNH CÔNG RỰC RỠ!")
print(f"👉 Từ {len(real_data)} quán gốc, đã nhân bản thành {len(final_list)} quán.")
print(f"👉 Dữ liệu đã được lưu vào: {output_file}")
print("👉 Bạn đã sẵn sàng để đẩy lên Firebase!")