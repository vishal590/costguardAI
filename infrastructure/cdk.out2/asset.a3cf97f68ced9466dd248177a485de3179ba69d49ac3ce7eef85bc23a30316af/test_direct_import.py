#!/usr/bin/env python
"""Direct test of ai_ml_handler imports"""

# Test each import individually
print("Testing imports...")

try:
    from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker
    print("✓ GPUCostTracker")
except Exception as e:
    print(f"✗ GPUCostTracker: {e}")

try:
    from src.services.ai_ml.workload_classifier import WorkloadClassifier
    print("✓ WorkloadClassifier")
except Exception as e:
    print(f"✗ WorkloadClassifier: {e}")

try:
    from src.services.dynamodb import get_dynamodb_client
    print("✓ get_dynamodb_client")
except Exception as e:
    print(f"✗ get_dynamodb_client: {e}")

try:
    from src.utils.error_handler import format_error
    print("✓ format_error")
except Exception as e:
    print(f"✗ format_error: {e}")

try:
    from src.utils.date_utils import validate_date_format, validate_date_range
    print("✓ date_utils")
except Exception as e:
    print(f"✗ date_utils: {e}")

# Now try importing the whole module
print("\nTrying to import src.ai_ml_handler...")
try:
    import src.ai_ml_handler as handler_module
    print(f"Module imported: {handler_module}")
    print(f"Module file: {handler_module.__file__}")
    print(f"Module attributes: {[attr for attr in dir(handler_module) if not attr.startswith('_')]}")
    
    if hasattr(handler_module, 'handler'):
        print("✓ handler function exists")
    else:
        print("✗ handler function NOT found")
        
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
