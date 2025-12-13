import pymysql
import json
import math
from typing import List, Dict, Any
import traceback

class DataManager:
    def __init__(self, db_connection):
        if db_connection is None:
            raise ValueError("DB Connection Lost")
        self.db = db_connection
        self._cache = {"restaurants": None}

    # ---------------------- UTILITIES ----------------------
    def _safe_float(self, val, default=0.0):
        try:
            return float(val) if val is not None else default
        except:
            return default

    def _parse_json(self, raw_data: Any) -> Any:
        if raw_data is None:
            return []
        if isinstance(raw_data, (dict, list)):
            return raw_data
        if isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except:
                pass
        return []

    def _parse_tags(self, tags_raw: Any) -> List[str]:
        """Chuẩn hóa danh sách tag, loại bỏ tag kỹ thuật rác."""
        if not tags_raw:
            return []

        parsed_list = []
        if isinstance(tags_raw, list):
            parsed_list = tags_raw
        elif isinstance(tags_raw, str):
            clean = tags_raw.strip()
            # Parse JSON nếu cần
            if clean.startswith("{") or clean.startswith("["):
                try:
                    loaded = json.loads(clean)
                    if isinstance(loaded, dict):
                        target_keys = ["cuisine", "diet", "amenity"]
                        parsed_list = [
                            v for k, v in loaded.items()
                            if k in target_keys or (":" not in k and "source" not in k)
                        ]
                    elif isinstance(loaded, list):
                        parsed_list = loaded
                except:
                    pass
            else:
                parsed_list = clean.split(",")

        # Loại bỏ tag rác
        garbage_prefixes = ["addr:", "source:", "phone:", "website:", "ref:", "opening_hours", "u'"]
        final_tags = []
        for t in parsed_list:
            t_str = str(t).lower().strip().replace('"', '').replace("'", "")
            if len(t_str) > 2 and not any(t_str.startswith(p) for p in garbage_prefixes):
                final_tags.append(t_str)

        return list(set(final_tags))

    # ---------------------- MAIN FUNCTIONS ----------------------
    def get_all_restaurants(self, use_cache=True, user_lat=None, user_lon=None):
        """Lấy toàn bộ nhà hàng trong DB, tính khoảng cách nếu có vị trí."""
        try:
            with self.db.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, address, lat, lng, tags, menu, reviews,
                           price_level, rating, description, image_url, province_name
                    FROM restaurants
                """)
                rows = cursor.fetchall()

            results = []
            for r in rows:
                # ✅ FIX: xử lý tên quán bị trống hoặc “Unnamed”
                name = r.get("name")
                if not name or name.strip().lower() in ["unnamed", "unknown", "null", "none", ""]:
                    name = f"Quán #{r['id']}"

                item = {
                    "id": r["id"],
                    "name": name,
                    "address": r.get("address") or "",
                    "lat": self._safe_float(r["lat"]),
                    "lng": self._safe_float(r["lng"]),
                    "tags": self._parse_tags(r.get("tags")),
                    "menu": self._parse_json(r.get("menu")),
                    "reviews": self._parse_json(r.get("reviews")),
                    "price_level": r.get("price_level") or "",
                    "rating": self._safe_float(r.get("rating"), 3.0),
                    "description": r.get("description") or "",
                    "image_url": r.get("image_url") or "",
                    "province_name": r.get("province_name") or "",
                    "distance_km": 0.0
                }

                if user_lat and user_lon and item["lat"]:
                    item["distance_km"] = self._haversine(user_lat, user_lon, item["lat"], item["lng"])
                elif user_lat == 0:
                    item["distance_km"] = 999.0

                results.append(item)
            return results

        except Exception as e:
            print(f"❌ DM Error: {e}")
            return []

    def get_restaurant_name(self, rid):
        """Truy xuất tên quán an toàn."""
        try:
            with self.db.cursor() as c:
                c.execute("SELECT name FROM restaurants WHERE id=%s", (rid,))
                res = c.fetchone()
            return res["name"] if res else f"Restaurant #{rid}"
        except Exception as e:
            print(f"[DataManager] Error fetching restaurant name for id={rid}: {e}")
            return f"Restaurant #{rid}"

    # ---------------------- USER HISTORY ----------------------

    def get_user_history(self, user_id, quiet=False):
        """
        Debug mode: xác định ai gọi hàm này nhiều lần.
        """
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT restaurant_id, action, created_at
                    FROM user_history
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
                rows = cur.fetchall()

            if not quiet:
                print(f"📜 [get_user_history] found {len(rows)} records for user_id={user_id}")
                print("   ↪ Stack trace (debug who called this):")
                traceback.print_stack(limit=5)
                print("--------------------------------------------------")

            return rows  # ✅ Quan trọng: trả về danh sách record

        except Exception as e:
            print(f"❌ get_user_history() error: {e}")
            return []


    def get_user_history_full(self, user_id):
        try:
            with self.db.cursor() as cur:
                sql = """
                    SELECT r.id, r.name, r.address, r.image_url, r.rating,
                           MAX(h.created_at) AS latest_viewed_at,
                           SUBSTRING_INDEX(GROUP_CONCAT(h.action ORDER BY h.created_at DESC), ',', 1) AS last_action
                    FROM user_history h
                    JOIN restaurants r ON h.restaurant_id = r.id
                    WHERE h.user_id = %s AND h.action IN ('view', 'visit')
                    GROUP BY r.id, r.name, r.address, r.image_url, r.rating
                    ORDER BY latest_viewed_at DESC
                    LIMIT 20
                """
                cur.execute(sql, (user_id,))
                rows = cur.fetchall()

            results = []
            for r in rows:
                name = r["name"] or f"Quán #{r['id']}"
                if name.lower() in ["unnamed", "unknown"]:
                    name = f"Quán #{r['id']}"
                results.append({
                    "id": r["id"],
                    "name": name,
                    "address": r.get("address", ""),
                    "image_url": r.get("image_url", ""),
                    "rating": r.get("rating", 0),
                    "created_at": r["latest_viewed_at"],
                    "last_action": r["last_action"]
                })
            return results
        except Exception as e:
            print(f"History Error: {e}")
            return []

    # ---------------------- USER PREFS ----------------------
    def get_user_preferences(self, user_id) -> Dict[str, Any]:
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT liked_tags, disliked_tags 
                    FROM user_preferences 
                    WHERE user_id = %s 
                    ORDER BY id DESC LIMIT 1
                """, (user_id,))
                row = cur.fetchone()

            if row:
                likes = self._parse_json(row.get("liked_tags"))
                dislikes = self._parse_json(row.get("disliked_tags"))
                if not isinstance(likes, list): likes = []
                if not isinstance(dislikes, list): dislikes = []
                return {
                    "like_tags": [str(t).lower().strip() for t in likes],
                    "dislike_tags": [str(t).lower().strip() for t in dislikes]
                }
        except Exception as e:
            print(f"❌ Get Prefs Error: {e}")

        return {"like_tags": [], "dislike_tags": []}

    def save_user_preferences(self, user_id, liked_list, disliked_list):
        try:
            val_like = json.dumps(liked_list, ensure_ascii=False)
            val_dislike = json.dumps(disliked_list, ensure_ascii=False)

            with self.db.cursor() as cur:
                cur.execute("SELECT id FROM user_preferences WHERE user_id = %s", (user_id,))
                exists = cur.fetchone()
                if exists:
                    cur.execute("""
                        UPDATE user_preferences
                        SET liked_tags=%s, disliked_tags=%s
                        WHERE user_id=%s
                    """, (val_like, val_dislike, user_id))
                else:
                    cur.execute("""
                        INSERT INTO user_preferences (user_id, liked_tags, disliked_tags)
                        VALUES (%s, %s, %s)
                    """, (user_id, val_like, val_dislike))
            self.db.commit()
            return True
        except Exception as e:
            print("Save Pref Error:", e)
            self.db.rollback()
            return False

    def update_user_history(self, user_id, rid, action='view'):
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_history (user_id, restaurant_id, action, created_at)
                    VALUES (%s, %s, %s, NOW())
                """, (user_id, rid, action))
            self.db.commit()
        except:
            self.db.rollback()

    # ---------------------- MATH ----------------------
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        if not lat1 or not lon1 or not lat2 or not lon2:
            return 9999
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))
