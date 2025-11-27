# app/user_service.py
from firebase_admin import firestore

# --------- HỒ SƠ CƠ BẢN ---------
def get_user_profile(db, user_id: str):
    """Lấy toàn bộ hồ sơ user từ Firestore."""
    doc_ref = db.collection('users').document(user_id)
    doc = doc_ref.get()

    if not doc.exists:
        # Nếu vì lý do gì đó user chưa có doc (user cũ trước khi bạn sửa code)
        # -> tạo một doc mặc định.
        default_data = {
            "email": "",
            "displayName": "",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "lastActiveAt": firestore.SERVER_TIMESTAMP,
            "preferences": {
                "favoriteTags": [],
                "dislikedTags": [],
                "maxDistanceKm": 5,
                "priceLevels": ["low", "medium", "high"],
                "timePreferences": []
            },
            "favoriteFoodIds": [],
            "favoriteRestaurantIds": []
        }
        doc_ref.set(default_data, merge=True)
        return default_data | {"id": user_id}

    data = doc.to_dict()
    data["id"] = doc.id
    return data


def update_user_basic(db, user_id: str, display_name: str | None = None):
    """Cập nhật thông tin cơ bản (ví dụ: displayName)."""
    update_data = {}
    if display_name is not None:
        update_data["displayName"] = display_name

    if not update_data:
        return

    db.collection('users').document(user_id).set(update_data, merge=True)


# --------- PREFERENCES (SỞ THÍCH) ---------
def update_user_preferences(
    db,
    user_id: str,
    favorite_tags: list[str] | None = None,
    disliked_tags: list[str] | None = None,
    max_distance_km: float | None = None,
    price_levels: list[str] | None = None,
    time_preferences: list[str] | None = None,
):
    """
    Cập nhật block 'preferences' cho user.
    Lưu ý: ở đây mình luôn gửi FULL map preferences xuống để ghi đè,
    nên khi gọi hàm nhớ truyền đủ các field.
    """
    prefs = {}

    if favorite_tags is not None:
        prefs["favoriteTags"] = favorite_tags
    if disliked_tags is not None:
        prefs["dislikedTags"] = disliked_tags
    if max_distance_km is not None:
        prefs["maxDistanceKm"] = max_distance_km
    if price_levels is not None:
        prefs["priceLevels"] = price_levels
    if time_preferences is not None:
        prefs["timePreferences"] = time_preferences

    if not prefs:
        return

    db.collection('users').document(user_id).set(
        {"preferences": prefs},
        merge=True
    )


# --------- YÊU THÍCH (FAVORITES) ---------
def add_favorite_food(db, user_id: str, food_id: str):
    db.collection('users').document(user_id).update({
        "favoriteFoodIds": firestore.ArrayUnion([food_id])
    })


def remove_favorite_food(db, user_id: str, food_id: str):
    db.collection('users').document(user_id).update({
        "favoriteFoodIds": firestore.ArrayRemove([food_id])
    })


def add_favorite_restaurant(db, user_id: str, restaurant_id: str):
    db.collection('users').document(user_id).update({
        "favoriteRestaurantIds": firestore.ArrayUnion([restaurant_id])
    })


def remove_favorite_restaurant(db, user_id: str, restaurant_id: str):
    db.collection('users').document(user_id).update({
        "favoriteRestaurantIds": firestore.ArrayRemove([restaurant_id])
    })


# --------- HISTORY (XEM LỊCH SỬ) – dùng cho trang profile nếu cần ---------
def get_recent_history(db, user_id: str, limit: int = 10):
    """
    Lấy N lịch sử mới nhất cho user (để hiển thị trên trang profile).
    """
    query = (
        db.collection('histories')
        .where('userId', '==', user_id)
        .order_by('timestamp', direction=firestore.Query.DESCENDING)
        .limit(limit)
    )

    docs = query.stream()
    history_items = []
    for doc in docs:
        item = doc.to_dict()
        item["id"] = doc.id
        history_items.append(item)

    return history_items
