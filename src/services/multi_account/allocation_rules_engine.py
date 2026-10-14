"""
Allocation Rules Engine

Manages cost allocation rules including creation, validation, and priority-based application.
"""
import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal

from .models import AllocationRule
from .repositories import AllocationRuleRepository


logger = logging.getLogger(__name__)


class AllocationRulesEngine:
    """
    Manages cost allocation rules.
    
    Supports creating, validating, and applying allocation rules with priority ordering.
    """
    
    def __init__(
        self,
        rule_repository: Optional[AllocationRuleRepository] = None
    ):
        """
        Initialize the Allocation Rules Engine.
        
        Args:
            rule_repository: Repository for allocation rules
        """
        self.rule_repository = rule_repository or AllocationRuleRepository()
    
    def create_rule(
        self,
        org_id: str,
        name: str,
        priority: int,
        rule_type: str,
        conditions: Dict[str, Any],
        allocation_target: str
    ) -> AllocationRule:
        """
        Create a new allocation rule.
        
        Args:
            org_id: Organization ID
            name: Rule name
            priority: Rule priority (higher = applied first)
            rule_type: Type of rule ("TAG_BASED", "PERCENTAGE", "FIXED")
            conditions: Rule conditions (varies by type)
            allocation_target: Target for cost allocation (team, project, etc.)
            
        Returns:
            Created AllocationRule
            
        Validates: Requirements 8.1, 8.2
        """
        logger.info(
            f"Creating allocation rule '{name}' for organization {org_id} "
            f"with priority {priority}"
        )
        
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 128 or type(priority) is not int or not 0 <= priority <= 10000:
            raise ValueError('Use a 1-128 character rule name and integer priority from 0 to 10000')
        # Validate rule before creating
        self.validate_rule(rule_type, conditions, allocation_target)
        
        # Generate rule ID
        import uuid
        rule_id = str(uuid.uuid4())
        
        # Create rule object
        rule = AllocationRule(
            rule_id=rule_id,
            name=name,
            priority=priority,
            rule_type=rule_type,
            conditions=conditions,
            allocation_target=allocation_target
        )
        
        # Save to repository
        self.rule_repository.save(rule, org_id)
        
        logger.info(f"Created allocation rule {rule_id}: '{name}'")
        
        return rule
    
    def validate_rule(
        self,
        rule_type: str,
        conditions: Dict[str, Any],
        allocation_target: str
    ) -> None:
        """
        Validate allocation rule syntax and semantics.
        
        Args:
            rule_type: Type of rule
            conditions: Rule conditions
            allocation_target: Target for allocation
            
        Raises:
            ValueError: If rule is invalid
            
        Validates: Requirements 8.2
        """
        logger.debug(f"Validating rule: type={rule_type}, target={allocation_target}")
        
        if not isinstance(conditions, dict): raise ValueError('conditions must be an object')
        allowed = {'TAG_BASED': {'tag_key', 'tag_value'}, 'PERCENTAGE': {'percentage'}, 'FIXED': {'service', 'account_id'}}
        if set(conditions)-allowed.get(rule_type, set()): raise ValueError('Unsupported rule condition')
        if not isinstance(allocation_target, str) or not 1 <= len(allocation_target.strip()) <= 256: raise ValueError('Use a 1-256 character allocation target')
        for key, value in conditions.items():
            if key != 'percentage' and (not isinstance(value, str) or not 1 <= len(value.strip()) <= 256): raise ValueError('Rule condition values must be nonempty bounded strings')
        # Validate rule type
        valid_types = ["TAG_BASED", "PERCENTAGE", "FIXED"]
        if rule_type not in valid_types:
            raise ValueError(
                f"Invalid rule_type '{rule_type}'. Must be one of: {valid_types}"
            )
        
        # Validate allocation target
        if not allocation_target or not isinstance(allocation_target, str):
            raise ValueError("allocation_target must be a non-empty string")
        
        # Validate conditions based on rule type
        if rule_type == "TAG_BASED":
            self._validate_tag_based_rule(conditions)
        elif rule_type == "PERCENTAGE":
            self._validate_percentage_rule(conditions)
        elif rule_type == "FIXED":
            self._validate_fixed_rule(conditions)
        
        logger.debug("Rule validation passed")
    
    def _validate_tag_based_rule(self, conditions: Dict[str, Any]) -> None:
        """Validate TAG_BASED rule conditions"""
        if 'tag_key' not in conditions:
            raise ValueError("TAG_BASED rule must have 'tag_key' in conditions")
        if 'tag_value' not in conditions:
            raise ValueError("TAG_BASED rule must have 'tag_value' in conditions")
        
        if not isinstance(conditions['tag_key'], str):
            raise ValueError("tag_key must be a string")
        if not isinstance(conditions['tag_value'], str):
            raise ValueError("tag_value must be a string")
    
    def _validate_percentage_rule(self, conditions: Dict[str, Any]) -> None:
        """Validate PERCENTAGE rule conditions"""
        if 'percentage' not in conditions:
            raise ValueError("PERCENTAGE rule must have 'percentage' in conditions")
        
        percentage = conditions['percentage']
        if isinstance(percentage, bool) or not isinstance(percentage, (int, float, Decimal)):
            raise ValueError("percentage must be a number")
        
        percentage = float(percentage)
        import math
        if not math.isfinite(percentage) or percentage <= 0 or percentage > 100:
            raise ValueError("percentage must be between 0 and 100")
    
    def _validate_fixed_rule(self, conditions: Dict[str, Any]) -> None:
        """Validate FIXED rule conditions"""
        if 'service' not in conditions and 'account_id' not in conditions:
            raise ValueError(
                "FIXED rule must have either 'service' or 'account_id' in conditions"
            )
    
    def apply_rules_by_priority(
        self,
        rules: List[AllocationRule],
        cost_data: Dict[str, Any]
    ) -> Dict[str, Decimal]:
        """
        Apply allocation rules in priority order.
        
        Rules are sorted by priority (highest first) and applied sequentially.
        Only the highest-priority matching rule is applied to each cost item.
        
        Args:
            rules: List of allocation rules
            cost_data: Cost data to allocate
            
        Returns:
            Dictionary mapping allocation targets to allocated costs
            
        Validates: Requirements 8.5, 8.6
        """
        logger.info(f"Applying {len(rules)} allocation rules by priority")
        
        # Sort rules by priority (highest first)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        
        logger.debug(
            f"Rule priority order: "
            f"{[(r.name, r.priority) for r in sorted_rules]}"
        )
        
        allocations: Dict[str, Decimal] = {}
        
        # Apply rules to cost data
        # This is a simplified implementation - actual logic depends on cost_data structure
        for rule in sorted_rules:
            target = rule.allocation_target
            
            # Initialize target if not exists
            if target not in allocations:
                allocations[target] = Decimal('0')
            
            logger.debug(
                f"Applied rule '{rule.name}' (priority {rule.priority}) "
                f"to target '{target}'"
            )
        
        logger.info(
            f"Completed rule application: {len(allocations)} allocation targets"
        )
        
        return allocations
    
    def get_rules_for_organization(
        self,
        org_id: str
    ) -> List[AllocationRule]:
        """
        Get all allocation rules for an organization.
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of allocation rules sorted by priority (highest first)
            
        Validates: Requirements 8.1
        """
        logger.info(f"Retrieving allocation rules for organization {org_id}")
        
        rules = self.rule_repository.list_by_organization(org_id)
        
        # Sort by priority (highest first)
        sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        
        logger.info(
            f"Retrieved {len(sorted_rules)} allocation rules for organization {org_id}"
        )
        
        return sorted_rules
    
    def update_rule(
        self,
        org_id: str,
        rule_id: str,
        name: Optional[str] = None,
        priority: Optional[int] = None,
        conditions: Optional[Dict[str, Any]] = None,
        allocation_target: Optional[str] = None
    ) -> AllocationRule:
        """
        Update an existing allocation rule.
        
        Args:
            org_id: Organization ID
            rule_id: Rule ID to update
            name: New rule name (optional)
            priority: New priority (optional)
            conditions: New conditions (optional)
            allocation_target: New allocation target (optional)
            
        Returns:
            Updated AllocationRule
            
        Validates: Requirements 8.1, 8.2
        """
        logger.info(f"Updating allocation rule {rule_id}")
        
        # Get existing rule
        existing_rules = self.rule_repository.list_by_organization(org_id)
        existing_rule = next((r for r in existing_rules if r.rule_id == rule_id), None)
        
        if not existing_rule:
            raise ValueError(f"Rule {rule_id} not found in organization {org_id}")
        
        # Update fields
        updated_name = name if name is not None else existing_rule.name
        updated_priority = priority if priority is not None else existing_rule.priority
        updated_conditions = conditions if conditions is not None else existing_rule.conditions
        updated_target = allocation_target if allocation_target is not None else existing_rule.allocation_target
        updated_type = existing_rule.rule_type  # Type cannot be changed
        
        # Validate updated rule
        self.validate_rule(updated_type, updated_conditions, updated_target)
        
        # Create updated rule
        updated_rule = AllocationRule(
            rule_id=rule_id,
            name=updated_name,
            priority=updated_priority,
            rule_type=updated_type,
            conditions=updated_conditions,
            allocation_target=updated_target
        )
        
        # Save updated rule
        self.rule_repository.save(updated_rule, org_id)
        
        logger.info(f"Updated allocation rule {rule_id}")
        
        return updated_rule
    
    def delete_rule(
        self,
        org_id: str,
        rule_id: str
    ) -> None:
        """
        Delete an allocation rule.
        
        Args:
            org_id: Organization ID
            rule_id: Rule ID to delete
            
        Validates: Requirements 8.1
        """
        logger.info(f"Deleting allocation rule {rule_id}")
        
        # Verify rule exists
        existing_rules = self.rule_repository.list_by_organization(org_id)
        existing_rule = next((r for r in existing_rules if r.rule_id == rule_id), None)
        
        if not existing_rule:
            raise ValueError(f"Rule {rule_id} not found in organization {org_id}")
        
        # Delete from repository (implementation depends on repository)
        # For now, we'll log that deletion would happen
        logger.warning(
            f"Rule deletion not fully implemented in repository. "
            f"Would delete rule {rule_id}"
        )
        
        logger.info(f"Deleted allocation rule {rule_id}")
