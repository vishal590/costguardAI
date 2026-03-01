#!/usr/bin/env python
"""Debug script to test ai_ml_handler imports."""

print("Step 1: Basic imports...")
import json
import logging
from typing import Dict, Any
from datetime import datetime, timedelta, UTC
print("✓ Basic imports OK")

print("\nStep 2: AI/ML service imports...")
from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker
print("✓ GPUCostTracker OK")

from src.services.ai_ml.workload_classifier import WorkloadClassifier, WorkloadClassification
print("✓ WorkloadClassifier OK")

from src.services.ai_ml.cost_per_inference_calculator import CostPerInferenceCalculator
print("✓ CostPerInferenceCalculator OK")

from src.services.ai_ml.cost_per_training_calculator import CostPerTrainingCalculator
print("✓ CostPerTrainingCalculator OK")

from src.services.ai_ml.spot_instance_recommender import SpotInstanceRecommender
print("✓ SpotInstanceRecommender OK")

from src.services.ai_ml.sagemaker_cost_tracker import SageMakerCostTracker
print("✓ SageMakerCostTracker OK")

from src.services.ai_ml.bedrock_cost_tracker import BedrockCostTracker
print("✓ BedrockCostTracker OK")

print("\nStep 3: Utility imports...")
from src.services.dynamodb import get_dynamodb_client
print("✓ get_dynamodb_client OK")

from src.utils.error_handler import format_error
print("✓ format_error OK")

from src.utils.date_utils import validate_date_format, validate_date_range
print("✓ date_utils OK")

print("\nStep 4: Import ai_ml_handler module...")
import src.ai_ml_handler
print(f"✓ Module imported: {src.ai_ml_handler}")
print(f"  Module attributes: {[x for x in dir(src.ai_ml_handler) if not x.startswith('_')]}")

print("\nStep 5: Try to import handler function...")
try:
    from src.ai_ml_handler import handler
    print(f"✓ handler imported successfully: {handler}")
except ImportError as e:
    print(f"✗ Failed to import handler: {e}")
    print(f"  Module file: {src.ai_ml_handler.__file__}")
    print(f"  Module dict keys: {list(src.ai_ml_handler.__dict__.keys())[:10]}")

print("\nDone!")
