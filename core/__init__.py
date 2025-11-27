# core/__init__.py
import importlib

# --- Lazy loader function ---
class _LazyModule:
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None

    def __getattr__(self, item):
        if self._module is None:
            # import bằng tên đầy đủ
            self._module = importlib.import_module(self._module_name)
        return getattr(self._module, item)


# --- Core modules (lazy) ---
config = _LazyModule("core.config")               # nếu có
database = _LazyModule("core.database")           # nếu có
models = _LazyModule("core.models")               # nếu có
utils = _LazyModule("core.utils")                 # helper functions
ai_assistant = _LazyModule("core.ai_assistant")   # SmartAssistant AI module

# Các module mới/đã sửa
context_utils = _LazyModule("core.context_utils")
data_manager = _LazyModule("core.data_manager")
search_handler = _LazyModule("core.search_handler")
recommendation = _LazyModule("core.recommendation")
service = _LazyModule("core.service")

__all__ = [
    "config",
    "database",
    "models",
    "utils",
    "ai_assistant",
    "context_utils",
    "data_manager",
    "search_handler",
    "recommendation",
    "service",
]
