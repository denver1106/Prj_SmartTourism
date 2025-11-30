import pymysql
import json
import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ===============================
# MySQL CONNECTION
# ===============================
db = pymysql.connect(
    host="localhost",
    user="root",
    password="Khoidmh1106",
    database="smarttourism",
    charset="utf8mb4"
)
cursor = db.cursor()


# =========================================
# SHOPEEFOOD SEARCH GLOBAL (API V3)
# =========================================
def sf_search_global(keyword):
    url = "https://gappapi.deliverynow.vn/api/v3/location/search"
    params = {"keyword": keyword}
    res = requests.get(url, params=params, headers=HEADERS)
    
    if res.status_code != 200:
        return None
        
    return res.json().get("reply", {}).get("items", [])


# =========================================
# SHOPEEFOOD GET DETAIL (API V5)
# =========================================
def sf_detail(shop_id):
    url = f"https://gappapi.deliverynow.vn/api/v5/shop/detail?shop_id={shop_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return None

    return res.json().get("reply", {}).get("shop_detail", {})


# =========================================
# SHOPEEFOOD MENU SCRAPER
# =========================================
def sf_menu(slug, city="ho-chi-minh"):
    url = f"https://shopeefood.vn/{city}/{slug}"
    res = requests.get(url, headers=HEADERS)
    
    if res.status_code != 200:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    items = []

    foods = soup.select(".menu-group .menu-group-items .menu-item")
    for f in foods:
        title = f.select_one(".menu-item-name").text.strip()
        price = f.select_one(".menu-item-price").text.strip()
        img = f.select_one("img")
        img_url = img["src"] if img else None
        
        items.append({
            "name": title,
            "price": price,
            "image": img_url
        })

    return items


# =========================================
# GRABFOOD SEARCH (DÙNG TP.HCM Default)
# =========================================
def gf_search(keyword):
    url = "https://portal.grab.com/foodweb/v2/search"
    
    # Trung tâm Quận 1, TP.HCM
    payload = {
        "keyword": keyword,
        "latlng": {"latitude": 10.776889, "longitude": 106.700806},
        "offset": 0,
        "pageSize": 20
    }
    
    res = requests.post(url, json=payload)
    if res.status_code != 200:
        return None

    return res.json().get("searchResult", {}).get("searchMerchants", [])


def gf_detail(merchant_id):
    url = f"https://portal.grab.com/foodweb/v2/merchants/{merchant_id}"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    
    return res.json()


# =========================================
# MATCHING
# =========================================
def match(name1, name2):
    return fuzz.token_sort_ratio(name1.lower(), name2.lower())


# =========================================
# MAIN ENRICH LOGIC
# =========================================
def enrich_place(name_original):
    print(f"\n🔍 ENRICH: {name_original}")

    # ============================
    # 1) TRY SHOPEEFOOD GLOBAL
    # ============================
    sf_items = sf_search_global(name_original)
    best_sf = None
    best_sf_score = 0

    if sf_items:
        for item in sf_items:
            shop_name = item.get("name", "")
            score = match(name_original, shop_name)

            if score > best_sf_score:
                best_sf_score = score
                best_sf = item

    if best_sf and best_sf_score >= 60:
        detail = sf_detail(best_sf["id"])
        if detail:
            slug = detail["url"].split("/")[-1]
            menu = sf_menu(slug)

            return {
                "source": "ShopeeFood",
                "address": detail.get("address"),
                "lat": detail["location"]["latitude"],
                "lng": detail["location"]["longitude"],
                "tags": ", ".join(detail.get("categories", [])),
                "rating": detail.get("rating"),
                "image_url": detail.get("photos", [{}])[0].get("value"),
                "menu_image": json.dumps([p["value"] for p in detail.get("photos", [])]),
                "menu": json.dumps(menu),
                "price_level": None
            }

    # ============================
    # 2) TRY GRABFOOD
    # ============================
    gf_items = gf_search(name_original)
    best_gf = None
    best_gf_score = 0

    if gf_items:
        for item in gf_items:
            shop_name = item["merchant"]["name"]
            score = match(name_original, shop_name)

            if score > best_gf_score:
                best_gf_score = score
                best_gf = item

    if best_gf and best_gf_score >= 60:
        rid = best_gf["merchant"]["merchantID"]
        detail = gf_detail(rid)

        if detail:
            m = detail["merchant"]
            return {
                "source": "GrabFood",
                "address": m.get("address"),
                "lat": m.get("latlng", {}).get("latitude"),
                "lng": m.get("latlng", {}).get("longitude"),
                "tags": ", ".join(m.get("cuisine", [])),
                "rating": m.get("rating"),
                "image_url": m.get("logoUrl"),
                "menu_image": json.dumps(m.get("photoUrls", [])),
                "menu": json.dumps(m.get("menuItems", [])),
                "price_level": m.get("priceRating")
            }

    return None


# =========================================
# UPDATE TO MYSQL
# =========================================
def update_restaurant(rid, data):
    sql = """
    UPDATE restaurants SET
        address=%s,
        lat=%s,
        lng=%s,
        tags=%s,
        popularity_score=%s,
        image_url=%s,
        menu_image=%s,
        menu=%s,
        price_level=%s
    WHERE id=%s
    """

    cursor.execute(sql, (
        data["address"],
        data["lat"],
        data["lng"],
        data["tags"],
        data["rating"],
        data["image_url"],
        data["menu_image"],
        data["menu"],
        data["price_level"],
        rid
    ))

    db.commit()


# =========================================
# MAIN RUN
# =========================================
def run():
    cursor.execute("SELECT id, name FROM restaurants")
    rows = cursor.fetchall()

    for rid, name in rows:
        enriched = enrich_place(name)

        if enriched:
            update_restaurant(rid, enriched)
            print(f"✅ UPDATED: {name}")
        else:
            print(f"❌ NOT FOUND: {name}")


if __name__ == "__main__":
    run()
