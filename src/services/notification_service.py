"""
Notification Service for sending SNS notifications.

Supports:
- Warning notifications at 80% budget threshold
- Action notifications for automated actions
- Error notifications with context
- Multi-topic support for different notification types
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)


def _opportunity(value):
    return 'Unavailable' if value is None else f'${value:.2f}/month (unverified estimate)'


class NotificationService:
    """Send notifications via SNS for cost prevention events."""
    
    def __init__(self, sns_client, config: Optional[Any] = None):
        """
        Initialize notification service.
        
        Args:
            sns_client: boto3 SNS client
            config: NotificationConfig with topic ARNs (optional)
        """
        self.sns = sns_client
        self.config = config
        
        # Topic ARNs from config or None
        self.warning_topic_arn = config.warning_topic_arn if config else None
        self.action_topic_arn = config.action_topic_arn if config else None
        self.error_topic_arn = config.error_topic_arn if config else None
    
    def send_warning(self, budget_status: Any):
        """
        Send warning notification at 80% threshold.
        
        Args:
            budget_status: BudgetStatus object
        """
        if not self.warning_topic_arn:
            logger.warning("No warning topic ARN configured")
            return
        
        subject = f"Cost Alert: Budget {budget_status.budget_name} at {budget_status.utilization_percent:.1f}%"
        
        message = f"""
AWS Cost Prevention - Budget Warning

Budget: {budget_status.budget_name}
Utilization: {budget_status.utilization_percent:.1f}%
Actual Spend: {budget_status.currency} {budget_status.actual_spend:.2f}
Budget Limit: {budget_status.currency} {budget_status.limit:.2f}
Forecasted Spend: {budget_status.currency} {format(budget_status.forecasted_spend, '.2f') if budget_status.forecasted_spend is not None else 'Unavailable'}
Time Period: {budget_status.time_period}

This budget has reached the warning threshold (80%). 
Automated cost prevention actions will trigger at 90%.

Timestamp: {datetime.now(UTC).isoformat()}
"""
        
        try:
            self.sns.publish(
                TopicArn=self.warning_topic_arn,
                Subject=subject,
                Message=message
            )
            logger.info(f"Sent warning notification for budget {budget_status.budget_name}")
        except Exception as e:
            logger.error(f"Failed to send warning notification: {e}")
    
    def send_action_notification(self, actions: List[Any]):
        """
        Send notification about automated actions.
        
        Args:
            actions: List of ActionResult objects
        """
        if not self.action_topic_arn:
            logger.warning("No action topic ARN configured")
            return
        
        # Calculate total savings
        values = [action.estimated_savings for action in actions]
        total_savings = sum(values) if values and all(value is not None for value in values) else None
        successful_actions = [a for a in actions if a.success]
        failed_actions = [a for a in actions if not a.success]
        
        subject = f"Cost Prevention: {len(successful_actions)} Requests Accepted"
        
        message = f"""
AWS Cost Prevention - Resource Requests Submitted

Total Actions: {len(actions)}
Accepted: {len(successful_actions)}
Failed: {len(failed_actions)}
Monetary opportunity: {_opportunity(total_savings)}

Accepted Requests:
"""
        
        for action in successful_actions:
            message += f"\n- {action.action} {action.resource_id} ({_opportunity(action.estimated_savings)})"
        
        if failed_actions:
            message += "\n\nFailed Actions:"
            for action in failed_actions:
                message += f"\n- {action.action} {action.resource_id}: {action.error_message}"
        
        message += f"\n\nTimestamp: {datetime.now(UTC).isoformat()}"
        message += "\n\nRollback requires a supported operation, valid snapshot and original action timestamp."
        
        try:
            self.sns.publish(
                TopicArn=self.action_topic_arn,
                Subject=subject,
                Message=message
            )
            logger.info(f"Sent action notification for {len(actions)} actions")
        except Exception as e:
            logger.error(f"Failed to send action notification: {e}")
    
    def send_error_notification(self, error: Exception, context: Dict[str, Any]):
        """
        Send error notification with context.
        
        Args:
            error: Exception that occurred
            context: Additional context about the error
        """
        if not self.error_topic_arn:
            logger.warning("No error topic ARN configured")
            return
        
        subject = f"Cost Prevention Error: {type(error).__name__}"
        
        message = f"""
AWS Cost Prevention - Error Occurred

Error Type: {type(error).__name__}
Error Message: {str(error)}

Context:
"""
        
        for key, value in context.items():
            message += f"\n- {key}: {value}"
        
        message += f"\n\nTimestamp: {datetime.now(UTC).isoformat()}"
        
        try:
            self.sns.publish(
                TopicArn=self.error_topic_arn,
                Subject=subject,
                Message=message
            )
            logger.info(f"Sent error notification: {type(error).__name__}")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
    
    def send_dry_run_report(self, planned_actions: List[Any], total_savings: float):
        """
        Send dry run report showing what would have been done.
        
        Args:
            planned_actions: List of PlannedAction objects
            total_savings: Total estimated monthly savings
        """
        if not self.action_topic_arn:
            logger.warning("No action topic ARN configured for dry run report")
            return
        
        subject = f"Cost Prevention DRY RUN: {len(planned_actions)} Actions Planned"
        
        message = f"""
AWS Cost Prevention - DRY RUN REPORT

This is a DRY RUN - no actual actions were taken.

Total Planned Actions: {len(planned_actions)}
Monetary opportunity: {_opportunity(total_savings)}

Planned Actions:
"""
        
        for action in planned_actions:
            message += f"\n- {action.action} {action.resource_id} ({action.resource_type})"
            message += f"\n  Reason: {action.reason}"
            message += f"\n  Monetary opportunity: {_opportunity(action.estimated_savings)}"
        
        message += f"\n\nTimestamp: {datetime.now(UTC).isoformat()}"
        message += "\n\nExecution also requires deployment enablement, durable audit and supported approval configuration."
        
        try:
            self.sns.publish(
                TopicArn=self.action_topic_arn,
                Subject=subject,
                Message=message
            )
            logger.info(f"Sent dry run report for {len(planned_actions)} planned actions")
        except Exception as e:
            logger.error(f"Failed to send dry run report: {e}")
    
    def send_safety_block_notification(self, resource: Any, action: str, reason: str):
        """
        Send notification when safety guard blocks an action.
        
        Args:
            resource: Resource object
            action: Action that was blocked
            reason: Reason for blocking
        """
        if not self.warning_topic_arn:
            logger.warning("No warning topic ARN configured for safety block")
            return
        
        subject = f"Cost Prevention: Action Blocked by Safety Guard"
        
        message = f"""
AWS Cost Prevention - Safety Guard Block

A planned action was blocked by safety checks.

Resource ID: {resource.resource_id}
Resource Type: {resource.resource_type}
Service: {resource.service}
Region: {resource.region}
State: {resource.state}

Planned Action: {action}
Block Reason: {reason}

Tags:
"""
        
        for key, value in resource.tags.items():
            message += f"\n- {key}: {value}"
        
        message += f"\n\nTimestamp: {datetime.now(UTC).isoformat()}"
        message += "\n\nThis is expected behavior for protected resources."
        
        try:
            self.sns.publish(
                TopicArn=self.warning_topic_arn,
                Subject=subject,
                Message=message
            )
            logger.info(f"Sent safety block notification for {resource.resource_id}")
        except Exception as e:
            logger.error(f"Failed to send safety block notification: {e}")
