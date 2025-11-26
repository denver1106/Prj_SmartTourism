"""
Module: manual_filters.py
Tính năng: LỌC THỦ CÔNG danh sách quán ăn dựa trên lựa chọn từ frontend.

Ý tưởng:
- Nhận vào 1 list các dict "restaurant" (định dạng giống DataManager.get_all_restaurants)
- Áp dụng lần lượt các tiêu chí:
    + max_distance (khoảng cách tối đa, km)
    + price_level   (cheap / medium / expensive)
    + tag           (fast_food / noodle / soup / breakfast / lunch / bbq)
    + cravings_text (chuỗi mô tả nhu cầu hiện tại của user)
    + people_count  (số lượng người trong nhóm – nếu có field max_people)

File này ĐỘC LẬP, không phụ thuộc Flask.
Có thể import vào app.py bằng:
    from core.manual_filters import filter_restaurants
"""

from typing import List, Dict, Any, Optional


def _parse_price_to_number(price_str: Any) -> Optional[int]:
    """
    Chuyển chuỗi giá dạng '30k', '50K', '100'... về số nguyên (nghìn).
    Ví dụ: '30k' -> 30, '50K' -> 50, '100' -> 100
    Nếu không parse được, trả về None.
    """
    if not price_str:
        return None

    s = str(price_str).strip().lower()
    # bỏ chữ 'k' nếu có
    s = s.replace("k", "")
    try:
        return int(s)
    except ValueError:
        return None


def _match_price_level(price_level_str: Any, level: Optional[str]) -> bool:
    """
    Kiểm tra 1 quán có match với mức giá được chọn hay không.

    level: 'cheap' / 'medium' / 'expensive' / None
    Quy ước demo (nghìn đồng):
        - cheap     : <= 40k
        - medium    : 40k < giá <= 80k
        - expensive : > 80k
    """
    if not level:
        return True  # không chọn filter này -> luôn match

    value = _parse_price_to_number(price_level_str)
    if value is None:
        # nếu không có thông tin giá -> không loại, cho qua
        return True

    if level == "cheap":
        return value <= 40
    if level == "medium":
        return 40 < value <= 80
    if level == "expensive":
        return value > 80

    # Nếu level lạ -> không áp dụng filter
    return True


def _match_tag(tags: List[Any], selected_tag: Optional[str]) -> bool:
    """
    Kiểm tra quán có chứa tag được chọn hay không.
    tag ví dụ: 'fast_food', 'noodle', 'soup', ...
    """
    if not selected_tag:
        return True

    tags_lower = [str(t).lower() for t in tags or []]
    return selected_tag.lower() in tags_lower


def _match_cravings_text(
    restaurant: Dict[str, Any],
    cravings_text: Optional[str]
) -> bool:
    """
    Dùng chuỗi cravings_text (mô tả nhu cầu) để match vào:
    - tên quán
    - menu
    - tags

    Nếu cravings_text rỗng -> luôn match.
    """
    if not cravings_text:
        return True

    q = cravings_text.strip().lower()
    if not q:
        return True

    name = str(restaurant.get("name", "")).lower()
    menu_str = " ".join([str(m) for m in restaurant.get("menu", [])]).lower()
    tags_str = " ".join([str(t) for t in restaurant.get("tags", [])]).lower()

    return (q in name) or (q in menu_str) or (q in tags_str)


def _match_distance(
    distance_km: Any,
    max_distance: Optional[float]
) -> bool:
    """
    Lọc theo khoảng cách tối đa (km).
    Nếu max_distance = None -> không lọc.
    Nếu quán chưa có distance_km -> cho qua (hoặc chỉnh lại tùy yêu cầu).
    """
    if max_distance is None:
        return True

    try:
        dist_val = float(distance_km)
    except (TypeError, ValueError):
        return True  # không có dữ liệu khoảng cách -> không loại

    return dist_val <= max_distance


def _match_people_count(
    restaurant: Dict[str, Any],
    people_count: Optional[int]
) -> bool:
    """
    Lọc theo số lượng người (nếu trong dữ liệu có field 'max_people').

    - people_count: số người user chọn (VD: 2,4,6,...)
    - restaurant['max_people']: sức chứa phù hợp (VD: 2,4,6,10...)

    Nếu:
        + people_count = None -> không lọc
        + 'max_people' không tồn tại -> không loại
    """
    if not people_count:
        return True

    max_p = restaurant.get("max_people")
    if isinstance(max_p, (int, float)):
        return max_p >= people_count
    # Không có thông tin -> không loại
    return True


def filter_restaurants(
    restaurants: List[Dict[str, Any]],
    *,
    max_distance: Optional[float] = None,
    price_level: Optional[str] = None,
    tag: Optional[str] = None,
    cravings_text: Optional[str] = None,
    people_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Hàm chính: LỌC THỦ CÔNG danh sách quán ăn.

    Tham số:
        restaurants  : list các quán ăn (dict) đã có sẵn dữ liệu từ DataManager.
                       Yêu cầu:
                            - mỗi quán có thể có các field:
                                + distance_km
                                + price_level
                                + tags (list)
                                + menu (list)
                                + max_people (tùy chọn)
        max_distance : khoảng cách tối đa (km) – lấy từ input 'max_distance' ở frontend.
        price_level  : 'cheap' / 'medium' / 'expensive' (select price_level ở index.html).
        tag          : loại quán: 'fast_food' / 'noodle' / 'soup' / 'breakfast' / ...
        cravings_text: mô tả nhu cầu hiện tại (textarea 'cravings_text').
        people_count : số lượng người trong nhóm (nếu sau này frontend có thêm input).

    Trả về:
        Danh sách quán đã được lọc theo tất cả tiêu chí (AND logic).
    """
    filtered: List[Dict[str, Any]] = []

    for r in restaurants:
        # 1. khoảng cách
        if not _match_distance(r.get("distance_km"), max_distance):
            continue

        # 2. mức giá
        if not _match_price_level(r.get("price_level"), price_level):
            continue

        # 3. loại quán (tag)
        if not _match_tag(r.get("tags", []), tag):
            continue

        # 4. cravings_text
        if not _match_cravings_text(r, cravings_text):
            continue

        # 5. số lượng người
        if not _match_people_count(r, people_count):
            continue

        # Nếu đi qua hết các filter mà không bị 'continue' -> giữ lại
        filtered.append(r)

    return filtered


# =========================
# Ví dụ cách dùng (demo)
# =========================
if __name__ == "__main__":
    demo_data = [
        {
            "name": "Phở Bò Gia Truyền",
            "distance_km": 1.2,
            "price_level": "40k",
            "tags": ["noodle", "breakfast"],
            "menu": ["phở tái", "phở nạm"],
            "max_people": 4,
        },
        {
            "name": "BBQ Nướng Tối",
            "distance_km": 4.5,
            "price_level": "120k",
            "tags": ["bbq", "lunch"],
            "menu": ["ba chỉ bò nướng", "hải sản nướng"],
            "max_people": 10,
        },
    ]

    result = filter_restaurants(
        demo_data,
        max_distance=3.0,
        price_level="cheap",
        tag="noodle",
        cravings_text="phở",
        people_count=2,
    )

    # In ra để kiểm tra nhanh
    from pprint import pprint
    pprint(result)

