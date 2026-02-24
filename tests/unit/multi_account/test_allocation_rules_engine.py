"""
Unit tests for Allocation Rules Engine
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from datetime import datetime

from src.services.multi_account.allocation_rules_engine import AllocationRulesEngine
from src.services.multi_account.models import AllocationRule


class TestAllocationRulesEngine:
    """Test suite for AllocationRulesEngine"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository"""
        return Mock()
    
    @pytest.fixture
    def engine(self, mock_repository):
        """Create AllocationRulesEngine with mock repository"""
        return AllocationRulesEngine(rule_repository=mock_repository)
    
    def test_create_rule_tag_based(self, engine, mock_repository):
        """Test creating a TAG_BASED allocation rule"""
        # Given: Rule parameters
        org_id = "o-123456789"
        name = "Team Engineering Rule"
        priority = 10
        rule_type = "TAG_BASED"
        conditions = {"tag_key": "Team", "tag_value": "Engineering"}
        allocation_target = "Engineering"
        
        # When: Creating rule
        with patch('uuid.uuid4', return_value='test-rule-id'):
            rule = engine.create_rule(
                org_id=org_id,
                name=name,
                priority=priority,
                rule_type=rule_type,
                conditions=conditions,
                allocation_target=allocation_target
            )
        
        # Then: Rule should be created and saved
        assert rule.rule_id == 'test-rule-id'
        assert rule.name == name
        assert rule.priority == priority
        assert rule.rule_type == rule_type
        assert rule.conditions == conditions
        assert rule.allocation_target == allocation_target
        
        mock_repository.save_rule.assert_called_once()
    
    def test_create_rule_percentage(self, engine, mock_repository):
        """Test creating a PERCENTAGE allocation rule"""
        # Given: Percentage rule parameters
        org_id = "o-123456789"
        name = "Split VPC Costs"
        priority = 5
        rule_type = "PERCENTAGE"
        conditions = {"percentage": 50.0, "service": "VPC"}
        allocation_target = "Infrastructure"
        
        # When: Creating rule
        with patch('uuid.uuid4', return_value='test-rule-id-2'):
            rule = engine.create_rule(
                org_id=org_id,
                name=name,
                priority=priority,
                rule_type=rule_type,
                conditions=conditions,
                allocation_target=allocation_target
            )
        
        # Then: Rule should be created
        assert rule.rule_id == 'test-rule-id-2'
        assert rule.rule_type == "PERCENTAGE"
        assert rule.conditions["percentage"] == 50.0
    
    def test_create_rule_fixed(self, engine, mock_repository):
        """Test creating a FIXED allocation rule"""
        # Given: Fixed rule parameters
        org_id = "o-123456789"
        name = "EC2 to DevOps"
        priority = 8
        rule_type = "FIXED"
        conditions = {"service": "EC2"}
        allocation_target = "DevOps"
        
        # When: Creating rule
        with patch('uuid.uuid4', return_value='test-rule-id-3'):
            rule = engine.create_rule(
                org_id=org_id,
                name=name,
                priority=priority,
                rule_type=rule_type,
                conditions=conditions,
                allocation_target=allocation_target
            )
        
        # Then: Rule should be created
        assert rule.rule_id == 'test-rule-id-3'
        assert rule.rule_type == "FIXED"
        assert rule.conditions["service"] == "EC2"
    
    def test_validate_rule_invalid_type(self, engine):
        """Test validation fails for invalid rule type"""
        # Given: Invalid rule type
        rule_type = "INVALID_TYPE"
        conditions = {}
        allocation_target = "Team"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="Invalid rule_type"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_rule_empty_target(self, engine):
        """Test validation fails for empty allocation target"""
        # Given: Empty allocation target
        rule_type = "TAG_BASED"
        conditions = {"tag_key": "Team", "tag_value": "Engineering"}
        allocation_target = ""
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="allocation_target must be a non-empty string"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_tag_based_rule_missing_tag_key(self, engine):
        """Test validation fails for TAG_BASED rule without tag_key"""
        # Given: TAG_BASED rule without tag_key
        rule_type = "TAG_BASED"
        conditions = {"tag_value": "Engineering"}
        allocation_target = "Engineering"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="must have 'tag_key'"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_tag_based_rule_missing_tag_value(self, engine):
        """Test validation fails for TAG_BASED rule without tag_value"""
        # Given: TAG_BASED rule without tag_value
        rule_type = "TAG_BASED"
        conditions = {"tag_key": "Team"}
        allocation_target = "Engineering"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="must have 'tag_value'"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_percentage_rule_missing_percentage(self, engine):
        """Test validation fails for PERCENTAGE rule without percentage"""
        # Given: PERCENTAGE rule without percentage
        rule_type = "PERCENTAGE"
        conditions = {}
        allocation_target = "Infrastructure"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="must have 'percentage'"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_percentage_rule_invalid_percentage(self, engine):
        """Test validation fails for invalid percentage value"""
        # Given: PERCENTAGE rule with invalid percentage
        rule_type = "PERCENTAGE"
        conditions = {"percentage": 150}  # > 100
        allocation_target = "Infrastructure"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="percentage must be between 0 and 100"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_percentage_rule_zero_percentage(self, engine):
        """Test validation fails for zero percentage"""
        # Given: PERCENTAGE rule with zero percentage
        rule_type = "PERCENTAGE"
        conditions = {"percentage": 0}
        allocation_target = "Infrastructure"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="percentage must be between 0 and 100"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_validate_fixed_rule_missing_conditions(self, engine):
        """Test validation fails for FIXED rule without service or account_id"""
        # Given: FIXED rule without required conditions
        rule_type = "FIXED"
        conditions = {}
        allocation_target = "DevOps"
        
        # When/Then: Validation should fail
        with pytest.raises(ValueError, match="must have either 'service' or 'account_id'"):
            engine.validate_rule(rule_type, conditions, allocation_target)
    
    def test_apply_rules_by_priority(self, engine):
        """Test applying rules in priority order"""
        # Given: Multiple rules with different priorities
        rules = [
            AllocationRule(
                rule_id="rule1",
                name="Low Priority",
                priority=5,
                rule_type="FIXED",
                conditions={"service": "S3"},
                allocation_target="Storage"
            ),
            AllocationRule(
                rule_id="rule2",
                name="High Priority",
                priority=10,
                rule_type="FIXED",
                conditions={"service": "EC2"},
                allocation_target="Compute"
            ),
            AllocationRule(
                rule_id="rule3",
                name="Medium Priority",
                priority=7,
                rule_type="TAG_BASED",
                conditions={"tag_key": "Team", "tag_value": "Data"},
                allocation_target="Data"
            )
        ]
        
        cost_data = {}
        
        # When: Applying rules
        allocations = engine.apply_rules_by_priority(rules, cost_data)
        
        # Then: Should return allocations dictionary
        assert isinstance(allocations, dict)
        assert "Storage" in allocations
        assert "Compute" in allocations
        assert "Data" in allocations
    
    def test_get_rules_for_organization(self, engine, mock_repository):
        """Test retrieving rules for an organization"""
        # Given: Organization with multiple rules
        org_id = "o-123456789"
        rules = [
            AllocationRule(
                rule_id="rule1",
                name="Rule 1",
                priority=5,
                rule_type="FIXED",
                conditions={"service": "S3"},
                allocation_target="Storage"
            ),
            AllocationRule(
                rule_id="rule2",
                name="Rule 2",
                priority=10,
                rule_type="FIXED",
                conditions={"service": "EC2"},
                allocation_target="Compute"
            )
        ]
        
        mock_repository.list_by_organization.return_value = rules
        
        # When: Getting rules
        result = engine.get_rules_for_organization(org_id)
        
        # Then: Rules should be sorted by priority (highest first)
        assert len(result) == 2
        assert result[0].priority == 10  # Highest priority first
        assert result[1].priority == 5
        
        mock_repository.list_by_organization.assert_called_once_with(org_id)
    
    def test_update_rule_name(self, engine, mock_repository):
        """Test updating rule name"""
        # Given: Existing rule
        org_id = "o-123456789"
        rule_id = "rule1"
        existing_rule = AllocationRule(
            rule_id=rule_id,
            name="Old Name",
            priority=5,
            rule_type="FIXED",
            conditions={"service": "S3"},
            allocation_target="Storage"
        )
        
        mock_repository.list_by_organization.return_value = [existing_rule]
        
        # When: Updating rule name
        updated_rule = engine.update_rule(
            org_id=org_id,
            rule_id=rule_id,
            name="New Name"
        )
        
        # Then: Name should be updated
        assert updated_rule.name == "New Name"
        assert updated_rule.priority == 5  # Unchanged
        assert updated_rule.rule_type == "FIXED"  # Unchanged
        
        mock_repository.save_rule.assert_called_once()
    
    def test_update_rule_priority(self, engine, mock_repository):
        """Test updating rule priority"""
        # Given: Existing rule
        org_id = "o-123456789"
        rule_id = "rule1"
        existing_rule = AllocationRule(
            rule_id=rule_id,
            name="Test Rule",
            priority=5,
            rule_type="FIXED",
            conditions={"service": "S3"},
            allocation_target="Storage"
        )
        
        mock_repository.list_by_organization.return_value = [existing_rule]
        
        # When: Updating rule priority
        updated_rule = engine.update_rule(
            org_id=org_id,
            rule_id=rule_id,
            priority=10
        )
        
        # Then: Priority should be updated
        assert updated_rule.priority == 10
        assert updated_rule.name == "Test Rule"  # Unchanged
    
    def test_update_rule_not_found(self, engine, mock_repository):
        """Test updating non-existent rule"""
        # Given: No existing rules
        org_id = "o-123456789"
        rule_id = "nonexistent"
        
        mock_repository.list_by_organization.return_value = []
        
        # When/Then: Update should fail
        with pytest.raises(ValueError, match="Rule .* not found"):
            engine.update_rule(
                org_id=org_id,
                rule_id=rule_id,
                name="New Name"
            )
    
    def test_delete_rule(self, engine, mock_repository):
        """Test deleting a rule"""
        # Given: Existing rule
        org_id = "o-123456789"
        rule_id = "rule1"
        existing_rule = AllocationRule(
            rule_id=rule_id,
            name="Test Rule",
            priority=5,
            rule_type="FIXED",
            conditions={"service": "S3"},
            allocation_target="Storage"
        )
        
        mock_repository.list_by_organization.return_value = [existing_rule]
        
        # When: Deleting rule
        engine.delete_rule(org_id=org_id, rule_id=rule_id)
        
        # Then: Should verify rule exists
        mock_repository.list_by_organization.assert_called_once_with(org_id)
    
    def test_delete_rule_not_found(self, engine, mock_repository):
        """Test deleting non-existent rule"""
        # Given: No existing rules
        org_id = "o-123456789"
        rule_id = "nonexistent"
        
        mock_repository.list_by_organization.return_value = []
        
        # When/Then: Delete should fail
        with pytest.raises(ValueError, match="Rule .* not found"):
            engine.delete_rule(org_id=org_id, rule_id=rule_id)
