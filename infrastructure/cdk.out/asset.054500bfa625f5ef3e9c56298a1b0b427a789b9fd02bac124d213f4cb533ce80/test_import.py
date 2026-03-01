import traceback
import sys

try:
    import src.ai_ml_handler
    print("Module attributes:", dir(src.ai_ml_handler))
    if hasattr(src.ai_ml_handler, 'handler'):
        print("handler function found!")
    else:
        print("handler function NOT found")
except Exception as e:
    print("Error importing:")
    traceback.print_exc()
