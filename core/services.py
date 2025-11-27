from core.data_manager import DataManager
from core.context_utils import ContextUtils
from core.recommender import Recommender

class SmartTourismService:
    def __init__(self, weather_api_key: str):
        self.dm = DataManager()
        self.context_utils = ContextUtils(weather_api_key=weather_api_key)

    def process_user_input(self, user_id, user_lat, user_lon):
        # 1. Build context
        context = self.context_utils.get_full_context(user_lat, user_lon)

        # 2. Recommend
        recommender = Recommender(
            user_id=user_id,
            user_lat=user_lat,
            user_lon=user_lon,
            context=context,
            data_manager=self.dm
        )
        result = recommender.generate(top_n=10)

        # 3. Update history
        if result:
            first_food = result[0].get("foods", [None])[0]
            if first_food:
                self.dm.update_user_history(user_id, first_food)

        return {
            "context": context,
            "recommendations": result
        }
