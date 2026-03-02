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
from dataclasses import asdict

from ..utils.types import (
    BudgetStatus, ThresholdEvent, Resource, ResourceMetadata,
    IdleStatus, SafetyCheck, ActionResult, PlannedAction,
    ApprovalRequest, ApprovalResponse
)

logger = logging.getLogger(__name__)


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
        
        # Load or use provided configuration
        if config is not None:
            self.config = self._validate_config(config)
        elif dynamodb_client:
            self.config = self._load_config_from_dynamodb()
        else:
            self.config = self._get_default_config()
            
        logger.info(f"PreventionEngine initialized with config: {self.config}")
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "enabled": False,
            "dry_run_mode": True,  # Start in dry run mode for safety
            "approval_required": False,
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
            
            if not (0 < warning < 100):
                raise ValueError("Warning threshold must be between 0 and 100")
            if not (0 < action <= 100):
                raise ValueError("Action threshold must be between 0 and 100")
            if warning >= action:
                raise ValueError("Warning threshold must be less than action threshold")
        
        # Validate enabled_services
        if "enabled_services" in config:
            if not isinstance(config["enabled_services"], list):
                raise ValueError("enabled_services must be a list")
            if not all(isinstance(s, str) for s in config["enabled_services"]):
                raise ValueError("All enabled_services must be strings")
        
        # Validate intervals
        for field in ["poll_interval_minutes", "inventory_refresh_minutes"]:
            if field in config:
                value = config[field]
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"{field} must be a positive number")
        
        logger.info("Configuration validated successfully")
        return validated
    
    def _load_config_from_dynamodb(self) -> Dict[str, Any]:
        """Load configuration from DynamoDB."""
        try:
            table_name = "prevention-config"
            response = self.dynamodb_client.get_item(
                TableName=table_name,
                Key={"config_key": {"S": "main"}}
            )
            
            if "Item" in response:
                # Parse DynamoDB item to dict
                config_value = response["Item"].get("config_value", {})
                config = self._parse_dynamodb_item(config_value)
                logger.info("Configuration loaded from DynamoDB")
                return self._validate_config(config)
            else:
                logger.info("No configuration found in DynamoDB, using defaults")
                return self._get_default_config()
                
        except Exception as e:
            logger.warning(f"Failed to load config from DynamoDB: {e}, using defaults")
            return self._get_default_config()
    
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
    
    def _save_config_to_dynamodb(self) -> None:
        """Save current configuration to DynamoDB."""
        if not self.dynamodb_client:
            logger.warning("No DynamoDB client, cannot save configuration")
            return
        
        try:
            table_name = "prevention-config"
            item = {
                "config_key": {"S": "main"},
                "config_value": self._to_dynamodb_item(self.config),
                "updated_at": {"S": datetime.now(UTC).isoformat()}
            }
            
            self.dynamodb_client.put_item(
                TableName=table_name,
                Item=item
            )
            logger.info("Configuration saved to DynamoDB")
            
        except Exception as e:
            logger.error(f"Failed to save config to DynamoDB: {e}")
    
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
        if not self.config.get("enabled", False):
            logger.info("Prevention engine is disabled, skipping cycle")
            return {
                "success": True,
                "skipped": True,
                "reason": "disabled",
                "timestamp": datetime.now(UTC).isoformat()
            }
        
        logger.info("Starting prevention cycle")
        cycle_start = datetime.now(UTC)
        
        try:
            # Step 1: Check budgets
            budget_events = self.budget_monitor.poll_budgets()
            logger.info(f"Found {len(budget_events)} budget events")
            
            actions_taken = 0
            
            # Step 2: Process threshold events
            for event in budget_events:
                if event.threshold_type == "warning":
                    logger.info(f"Warning threshold reached for {event.budget_name}")
                    self.notification_service.send_warning(event.budget_status)
                elif event.threshold_type == "action":
                    logger.info(f"Action threshold reached for {event.budget_name}")
                    actions_taken += self._execute_prevention_workflow(event)
            
            # Update last run timestamp
            self.config["last_run"] = datetime.now(UTC).isoformat()
            self._save_config_to_dynamodb()
            
            cycle_duration = (datetime.now(UTC) - cycle_start).total_seconds()
            logger.info(f"Prevention cycle completed in {cycle_duration:.2f}s")
            
            return {
                "success": True,
                "budget_events": len(budget_events),
                "actions_taken": actions_taken,
                "cycle_duration_seconds": cycle_duration,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Prevention cycle failed: {e}", exc_info=True)
            self.notification_service.send_error_notification(e, {
                "cycle_start": cycle_start.isoformat(),
                "config": self.config
            })
            return {
                "success": False,
                "error": str(e),
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
        
        try:
            # Step 1: Discover resources (with inventory refresh check)
            resources = self._discover_resources_with_cache()
            logger.info(f"Discovered {len(resources)} resources")
            
            # Step 2: Detect idle resources
            idle_resources = self._detect_idle_resources(resources)
            logger.info(f"Found {len(idle_resources)} idle resources")
            
            # Step 3: Check safety and plan actions
            planned_actions = self._plan_actions(idle_resources)
            logger.info(f"Planned {len(planned_actions)} safe actions")
            
            if not planned_actions:
                logger.info("No safe actions to execute")
                return 0
            
            # Step 4: Execute based on mode
            if self.config.get("dry_run_mode", False):
                self._handle_dry_run(planned_actions)
                return 0  # No actual actions in dry run
            elif self.config.get("approval_required", False):
                return self._handle_approval_workflow(planned_actions)
            else:
                return self._execute_actions(planned_actions)
                
        except Exception as e:
            logger.error(f"Prevention workflow failed: {e}", exc_info=True)
            self.notification_service.send_error_notification(e, {
                "threshold_event": asdict(threshold_event),
                "workflow_start": workflow_start.isoformat()
            })
            return 0
    
    def _discover_resources_with_cache(self) -> List[Resource]:
        """
        Discover resources with inventory caching.
        
        Refreshes inventory only if it's older than configured interval.
        
        Returns:
            List of discovered resources
        """
        last_refresh = self.config.get("last_inventory_refresh")
        refresh_interval = self.config.get("inventory_refresh_minutes", 15)
        
        should_refresh = True
        if last_refresh:
            try:
                last_refresh_dt = datetime.fromisoformat(last_refresh)
                minutes_since_refresh = (datetime.now(UTC) - last_refresh_dt).total_seconds() / 60
                should_refresh = minutes_since_refresh >= refresh_interval
            except Exception:
                should_refresh = True
        
        if should_refresh:
            logger.info("Refreshing resource inventory")
            resources = self.resource_manager.discover_resources(
                self.config.get("enabled_services", [])
            )
            self.resource_manager.update_inventory(resources)
            self.config["last_inventory_refresh"] = datetime.now(UTC).isoformat()
            self._save_config_to_dynamodb()
            return resources
        else:
            logger.info("Using cached resource inventory")
            # In a real implementation, would load from DynamoDB
            # For now, do a fresh discovery
            return self.resource_manager.discover_resources(
                self.config.get("enabled_services", [])
            )
    
    def _detect_idle_resources(self, resources: List[Resource]) -> List[tuple]:
        """
        Detect which resources are idle.
        
        Args:
            resources: List of resources to check
            
        Returns:
            List of tuples (resource, metadata, idle_status) for idle resources
        """
        idle_resources = []
        
        for resource in resources:
            try:
                metadata = self.resource_manager.get_resource_metadata(resource)
                idle_status = self.idle_detector.is_resource_idle(resource, metadata)
                
                if idle_status.is_idle:
                    idle_resources.append((resource, metadata, idle_status))
                    logger.debug(f"Resource {resource.resource_id} is idle: {idle_status.metrics_used}")
                    
            except Exception as e:
                logger.warning(f"Failed to check idle status for {resource.resource_id}: {e}")
                continue
        
        return idle_resources
    
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
                
                # Check safety
                safety_check = self.safety_guard.is_action_safe(resource, action)
                
                if safety_check.is_safe:
                    # Calculate estimated savings (monthly)
                    estimated_savings = metadata.cost_per_hour * 24 * 30
                    
                    planned_action = PlannedAction(
                        resource_id=resource.resource_id,
                        resource_type=resource.resource_type,
                        action=action,
                        reason=f"Idle for {idle_status.idle_duration} minutes",
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
        action_map = {
            "ec2": "stop",
            "rds": "stop",
            "lambda": "limit_concurrency",
            "ebs": "snapshot_and_delete",
            "dynamodb": "switch_to_ondemand",
            "nat_gateway": "delete"
        }
        return action_map.get(resource.resource_type, "stop")
    
    def _handle_dry_run(self, planned_actions: List[PlannedAction]) -> None:
        """
        Handle dry run mode - log actions without executing.
        
        Args:
            planned_actions: List of planned actions
        """
        logger.info(f"DRY RUN: Would execute {len(planned_actions)} actions")
        
        total_savings = sum(action.estimated_savings for action in planned_actions)
        
        for action in planned_actions:
            logger.info(
                f"DRY RUN: Would {action.action} {action.resource_id} "
                f"(type: {action.resource_type}, reason: {action.reason}, "
                f"savings: ${action.estimated_savings:.2f}/month)"
            )
        
        logger.info(f"DRY RUN: Total estimated savings: ${total_savings:.2f}/month")
        
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
            return 0
    
    def _execute_actions(self, planned_actions: List[PlannedAction]) -> int:
        """
        Execute planned actions.
        
        Args:
            planned_actions: List of planned actions
            
        Returns:
            Number of successfully executed actions
        """
        logger.info(f"Executing {len(planned_actions)} actions")
        
        # Sort by cost impact (highest first) - Property 13
        planned_actions.sort(key=lambda x: x.estimated_savings, reverse=True)
        
        results = []
        successful_count = 0
        
        for planned_action in planned_actions:
            try:
                # Create Resource object from planned action
                # In real implementation, would load full resource from inventory
                resource = Resource(
                    resource_id=planned_action.resource_id,
                    resource_type=planned_action.resource_type,
                    service=planned_action.resource_type,
                    region="us-east-1",  # Would be loaded from inventory
                    tags={},
                    state="running",
                    creation_date=datetime.now(UTC).isoformat()
                )
                
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
    
    def get_status(self) -> Dict[str, Any]:
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
        return {
            "enabled": self.config.get("enabled", False),
            "dry_run_mode": self.config.get("dry_run_mode", False),
            "approval_required": self.config.get("approval_required", False),
            "enabled_services": self.config.get("enabled_services", []),
            "budget_thresholds": self.config.get("budget_thresholds", {}),
            "poll_interval_minutes": self.config.get("poll_interval_minutes", 5),
            "inventory_refresh_minutes": self.config.get("inventory_refresh_minutes", 15),
            "last_run": self.config.get("last_run"),
            "last_inventory_refresh": self.config.get("last_inventory_refresh"),
        }
    
    def enable(self) -> None:
        """Enable automated prevention."""
        self.config["enabled"] = True
        self._save_config_to_dynamodb()
        logger.info("Automated prevention enabled")
    
    def disable(self) -> None:
        """Disable automated prevention."""
        self.config["enabled"] = False
        self._save_config_to_dynamodb()
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
        merged_config = {**self.config, **new_config}
        
        # Validate merged config
        validated_config = self._validate_config(merged_config)
        
        # Apply validated config
        self.config = validated_config
        self._save_config_to_dynamodb()
        
        logger.info(f"Configuration updated: {new_config}")
    
    def get_resources(self, filters: Optional[Dict[str, Any]] = None) -> List[Resource]:
        """
        Get resources from inventory with optional filters.
        
        Args:
            filters: Optional filters (service, state, etc.)
            
        Returns:
            List of resources matching filters
        """
        # Discover resources
        resources = self.resource_manager.discover_resources(
            self.config.get("enabled_services", [])
        )
        
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
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get action history from audit logs.
        
        Args:
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            limit: Maximum number of records to return
            
        Returns:
            List of action history records
        """
        # In real implementation, would query DynamoDB prevention-audit table
        # For now, return empty list
        logger.info(f"Querying action history: start={start_date}, end={end_date}, limit={limit}")
        return []
    
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
                    "restored_state": result.restored_state,
                    "timestamp": result.timestamp
                }
            else:
                logger.warning(f"Failed to rollback action {action_id}")
                return {
                    "success": False,
                    "action_id": action_id,
                    "error": "Rollback failed"
                }
                
        except Exception as e:
            logger.error(f"Error during rollback of action {action_id}: {e}")
            return {
                "success": False,
                "action_id": action_id,
                "error": str(e)
            }
