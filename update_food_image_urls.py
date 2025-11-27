import json
from pathlib import Path

# Xác định đường dẫn gốc project (file này nằm ở gốc SmartTourism)
BASE_DIR = Path(__file__).resolve().parent

# Đường dẫn tới foods.json
FOODS_PATH = BASE_DIR / "data" / "foods.json"

def build_image_url(food_id: str) -> str:
    """
    Cách A: dùng static của Flask
    Ảnh được lưu tại: static/images/foods/<id>.jpg
    """
    return f"/static/images/foods/{food_id}.jpg"

def main():
    # Đọc file foods.json
    with FOODS_PATH.open("r", encoding="utf-8-sig") as f:
        foods = json.load(f)

    # Cập nhật imageUrl cho tất cả món
    for item in foods:
        food_id = item.get("id")
        if not food_id:
            continue
        item["imageUrl"] = build_image_url(food_id)

    # Ghi lại file
    with FOODS_PATH.open("w", encoding="utf-8") as f:
        json.dump(foods, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã cập nhật imageUrl cho {len(foods)} món ăn trong data/foods.json")

if __name__ == "__main__":
    main()
