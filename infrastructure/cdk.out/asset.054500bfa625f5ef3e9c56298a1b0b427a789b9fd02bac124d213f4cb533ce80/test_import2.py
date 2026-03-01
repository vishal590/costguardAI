import sys
import importlib.util

spec = importlib.util.spec_from_file_location("ai_ml_handler", "src/ai_ml_handler.py")
module = importlib.util.module_from_spec(spec)

try:
    spec.loader.exec_module(module)
    print("Module loaded successfully")
    print("Module attributes:", dir(module))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
