print("Step 1: Import json")
import json
print("Step 2: Import logging")
import logging
print("Step 3: Import typing")
from typing import Dict, Any
print("Step 4: Import datetime")
from datetime import datetime, timedelta, UTC
print("Step 5: Import GPU tracker")
from src.services.ai_ml.gpu_cost_tracker import GPUCostTracker
print("Step 6: Import workload classifier")
from src.services.ai_ml.workload_classifier import WorkloadClassifier
print("Step 7: Import cost per inference")
from src.services.ai_ml.cost_per_inference_calculator import CostPerInferenceCalculator
print("Step 8: Import cost per training")
from src.services.ai_ml.cost_per_training_calculator import CostPerTrainingCalculator
print("Step 9: Import spot recommender")
from src.services.ai_ml.spot_instance_recommender import SpotInstanceRecommender
print("Step 10: Import sagemaker tracker")
from src.services.ai_ml.sagemaker_cost_tracker import SageMakerCostTracker
print("Step 11: Import bedrock tracker")
from src.services.ai_ml.bedrock_cost_tracker import BedrockCostTracker
print("Step 12: Import dynamodb")
from src.services.dynamodb import get_dynamodb_client
print("Step 13: Import error handler")
from src.utils.error_handler import format_error
print("Step 14: Import date utils")
from src.utils.date_utils import validate_date_format, validate_date_range
print("All imports successful!")
