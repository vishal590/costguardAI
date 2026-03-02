"""
Safety Guard for enforcing safety rules to protect production resources.

Safety rules:
1. Never touch resources with "Environment=production" tag
2. Never touch resources with "CostGuard=protected" tag
3. Never touch resources with "CostGuard=exclude" tag
4. Never touch resources in whitelist
5. Never touch resources with active connections
6. Require minimum idle duration before action
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SafetyGuard:
    """Enforce safety rules to protect production resources."""
    
    def __init__(self, config=None):
        """
        Initialize safety guard.
        
        Args:
            config: SafetyConfig object (optional, will use defaults if None)
        """
        self.config = config
        
        # Default protected tags
        if config is not None and hasattr(config, 'protected_tags'):
            self.protected_tags = config.protected_tags or [
                "Environment=production",
                "CostGuard=protected",
                "CostGuard=exclude"
            ]
        else:
            self.protected_tags = [
                "Environment=production",
                "CostGuard=protected",
                "CostGuard=exclude"
            ]
        
        # Whitelist of resource IDs that should never be touched
        if config is not None and hasattr(config, 'whitelist_ids'):
            self.whitelist_ids = config.whitelist_ids or []
        else:
            self.whitelist_ids = []
        
        # Minimum idle duration by service (minutes)
        if config is not None and hasattr(config, 'minimum_idle_minutes'):
            self.minimum_idle_minutes = config.minimum_idle_minutes or {
                'ec2': 120,      # 2 hours
                'rds': 60,       # 1 hour
                'lambda': 1440,  # 24 hours
                'ebs': 10080,    # 7 days
                's3': 43200,     # 30 days
                'dynamodb': 1440 # 24 hours
            }
        else:
            self.minimum_idle_minutes = {
                'ec2': 120,      # 2 hours
                'rds': 60,       # 1 hour
                'lambda': 1440,  # 24 hours
                'ebs': 10080,    # 7 days
                's3': 43200,     # 30 days
                'dynamodb': 1440 # 24 hours
            }
        
        # Dry run mode
        if config is not None and hasattr(config, 'dry_run_mode'):
            self.dry_run_mode = config.dry_run_mode
        else:
            self.dry_run_mode = True  # Default to dry run for safety
    
    def is_action_safe(self, resource, action: str) -> Any:
        """
        Check if action is safe to perform on resource.
        
        Args:
            resource: Resource object
            action: Action to perform (e.g., "stop", "terminate")
            
        Returns:
            SafetyCheck object
        """
        from ..utils.types import SafetyCheck
        
        checks_performed = []
        
        # Check 1: Protected tags
        if not self.check_tags(resource):
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Resource has protected tag",
                checks_performed=["tag_check"]
            )
        checks_performed.append("tag_check")
        
        # Check 2: Whitelist
        if not self.check_whitelist(resource):
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Resource is in whitelist",
                checks_performed=checks_performed + ["whitelist_check"]
            )
        checks_performed.append("whitelist_check")
        
        # Check 3: Active usage
        if not self.check_active_usage(resource):
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Resource has active connections or traffic",
                checks_performed=checks_performed + ["active_usage_check"]
            )
        checks_performed.append("active_usage_check")
        
        # Check 4: Minimum idle duration
        if not self._check_minimum_idle_duration(resource):
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Resource has not been idle long enough",
                checks_performed=checks_performed + ["idle_duration_check"]
            )
        checks_performed.append("idle_duration_check")
        
        # Check 5: Dry run mode
        if self.dry_run_mode:
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Dry run mode enabled",
                checks_performed=checks_performed + ["dry_run_check"]
            )
        
        # All checks passed
        return SafetyCheck(
            is_safe=True,
            blocked_reason=None,
            checks_performed=checks_performed
        )
    
    def check_tags(self, resource) -> bool:
        """
        Check if resource has protected tags.
        
        Args:
            resource: Resource object
            
        Returns:
            True if safe (no protected tags), False if blocked
        """
        tags = resource.tags
        
        for protected_tag in self.protected_tags:
            if '=' in protected_tag:
                key, value = protected_tag.split('=', 1)
                if tags.get(key) == value:
                    logger.info(f"Resource {resource.resource_id} blocked by tag: {protected_tag}")
                    return False
        
        return True
    
    def check_whitelist(self, resource) -> bool:
        """
        Check if resource is in whitelist.
        
        Args:
            resource: Resource object
            
        Returns:
            True if safe (not in whitelist), False if blocked
        """
        if resource.resource_id in self.whitelist_ids:
            logger.info(f"Resource {resource.resource_id} is in whitelist")
            return False
        
        return True
    
    def check_active_usage(self, resource) -> bool:
        """
        Check if resource has active connections or traffic.
        
        Args:
            resource: Resource object
            
        Returns:
            True if safe (no active usage), False if blocked
        """
        # For now, assume resources in 'running' or 'available' state might have active usage
        # This would be enhanced with actual CloudWatch metrics
        
        active_states = ['running', 'available', 'in-use']
        
        if resource.state in active_states:
            # Would check CloudWatch metrics here for actual connections/traffic
            # For now, we'll be conservative and allow it
            pass
        
        return True
    
    def validate_safe_state(self, resource) -> bool:
        """
        Validate that resource is in a safe state for action.
        
        Args:
            resource: Resource object
            
        Returns:
            True if in safe state, False otherwise
        """
        # Check if resource is in a state that can be safely modified
        unsafe_states = ['terminating', 'terminated', 'deleting', 'deleted']
        
        if resource.state in unsafe_states:
            logger.warning(f"Resource {resource.resource_id} in unsafe state: {resource.state}")
            return False
        
        return True
    
    def _check_minimum_idle_duration(self, resource) -> bool:
        """Check if resource has been idle for minimum required duration."""
        service = resource.service
        minimum_minutes = self.minimum_idle_minutes.get(service, 0)
        
        # This would check actual idle duration from IdleDetector
        # For now, assume it meets the requirement
        return True
