"""
Prevention Engine for automated cost prevention.

This module orchestrates the automated cost prevention process by:
1. Monitoring AWS budgets continuously
2. Discovering and tracking resources across 20+ services
3. Detecting idle resources
4. Enforcing safety checks
5. Executing automated actions (or requesting approval)
6. Sending notifications
7. Maintaining audit trail
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
import logging
import os
import math
import time
from dataclasses import asdict

from ..utils.types import (
    BudgetStatus, ThresholdEvent, Resource, ResourceMetadata,
    IdleStatus, SafetyCheck, ActionResult, PlannedAction,
    ApprovalRequest, ApprovalResponse
)

logger = logging.getLogger(__name__)


class PreventionConfigurationUnavailable(RuntimeError):
    """Durable monitoring configuration could not be read or written."""


class PreventionConfigurationConflict(RuntimeError):
    """A newer monitoring configuration must be read before retrying."""


class PreventionEngine:
    """Main orchestrator for automated cost prevention."""
    
    def __init__(
        self,
        budget_monitor,
        resource_manager,
        idle_detector,
        safety_guard,
        action_executor,
        approval_manager,
        rollback_manager,
        notification_service,
        dynamodb_client=None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize prevention engine with all components.
        
        Args:
            budget_monitor: BudgetMonitor instance
            resource_manager: ResourceManager instance
            idle_detector: IdleDetector instance
            safety_guard: SafetyGuard instance
            action_executor: ActionExecutor instance
            approval_manager: ApprovalManager instance
            rollback_manager: RollbackManager instance
            notification_service: NotificationService instance
            dynamodb_client: DynamoDB client for configuration storage
            config: Prevention configuration (optional, loaded from DynamoDB if not provided)
        """
        self.budget_monitor = budget_monitor
        self.resource_manager = resource_manager
        self.idle_detector = idle_detector
        self.safety_guard = safety_guard
        self.action_executor = action_executor
        self.approval_manager = approval_manager
        self.rollback_manager = rollback_manager
        self.notification_service = notification_service
        self.dynamodb_client = dynamodb_client
        self.config_version = 0
        
        # Load or use provided configuration
        if config is not None:
            self.config = self._validate_config(config)
        elif dynamodb_client:
            self.config = self._load_config_from_dynamodb()
        else:
            self.config = self._get_default_config()
            
        logger.info(f"PreventionEngine initialized with config: {self.config}")

    def monitor_budgets(self) -> Dict[str, Any]:
        """
        Run budget monitoring (poll budgets and optionally run prevention workflow).
        Called by EventBridge scheduler for the budget-monitoring event.
        Delegates to run_prevention_cycle() and returns a result with 'status' for compatibility.
        """
        result = self.run_prevention_cycle()
        # Scheduler expects a 'status' key for logging
        result["status"] = "ok" if result.get("success") else "error"
        if result.get("skipped"):
            result["status"] = "skipped"
        return result

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "enabled": False,
            "dry_run_mode": True,  # Start in dry run mode for safety
            "approval_required": True,
            "enabled_services": [
                "ec2", "rds", "lambda", "ebs", "s3", "dynamodb",
                "elasticache", "redshift", "nat_gateway", "elastic_ip",
                "elb", "alb", "nlb", "cloudfront", "api_gateway",
                "step_functions", "glue", "sagemaker", "ecs", "eks",
                "sns", "sqs"
            ],
            "budget_thresholds": {
                "warning": 80,
                "action": 90
            },
            "poll_interval_minutes": 5,
            "inventory_refresh_minutes": 15,
            "last_run": None,
            "last_inventory_refresh": None
        }
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration before applying.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Validated configuration
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not isinstance(config, dict): raise ValueError('Prevention config must be an object')
        # Start with defaults
        validated = self._get_default_config()
        
        # Update with provided config
        validated.update(config)
        
        # Validate boolean fields
        for field in ["enabled", "dry_run_mode", "approval_required"]:
            if field in config and not isinstance(config[field], bool):
                raise ValueError(f"Config field '{field}' must be boolean")
        
        # Validate thresholds
        if "budget_thresholds" in config:
            thresholds = config["budget_thresholds"]
            if not isinstance(thresholds, dict):
                raise ValueError("budget_thresholds must be a dictionary")
            
            warning = thresholds.get("warning", 80)
            action = thresholds.get("action", 90)
            
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                   for value in (warning, action)):
                raise ValueError('Budget thresholds must be finite numbers')
            if not (0 < warning < 100):
                raise ValueError("Warning threshold must be between 0 and 100")
            if not (0 < action <= 100):
                raise ValueError("Action threshold must be between 0 and 100")
            if warning >= action:
                raise ValueError("Warning threshold must be less than action threshold")
            validated['budget_thresholds'] = {'warning': warning, 'action': action}
        
        # Validate enabled_services
        if "enabled_services" in config:
            if not isinstance(config["enabled_services"], list):
                raise ValueError("enabled_services must be a list")
            if not all(isinstance(s, str) for s in config["enabled_services"]):
                raise ValueError("All enabled_services must be strings")
            supported = set(self._get_default_config()['enabled_services'])
            if any(service not in supported for service in config['enabled_services']):
                raise ValueError('enabled_services contains an unsupported service')
            validated['enabled_services'] = list(dict.fromkeys(config['enabled_services']))
        
        # Validate intervals
        for field in ["poll_interval_minutes", "inventory_refresh_minutes"]:
            if field in config:
                value = config[field]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                    raise ValueError(f"{field} must be a positive number")
        
        logger.info("Configuration validated successfully")
        return validated
    
    def _load_config_from_dynamodb(self) -> Dict[str, Any]:
        """Load configuration from DynamoDB."""
        try:
            table_name = os.environ.get("PREVENTION_CONFIG_TABLE", "costguard-prevention-config")
            response = self.dynamodb_client.get_item(
                TableName=table_name,
                Key={"config_key": {"S": "main"}}, ConsistentRead=True
            )
            
            if "Item" in response:
                version = response['Item'].get('config_version', {}).get('N', '0')
                self.config_version = int(version)
                if self.config_version < 0: raise ValueError('Invalid config version')
                if 'config_value' not in response['Item']: raise ValueError('Missing stored config')
                # Parse DynamoDB item to dict (config_value is stored as {"M": {...}})
                config_value = response["Item"].get("config_value", {})
                config = self._parse_dynamodb_item(config_value)
                # Unwrap top-level "M" so config is {enabled: True, ...} not {M: {enabled: True, ...}}
                if isinstance(config, dict) and "M" in config and len(config) == 1:
                    config = config["M"]
                logger.info("Configuration loaded from DynamoDB")
                return self._validate_config(config)
            else:
                logger.info("No configuration found in DynamoDB, using defaults")
                return self._get_default_config()
                
        except Exception as e:
            logger.warning('Prevention configuration read unavailable: %s', type(e).__name__)
            raise PreventionConfigurationUnavailable('Monitoring configuration is unavailable') from e
    
    def _parse_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse DynamoDB item format to plain dict."""
        if not item:
            return {}
        
        result = {}
        for key, value in item.items():
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                result[key] = float(value["N"]) if "." in value["N"] else int(value["N"])
            elif "NULL" in value:
                result[key] = None
            elif "BOOL" in value:
                result[key] = value["BOOL"]
            elif "L" in value:
                result[key] = [self._parse_dynamodb_value(v) for v in value["L"]]
            elif "M" in value:
                result[key] = self._parse_dynamodb_item(value["M"])
        
        return result
    
    def _parse_dynamodb_value(self, value: Dict[str, Any]) -> Any:
        """Parse a single DynamoDB value."""
        if "S" in value:
            return value["S"]
        elif "N" in value:
            return float(value["N"]) if "." in value["N"] else int(value["N"])
        elif "BOOL" in value:
            return value["BOOL"]
        elif "L" in value:
            return [self._parse_dynamodb_value(v) for v in value["L"]]
        elif "M" in value:
            return self._parse_dynamodb_item(value["M"])
        return None
    
    def _save_config_to_dynamodb(self, candidate=None) -> None:
        """Save a whole configuration only if its read version is still current."""
        if self.dynamodb_client is None:
            raise PreventionConfigurationUnavailable('Monitoring configuration storage is unavailable')
        candidate = self.config if candidate is None else candidate
        try:
            parameters = {
                'TableName': os.environ.get('PREVENTION_CONFIG_TABLE', 'costguard-prevention-config'),
                'Item': {'config_key': {'S': 'main'}, 'config_value': self._to_dynamodb_item(candidate),
                         'config_version': {'N': str(self.config_version+1)},
                         'updated_at': {'S': datetime.now(UTC).isoformat()}},
                'ConditionExpression': 'attribute_not_exists(config_version)' if self.config_version == 0 else 'config_version = :version'
            }
            if self.config_version:
                parameters['ExpressionAttributeValues'] = {':version': {'N': str(self.config_version)}}
            self.dynamodb_client.put_item(**parameters)
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                raise PreventionConfigurationConflict('Monitoring configuration changed; refresh before retrying') from error
            logger.warning('Prevention configuration save unavailable: %s', type(error).__name__)
            raise PreventionConfigurationUnavailable('Monitoring configuration could not be saved') from error
        self.config_version += 1
        self.config = candidate

    def _record_cycle_outcome(self, status, started_at, *, summary=None, error_code=None, reason=None):
        """Atomically retain the latest outcome and preserve the prior successful summary."""
        if self.dynamodb_client is None: return 'unavailable'
        completed_at = datetime.now(UTC).isoformat()
        inventory_at = getattr(self, '_last_inventory_observed_at', None)
        observation = {'status': status, 'started_at': started_at, 'completed_at': completed_at,
                       'summary': summary, 'error_code': error_code, 'reason': reason,
                       'inventory_observed_at': inventory_at}
        try:
            from .monitoring_observations import validate_outcome
            validate_outcome(observation)
        except Exception as error:
            logger.warning('Monitoring outcome is unavailable: %s', type(error).__name__)
            return 'unavailable'
        order = str(time.time_ns())
        assignments = ['schema_version = :schema', 'completed_order = :order', 'observation = :observation']
        values = {':schema': {'N': '1'}, ':order': {'N': order}, ':observation': self._to_dynamodb_item(observation)}
        if status == 'success' and summary is not None:
            assignments += ['last_successful_summary = :summary', 'last_successful_at = :completed']
            values.update({':summary': self._to_dynamodb_item(summary), ':completed': {'S': completed_at}})
        if inventory_at:
            assignments.append('last_inventory_observed_at = :inventory')
            values[':inventory'] = {'S': inventory_at}
        try:
            self.dynamodb_client.update_item(
                TableName=os.environ.get('PREVENTION_CONFIG_TABLE', 'costguard-prevention-config'),
                Key={'config_key': {'S': 'last_cycle'}},
                UpdateExpression='SET '+', '.join(assignments),
                ConditionExpression='attribute_not_exists(completed_order) OR completed_order < :order',
                ExpressionAttributeValues=values)
            return 'stored'
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') == 'ConditionalCheckFailedException': return 'superseded'
            logger.warning('Monitoring outcome could not be stored: %s', type(error).__name__)
            return 'unavailable'

    def _latest_cycle_status(self):
        # Legacy successful summary/timestamps remain fallback-only until a new observation exists.
        from .monitoring_observations import validate_outcome, validate_summary
        result = {'latest_cycle': None, 'latest_cycle_read_status': 'not_recorded',
                  'last_cycle_summary': None,
                  'last_run': self.config.get('last_run'),
                  'last_inventory_refresh': self.config.get('last_inventory_refresh')}
        try:
            if self.config.get('last_cycle_summary') is not None:
                result['last_cycle_summary'] = validate_summary(self.config['last_cycle_summary'])
            if self.dynamodb_client is None: raise ValueError('Observation storage unavailable')
            response = self.dynamodb_client.get_item(
                TableName=os.environ.get('PREVENTION_CONFIG_TABLE', 'costguard-prevention-config'),
                Key={'config_key': {'S': 'last_cycle'}}, ConsistentRead=True)
            item = response.get('Item')
            if not item: return result
            if item.get('schema_version', {}).get('N') != '1': raise ValueError('Unknown observation schema')
            observation = validate_outcome(self._parse_dynamodb_item(item['observation']['M']))
            if observation.get('status') not in ('success', 'failed', 'skipped'): raise ValueError('Unknown observation status')
            result.update({'latest_cycle': observation, 'latest_cycle_read_status': 'available'})
            if 'last_successful_summary' in item:
                result['last_cycle_summary'] = validate_summary(self._parse_dynamodb_item(item['last_successful_summary']['M']))
                result['last_run'] = item.get('last_successful_at', {}).get('S')
            elif observation['status'] == 'success':
                result['last_cycle_summary'] = observation.get('summary')
                result['last_run'] = observation.get('completed_at')
            result['last_inventory_refresh'] = item.get('last_inventory_observed_at', {}).get('S') or observation.get('inventory_observed_at') or result['last_inventory_refresh']
            return result
        except Exception as error:
            logger.warning('Monitoring outcome read unavailable: %s', type(error).__name__)
            result['latest_cycle_read_status'] = 'unavailable'
            result['latest_cycle'] = None
            result['last_cycle_summary'] = None
            return result

    def _to_dynamodb_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert dict to DynamoDB item format."""
        result = {}
        for key, value in data.items():
            result[key] = self._to_dynamodb_value(value)
        return {"M": result}
    
    def _to_dynamodb_value(self, value: Any) -> Dict[str, Any]:
        """Convert Python value to DynamoDB value format."""
        if isinstance(value, str):
            return {"S": value}
        elif isinstance(value, bool):
            return {"BOOL": value}
        elif isinstance(value, (int, float)):
            return {"N": str(value)}
        elif isinstance(value, list):
            return {"L": [self._to_dynamodb_value(v) for v in value]}
        elif isinstance(value, dict):
            return {"M": {k: self._to_dynamodb_value(v) for k, v in value.items()}}
        elif value is None:
            return {"NULL": True}
        else:
            return {"S": str(value)}
        
    def run_prevention_cycle(self) -> Dict[str, Any]:
        """
        Run a complete prevention cycle.
        
        This is the main entry point called by EventBridge schedule.
        Performs budget monitoring and triggers prevention workflow if needed.
        
        Returns:
            Dict with cycle results including:
            - success: bool
            - budget_events: int (number of threshold events)
            - actions_taken: int (number of actions executed)
            - timestamp: str
        """
        cycle_start = datetime.now(UTC)
        self._last_inventory_observed_at = None
        if not self.config.get("enabled", False):
            persistence = self._record_cycle_outcome('skipped', cycle_start.isoformat(), reason='monitoring_disabled')
            logger.info("Prevention engine is disabled, skipping cycle")
            return {
                "success": True,
                "skipped": True,
                "outcome_persistence": persistence,
                "reason": "disabled",
                "timestamp": datetime.now(UTC).isoformat()
            }
        
        logger.info("Starting prevention cycle")
        
        try:
            # Step 1: Check budgets
            thresholds = self.config['budget_thresholds']
            self.budget_monitor.warning_threshold = thresholds['warning']/100.0
            self.budget_monitor.action_threshold = thresholds['action']/100.0
            budget_events = self.budget_monitor.poll_budgets()
            logger.info(f"Found {len(budget_events)} budget events")
            
            actions_taken = 0
            
            action_events = []
            self._cycle_summary = {'discovery_performed': False, 'inventory_completeness': 'unverified',
                                   'budget_scope_verified': False, 'planned_review_candidates': 0,
                                   'candidate_examples': []}
            # Warnings remain budget-specific. Shared discovery/planning runs once per cycle.
            for event in budget_events:
                if event.threshold_type == 'warning':
                    self.notification_service.send_warning(event.budget_status)
                elif event.threshold_type == 'action':
                    action_events.append(event)
            if action_events:
                actions_taken = self._execute_prevention_workflow(action_events[0])
            self._cycle_summary.update({
                'completed_at': datetime.now(UTC).isoformat(),
                'triggering_budget_count': len(action_events),
                'triggering_budget_examples': [event.budget_name for event in action_events[:20]],
                'triggering_budget_examples_truncated': len(action_events) > 20,
                'action_requests_accepted': actions_taken, 'resource_outcomes_verified': False,
                'effective_dry_run_mode': self.get_status(include_cycle=False)['effective_dry_run_mode']})

            persistence = self._record_cycle_outcome('success', cycle_start.isoformat(), summary=self._cycle_summary)
            cycle_duration = (datetime.now(UTC) - cycle_start).total_seconds()
            logger.info(f"Prevention cycle completed in {cycle_duration:.2f}s")
            
            return {
                "success": True,
                "budget_events": len(budget_events),
                "cycle_summary": self._cycle_summary,
                "outcome_persistence": persistence,
                "actions_taken": actions_taken,
                "execution_enabled": self.get_status(include_cycle=False)["execution_enabled"],
                "effective_dry_run_mode": self.get_status(include_cycle=False)["effective_dry_run_mode"],
                "cycle_duration_seconds": cycle_duration,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Prevention cycle failed: {e}", exc_info=True)
            persistence = self._record_cycle_outcome('failed', cycle_start.isoformat(), error_code='MONITORING_CYCLE_FAILED')
            self.notification_service.send_error_notification(e, {
                "cycle_start": cycle_start.isoformat(),
                "config": self.config
            })
            return {
                "success": False,
                "error": str(e),
                "outcome_persistence": persistence,
                "timestamp": datetime.now(UTC).isoformat()
            }
    
    def _execute_prevention_workflow(self, threshold_event: ThresholdEvent) -> int:
        """
        Execute prevention workflow when budget threshold is crossed.
        
        Args:
            threshold_event: The threshold event that triggered this workflow
            
        Returns:
            Number of actions taken
        """
        logger.info(f"Executing prevention workflow for {threshold_event.budget_name}")
        workflow_start = datetime.now(UTC)
        if not isinstance(getattr(self, '_cycle_summary', None), dict): self._cycle_summary = {}
        
        try:
            # Step 1: Discover resources (with inventory refresh check)
            resources = self._discover_resources_with_cache()
            logger.info(f"Discovered {len(resources)} resources")
            
            # Step 2: Detect idle resources
            idle_resources = self._detect_idle_resources(resources)
            logger.info(f"Found {len(idle_resources)} idle resources")
            
            # Step 3: Check safety and plan actions
            planned_actions = self._plan_actions(idle_resources)
            logger.info(f"Planned {len(planned_actions)} review candidates")
            self._cycle_summary.update({'discovery_performed': True, 'discovered_resources': len(resources),
                'discovery_report': self.resource_manager.last_discovery_report,
                'low_usage_rule_matches': len(idle_resources), 'evidence_counts': self._idle_evidence_counts,
                'unavailable_evidence_reasons': self._unavailable_evidence_reasons,
                'unavailable_evidence_examples': self._unavailable_evidence_examples,
                'unavailable_evidence_examples_truncated': self._idle_evidence_counts['unavailable'] > len(self._unavailable_evidence_examples),
                'planned_review_candidates': len(planned_actions),
                'candidate_examples': [asdict(action) for action in planned_actions[:20]],
                'candidate_examples_truncated': len(planned_actions) > 20})
            
            if not planned_actions:
                logger.info("No review candidates passed the available checks")
                return 0
            
            # Step 4: Execute based on mode
            if self.get_status(include_cycle=False)["effective_dry_run_mode"]:
                self._handle_dry_run(planned_actions)
                return 0  # No actual actions in dry run
            elif self.config.get("approval_required", False):
                return self._handle_approval_workflow(planned_actions)
            else:
                return self._execute_actions(planned_actions)
                
        except Exception as e:
            logger.error(f"Prevention workflow failed: {e}", exc_info=True)
            raise RuntimeError('Prevention workflow could not complete') from e
    
    def _discover_resources_with_cache(self) -> List[Resource]:
        """Read fresh discovery; persisted observations are not a runtime cache."""
        resources = self.resource_manager.discover_resources(self.config.get('enabled_services', []))
        self._last_inventory_observed_at = datetime.now(UTC).isoformat()
        return resources

    def _detect_idle_resources(self, resources: List[Resource]) -> List[tuple]:
        """
        Detect which resources are idle.
        
        Args:
            resources: List of resources to check
            
        Returns:
            List of tuples (resource, metadata, idle_status) for idle resources
        """
        idle_resources = []
        self._idle_evidence_counts = {'rule_matched': 0, 'rule_not_matched': 0, 'unavailable': 0}
        self._unavailable_evidence_reasons = {}
        self._unavailable_evidence_examples = []
        for resource in resources:
            try:
                metadata = None  # The observed-window adapter owns evidence retrieval.
                idle_status = self.idle_detector.is_resource_idle(resource, metadata)
                
                evidence = idle_status.observation_status
                self._idle_evidence_counts[evidence if evidence in self._idle_evidence_counts else 'unavailable'] += 1
                if evidence not in ('rule_matched', 'rule_not_matched'):
                    self._record_unavailable_evidence(resource, idle_status.reason or 'Evidence unavailable')
                if idle_status.is_idle and evidence == 'rule_matched':
                    idle_resources.append((resource, metadata, idle_status))
                    logger.debug(f"Resource {resource.resource_id} is idle: {idle_status.metrics_used}")
                    
            except Exception as e:
                self._idle_evidence_counts['unavailable'] += 1
                self._record_unavailable_evidence(resource, 'Evidence evaluation could not complete')
                logger.warning(f"Failed to check idle status for {resource.resource_id}: {e}")
                continue
        
        return idle_resources
    
    def _record_unavailable_evidence(self, resource, reason):
        reason = str(reason)[:256]
        self._unavailable_evidence_reasons[reason] = self._unavailable_evidence_reasons.get(reason, 0)+1
        if len(self._unavailable_evidence_examples) < 20:
            self._unavailable_evidence_examples.append({'resource_id': resource.resource_id,
                'service': resource.service, 'region': resource.region, 'reason': reason})

    def _plan_actions(self, idle_resources: List[tuple]) -> List[PlannedAction]:
        """
        Plan actions for idle resources after safety checks.
        
        Args:
            idle_resources: List of (resource, metadata, idle_status) tuples
            
        Returns:
            List of PlannedAction objects that passed safety checks
        """
        planned_actions = []
        
        for resource, metadata, idle_status in idle_resources:
            try:
                # Determine action based on resource type
                action = self._determine_action(resource)
                if action is None:
                    logger.info('No supported reversible action for service %s', resource.service)
                    continue
                
                # Check safety
                safety_check = self.safety_guard.is_action_safe(resource, action, idle_status, for_preview=True)
                
                if safety_check.is_safe:
                    # Calculate estimated savings (monthly)
                    estimated_savings = None  # Generic resource metadata cannot establish avoidable charges.
                    
                    planned_action = PlannedAction(
                        resource_id=resource.resource_id,
                        resource_type=resource.resource_type,
                        action=action,
                        reason=f"Observed low-usage rule over {idle_status.idle_duration} minutes; workload inactivity is unverified",
                        estimated_savings=estimated_savings
                    )
                    planned_actions.append(planned_action)
                    logger.debug(f"Planned action for {resource.resource_id}: {action}")
                else:
                    logger.info(f"Action blocked for {resource.resource_id}: {safety_check.blocked_reason}")
                    # Send notification about blocked action
                    self.notification_service.send_safety_block_notification(
                        resource, action, safety_check.blocked_reason
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to plan action for {resource.resource_id}: {e}")
                continue
        
        return planned_actions
    
    def _determine_action(self, resource: Resource) -> str:
        """
        Determine appropriate action for resource type.
        
        Args:
            resource: Resource to determine action for
            
        Returns:
            Action string (e.g., "stop", "delete", "limit_concurrency")
        """
        from .resource_actions import supported_action
        return supported_action(resource)
    
    def _handle_dry_run(self, planned_actions: List[PlannedAction]) -> None:
        """
        Handle dry run mode - log actions without executing.
        
        Args:
            planned_actions: List of planned actions
        """
        logger.info(f"DRY RUN: Would execute {len(planned_actions)} actions")
        
        values = [action.estimated_savings for action in planned_actions]
        total_savings = sum(values) if values and all(value is not None for value in values) else None
        for action in planned_actions:
            logger.info('DRY RUN: planned %s for %s (%s); monetary opportunity unavailable', action.action, action.resource_id, action.reason)

        # Send dry run report
        self.notification_service.send_dry_run_report(planned_actions, total_savings)
    
    def _handle_approval_workflow(self, planned_actions: List[PlannedAction]) -> int:
        """
        Handle approval workflow - request approval before executing.
        
        Args:
            planned_actions: List of planned actions
            
        Returns:
            Number of actions executed
        """
        logger.info(f"Requesting approval for {len(planned_actions)} actions")
        
        try:
            approval_request = self.approval_manager.request_approval(planned_actions)
            approval_response = self.approval_manager.wait_for_approval(
                approval_request.request_id,
                timeout_minutes=30
            )
            
            if approval_response.approved:
                logger.info(f"Approval granted by {approval_response.approved_by}")
                return self._execute_actions(planned_actions)
            else:
                logger.info(f"Actions denied or timed out: {approval_request.request_id}")
                return 0
                
        except Exception as e:
            logger.error(f"Approval workflow failed: {e}")
            raise RuntimeError('Approval workflow could not complete') from e
    
    def _execute_actions(self, planned_actions: List[PlannedAction]) -> int:
        """
        Execute planned actions.
        
        Args:
            planned_actions: List of planned actions
            
        Returns:
            Number of successfully executed actions
        """
        if self.get_status(include_cycle=False)['effective_dry_run_mode']:
            logger.info('Resource execution is unavailable or disabled; no actions submitted')
            return 0
        logger.info(f"Executing {len(planned_actions)} actions")
        
        # Sort by cost impact (highest first) - Property 13
        planned_actions.sort(key=lambda x: x.estimated_savings if x.estimated_savings is not None else 0.0, reverse=True)
        
        results = []
        successful_count = 0
        
        for planned_action in planned_actions:
            try:
                # Re-resolve real metadata before execution; never invent region,
                # tags or state for a planned resource.
                matches = [resource for resource in self.resource_manager.discover_resources(
                    self.config.get('enabled_services', []))
                    if resource.resource_id == planned_action.resource_id and resource.resource_type == planned_action.resource_type]
                if len(matches) != 1:
                    raise ValueError('Resource is unavailable or ambiguous; action blocked')
                resource = matches[0]
                if self._determine_action(resource) != planned_action.action:
                    raise ValueError('Planned action no longer matches resource metadata')
                fresh_idle_status = self.idle_detector.is_resource_idle(resource, None)
                safety = self.safety_guard.is_action_safe(resource, planned_action.action, fresh_idle_status)
                if not safety.is_safe:
                    raise ValueError('Resource failed current safety checks')
                client = self.action_executor.clients.get(resource.service)
                if client is None or getattr(getattr(client, 'meta', None), 'region_name', None) != resource.region:
                    raise ValueError('Execution client does not match observed resource region')

                # Store pre-action state for rollback
                self.rollback_manager.store_pre_action_state(
                    resource,
                    planned_action.action
                )
                
                # Execute action
                result = self.action_executor.execute_action(
                    resource,
                    planned_action.action
                )
                results.append(result)
                
                if result.success:
                    successful_count += 1
                    logger.info(f"Successfully executed {planned_action.action} on {planned_action.resource_id}")
                else:
                    logger.warning(f"Failed to execute {planned_action.action} on {planned_action.resource_id}: {result.error_message}")
                    
            except Exception as e:
                # Property 14: Error Isolation - continue with remaining actions
                logger.error(f"Error executing action on {planned_action.resource_id}: {e}")
                continue
        
        # Send notification about executed actions
        if results:
            self.notification_service.send_action_notification(results)
        
        logger.info(f"Executed {successful_count}/{len(planned_actions)} actions successfully")
        return successful_count
    
    def get_status(self, include_cycle=True) -> Dict[str, Any]:
        """
        Get current prevention status.
        
        Returns:
            Dict with current status including:
            - enabled: bool
            - dry_run_mode: bool
            - approval_required: bool
            - enabled_services: list
            - budget_thresholds: dict
            - last_run: str (ISO timestamp)
            - last_inventory_refresh: str (ISO timestamp)
        """
        try:
            configured_schedule = int(os.environ.get('BUDGET_POLL_INTERVAL_MINUTES', ''))
            if configured_schedule <= 0: configured_schedule = None
        except ValueError:
            configured_schedule = None
        deployment_execution = os.environ.get('PREVENTION_EXECUTION_ENABLED', 'false').lower() == 'true'
        execution_configured = self.action_executor.audit_logger is not None and all(self.action_executor.clients.get(service) is not None for service in ('ec2', 'rds', 'lambda'))
        return {
            "config_version": self.config_version,
            "execution_enabled": deployment_execution,
            "execution_configured": execution_configured,
            "effective_dry_run_mode": bool(self.config.get('dry_run_mode', True) or not deployment_execution or not execution_configured),
            "readiness": {
                "budget_client_configured": self.budget_monitor.budgets_client is not None,
                "metrics_client_configured": self.idle_detector.cloudwatch is not None,
                "audit_configured": self.action_executor.audit_logger is not None,
                "notification_topics_configured": all(getattr(self.notification_service, field, None) for field in ('warning_topic_arn', 'action_topic_arn', 'error_topic_arn')),
                "aws_access_verified": False,
            },
            "enabled": self.config.get("enabled", False),
            "dry_run_mode": self.config.get("dry_run_mode", False),
            "approval_required": self.config.get("approval_required", False),
            "enabled_services": self.config.get("enabled_services", []),
            "budget_thresholds": self.config.get("budget_thresholds", {}),
            "poll_interval_minutes": self.config.get("poll_interval_minutes", 5),
            "schedule": {'configured_interval_minutes': configured_schedule,
                         'source': 'deployment_configuration', 'live_schedule_verified': False,
                         'runtime_preference_applied': False},
            "inventory_read_mode": "fresh_discovery",
            "inventory_refresh_preference_applied": False,
            "inventory_refresh_minutes": self.config.get("inventory_refresh_minutes", 15),
            "last_run": self.config.get("last_run"),
            "last_cycle_summary": self.config.get('last_cycle_summary'),
            "last_inventory_refresh": self.config.get("last_inventory_refresh"),
            **(self._latest_cycle_status() if include_cycle else {}),
        }
    
    def enable(self) -> None:
        """Enable automated prevention."""
        self._save_config_to_dynamodb({**self.config, 'enabled': True})
        logger.info("Automated prevention enabled")
    
    def disable(self) -> None:
        """Disable automated prevention."""
        self._save_config_to_dynamodb({**self.config, 'enabled': False})
        logger.info("Automated prevention disabled")
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        Update configuration with validation.
        
        Args:
            new_config: New configuration values to apply
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Merge with existing config
        if not isinstance(new_config, dict): raise ValueError('Prevention config must be an object')
        merged_config = {**self.config, **new_config}
        if 'budget_thresholds' in new_config and isinstance(new_config['budget_thresholds'], dict):
            merged_config['budget_thresholds'] = {**self.config['budget_thresholds'], **new_config['budget_thresholds']}
        
        # Validate merged config
        validated_config = self._validate_config(merged_config)
        
        # Apply validated config
        self._save_config_to_dynamodb(validated_config)
        
        logger.info(f"Configuration updated: {new_config}")
    
    def get_resources(self, filters: Optional[Dict[str, Any]] = None) -> List[Resource]:
        """
        Get resources from inventory with optional filters.
        
        Args:
            filters: Optional filters (service, state, etc.)
            
        Returns:
            List of resources matching filters
        """
        import re
        if filters is not None and not isinstance(filters, dict): raise ValueError('Resource filters must be an object')
        filters = filters or {}
        if set(filters)-{'service', 'state', 'resource_type'}: raise ValueError('Unsupported resource filter')
        if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', value) for value in filters.values()):
            raise ValueError('Resource filters must be nonempty names of at most 64 characters')
        service = filters.get('service')
        if service is not None and service not in self._get_default_config()['enabled_services']:
            raise ValueError('Unknown resource discovery service')
        configured = self.config.get('enabled_services', [])
        services = configured if service is None else [service] if service in configured else []
        resources = self.resource_manager.discover_resources(services)
        if not filters:
            return resources
        
        # Apply filters
        filtered = resources
        
        if "service" in filters:
            filtered = [r for r in filtered if r.service == filters["service"]]
        
        if "state" in filters:
            filtered = [r for r in filtered if r.state == filters["state"]]
        
        if "resource_type" in filters:
            filtered = [r for r in filtered if r.resource_type == filters["resource_type"]]
        
        return filtered
    
    def get_action_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        report: Optional[Dict[str, Any]] = None,
        scan_start_key: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get action history from audit logs (costguard-prevention-audit table).
        
        Args:
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            limit: Maximum number of records to return
            
        Returns:
            List of action history records with action_id, timestamp, resource_id, action, etc.
        """
        from .time_values import history_boundary
        first = history_boundary(start_date) if start_date else None
        last = history_boundary(end_date, end=True) if end_date else None
        if first and last and first > last: raise ValueError('Start must not exceed end')
        if first and last and (last-first).days > 365: raise ValueError('Select at most 366 dates')
        if type(limit) is not int or not 1 <= limit <= 1001: raise ValueError('Invalid audit history limit')
        if not self.dynamodb_client:
            raise RuntimeError("Action history storage is unavailable")
        table_name = os.environ.get("PREVENTION_AUDIT_TABLE", "costguard-prevention-audit")
        logger.info(f"Querying action history: start={start_date}, end={end_date}, limit={limit}")
        report = report if report is not None else {}
        report.update({'status': 'reading', 'page_limit': 10, 'page_size': 100, 'pages_read': 0,
            'examined_rows': 0, 'invalid_rows': 0, 'unavailable_timestamp_rows': 0,
            'has_more_stored_rows': None, 'matched_rows_in_selection': None, 'next_scan_key': None,
            'selection_scope': 'bounded_scan_sorted_within_selection_not_global_latest',
            'execution_verified': False, 'monetary_savings_verified': False})
        fields = ('action_id', 'timestamp', 'resource_id', 'resource_type', 'region', 'action', 'event_type',
            'status', 'success', 'estimated_savings', 'error', 'message', 'account_id', 'execution_mode', 'dry_run', 'approval_id')
        names = {f'#field{index}': name for index, name in enumerate(fields)}
        items = []
        try:
            scan_kwargs = {'TableName': table_name, 'Limit': 100,
                'ProjectionExpression': ', '.join(names), 'ExpressionAttributeNames': names}
            if scan_start_key is not None:
                from .prevention_history_cursor import _key
                scan_kwargs['ExclusiveStartKey'] = _key(scan_start_key)
            seen = set()
            for _ in range(10):
                scan_kwargs['Limit'] = min(100, limit-len(items))
                response = self.dynamodb_client.scan(**scan_kwargs)
                report['pages_read'] += 1
                for item in response.get('Items', []):
                    report['examined_rows'] += 1
                    try: rec = self._parse_audit_item(item)
                    except (ValueError, TypeError, KeyError): rec = None
                    if not rec:
                        report['invalid_rows'] += 1; continue
                    epoch = rec.get('timestamp_epoch')
                    if epoch is None:
                        report['unavailable_timestamp_rows'] += 1
                        if first or last: continue
                    elif (first is not None and epoch < first.timestamp()) or (last is not None and epoch > last.timestamp()):
                        continue
                    items.append(rec)
                cursor = response.get('LastEvaluatedKey')
                report['has_more_stored_rows'] = bool(cursor)
                report['next_scan_key'] = cursor or None
                if not cursor or len(items) >= limit: break
                fingerprint = str(sorted(cursor.items()))
                if fingerprint in seen: raise ValueError('Repeated audit history cursor')
                seen.add(fingerprint)
                scan_kwargs['ExclusiveStartKey'] = cursor
            items.sort(key=lambda item: item.get('timestamp_epoch', float('-inf')), reverse=True)
            report['matched_rows_in_selection'] = len(items)
            partial = report['has_more_stored_rows'] or report['invalid_rows'] or report['unavailable_timestamp_rows']
            report['status'] = 'bounded_or_partial' if partial else 'observed_scan_selection'
            return items[:limit]
        except Exception as e:
            report.update({'status': 'unavailable', 'matched_rows_in_selection': None, 'has_more_stored_rows': None})
            logger.warning('Action history read failed: %s', type(e).__name__)
            raise RuntimeError('Action history could not be loaded') from e

    def _parse_audit_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize typed audit values and numeric/ISO timestamps for the API."""
        if not item: return None
        from boto3.dynamodb.types import TypeDeserializer
        decoder = TypeDeserializer()
        allowed = ('action_id', 'timestamp', 'resource_id', 'resource_type', 'region', 'action', 'event_type',
            'status', 'success', 'estimated_savings', 'error', 'message', 'account_id', 'execution_mode', 'dry_run', 'approval_id')
        result = {key: decoder.deserialize(value) for key, value in item.items() if key in allowed}
        if not isinstance(result.get('action_id'), str) or not 1 <= len(result['action_id']) <= 256:
            return None
        for key in ('resource_id', 'approval_id'):
            if key in result and result[key] is not None and (not isinstance(result[key], str) or len(result[key]) > 2048):
                return None
        for key in ('resource_type', 'region', 'action', 'event_type', 'status', 'error', 'message', 'account_id', 'execution_mode'):
            value = result.get(key)
            result[key] = value[:1024] if isinstance(value, str) else None
        for key in ('success', 'dry_run'):
            if not isinstance(result.get(key), bool): result[key] = None
        value = result.get('estimated_savings')
        try:
            amount = float(value) if value is not None and not isinstance(value, bool) else None
            result['estimated_savings'] = amount if amount is not None and math.isfinite(amount) and amount >= 0 else None
        except (TypeError, ValueError, OverflowError): result['estimated_savings'] = None
        result.update({'execution_verified': False, 'monetary_savings_verified': False,
            'estimated_savings_currency': None, 'estimate_currency_verified': False,
            'record_scope': 'stored_audit_summary_not_independent_verification'})
        from .time_values import parse_utc_timestamp
        try:
            moment = parse_utc_timestamp(result.get('timestamp'))
            result['timestamp_epoch'] = moment.timestamp()
            result['timestamp'] = moment.isoformat()
        except ValueError:
            result.pop('timestamp_epoch', None)
            result['timestamp'] = None
            result['timestamp_status'] = 'unavailable'
        return result

    def execute_rollback(self, action_id: str) -> Dict[str, Any]:
        """
        Execute rollback for a specific action.
        
        Args:
            action_id: ID of action to rollback
            
        Returns:
            Dict with rollback result
        """
        try:
            result = self.rollback_manager.execute_rollback(action_id)
            
            if result.success:
                logger.info(f"Successfully rolled back action {action_id}")
                return {
                    "success": True,
                    "action_id": action_id,
                    "resource_id": result.resource_id,
                    "target_state": result.restored_state,
                    "restored_state": None,
                    "status": "rollback_submitted",
                    "verification_status": "unverified",
                    "message": "Rollback request accepted; completion is not verified",
                    "timestamp": result.timestamp
                }
            else:
                logger.warning(f"Failed to rollback action {action_id}")
                return {
                    "success": False,
                    "action_id": action_id,
                    "error": getattr(result, "error_message", None) or "Rollback failed"
                }
                
        except Exception as e:
            logger.error(f"Error during rollback of action {action_id}: {e}")
            return {
                "success": False,
                "action_id": action_id,
                "error": str(e)
            }
