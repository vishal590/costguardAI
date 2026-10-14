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
        
        baseline_tags = ['Environment=production', 'CostGuard=protected', 'CostGuard=exclude']
        custom_tags = getattr(config, 'protected_tags', None) or []
        if not isinstance(custom_tags, list) or any(not isinstance(tag, str) or '=' not in tag
                or not all(part.strip() for part in tag.split('=', 1)) for tag in custom_tags):
            raise ValueError('Protected tags must be a list of nonempty key=value rules')
        self.protected_tags = list(dict.fromkeys(baseline_tags+custom_tags))

        # Whitelist of resource IDs that should never be touched
        if config is not None and hasattr(config, 'whitelist_ids'):
            self.whitelist_ids = config.whitelist_ids or []
        else:
            self.whitelist_ids = []
        
        if not isinstance(self.whitelist_ids, list) or any(not isinstance(value, str) or not value.strip() for value in self.whitelist_ids):
            raise ValueError('Protected resource IDs must be a list of nonempty strings')
        self.whitelist_ids = list(self.whitelist_ids)
        baseline_minutes = {'ec2': 120, 'rds': 60, 'lambda': 1440,
                            'ebs': 10080, 's3': 43200, 'dynamodb': 1440}
        custom_minutes = getattr(config, 'minimum_idle_minutes', None) or {}
        if not isinstance(custom_minutes, dict) or any(not isinstance(service, str)
                or isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for service, value in custom_minutes.items()):
            raise ValueError('Minimum observation durations must be positive integer minutes')
        self.minimum_idle_minutes = {**baseline_minutes, **custom_minutes}
        for service, minimum in baseline_minutes.items():
            self.minimum_idle_minutes[service] = max(minimum, self.minimum_idle_minutes[service])
        self.dry_run_mode = getattr(config, 'dry_run_mode', True)
        if not isinstance(self.dry_run_mode, bool): raise ValueError('Dry-run mode must be boolean')

    def is_action_safe(self, resource, action: str, idle_status=None, *, for_preview=False) -> Any:
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
        if not self.validate_safe_state(resource) or not self.check_active_usage(resource, idle_status):
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Fresh matching low-usage evidence or actionable state is unavailable",
                checks_performed=checks_performed + ["active_usage_check"]
            )
        checks_performed.append("active_usage_check")
        
        # Check 4: Minimum idle duration
        if not self._check_minimum_idle_duration(resource, idle_status):
            return SafetyCheck(
                is_safe=False,
                blocked_reason="Resource has not been idle long enough",
                checks_performed=checks_performed + ["idle_duration_check"]
            )
        checks_performed.append("idle_duration_check")
        
        # Check 5: Dry run mode
        if self.dry_run_mode and not for_preview:
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
        if not isinstance(tags, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in tags.items()):
            return False
        normalized = {(key.strip().casefold(), value.strip().casefold()) for key, value in tags.items()}
        for protected_tag in self.protected_tags:
            if '=' in protected_tag:
                key, value = protected_tag.split('=', 1)
                if (key.strip().casefold(), value.strip().casefold()) in normalized:
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
    
    def check_active_usage(self, resource, idle_status=None) -> bool:
        """Require fresh matching observations; absence never establishes safety."""
        from datetime import datetime, UTC
        from .time_values import parse_utc_timestamp
        try:
            if (idle_status is None or idle_status.resource_id != resource.resource_id
                    or not idle_status.is_idle or idle_status.observation_status != 'rule_matched'):
                return False
            end = parse_utc_timestamp(idle_status.window_end)
            start = parse_utc_timestamp(idle_status.window_start)
            age = (datetime.now(UTC)-end).total_seconds()
            return (0 <= age <= 900 and start < end
                    and (end-start).total_seconds() == idle_status.idle_duration*60)
        except (ValueError, TypeError, AttributeError):
            return False

    def validate_safe_state(self, resource) -> bool:
        """
        Validate that resource is in a safe state for action.
        
        Args:
            resource: Resource object
            
        Returns:
            True if in safe state, False otherwise
        """
        # Check if resource is in a state that can be safely modified
        allowed = {'ec2': {'running'}, 'rds': {'available'}, 'lambda': {'Active'}}
        if resource.state not in allowed.get(resource.service, set()):
            logger.warning(f"Resource {resource.resource_id} in unsafe state: {resource.state}")
            return False
        
        return True
    
    def _check_minimum_idle_duration(self, resource, idle_status=None) -> bool:
        """Require measured duration for a service with a configured minimum."""
        minimum = self.minimum_idle_minutes.get(resource.service)
        return (minimum is not None and minimum > 0 and idle_status is not None
                and self.check_active_usage(resource, idle_status)
                and idle_status.idle_duration >= minimum)
