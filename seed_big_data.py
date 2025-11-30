import firebase_admin
from firebase_admin import credentials, firestore
import random
import time

# --- CẤU HÌNH ---
CRED_PATH = "firebase-key.json" 
NUM_RESTAURANTS = 5000  # CHỐT 5000 QUÁN!

# Tọa độ gốc: KHTN (Quận 5)
BASE_LAT = 10.7628
BASE_LNG = 106.6825

# --- KẾT NỐI ---
if not firebase_admin._apps:
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- 1. KHO DỮ LIỆU ĐỊA LÝ (MỞ RỘNG) ---
LOCATIONS = [
    {"dist": "Quận 1", "streets": ["Nguyễn Huệ", "Lê Lợi", "Pasteur", "Hai Bà Trưng", "Đinh Tiên Hoàng", "Trần Quang Khải", "Bùi Viện"]},
    {"dist": "Quận 3", "streets": ["Lê Văn Sỹ", "Nam Kỳ Khởi Nghĩa", "Trương Định", "Võ Thị Sáu", "Điện Biên Phủ", "Nguyễn Đình Chiểu"]},
    {"dist": "Quận 4", "streets": ["Hoàng Diệu", "Khánh Hội", "Tôn Đản", "Đoàn Văn Bơ", "Bến Vân Đồn"]},
    {"dist": "Quận 5", "streets": ["Nguyễn Trãi", "Trần Hưng Đạo", "An Dương Vương", "Nguyễn Tri Phương", "Hồng Bàng", "Hải Thượng Lãn Ông"]},
    {"dist": "Quận 6", "streets": ["Hậu Giang", "Kinh Dương Vương", "Bà Hom", "Phạm Văn Chí"]},
    {"dist": "Quận 7", "streets": ["Nguyễn Thị Thập", "Huỳnh Tấn Phát", "Nguyễn Văn Linh", "Lê Văn Lương"]},
    {"dist": "Quận 8", "streets": ["Phạm Thế Hiển", "Tạ Quang Bửu", "Dương Bá Trạc"]},
    {"dist": "Quận 10", "streets": ["Sư Vạn Hạnh", "3 Tháng 2", "Thành Thái", "Tô Hiến Thành", "Hòa Hảo", "Cách Mạng Tháng 8"]},
    {"dist": "Quận 11", "streets": ["Lãnh Binh Thăng", "Ông Ích Khiêm", "Lạc Long Quân", "Bình Thới"]},
    {"dist": "Phú Nhuận", "streets": ["Phan Xích Long", "Phan Đăng Lưu", "Nguyễn Kiệm", "Huỳnh Văn Bánh"]},
    {"dist": "Tân Bình", "streets": ["Cộng Hòa", "Trường Chinh", "Hoàng Văn Thụ", "Lê Văn Sỹ", "Phạm Văn Hai"]}
]

PREFIXES = ["Quán", "Tiệm", "Nhà Hàng", "Bếp", "Góc", "Tiệm Ăn", "Phố", "Làng", "Vườn", "Hẻm", "Lò", "Xe"]
NAMES = [
    "Cô Ba", "Chú Tư", "Bà Bảy", "Út Lành", "Mười Khó", "Sài Gòn", "Phố Cổ", "Hương Quê", "Ngon", "Gia Truyền", 
    "Mẹ Nấu", "Đêm", "24h", "Bà Tám", "Ông Hai", "Cậu Út", "Dì Năm", "Cô Sáu", "Thanh Xuân", "Hạnh Phúc", 
    "Bình Dân", "Sinh Viên", "Đại Gia", "Tí Hon", "Mập", "Còi", "Xưa & Nay", "Ký Ức", "Tuổi Thơ", "Sạch", 
    "Gốc Hoa", "Béo", "Hè Phố", "Góc Nhỏ", "Yêu Thương", "Mầm Đá", "Lão Trư", "Chị Đẹp", "Anh Béo"
]

# --- 2. CẤU HÌNH CHI TIẾT (FULL TAGS) ---
CATEGORIES = {
    "com_tam": {
        "name": "Cơm Tấm", "menu": ["Cơm sườn", "Cơm bì chả", "Canh khổ qua"], "foods": ["com_tam", "suon_bi"],
        "tags": ["cơm", "trưa", "no nê", "bình dân"], 
        "vibe_pool": ["street_food", "street_food", "cozy"], 
        "groups": ["alone", "family", "friends", "company"], 
        "cuisine": "vietnamese", 
        "amenities": ["parking_free", "takeaway"], 
        "calo": [600, 900],
        "imgs": ["https://statics.vinpearl.com/com-tam-sai-gon-0_1630563211.jpg"]
    },
    "pho": {
        "name": "Phở", "menu": ["Phở tái", "Phở nạm", "Quẩy"], "foods": ["pho_bo"],
        "tags": ["sáng", "món nước", "truyền thống", "ấm bụng"], 
        "vibe_pool": ["traditional", "street_food"],
        "groups": ["family", "alone", "friends"], 
        "cuisine": "vietnamese", 
        "amenities": ["parking_free"], 
        "calo": [350, 550],
        "imgs": ["https://cdn.tgdd.vn/Files/2022/01/25/1412805/cach-nau-pho-bo-nam-dinh-chuan-vi-thom-ngon-nhu-hang-quan-202201250230038502.jpg"]
    },
    "tra_sua": {
        "name": "Trà Sữa", "menu": ["Trà sữa trân châu", "Hồng trà", "Lục trà"], "foods": ["tra_sua"],
        "tags": ["giải khát", "chiều", "ngọt", "học bài"], 
        "vibe_pool": ["modern", "cozy", "cute"],
        "groups": ["dating", "friends", "alone"], 
        "cuisine": "taiwanese", 
        "amenities": ["wifi", "ac", "parking_free", "delivery"], 
        "calo": [300, 500],
        "imgs": ["https://cdn.tgdd.vn/Files/2021/08/18/1376045/cach-lam-tra-sua-truyen-thong-ngon-tao-nha-don-gian-202108181122285496.jpg"]
    },
    "lau_nuong": {
        "name": "Lẩu Nướng", "menu": ["Combo bò mỹ", "Ba chỉ nướng", "Lẩu thái"], "foods": ["lau", "bbq"],
        "tags": ["tối", "nhậu", "tiệc tùng", "sang trọng"], 
        "vibe_pool": ["luxury", "modern"],
        "groups": ["company", "class", "family"], 
        "cuisine": "korean", 
        "amenities": ["ac", "car_parking", "credit_card", "vat"], 
        "calo": [800, 1500],
        "imgs": ["https://cdn.tgdd.vn/Files/2020/12/16/1314120/cach-lam-lau-nuong-tai-nha-don-gian-thom-ngon-h-7.jpg"]
    },
    "banh_mi": {
        "name": "Bánh Mì", "menu": ["Bánh mì thịt", "Bánh mì chả cá", "Xôi mặn"], "foods": ["banh_mi"],
        "tags": ["sáng", "nhanh", "mang đi"], 
        "vibe_pool": ["street_food"],
        "groups": ["alone", "friends"], 
        "cuisine": "vietnamese", 
        "amenities": ["takeaway"], 
        "calo": [300, 450],
        "imgs": ["https://cdn.tgdd.vn/Files/2021/07/22/1369932/cach-lam-banh-mi-thit-nuong-thom-ngon-cho-bua-sang-day-du-dinh-duong-202206061223590497.jpg"]
    }
}

REVIEWS_POOL = [
    {"user": "Minh Tuấn", "rating": 5, "comment": "Quán ruột, ngon rẻ!"},
    {"user": "Lan Anh", "rating": 4, "comment": "Đồ ăn ngon, nhưng quán hơi đông."},
    {"user": "Huy Hoàng", "rating": 5, "comment": "10 điểm chất lượng."},
    {"user": "Thảo Vy", "rating": 3, "comment": "Tạm ổn, phục vụ hơi chậm."},
]

# --- 3. HÀM TẠO DỮ LIỆU THÔNG MINH ---
def generate_smart_restaurant(index):
    cat_key = random.choice(list(CATEGORIES.keys()))
    cat_data = CATEGORIES[cat_key]
    
    # Địa điểm & Tên
    loc = random.choice(LOCATIONS)
    street = random.choice(loc["streets"])
    address = f"{random.randint(1, 999)} {street}, {loc['dist']}, TP.HCM"
    
    # Random tên
    suffix_num = f" {random.randint(1, 99)}" if random.random() < 0.3 else ""
    name_style = random.choice([1, 2, 3])
    if name_style == 1:
        name = f"{random.choice(PREFIXES)} {cat_data['name']} {random.choice(NAMES)}{suffix_num}"
    elif name_style == 2:
        name = f"{cat_data['name']} {street}" 
    else:
        name = f"{cat_data['name']} {random.choice(NAMES)}"

    # Toạ độ (Rộng 5-6km)
    lat = BASE_LAT + random.uniform(-0.06, 0.06)
    lng = BASE_LNG + random.uniform(-0.06, 0.06)
    
    # Logic Vibe & Amenities
    vibe = random.choice(cat_data["vibe_pool"])
    amenities = cat_data["amenities"].copy()
    
    if vibe == "luxury":
        price_level = "expensive"
        price_range = "200k - 500k"
        amenities.extend(["ac", "credit_card", "wifi"])
    elif vibe == "street_food":
        price_level = "cheap"
        price_range = "20k - 40k"
        amenities.append("outdoor")
        if "wifi" in amenities: amenities.remove("wifi") 
    else:
        price_level = "medium"
        price_range = "40k - 80k"
        amenities.append("ac")
    
    amenities = list(set(amenities)) 

    # Groups & Reviews
    selected_groups = random.sample(cat_data["groups"], k=min(2, len(cat_data["groups"])))
    if "alone" in cat_data["groups"] and random.random() < 0.6: 
        selected_groups.append("alone")
    selected_groups = list(set(selected_groups))
    
    shop_reviews = random.sample(REVIEWS_POOL, k=random.randint(1, 4))
    rating = round(random.uniform(3.8, 5.0), 1)
    
    # Tags tổng hợp (Đủ 5-7 tag)
    final_tags = cat_data["tags"] + [loc["dist"].lower(), vibe]
    if amenities: final_tags.append(amenities[0])
    final_tags = list(set(final_tags))

    return {
        "id": f"seed_{index}_{cat_key}_{random.randint(100000,999999)}",
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "openTime": f"{random.randint(6,9)}:00",
        "closeTime": f"{random.randint(21,23)}:00",
        
        # --- FULL FIELDS (Chất lượng) ---
        "price_level": price_level,
        "price_range": price_range,
        "rating": rating,
        "total_reviews": random.randint(20, 500),
        "menu": cat_data["menu"],
        "foods": cat_data["foods"],
        "images": cat_data["imgs"],
        "reviews": shop_reviews,
        "calories": f"{random.randint(cat_data['calo'][0], cat_data['calo'][1])} kcal",
        
        # --- 5 NHÓM TAG CHUẨN CHỈNH ---
        "tags": final_tags,             
        "group_type": selected_groups,  
        "vibe": vibe,                   
        "cuisine": cat_data["cuisine"], 
        "amenities": amenities,         
        
        "generated_by_script": True
    }

# --- 4. CHẠY ---
def seed_data():
    print(f"🚀 Đang tạo {NUM_RESTAURANTS} quán ăn (Phiên bản FULL OPTIONS)...")
    batch = db.batch()
    count = 0
    BATCH_LIMIT = 400

    all_data = [generate_smart_restaurant(i) for i in range(NUM_RESTAURANTS)]
    print(f"📦 Dữ liệu sẵn sàng. Bắt đầu đẩy lên Firebase...")

    for i, data in enumerate(all_data):
        doc_ref = db.collection("restaurants").document(data["id"])
        batch.set(doc_ref, data)
        count += 1
        
        if count % BATCH_LIMIT == 0:
            print(f"⏳ Đang ghi batch {count}...")
            batch.commit()
            batch = db.batch()
            time.sleep(1.5)

    if count % BATCH_LIMIT != 0:
        batch.commit()
        print(f"✅ Batch cuối xong.")

    print(f"\n🎉 XONG! {NUM_RESTAURANTS} quán đã có đầy đủ mọi thứ!")

if __name__ == "__main__":
    x = input(f"Chạy script tạo {NUM_RESTAURANTS} quán? (y/n): ")
    if x.lower() == 'y':
        seed_data()