"""
EventBridge Scheduler for Automated Cost Prevention

This module handles EventBridge schedule configuration and event processing
for triggering budget monitoring every 5 minutes.

Requirements:
- 1.1: Poll budgets every 5 minutes
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


class EventBridgeScheduler:
    """
    Manages EventBridge schedule configuration and event processing.
    
    This class provides methods to:
    - Parse EventBridge scheduled events
    - Trigger budget monitoring workflows
    - Handle event-driven prevention execution
    """
    
    def __init__(self, prevention_engine):
        """
        Initialize EventBridge scheduler.
        
        Args:
            prevention_engine: PreventionEngine instance to trigger
        """
        self.prevention_engine = prevention_engine
        logger.info("EventBridge scheduler initialized")
    
    def parse_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse EventBridge scheduled event.
        
        Args:
            event: EventBridge event payload
            
        Returns:
            Parsed event data or None if invalid
            
        Requirements:
        - 1.1: Parse scheduled events for budget monitoring
        """
        try:
            # EventBridge scheduled events have specific structure
            if event.get('source') == 'aws.events' and event.get('detail-type') == 'Scheduled Event':
                return {
                    'event_type': 'scheduled',
                    'time': event.get('time'),
                    'resources': event.get('resources', []),
                    'account': event.get('account'),
                    'region': event.get('region')
                }
            
            # Support custom event format for testing
            if event.get('type') == 'budget-monitoring':
                return {
                    'event_type': 'budget-monitoring',
                    'time': event.get('time', datetime.now(UTC).isoformat()),
                    'dry_run': event.get('dry_run', False)
                }
            
            logger.warning(f"Unknown event format: {event.get('source')}, {event.get('detail-type')}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing EventBridge event: {e}")
            return None
    
    def handle_scheduled_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle scheduled EventBridge event and trigger budget monitoring.
        
        Args:
            event: EventBridge event payload
            
        Returns:
            Result of budget monitoring execution
            
        Requirements:
        - 1.1: Trigger budget monitoring every 5 minutes
        """
        try:
            # Parse event
            parsed_event = self.parse_event(event)
            if not parsed_event:
                return {
                    'success': False,
                    'error': 'Invalid event format'
                }
            
            logger.info(f"Processing scheduled event: {parsed_event['event_type']}")
            
            # Trigger budget monitoring workflow
            result = self.prevention_engine.monitor_budgets()
            
            if not isinstance(result, dict): raise ValueError('Monitoring result is unavailable')
            logger.info(f"Budget monitoring completed: {result.get('status')}")
            
            return {
                'success': result.get('success') is True,
                'error': None if result.get('success') is True else result.get('error', 'Monitoring could not complete'),
                'event_type': parsed_event['event_type'],
                'event_time': parsed_event['time'],
                'monitoring_result': result
            }
            
        except Exception as e:
            logger.error(f"Error handling scheduled event: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_schedule_expression() -> str:
        """
        Get EventBridge schedule expression for 5-minute intervals.
        
        Returns:
            Schedule expression string
            
        Requirements:
        - 1.1: Poll budgets every 5 minutes
        """
        return "rate(5 minutes)"
    
    @staticmethod
    def get_schedule_config() -> Dict[str, Any]:
        """
        Get complete EventBridge schedule configuration.
        
        Returns:
            Configuration dictionary for EventBridge schedule
            
        Requirements:
        - 1.1: Configure 5-minute schedule with Lambda target
        """
        return {
            'Name': 'cost-prevention-budget-monitor',
            'Description': 'Trigger budget monitoring every 5 minutes for automated cost prevention',
            'ScheduleExpression': 'rate(5 minutes)',
            'State': 'ENABLED',
            'Target': {
                'Arn': '${LAMBDA_FUNCTION_ARN}',  # To be replaced in infrastructure
                'RoleArn': '${EVENTBRIDGE_ROLE_ARN}',  # To be replaced in infrastructure
                'Input': json.dumps({
                    'type': 'budget-monitoring',
                    'source': 'eventbridge-scheduler'
                })
            }
        }
