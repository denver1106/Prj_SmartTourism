# core/__init__.py
import importlib
import sys
import os

# ---------------------------------------------------------
# BASE PATH — đảm bảo import core.* hoạt động ở mọi môi trường
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)


# ---------------------------------------------------------
# LAZY MODULE LOADER
# ---------------------------------------------------------
class _LazyModule:
    """
    Cho phép import module khi cần dùng (runtime).
    Tránh lỗi circular import, tăng tốc độ startup.
    """
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None

    def _load(self):
        if self._module is None:
            self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, item):
        module = self._load()
        return getattr(module, item)

    def __repr__(self):
        return f"<LazyModule {self._module_name}>"


# ---------------------------------------------------------
# MODULES ĐANG DÙNG TRONG PROJECT (REAL)
# ---------------------------------------------------------

# Core logic modules
context_utils = _LazyModule("core.context_utils")
data_manager   = _LazyModule("core.data_manager")
search_handler = _LazyModule("core.search_handler")
recommendation = _LazyModule("core.recommendation")
service        = _LazyModule("core.services")
auth_service   = _LazyModule("core.auth_service")   # thêm login Google


def _safe_lazy(module_name: str):
    try:
        importlib.import_module(module_name)
        return _LazyModule(module_name)
    except ModuleNotFoundError:
        return None  # Không tồn tại thì bỏ qua

config   = _safe_lazy("core.config")
database = _safe_lazy("core.database")
models   = _safe_lazy("core.models")
utils    = _safe_lazy("core.utils")
ai_assistant = _safe_lazy("core.ai_assistant")


# ---------------------------------------------------------
# EXPORT API
# ---------------------------------------------------------
__all__ = [
    # Real modules
    "context_utils",
    "data_manager",
    "search_handler",
    "recommendation",
    "service",
    "auth_service",

    # Optional modules (nếu tồn tại)
    "config",
    "database",
    "models",
    "utils",
    "ai_assistant",
]
# core/__init__.py

# Export các module chính để dễ import từ bên ngoài
from core.data_manager import DataManager
from core.auth_service import AuthService
from core.services import SmartTourismService
from core.search_handler import SearchHandler
from core.recommendation import Recommender
from core.context_utils import ContextUtils
from core.manual_filters import filter_restaurants

__all__ = [
    "DataManager",
    "AuthService",
    "SmartTourismService",
    "SearchHandler",
    "Recommender",
    "ContextUtils",
    "filter_restaurants"
]