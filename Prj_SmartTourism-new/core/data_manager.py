import pymysql
import json
import math
from typing import List, Dict, Any


class DataManager:
    def __init__(self, db_connection):
        if db_connection is None:
            raise ValueError("DB Connection Lost")
        self.db = db_connection
        self._cache = {"restaurants": None}

    # =============== CÁC HÀM TIỆN ÍCH NỘI BỘ ===============

    def _safe_float(self, val, default: float = 0.0) -> float:
        try:
            return float(val) if val is not None else default
        except Exception:
            return default

    def _parse_json(self, raw_data: Any) -> Any:
        """Chuyển dữ liệu JSON/text sang object Python (list/dict)."""
        if raw_data is None:
            return []
        if isinstance(raw_data, (dict, list)):
            return raw_data
        if isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except Exception:
                pass
        return []

    def _parse_tags(self, tags_raw: Any) -> List[str]:
        """
        Làm sạch tag, lọc bỏ các tag kỹ thuật rác (addr, source, phone...).
        Input có thể là:
        - list Python
        - JSON string
        - chuỗi "pho, bun, com"
        """
        if not tags_raw:
            return []

        # Chuyển đổi về List Python
        parsed_list: List[Any] = []
        if isinstance(tags_raw, list):
            parsed_list = tags_raw
        elif isinstance(tags_raw, str):
            clean = tags_raw.strip()
            # Xử lý nếu là JSON String
            if clean.startswith("{") or clean.startswith("["):
                try:
                    loaded = json.loads(clean)
                    # Nếu là Dict (OSM tags), chỉ lấy giá trị cuisine / diet / amenity
                    if isinstance(loaded, dict):
                        target_keys = ["cuisine", "diet", "amenity"]
                        parsed_list = [
                            v
                            for k, v in loaded.items()
                            if k in target_keys
                            or (":" not in k and "source" not in k)
                        ]
                    elif isinstance(loaded, list):
                        parsed_list = loaded
                except Exception:
                    pass
            else:
                # Nếu là chuỗi "pho, bun"
                parsed_list = clean.split(",")

        # Lọc lần cuối: loại bỏ tag rác
        final_tags: List[str] = []
        garbage_prefixes = [
            "addr:",
            "source:",
            "phone:",
            "website:",
            "ref:",
            "opening_hours",
            "u'",
            "'",
        ]

        for t in parsed_list:
            t_str = str(t).lower().strip().replace('"', "").replace("'", "")
            # Chỉ lấy tag hợp lệ (không chứa ký tự lạ, không phải tag kỹ thuật)
            if len(t_str) > 2 and not any(
                t_str.startswith(p) for p in garbage_prefixes
            ):
                final_tags.append(t_str)

        # Loại trùng
        return list(set(final_tags))

    def _build_restaurant_item(
        self, r: Dict[str, Any], user_lat: float | None = None, user_lon: float | None = None
    ) -> Dict[str, Any]:
        """
        Dùng chung để build 1 object quán ăn.
        Giúp thống nhất cấu trúc giữa list (Result Page) và detail (Detail Page).
        """
        item: Dict[str, Any] = {
            "id": r["id"],
            "name": r.get("name") or "Quán chưa đặt tên",
            "address": r.get("address") or "",
            "lat": self._safe_float(r.get("lat")),
            "lng": self._safe_float(r.get("lng")),
            "tags": self._parse_tags(r.get("tags")),
            "menu": self._parse_json(r.get("menu")),
            "reviews": self._parse_json(r.get("reviews")),
            "price_level": r.get("price_level") or "",
            "rating": self._safe_float(r.get("rating"), 3.0),
            "description": r.get("description") or "",
            "image_url": r.get("image_url") or "",
            "distance_km": 0.0,
        }

        # Tính khoảng cách nếu có vị trí người dùng
        if user_lat is not None and user_lon is not None and item["lat"]:
            item["distance_km"] = self._haversine(
                user_lat, user_lon, item["lat"], item["lng"]
            )
        elif user_lat == 0:
            # Trick: nếu truyền user_lat=0 -> gán khoảng cách lớn, dùng cho mode "không có vị trí"
            item["distance_km"] = 999.0

        return item

    # =============== RESTAURANTS ===============

    def get_all_restaurants(self, use_cache=True, user_lat=None, user_lon=None):
        """
        Lấy toàn bộ danh sách quán (dùng cho Result Page, auto-filter, gợi ý...).
        Kết quả: list các dict quán ăn, mỗi dict có cùng cấu trúc với Detail Page.
        """
        try:
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, address, lat, lng, tags, menu, reviews,
                           price_level, rating, description, image_url
                    FROM restaurants
                """
                )
                rows = cursor.fetchall()

            results: List[Dict[str, Any]] = []
            for r in rows:
                results.append(
                    self._build_restaurant_item(
                        r, user_lat=user_lat, user_lon=user_lon
                    )
                )
            return results
        except Exception as e:
            print(f"❌ DM Error (get_all_restaurants): {e}")
            return []

    def get_restaurant_by_id(
        self, restaurant_id: int, user_lat: float | None = None, user_lon: float | None = None
    ) -> Dict[str, Any] | None:
        """
        Lấy thông tin CHI TIẾT 1 quán theo id.
        Dùng cho Result - Detail Page.
        """
        try:
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, address, lat, lng, tags, menu, reviews,
                           price_level, rating, description, image_url
                    FROM restaurants
                    WHERE id = %s
                """,
                    (restaurant_id,),
                )
                row = cursor.fetchone()

            if not row:
                return None

            return self._build_restaurant_item(
                row, user_lat=user_lat, user_lon=user_lon
            )
        except Exception as e:
            print(f"❌ get_restaurant_by_id Error: {e}")
            return None

    def get_restaurants_near_user(self, lat, lng, radius_km=20):
        """
        Lấy các quán trong bán kính radius_km (km) tính từ vị trí người dùng.
        """
        all_r = self.get_all_restaurants(
            use_cache=True, user_lat=lat, user_lon=lng
        )
        return [r for r in all_r if r["distance_km"] <= radius_km]

    # =============== USER HISTORY & PREFERENCES ===============

    def get_user_history_full(self, user_id):
        """
        Lấy lịch sử quán đã xem của user, JOIN sang bảng restaurants để có thông tin quán.
        """
        try:
            with self.db.cursor() as cur:
                # Dùng DISTINCT để tránh 1 quán hiện 10 lần nếu user bấm 10 lần
                sql = """
                    SELECT DISTINCT r.id, r.name, r.address, r.image_url, 
                                    r.lat, r.lng, r.rating, r.price_level
                    FROM user_history h
                    JOIN restaurants r ON h.restaurant_id = r.id
                    WHERE h.user_id = %s
                    ORDER BY h.created_at DESC
                    LIMIT 20
                """
                cur.execute(sql, (user_id,))
                rows = cur.fetchall()

            results = []
            for r in rows:
                results.append(
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "address": r.get("address", ""),
                        "image_url": r.get("image_url", ""),
                        "rating": r.get("rating", 0),
                        "price": r.get("price_level", ""),
                    }
                )
            return results
        except Exception as e:
            print(f"History Error: {e}")
            return []

    def get_user_preferences(self, user_id) -> Dict[str, Any]:
        """
        Lấy sở thích ăn uống của user (tags like/dislike) từ bảng user_preferences.
        """
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT like_tags, dislike_tags FROM user_preferences WHERE user_id=%s",
                    (user_id,),
                )
                row = cur.fetchone()
            if row:
                return {
                    "like_tags": self._parse_json(row.get("like_tags")),
                    "dislike_tags": self._parse_json(
                        row.get("dislike_tags")
                    ),  # Lấy thêm dislike
                }
        except Exception:
            pass
        return {"like_tags": [], "dislike_tags": []}

    def save_user_preferences(self, user_id, liked_list, disliked_list):
        """
        Lưu / cập nhật sở thích (like & dislike tags) của user.
        """
        try:
            with self.db.cursor() as cur:
                val_like = json.dumps(liked_list)
                val_dislike = json.dumps(disliked_list)

                sql = """
                    INSERT INTO user_preferences (user_id, like_tags, dislike_tags) 
                    VALUES (%s, %s, %s) 
                    ON DUPLICATE KEY UPDATE 
                        like_tags = VALUES(like_tags),
                        dislike_tags = VALUES(dislike_tags)
                """
                # Chú ý: Database phải có cột 'dislike_tags' (hoặc 'disliked_tags' nếu bạn đặt tên khác)
                cur.execute(sql, (user_id, val_like, val_dislike))
            self.db.commit()
            return True
        except Exception as e:
            print("Save Pref Error:", e)
            self.db.rollback()
            return False

    def update_user_history(self, user_id, rid, action: str = "view"):
        """
        Cập nhật lịch sử khi user xem / tương tác với 1 quán.
        """
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_history (user_id, restaurant_id, action, created_at) 
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (user_id, rid, action),
                )
            self.db.commit()
        except Exception:
            self.db.rollback()

    # =============== HÀM TÍNH TOÁN ===============

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """
        Tính khoảng cách 2 điểm (lat, lon) trên quả đất (km).
        Dùng công thức Haversine.
        """
        if not lat1 or not lon1 or not lat2 or not lon2:
            return 9999
        R = 6371  # bán kính trái đất (km)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))
