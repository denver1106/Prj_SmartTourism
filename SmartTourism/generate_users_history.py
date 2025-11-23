import json
import random
import datetime
from werkzeug.security import generate_password_hash # Cần cài thư viện này để mã hóa pass

# === CẤU HÌNH ===
NUM_USERS = 50
NUM_HISTORY = 300 # Giả lập 300 hoạt động

# Danh sách tên mẫu để random cho đẹp
FIRST_NAMES = ["Anh", "Bình", "Châu", "Dương", "Em", "Giang", "Hải", "Hưng", "Khánh", "Linh", "Minh", "Nam", "Phát", "Quân", "Thảo", "Uyên", "Vinh", "Yến"]
LAST_NAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ"]
PREFERENCES_LIST = ["Món nước", "Món khô", "Lẩu", "Nướng", "Cay", "Không cay", "Món Huế", "Món Bắc", "Món Nam", "Hải sản"]

# === HÀM HỖ TRỢ ===
def get_random_name():
    return f"{random.choice(LAST_NAMES)} {random.choice(FIRST_NAMES)}"

def get_random_username(name):
    # Biến "Nguyễn Văn A" thành "anv123"
    name_parts = name.lower().split()
    suffix = random.randint(100, 9999)
    return f"{name_parts[-1]}{name_parts[0]}{suffix}"

# === BƯỚC 1: ĐỌC DỮ LIỆU CŨ (Để tạo lịch sử cho đúng logic) ===
try:
    with open('data/restaurants.json', 'r', encoding='utf-8-sig') as f:
        restaurants = json.load(f)
    with open('data/foods.json', 'r', encoding='utf-8-sig') as f:
        foods = json.load(f)
    
    # Lấy danh sách ID
    res_ids = [r['id'] for r in restaurants]
    food_ids = [f['id'] for f in foods]
    
    print(f"✅ Đã đọc được {len(res_ids)} quán và {len(food_ids)} món.")
except FileNotFoundError:
    print("❌ Lỗi: Không tìm thấy file data/restaurants.json hoặc data/foods.json")
    print("👉 Bạn cần có 2 file này trước thì mới tạo lịch sử được nhé!")
    exit()

# === BƯỚC 2: TẠO USERS ===
users = []
print("\n🚀 Đang tạo User...")

# 2.1 Tạo Admin (Manager) trước
admin_user = {
    "id": "user_000",
    "username": "admin",
    # Mật khẩu là 'admin123' nhưng đã được mã hóa bảo mật
    "password": generate_password_hash("admin123"), 
    "full_name": "Quản Trị Viên",
    "email": "admin@smarttourism.com",
    "avatar": "https://ui-avatars.com/api/?name=Admin&background=0D8ABC&color=fff",
    "role": "admin", # <--- QUYỀN QUẢN LÝ
    "preferences": ["Tất cả"],
    "created_at": datetime.datetime.now().isoformat()
}
users.append(admin_user)

# 2.2 Tạo User thường
for i in range(1, NUM_USERS + 1):
    full_name = get_random_name()
    username = get_random_username(full_name)
    
    user = {
        "id": f"user_{i:03d}",
        "username": username,
        "password": generate_password_hash("123456"), # Mật khẩu mặc định cho user thường
        "full_name": full_name,
        "email": f"{username}@gmail.com",
        "avatar": f"https://ui-avatars.com/api/?name={full_name.replace(' ', '+')}&background=random",
        "role": "customer", # <--- QUYỀN KHÁCH HÀNG
        "preferences": random.sample(PREFERENCES_LIST, k=random.randint(1, 3)), # Random 1-3 sở thích
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 365))).isoformat()
    }
    users.append(user)

# === BƯỚC 3: TẠO HISTORY ===
histories = []
print("🚀 Đang tạo History (Lịch sử hoạt động)...")

actions = ["view", "like", "rate", "check_in"] # Các hành động có thể làm

for i in range(NUM_HISTORY):
    # Chọn bừa 1 user (trừ admin ra cho giống thật)
    random_user = random.choice(users[1:]) 
    
    # Chọn bừa xem user đó tương tác với Quán hay Món
    target_type = random.choice(["restaurant", "food"])
    
    if target_type == "restaurant" and res_ids:
        target_id = random.choice(res_ids)
    elif target_type == "food" and food_ids:
        target_id = random.choice(food_ids)
    else:
        continue # Bỏ qua nếu không có data

    history_item = {
        "id": f"hist_{i:04d}",
        "user_id": random_user['id'],
        "target_id": target_id,
        "target_type": target_type,
        "action": random.choice(actions),
        # Random thời gian trong 30 ngày qua
        "timestamp": (datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).isoformat()
    }
    
    # Nếu hành động là 'rate' (đánh giá), thêm điểm số và comment giả
    if history_item['action'] == "rate":
        history_item['rating'] = random.randint(3, 5)
        history_item['comment'] = random.choice(["Ngon tuyệt!", "Bình thường", "Sẽ quay lại", "Không hợp khẩu vị lắm", "Quán đẹp"])

    histories.append(history_item)

# === BƯỚC 4: LƯU FILE ===
with open('data/users.json', 'w', encoding='utf-8') as f:
    json.dump(users, f, ensure_ascii=False, indent=4)

with open('data/histories.json', 'w', encoding='utf-8') as f:
    json.dump(histories, f, ensure_ascii=False, indent=4)

print("-" * 50)
print(f"🎉 Đã tạo xong {len(users)} Users và {len(histories)} dòng Lịch sử.")
print("👉 File lưu tại: data/users.json và data/histories.json")