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
