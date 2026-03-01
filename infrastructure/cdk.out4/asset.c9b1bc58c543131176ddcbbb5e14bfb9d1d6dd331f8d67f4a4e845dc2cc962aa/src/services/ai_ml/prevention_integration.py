"""
Prevention Integration for AI/ML Workload Cost Management.

This module integrates Phase 6 (AI/ML) with Phase 3 (Prevention) by:
1. Extending prevention to stop idle GPU instances
2. Tracking GPU cost savings from prevention actions
3. Providing GPU-specific prevention recommendations

Requirements: IR-2.3
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class GPUPreventionAction:
    """GPU prevention action data model."""
    action_id: str
    instance_id: str
    instance_type: str
    action_type: str  # "stop", "terminate", "downsize"
    reason: str
    idle_hours: float
    cost_saved: float  # Projected cost savings
    timestamp: str
    status: str  # "planned", "executed", "failed"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class GPUCostSavings:
    """GPU cost savings tracking data model."""
    period_start: str
    period_end: str
    total_savings: float
    actions_count: int
    instances_stopped: int
    instances_terminated: int
    avg_idle_hours: float
    breakdown_by_instance_type: Dict[str, float]
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class GPUPreventionIntegration:
    """
    Integrates AI/ML idle GPU detection with prevention engine.
    
    Requirements: IR-2.3
    """
    
    def __init__(
        self,
        idle_gpu_detector,
        prevention_engine,
        dynamodb_client,
        ec2_client=None
    ):
        """
        Initialize GPU Prevention Integration.
        
        Args:
            idle_gpu_detector: IdleGPUDetector instance from Phase 6
            prevention_engine: PreventionEngine instance from Phase 3
            dynamodb_client: DynamoDB client for tracking savings
            ec2_client: EC2 client for instance actions (optional)
        """
        self.idle_gpu_detector = idle_gpu_detector
        self.prevention_engine = prevention_engine
        self.dynamodb = dynamodb_client
        self.ec2 = ec2_client
        
        # DynamoDB table for tracking GPU prevention actions
        self.actions_table = "gpu_prevention_actions"
        self.savings_table = "gpu_cost_savings"
    
    def run_gpu_prevention_cycle(
        self,
        start_date: str,
        end_date: str,
        threshold: float = 10.0,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Run prevention cycle for idle GPU instances.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            threshold: GPU utilization threshold (default: 10%)
            dry_run: If True, only plan actions without executing
            
        Returns:
            Dict with prevention cycle results
            
        Requirements: IR-2.3
        """
        logger.info(f"Running GPU prevention cycle (dry_run={dry_run})")
        
        # Identify idle GPUs
        idle_gpus = self.idle_gpu_detector.identify_idle_gpus(
            start_date,
            end_date,
            threshold
        )
        
        if not idle_gpus:
            logger.info("No idle GPUs found")
            return {
                "success": True,
                "idle_gpus_found": 0,
                "actions_planned": 0,
                "actions_executed": 0,
                "total_savings": 0.0,
                "dry_run": dry_run
            }
        
        # Plan prevention actions
        planned_actions = self._plan_gpu_prevention_actions(idle_gpus)
        
        # Execute actions (if not dry run)
        executed_actions = []
        if not dry_run:
            executed_actions = self._execute_gpu_prevention_actions(planned_actions)
        
        # Calculate total savings
        total_savings = sum(action.cost_saved for action in planned_actions)
        
        # Store actions in DynamoDB
        self._store_prevention_actions(planned_actions if dry_run else executed_actions)
        
        # Update savings tracking
        self._update_savings_tracking(planned_actions if dry_run else executed_actions)
        
        return {
            "success": True,
            "idle_gpus_found": len(idle_gpus),
            "actions_planned": len(planned_actions),
            "actions_executed": len(executed_actions),
            "total_savings": total_savings,
            "dry_run": dry_run
        }
    
    def get_gpu_cost_savings(
        self,
        start_date: str,
        end_date: str
    ) -> GPUCostSavings:
        """
        Get GPU cost savings from prevention actions.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            GPUCostSavings object
            
        Requirements: IR-2.3
        """
        logger.info(f"Retrieving GPU cost savings from {start_date} to {end_date}")
        
        # Query prevention actions from DynamoDB
        actions = self._query_prevention_actions(start_date, end_date)
        
        if not actions:
            return GPUCostSavings(
                period_start=start_date,
                period_end=end_date,
                total_savings=0.0,
                actions_count=0,
                instances_stopped=0,
                instances_terminated=0,
                avg_idle_hours=0.0,
                breakdown_by_instance_type={}
            )
        
        # Calculate metrics
        total_savings = sum(action.cost_saved for action in actions)
        instances_stopped = sum(1 for action in actions if action.action_type == "stop")
        instances_terminated = sum(1 for action in actions if action.action_type == "terminate")
        avg_idle_hours = sum(action.idle_hours for action in actions) / len(actions)
        
        # Breakdown by instance type
        breakdown = {}
        for action in actions:
            if action.instance_type not in breakdown:
                breakdown[action.instance_type] = 0.0
            breakdown[action.instance_type] += action.cost_saved
        
        return GPUCostSavings(
            period_start=start_date,
            period_end=end_date,
            total_savings=total_savings,
            actions_count=len(actions),
            instances_stopped=instances_stopped,
            instances_terminated=instances_terminated,
            avg_idle_hours=avg_idle_hours,
            breakdown_by_instance_type=breakdown
        )
    
    def _plan_gpu_prevention_actions(
        self,
        idle_gpus: List
    ) -> List[GPUPreventionAction]:
        """
        Plan prevention actions for idle GPUs.
        
        Args:
            idle_gpus: List of IdleGPU objects
            
        Returns:
            List of GPUPreventionAction objects
        """
        planned_actions = []
        
        for idle_gpu in idle_gpus:
            # Determine action type based on utilization and idle time
            action_type = self._determine_action_type(
                idle_gpu.utilization,
                idle_gpu.idle_hours,
                idle_gpu.wasted_cost
            )
            
            # Calculate projected savings
            cost_saved = self._calculate_projected_savings(
                idle_gpu,
                action_type
            )
            
            action = GPUPreventionAction(
                action_id=f"gpu-prevent-{idle_gpu.instance_id}-{datetime.utcnow().timestamp()}",
                instance_id=idle_gpu.instance_id,
                instance_type=idle_gpu.instance_type,
                action_type=action_type,
                reason=f"GPU utilization {idle_gpu.utilization:.1f}% below threshold for {idle_gpu.idle_hours:.1f} hours",
                idle_hours=idle_gpu.idle_hours,
                cost_saved=cost_saved,
                timestamp=datetime.utcnow().isoformat(),
                status="planned"
            )
            
            planned_actions.append(action)
        
        return planned_actions
    
    def _execute_gpu_prevention_actions(
        self,
        planned_actions: List[GPUPreventionAction]
    ) -> List[GPUPreventionAction]:
        """
        Execute planned GPU prevention actions.
        
        Args:
            planned_actions: List of GPUPreventionAction objects
            
        Returns:
            List of executed GPUPreventionAction objects
        """
        executed_actions = []
        
        for action in planned_actions:
            try:
                # Execute action via EC2 API
                if action.action_type == "stop":
                    self._stop_instance(action.instance_id)
                elif action.action_type == "terminate":
                    self._terminate_instance(action.instance_id)
                
                # Mark as executed
                action.status = "executed"
                executed_actions.append(action)
                
                logger.info(f"Executed {action.action_type} for {action.instance_id}")
                
            except Exception as e:
                logger.error(f"Failed to execute action for {action.instance_id}: {e}")
                action.status = "failed"
        
        return executed_actions
    
    def _determine_action_type(
        self,
        utilization: float,
        idle_hours: float,
        wasted_cost: float
    ) -> str:
        """
        Determine appropriate action type based on idle metrics.
        
        Args:
            utilization: Average GPU utilization
            idle_hours: Total idle hours
            wasted_cost: Wasted cost in USD
            
        Returns:
            Action type: "stop", "terminate", or "monitor"
        """
        # Very low utilization and high cost -> terminate
        if utilization < 5.0 and wasted_cost > 500.0:
            return "terminate"
        
        # Low utilization and moderate cost -> stop
        elif utilization < 10.0 and wasted_cost > 100.0:
            return "stop"
        
        # Otherwise just monitor
        else:
            return "monitor"
    
    def _calculate_projected_savings(
        self,
        idle_gpu,
        action_type: str
    ) -> float:
        """
        Calculate projected cost savings from action.
        
        Args:
            idle_gpu: IdleGPU object
            action_type: Action type ("stop", "terminate", "monitor")
            
        Returns:
            Projected savings in USD
        """
        if action_type == "stop":
            # Assume instance will be stopped for 12 hours/day
            return idle_gpu.cost_per_hour * 12 * 30  # Monthly savings
        
        elif action_type == "terminate":
            # Full cost savings
            return idle_gpu.cost_per_hour * 24 * 30  # Monthly savings
        
        else:
            return 0.0
    
    def _stop_instance(self, instance_id: str) -> None:
        """Stop EC2 instance."""
        if self.ec2:
            self.ec2.stop_instances(InstanceIds=[instance_id])
            logger.info(f"Stopped instance {instance_id}")
        else:
            logger.warning("EC2 client not available, skipping stop action")
    
    def _terminate_instance(self, instance_id: str) -> None:
        """Terminate EC2 instance."""
        if self.ec2:
            self.ec2.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated instance {instance_id}")
        else:
            logger.warning("EC2 client not available, skipping terminate action")
    
    def _store_prevention_actions(
        self,
        actions: List[GPUPreventionAction]
    ) -> None:
        """Store prevention actions in DynamoDB."""
        logger.info(f"Storing {len(actions)} prevention actions")
        
        if not self.dynamodb:
            logger.warning("DynamoDB client not available, skipping storage")
            return
        
        try:
            for action in actions:
                item = {
                    "action_id": {"S": action.action_id},
                    "instance_id": {"S": action.instance_id},
                    "instance_type": {"S": action.instance_type},
                    "action_type": {"S": action.action_type},
                    "reason": {"S": action.reason},
                    "idle_hours": {"N": str(action.idle_hours)},
                    "cost_saved": {"N": str(action.cost_saved)},
                    "timestamp": {"S": action.timestamp},
                    "status": {"S": action.status}
                }
                
                self.dynamodb.put_item(
                    TableName=self.actions_table,
                    Item=item
                )
            
            logger.info(f"Successfully stored {len(actions)} prevention actions")
            
        except Exception as e:
            logger.error(f"Failed to store prevention actions: {e}")
    
    def _update_savings_tracking(
        self,
        actions: List[GPUPreventionAction]
    ) -> None:
        """Update savings tracking in DynamoDB."""
        logger.info(f"Updating savings tracking for {len(actions)} actions")
        
        if not self.dynamodb or not actions:
            return
        
        try:
            # Calculate aggregated metrics
            total_savings = sum(action.cost_saved for action in actions)
            instances_stopped = sum(1 for action in actions if action.action_type == "stop")
            instances_terminated = sum(1 for action in actions if action.action_type == "terminate")
            avg_idle_hours = sum(action.idle_hours for action in actions) / len(actions)
            
            # Breakdown by instance type
            breakdown = {}
            for action in actions:
                if action.instance_type not in breakdown:
                    breakdown[action.instance_type] = 0.0
                breakdown[action.instance_type] += action.cost_saved
            
            # Store aggregated savings
            timestamp = datetime.utcnow().isoformat()
            item = {
                "savings_id": {"S": f"gpu-savings-{timestamp}"},
                "timestamp": {"S": timestamp},
                "total_savings": {"N": str(total_savings)},
                "actions_count": {"N": str(len(actions))},
                "instances_stopped": {"N": str(instances_stopped)},
                "instances_terminated": {"N": str(instances_terminated)},
                "avg_idle_hours": {"N": str(avg_idle_hours)},
                "breakdown": {"M": {k: {"N": str(v)} for k, v in breakdown.items()}}
            }
            
            self.dynamodb.put_item(
                TableName=self.savings_table,
                Item=item
            )
            
            logger.info(f"Successfully updated savings tracking: ${total_savings:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to update savings tracking: {e}")
    
    def _query_prevention_actions(
        self,
        start_date: str,
        end_date: str
    ) -> List[GPUPreventionAction]:
        """Query prevention actions from DynamoDB."""
        logger.info(f"Querying prevention actions from {start_date} to {end_date}")
        
        if not self.dynamodb:
            logger.warning("DynamoDB client not available")
            return []
        
        try:
            # Convert dates to ISO format for comparison
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            
            # Scan table for actions in date range
            # In production, would use a GSI on timestamp for better performance
            response = self.dynamodb.scan(
                TableName=self.actions_table,
                FilterExpression="timestamp BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":start": {"S": start_dt.isoformat()},
                    ":end": {"S": end_dt.isoformat()}
                }
            )
            
            actions = []
            for item in response.get("Items", []):
                action = GPUPreventionAction(
                    action_id=item["action_id"]["S"],
                    instance_id=item["instance_id"]["S"],
                    instance_type=item["instance_type"]["S"],
                    action_type=item["action_type"]["S"],
                    reason=item["reason"]["S"],
                    idle_hours=float(item["idle_hours"]["N"]),
                    cost_saved=float(item["cost_saved"]["N"]),
                    timestamp=item["timestamp"]["S"],
                    status=item["status"]["S"]
                )
                actions.append(action)
            
            logger.info(f"Retrieved {len(actions)} prevention actions")
            return actions
            
        except Exception as e:
            logger.error(f"Failed to query prevention actions: {e}")
            return []
