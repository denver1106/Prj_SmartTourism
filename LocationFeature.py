import json
import unicodedata
from math import radians, sin, cos, asin, sqrt

with open("places.json", "r", encoding="utf-8") as f:
    places = json.load(f)
with open("foods.json", "r", encoding="utf-8") as f:
    foods = json.load(f)
with open("restaurants.json", "r", encoding="utf-8") as f:
    restaurants = json.load(f)
with open("user_data.json", "r", encoding="utf-8") as f:
    user_data = json.load(f)
# lấy dữ liệu người dùng
def get_user_distance():
    return user_data.get("distance", 5)
def get_user_budget():
    return user_data.get("budget", 0)
# loại bỏ dấu
def remove_accents(s):
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()

# xử lý với input là địa điểm
def suggest_specialties_by_place(place_name):
    norm_query = remove_accents(place_name)
    for place in places:
        place_id_norm = remove_accents(place["place_id"])
        place_name_norm = remove_accents(place["name"])
        if norm_query == place_id_norm or norm_query == place_name_norm:
            return place.get("specialties", [])
    return []
# xử lý với input là món ăn
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def parse_price_range(price_str):
    try:
        min_price, max_price = price_str.lower().replace('k','').split('-')
        return int(min_price)*1000, int(max_price)*1000
    except:
        return 0, float('inf')  # nếu lỗi thì coi là không giới hạn

def find_restaurants(food_id, user_lat, user_lon):
    user_budget = get_user_budget()
    user_distance = get_user_distance()

    result = []
    for r in restaurants:
        if food_id in r["foods"]:
            lat, lon = r["coordinates"]["lat"], r["coordinates"]["lng"]
            distance = haversine(user_lat, user_lon, lat, lon)
            if distance <= user_distance: 
                min_p, max_p = parse_price_range(r.get("price_range","0-1000000"))
                if user_budget is None or min_p <= user_budget:
                    result.append({
                    "name": r["name"],
                    "distance_km": round(distance, 2),
                    "rating": r["rating"],
                    "price_range": r.get("price_range", ""),
                    "address": r["address"]
                    })
    result.sort(key=lambda x: (-x["rating"], x["distance_km"]))
    return result

# phân loại đầu vào
def classify_input(user_input):
    query = remove_accents(user_input.strip())

    for place in places:
        place_id_norm = remove_accents(place["place_id"])
        place_name_norm = remove_accents(place["name"])
        if query.lower() == place_id_norm.lower() or query.lower() == place_name_norm.lower():
            return "place", place["name"]

    for food in foods:
        food_id_norm = remove_accents(food["food_id"])
        food_name_norm = remove_accents(food["name"])
        if query.lower() == food_id_norm.lower() or query.lower() == food_name_norm.lower():
            return "food", food["food_id"]
    return "unknown", user_input
# xác định đầu vào
def handle_input(user_input, user_lat, user_lon):
    kind, recognized = classify_input(user_input)

    if kind == "place":
        specialties = suggest_specialties_by_place(recognized)
        return {
            "type": "place",
            "place": recognized,
            "specialties": specialties
        }

    if kind == "food":
        restaurants_list = find_restaurants(recognized, user_lat, user_lon)
        return {
            "type": "dish",
            "dish": recognized,
            "restaurants": restaurants_list
        }

    return {
        "type": "unknown",
        "message": f"Không nhận dạng được '{user_input}'"
    }
# xuất ra file json
def export_to_file(result, filename="output.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"Đã xuất kết quả ra {filename}")
# test
if __name__ == "__main__":
    # nhập tọa độ người dùng
    user_lat = float(input("Nhập vĩ độ (latitude): "))
    user_lon = float(input("Nhập kinh độ (longitude): "))

    while True:
        query = input("\nNhập món ăn hoặc địa điểm (hoặc gõ 'exit' để thoát): ")

        if query.lower() == "exit":
            print("Kết thúc chương trình.")
            break

        result = handle_input(query, user_lat, user_lon)
        export_to_file(result)