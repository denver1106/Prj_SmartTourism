import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import json
import random
import pymysql
import requests


# =====================================
# MYSQL
# =====================================
db = pymysql.connect(
    host="localhost",
    user="root",
    password="Khoidmh1106",
    database="smarttourism",
    charset="utf8mb4"
)
cursor = db.cursor()


def save_restaurant(data):
    sql = """
    INSERT INTO restaurants
    (name, address, lat, lng, tags, price_level, description,
     image_url, menu_image, menu, rating, reviews)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        address=VALUES(address),
        lat=VALUES(lat),
        lng=VALUES(lng),
        tags=VALUES(tags),
        price_level=VALUES(price_level),
        description=VALUES(description),
        image_url=VALUES(image_url),
        menu_image=VALUES(menu_image),
        menu=VALUES(menu),
        rating=VALUES(rating),
        reviews=VALUES(reviews)
    """
    cursor.execute(sql, (
        data["name"],
        data["address"],
        data["lat"],
        data["lng"],
        data["tags"],
        data["price_level"],
        data["description"],
        data["image_url"],
        json.dumps(data["menu_image"], ensure_ascii=False),
        json.dumps(data["menu"], ensure_ascii=False),
        data["rating"],
        json.dumps(data["reviews"], ensure_ascii=False)
    ))
    db.commit()


# =====================================
# FOODY REVIEW API
# =====================================
def get_reviews(res_id):
    reviews = []
    page = 1

    while True:
        url = f"https://www.foody.vn/__get/ReviewRes.ashx?ResId={res_id}&PageIndex={page}"

        try:
            data = requests.get(url).json()
        except:
            break

        items = data.get("Items", [])
        if not items:
            break

        for rv in items:
            reviews.append({
                "user": rv.get("User", {}).get("Name"),
                "rating": rv.get("AvgRating"),
                "date": rv.get("Date"),
                "text": rv.get("Review"),
                "images": [img.get("ImageUrl") for img in rv.get("ReviewImages", [])]
            })

        if len(items) < 10:
            break

        page += 1
        time.sleep(0.2)

    return reviews


# =====================================
# BUILD DRIVER (ANTI-BOT FOR MAC M1)
# =====================================
def build_driver():
    chrome_options = Options()

    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    )

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--start-maximized")

    # BẮT BUỘC CHO M1
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    chrome_options.add_argument("--disable-site-isolation-trials")

    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = uc.Chrome(
        options=chrome_options,
        version_main=142,
        use_subprocess=True
    )

    # PATCH NAVIGATOR
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1,2,3]
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['vi-VN', 'vi']
                });

                Object.defineProperty(navigator, 'platform', {
                    get: () => 'MacIntel'
                });
            """
        }
    )

    return driver


# =====================================
# PARSE DETAIL PAGE
# =====================================
def parse_detail_html(driver, url):
    driver.get(url)
    time.sleep(1.2)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    name = soup.select_one(".main-info-title")
    name = name.text.strip() if name else None

    address = soup.select_one(".res-common-add span")
    address = address.text.strip() if address else None

    rating_tag = soup.select_one(".microsite-point-avg")
    rating = float(rating_tag.text.strip()) if rating_tag else None

    map_tag = soup.select_one("#restaurant-map")
    lat = map_tag.get("data-lat") if map_tag else None
    lng = map_tag.get("data-lng") if map_tag else None

    gallery = []
    for img in soup.select(".swiper-wrapper .swiper-slide img"):
        src = img.get("src") or img.get("data-src")
        if src:
            gallery.append(src)

    menu = []
    for item in soup.select(".menu-items .item"):
        title = item.select_one(".title-menu")
        price = item.select_one(".price-menu")
        img_tag = item.select_one("img")

        menu.append({
            "name": title.text.strip() if title else None,
            "price": price.text.strip() if price else None,
            "image": img_tag.get("data-src") if img_tag else None
        })

    tags = ", ".join([x.text.strip() for x in soup.select(".category-items a")])

    price_level_tag = soup.select_one(".res-summary-price span")
    price_level = price_level_tag.text.strip() if price_level_tag else None

    desc_tag = soup.select_one(".read-more")
    description = desc_tag.text.strip() if desc_tag else ""

    logo_tag = soup.select_one(".pic img")
    image_url = logo_tag.get("src") if logo_tag else None

    res_meta = soup.select_one("meta[property='foody:restaurant_id']")
    res_id = res_meta.get("content") if res_meta else None

    reviews = get_reviews(res_id) if res_id else []

    return {
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "tags": tags,
        "price_level": price_level,
        "description": description,
        "image_url": image_url,
        "menu_image": gallery,
        "menu": menu,
        "rating": rating,
        "reviews": reviews
    }


# =====================================
# SCRAPE LIST PAGE
# =====================================
def scrape_list(driver, district):
    page = 1
    while True:
        list_url = f"https://www.foody.vn/ho-chi-minh/{district}/food?page={page}"
        print("LIST:", list_url)

        driver.get(list_url)
        time.sleep(1.4)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.select(".search-item")

        if not items:
            print(" → No more items.")
            break

        for it in items:
            href = it.get("href")
            if not href:
                continue

            detail_url = "https://www.foody.vn" + href
            print(" → Detail:", detail_url)

            data = parse_detail_html(driver, detail_url)
            save_restaurant(data)

            time.sleep(random.uniform(0.6, 1.2))

        page += 1
        time.sleep(0.4)


# =====================================
# MAIN
# =====================================
DISTRICTS = [
    "quan-1", "quan-3", "quan-4", "quan-5", "quan-6",
    "quan-7", "quan-8", "quan-10", "quan-11", "quan-12",
    "quan-phu-nhuan", "quan-binh-thanh", "quan-tan-binh",
    "quan-tan-phu", "quan-go-vap", "quan-binh-tan",
    "thu-duc", "quan-2", "quan-9"
]


if __name__ == "__main__":
    driver = build_driver()

    for d in DISTRICTS:
        print("==========", d, "==========")
        scrape_list(driver, d)

    driver.quit()
    print("\nDONE EVERYTHING!")
