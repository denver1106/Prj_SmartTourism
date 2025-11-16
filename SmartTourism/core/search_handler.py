# core/search_handler.py
from typing import Dict, Any

class SearchHandler:

    def parse(self, text_query: str) -> Dict[str, Any]:
        if not text_query:
            return {}

        q = text_query.strip().lower()

        # heuristic very simple:
        if any(tok in q for tok in ["ăn", "món", "thức ăn", "phở", "bún", "cơm", "pizza", "mỳ"]):
            return {"type": "food", "q": q}
        if any(tok in q for tok in ["tỉnh", "thành phố", "địa điểm", "ở", "near", "gần"]):
            return {"type": "place", "q": q}
        # default -> intent / mood
        return {"type": "intent", "q": q}
