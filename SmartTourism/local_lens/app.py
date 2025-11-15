import os
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, render_template, request, redirect, url_for, flash

# ====== Config ======
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = "dev-secret"  # đổi khi deploy thực tế
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


# ====== Helpers ======
def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


def make_maps_link(query: str):
    # Link Google Maps search như “bún bò Huế near Ho Chi Minh City”
    params = {"q": query}
    return f"https://www.google.com/maps/search/?{urlencode(params)}"


def fake_analyze_image(image_path: Path):
    """
    Placeholder phân tích ảnh.
    TODO: thay bằng model thực tế (Vision API, CLIP, v.v.)
    Trả về: (identified_location, [dishes])
    """
    # Demo cứng: bạn có thể random theo tên file nếu muốn
    identified_location = "Ho Chi Minh City"
    dishes = [
        {"name": "Bún bò Huế", "desc": "Món nước đậm vị, sả và mắm ruốc nhẹ."},
        {"name": "Cơm tấm", "desc": "Sườn bì chả, mỡ hành, nước mắm chua ngọt."},
        {"name": "Bánh mì", "desc": "Ổ bánh mì giòn, pate, thịt nguội, rau thơm."},
    ]
    return identified_location, dishes


# ====== Routes ======
@app.route("/", methods=["GET"])
def home():
    # Trạng thái ban đầu (hình 1)
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    """
    Nhận input: có thể là từ khóa (search_text) hoặc upload ảnh (image).
    - Nếu có ảnh: lưu file → phân tích → render kết quả (hình 2).
    - Nếu chỉ có text: hiển thị kết quả thẳng, dùng text làm location.
    """
    search_text = request.form.get("search_text", "").strip()

    file = request.files.get("image")
    if file and file.filename:
        if not allowed_file(file.filename):
            flash("Định dạng ảnh không hợp lệ. Cho phép: jpg, jpeg, png, webp.")
            return redirect(url_for("home"))

        save_path = UPLOAD_DIR / file.filename
        file.save(save_path)

        # Phân tích ảnh (giả lập)
        location, dishes = fake_analyze_image(save_path)

    else:
        # Không có ảnh, dùng text làm “location”
        if not search_text:
            flash("Hãy nhập từ khóa hoặc chọn một ảnh.")
            return redirect(url_for("home"))
        location = search_text
        # Demo món ăn mẫu
        dishes = [
            {"name": "Phở bò", "desc": "Bánh phở, nước dùng trong, thịt bò thái mỏng."},
            {"name": "Bún chả", "desc": "Chả nướng ăn cùng bún, rau sống, nước chấm."},
            {"name": "Gỏi cuốn", "desc": "Cuốn tôm thịt, bún, rau, chấm tương đậu."},
        ]

    # Chuẩn bị 3 cột gợi ý quán ăn (mỗi món 3 quán demo)
    cards = []
    for dish in dishes[:3]:
        shops = [
            {
                "label": "Quán ăn 1",
                "map_url": make_maps_link(f"{dish['name']} near {location}"),
            },
            {
                "label": "Quán ăn 2",
                "map_url": make_maps_link(f"{dish['name']} best near {location}"),
            },
            {
                "label": "Quán ăn 3",
                "map_url": make_maps_link(f"{dish['name']} street food near {location}"),
            },
        ]
        cards.append(
            {
                "dish": dish["name"],
                "desc": dish["desc"],
                "image_url": url_for("static", filename="placeholder-food.png"),
                "shops": shops,
            }
        )

    return render_template(
        "results.html",
        identified_location=location,
        cards=cards,
    )


if __name__ == "__main__":
    # Run dev server
    app.run(debug=True)
