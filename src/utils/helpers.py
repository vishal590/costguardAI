"""
Helper utility functions.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.utils.types import CostRecord


def calculate_ttl(days: int) -> int:
    """
    Calculate Unix timestamp for TTL (days from now).
    
    Args:
        days: Number of days from now
        
    Returns:
        Unix timestamp
    """
    future_date = datetime.now() + timedelta(days=days)
    return int(future_date.timestamp())


# Cost Explorer returns long names (e.g. "Amazon Elastic Compute Cloud - Compute").
# Map to short names so Phase 1 query ?service=ec2 and Phase 2 forecast by service match.
COST_EXPLORER_TO_SHORT_SERVICE = {
    'ec2': ['elastic compute', 'ec2', 'amazon ec2', 'compute cloud'],
    'lambda': ['lambda', 'aws lambda'],
    'dynamodb': ['dynamodb', 'amazon dynamodb'],
    's3': ['s3', 'simple storage', 'amazon s3'],
    'rds': ['rds', 'relational database', 'amazon rds'],
}


def cost_explorer_service_to_short(long_name: str) -> str:
    """
    Map Cost Explorer SERVICE dimension value to short name (ec2, lambda, dynamodb, s3, rds).
    If no match, returns normalized long name (lowercase, spaces to hyphens) for storage.
    """
    if not long_name:
        return 'unknown'
    lower = long_name.lower()
    for short, keywords in COST_EXPLORER_TO_SHORT_SERVICE.items():
        if any(kw in lower for kw in keywords):
            return short
    return normalize_service_name(long_name)


def normalize_service_name(service: str) -> str:
    """
    Normalize service name for sort key (lowercase, replace spaces with hyphens).
    
    Args:
        service: AWS service name
        
    Returns:
        Normalized service name
    """
    return service.lower().replace(' ', '-')


def calculate_cost_summary(records: List[CostRecord]) -> Dict[str, Any]:
    """
    Calculate total cost, service count, and record count.
    
    Args:
        records: List of cost records
        
    Returns:
        Dictionary with totalCost, serviceCount, recordCount
    """
    if not records:
        return {
            'totalCost': 0.0,
            'serviceCount': 0,
            'recordCount': 0
        }
    
    total_cost = sum(record.blended_cost for record in records)
    unique_services = set(record.service for record in records)
    
    return {
        'totalCost': round(total_cost, 2),
        'serviceCount': len(unique_services),
        'recordCount': len(records)
    }
