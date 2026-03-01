"""
Query Processor for parsing natural language queries.

This module parses natural language queries to extract:
1. Intent (cost analysis, optimization, trend analysis, forecast, prevention)
2. Time ranges (relative and absolute dates)
3. Service names (normalized to AWS identifiers)
4. Entities (resource IDs, account IDs)
"""

from typing import List, Tuple, Optional
from datetime import datetime, timedelta, UTC
import re
import logging

from ..utils.types import QueryIntent

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Parse and understand natural language queries."""
    
    # Intent keywords mapping
    INTENT_KEYWORDS = {
        'cost_analysis': ['cost', 'spend', 'spending', 'bill', 'charge', 'expense'],
        'optimization': ['optimize', 'reduce', 'save', 'savings', 'cheaper', 'lower'],
        'trend_analysis': ['trend', 'pattern', 'increase', 'decrease', 'growth'],
        'forecast': ['forecast', 'predict', 'future', 'estimate', 'projection'],
        'prevention': ['prevent', 'stop', 'idle', 'unused', 'waste']
    }
    
    # Service name mappings
    SERVICE_MAPPINGS = {
        'ec2': ['ec2', 'instance', 'instances', 'compute', 'vm', 'virtual machine'],
        'lambda': ['lambda', 'function', 'functions', 'serverless'],
        'dynamodb': ['dynamodb', 'dynamo', 'database', 'nosql'],
        's3': ['s3', 'storage', 'bucket', 'buckets', 'object storage'],
        'rds': ['rds', 'relational', 'mysql', 'postgres', 'postgresql', 'database']
    }
    
    def __init__(self):
        """Initialize query processor."""
        logger.info("QueryProcessor initialized")
    
    def parse_query(self, query: str) -> QueryIntent:
        """
        Parse query and extract intent, entities, and time ranges.
        
        Args:
            query: Natural language query
            
        Returns:
            QueryIntent with extracted information
        """
        query_lower = query.lower()
        
        # Extract intent
        intent_type = self._classify_intent(query_lower)
        
        # Extract time range
        time_range = self.extract_time_range(query_lower)
        
        # Extract services
        services = self.extract_services(query_lower)
        
        # Extract accounts (basic implementation)
        accounts = self._extract_accounts(query_lower)
        
        # Extract entities
        entities = self._extract_entities(query_lower)
        
        logger.debug(f"Parsed query: intent={intent_type}, services={services}, time_range={time_range}")
        
        return QueryIntent(
            intent_type=intent_type,
            services=services,
            time_range=time_range,
            accounts=accounts,
            entities=entities
        )
    
    def extract_time_range(self, query: str) -> Tuple[datetime, datetime]:
        """
        Extract time period from query (e.g., 'last month').
        
        Args:
            query: Natural language query (lowercase)
            
        Returns:
            Tuple of (start_date, end_date)
        """
        now = datetime.now(UTC)
        
        # Last N days
        if match := re.search(r'last (\d+) days?', query):
            days = int(match.group(1))
            return (now - timedelta(days=days), now)
        
        # Last week
        if 'last week' in query:
            return (now - timedelta(days=7), now)
        
        # Last month
        if 'last month' in query:
            return (now - timedelta(days=30), now)
        
        # This week
        if 'this week' in query:
            start_of_week = now - timedelta(days=now.weekday())
            return (start_of_week, now)
        
        # This month
        if 'this month' in query:
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return (start_of_month, now)
        
        # Yesterday
        if 'yesterday' in query:
            yesterday = now - timedelta(days=1)
            return (yesterday.replace(hour=0, minute=0, second=0, microsecond=0),
                    yesterday.replace(hour=23, minute=59, second=59, microsecond=999999))
        
        # Today
        if 'today' in query:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return (today_start, now)
        
        # Default: last 7 days
        return (now - timedelta(days=7), now)
    
    def extract_services(self, query: str) -> List[str]:
        """
        Extract AWS service names from query.
        
        Args:
            query: Natural language query (lowercase)
            
        Returns:
            List of AWS service identifiers
        """
        services = []
        
        for service_id, keywords in self.SERVICE_MAPPINGS.items():
            for keyword in keywords:
                if keyword in query:
                    if service_id not in services:
                        services.append(service_id)
                    break
        
        return services
    
    def normalize_service_names(self, services: List[str]) -> List[str]:
        """
        Map common names to AWS service identifiers.
        
        Args:
            services: List of service names (may be common names)
            
        Returns:
            List of normalized AWS service identifiers
        """
        normalized = []
        
        for service in services:
            service_lower = service.lower()
            
            # Check if already a valid service ID
            if service_lower in self.SERVICE_MAPPINGS:
                normalized.append(service_lower)
                continue
            
            # Map common name to service ID
            for service_id, keywords in self.SERVICE_MAPPINGS.items():
                if service_lower in keywords:
                    if service_id not in normalized:
                        normalized.append(service_id)
                    break
        
        return normalized
    
    def _classify_intent(self, query: str) -> str:
        """
        Classify query intent based on keywords.
        
        Args:
            query: Natural language query (lowercase)
            
        Returns:
            Intent type string
        """
        intent_scores = {}
        
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in query)
            if score > 0:
                intent_scores[intent_type] = score
        
        if not intent_scores:
            return 'cost_analysis'  # Default intent
        
        # Return intent with highest score
        return max(intent_scores.items(), key=lambda x: x[1])[0]
    
    def _extract_accounts(self, query: str) -> List[str]:
        """
        Extract AWS account IDs from query.
        
        Args:
            query: Natural language query (lowercase)
            
        Returns:
            List of account IDs
        """
        # Look for 12-digit account IDs
        account_pattern = r'\b\d{12}\b'
        matches = re.findall(account_pattern, query)
        return matches
    
    def _extract_entities(self, query: str) -> dict:
        """
        Extract entities like resource IDs from query.
        
        Args:
            query: Natural language query (lowercase)
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        
        # Extract instance IDs (i-xxxxxxxxxxxxxxxxx)
        instance_ids = re.findall(r'i-[a-f0-9]{17}', query)
        if instance_ids:
            entities['instance_ids'] = instance_ids
        
        # Extract function names (basic pattern)
        if 'function' in query:
            # Look for quoted strings or capitalized words after "function"
            function_pattern = r'function ["\']?([a-zA-Z0-9_-]+)["\']?'
            function_matches = re.findall(function_pattern, query)
            if function_matches:
                entities['function_names'] = function_matches
        
        return entities
