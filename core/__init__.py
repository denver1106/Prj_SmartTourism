import importlib

# --- Lazy loader function ---
class _LazyModule:
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None

    def __getattr__(self, item):
        if self._module is None:
            # Import module khi cần thiết (runtime)
            self._module = importlib.import_module(self._module_name)
        return getattr(self._module, item)


# --- Core modules (lazy) ---
# Các module này chưa tạo, cứ để đó khi nào dùng thì tạo file
config = _LazyModule("core.config")               
database = _LazyModule("core.database")           
models = _LazyModule("core.models")               
utils = _LazyModule("core.utils")                 
ai_assistant = _LazyModule("core.ai_assistant")   

# Các module đã hoàn thiện trong dự án
context_utils = _LazyModule("core.context_utils")
data_manager = _LazyModule("core.data_manager")
search_handler = _LazyModule("core.search_handler")
recommendation = _LazyModule("core.recommendation")

# Lưu ý: File thực tế là 'services.py', mình map biến 'service' vào đó
service = _LazyModule("core.services")

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