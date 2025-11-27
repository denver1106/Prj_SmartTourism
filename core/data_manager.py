# core/data_manager.py
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import exceptions as gcloud_exceptions
from typing import List, Dict, Optional, Any

class DataManager:
    """
    Wrapper đơn giản cho Firestore + cache local.
    Mong rằng collection 'restaurants' có document fields:
      - id (doc.id)
      - name, lat (float), lon (float)
      - tags (list of str)
      - foods (list of str)  <-- danh sách tên món (chuẩn hoá)
      - open_hours (optional)
    """
    def __init__(self, cred_path: str = "firebase_key.json", use_app_name: Optional[str] = None):
        # init firebase app nếu chưa có
        try:
            self.app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(cred_path)
            self.app = firebase_admin.initialize_app(cred, name=use_app_name)

        self.db = firestore.client()
        self._cache = {
            "restaurants": None,
            "foods": None,
            "places": None
        }

    # ---------------- basic loaders ----------------
    def get_all_restaurants(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        if use_cache and self._cache["restaurants"] is not None:
            return self._cache["restaurants"]

        try:
            ref = self.db.collection("restaurants")
            docs = ref.stream()
            restaurants = []
            for doc in docs:
                item = doc.to_dict() or {}
                item["id"] = doc.id
                # đảm bảo tên trường lat/lon chuẩn và kiểu float nếu có
                if "lat" in item:
                    try:
                        item["lat"] = float(item["lat"])
                    except Exception:
                        item["lat"] = None
                if "lon" in item:
                    try:
                        item["lon"] = float(item["lon"])
                    except Exception:
                        item["lon"] = None
                # chuẩn hoá foods -> list of strings
                foods = item.get("foods", [])
                if isinstance(foods, dict):
                    # nếu lưu dạng dict id -> obj
                    foods = list(foods.keys())
                item["foods"] = [str(f).lower() for f in (foods or [])]
                item["tags"] = [str(t).lower() for t in item.get("tags", [])]
                restaurants.append(item)

            self._cache["restaurants"] = restaurants
            return restaurants

        except Exception as e:
            print("ERROR get_all_restaurants:", e)
            return []

    def get_all_foods(self, use_cache: bool = True) -> Dict[str, Dict]:
        if use_cache and self._cache["foods"] is not None:
            return self._cache["foods"]

        try:
            ref = self.db.collection("foods")
            docs = ref.stream()
            foods = {}
            for doc in docs:
                data = doc.to_dict() or {}
                foods[doc.id] = data
            self._cache["foods"] = foods
            return foods
        except Exception as e:
            print("ERROR get_all_foods:", e)
            return {}

    def _load_places(self) -> Dict[str, Dict]:
        if self._cache["places"] is not None:
            return self._cache["places"]

        try:
            ref = self.db.collection("places")
            docs = ref.stream()
            places = {doc.id: doc.to_dict() or {} for doc in docs}
            self._cache["places"] = places
            return places
        except Exception as e:
            print("ERROR loading places:", e)
            return {}

    def get_specialties_by_place(self, place_name: str) -> List[str]:
        try:
            ref = self.db.collection("places").document(place_name)
            doc = ref.get()
            if doc.exists:
                return [str(s).lower() for s in doc.to_dict().get("specialties", [])]
            return []
        except Exception as e:
            print("ERROR get_specialties_by_place:", e)
            return []

    # ---------------- user helpers ----------------
    def get_user_history(self, user_id: str) -> List[str]:
        try:
            doc = self.db.collection("users").document(user_id).get()
            if doc.exists:
                return [str(x).lower() for x in doc.to_dict().get("history", [])]
            return []
        except Exception as e:
            print("ERROR get_user_history:", e)
            return []

    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        try:
            doc = self.db.collection("users").document(user_id).get()
            if doc.exists:
                prefs = doc.to_dict().get("preferences", {}) or {}
                # chuẩn hoá tag list
                if "like_tags" in prefs:
                    prefs["like_tags"] = [str(t).lower() for t in prefs.get("like_tags", [])]
                if "dislike_tags" in prefs:
                    prefs["dislike_tags"] = [str(t).lower() for t in prefs.get("dislike_tags", [])]
                return prefs
            return {}
        except Exception as e:
            print("ERROR get_user_preferences:", e)
            return {}

    def update_user_history(self, user_id: str, new_food: str):
        new_food = str(new_food).lower()
        try:
            ref = self.db.collection("users").document(user_id)
            history = self.get_user_history(user_id)
            if new_food not in history:
                history.append(new_food)
                ref.set({"history": history}, merge=True)
        except gcloud_exceptions.NotFound:
            ref.set({"history": [new_food]})
        except Exception as e:
            print("ERROR update_user_history:", e)
