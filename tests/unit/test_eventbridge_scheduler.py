"""
Unit tests for EventBridge Scheduler

Requirements:
- 1.1: Poll budgets every 5 minutes
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from src.services.eventbridge_scheduler import EventBridgeScheduler


class TestEventBridgeScheduler(unittest.TestCase):
    """Test EventBridge scheduler functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_prevention_engine = Mock()
        self.scheduler = EventBridgeScheduler(self.mock_prevention_engine)
    
    def test_initialization(self):
        """Test scheduler initialization"""
        self.assertIsNotNone(self.scheduler)
        self.assertEqual(self.scheduler.prevention_engine, self.mock_prevention_engine)
    
    def test_parse_scheduled_event(self):
        """Test parsing EventBridge scheduled event"""
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event',
            'time': '2024-01-15T10:00:00Z',
            'resources': ['arn:aws:events:us-east-1:123456789012:rule/cost-prevention'],
            'account': '123456789012',
            'region': 'us-east-1'
        }
        
        result = self.scheduler.parse_event(event)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['event_type'], 'scheduled')
        self.assertEqual(result['time'], '2024-01-15T10:00:00Z')
        self.assertEqual(result['account'], '123456789012')
        self.assertEqual(result['region'], 'us-east-1')
    
    def test_parse_custom_budget_monitoring_event(self):
        """Test parsing custom budget monitoring event"""
        event = {
            'type': 'budget-monitoring',
            'time': '2024-01-15T10:00:00Z',
            'dry_run': True
        }
        
        result = self.scheduler.parse_event(event)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['event_type'], 'budget-monitoring')
        self.assertEqual(result['time'], '2024-01-15T10:00:00Z')
        self.assertTrue(result['dry_run'])
    
    def test_parse_custom_event_without_time(self):
        """Test parsing custom event without time field"""
        event = {
            'type': 'budget-monitoring',
            'dry_run': False
        }
        
        result = self.scheduler.parse_event(event)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['event_type'], 'budget-monitoring')
        self.assertIsNotNone(result['time'])  # Should have default time
        self.assertFalse(result['dry_run'])
    
    def test_parse_invalid_event(self):
        """Test parsing invalid event format"""
        event = {
            'source': 'unknown.source',
            'detail-type': 'Unknown Event'
        }
        
        result = self.scheduler.parse_event(event)
        
        self.assertIsNone(result)
    
    def test_parse_malformed_event(self):
        """Test parsing malformed event"""
        event = None
        
        result = self.scheduler.parse_event(event)
        
        self.assertIsNone(result)
    
    def test_handle_scheduled_event_success(self):
        """Test handling scheduled event successfully"""
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event',
            'time': '2024-01-15T10:00:00Z',
            'resources': ['arn:aws:events:us-east-1:123456789012:rule/cost-prevention']
        }
        
        self.mock_prevention_engine.monitor_budgets.return_value = {
            'status': 'success',
            'budgets_checked': 2,
            'thresholds_breached': 0
        }
        
        result = self.scheduler.handle_scheduled_event(event)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['event_type'], 'scheduled')
        self.assertEqual(result['event_time'], '2024-01-15T10:00:00Z')
        self.assertIn('monitoring_result', result)
        self.mock_prevention_engine.monitor_budgets.assert_called_once()
    
    def test_handle_custom_event_success(self):
        """Test handling custom budget monitoring event"""
        event = {
            'type': 'budget-monitoring',
            'time': '2024-01-15T10:00:00Z'
        }
        
        self.mock_prevention_engine.monitor_budgets.return_value = {
            'status': 'success',
            'budgets_checked': 1
        }
        
        result = self.scheduler.handle_scheduled_event(event)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['event_type'], 'budget-monitoring')
        self.mock_prevention_engine.monitor_budgets.assert_called_once()
    
    def test_handle_invalid_event(self):
        """Test handling invalid event format"""
        event = {
            'source': 'unknown.source'
        }
        
        result = self.scheduler.handle_scheduled_event(event)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.mock_prevention_engine.monitor_budgets.assert_not_called()
    
    def test_handle_event_with_engine_error(self):
        """Test handling event when prevention engine raises error"""
        event = {
            'type': 'budget-monitoring',
            'time': '2024-01-15T10:00:00Z'
        }
        
        self.mock_prevention_engine.monitor_budgets.side_effect = Exception("Engine error")
        
        result = self.scheduler.handle_scheduled_event(event)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertEqual(result['error'], "Engine error")
    
    def test_get_schedule_expression(self):
        """Test getting schedule expression for 5-minute intervals"""
        expression = EventBridgeScheduler.get_schedule_expression()
        
        self.assertEqual(expression, "rate(5 minutes)")
    
    def test_get_schedule_config(self):
        """Test getting complete schedule configuration"""
        config = EventBridgeScheduler.get_schedule_config()
        
        self.assertEqual(config['Name'], 'cost-prevention-budget-monitor')
        self.assertIn('budget monitoring every 5 minutes', config['Description'])
        self.assertEqual(config['ScheduleExpression'], 'rate(5 minutes)')
        self.assertEqual(config['State'], 'ENABLED')
        self.assertIn('Target', config)
        self.assertIn('Arn', config['Target'])
        self.assertIn('RoleArn', config['Target'])
        self.assertIn('Input', config['Target'])
        
        # Verify input is valid JSON
        input_data = json.loads(config['Target']['Input'])
        self.assertEqual(input_data['type'], 'budget-monitoring')
        self.assertEqual(input_data['source'], 'eventbridge-scheduler')
    
    def test_multiple_scheduled_events(self):
        """Test handling multiple scheduled events in sequence"""
        event = {
            'type': 'budget-monitoring',
            'time': '2024-01-15T10:00:00Z'
        }
        
        self.mock_prevention_engine.monitor_budgets.return_value = {
            'status': 'success'
        }
        
        # Handle multiple events
        result1 = self.scheduler.handle_scheduled_event(event)
        result2 = self.scheduler.handle_scheduled_event(event)
        result3 = self.scheduler.handle_scheduled_event(event)
        
        self.assertTrue(result1['success'])
        self.assertTrue(result2['success'])
        self.assertTrue(result3['success'])
        self.assertEqual(self.mock_prevention_engine.monitor_budgets.call_count, 3)


if __name__ == '__main__':
    unittest.main()
