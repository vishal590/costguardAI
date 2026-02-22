"""
Unit tests for SafetyGuard.

Tests safety mechanisms for protecting production resources.
"""

import pytest
from src.services.safety_guard import SafetyGuard
from src.utils.types import Resource, SafetyConfig, SafetyCheck


class TestSafetyGuard:
    """Test SafetyGuard class."""
    
    @pytest.fixture
    def default_config(self):
        """Create default safety configuration."""
        return SafetyConfig(
            protected_tags=["Environment=production", "CostGuard=protected", "CostGuard=exclude"],
            whitelist_ids=["i-whitelist123", "db-whitelist456"],
            minimum_idle_minutes={'ec2': 120, 'rds': 60},
            dry_run_mode=False
        )
    
    @pytest.fixture
    def safety_guard(self, default_config):
        """Create SafetyGuard instance."""
        return SafetyGuard(default_config)
    
    @pytest.fixture
    def safe_resource(self):
        """Create a safe resource (no protected tags)."""
        return Resource(
            resource_id='i-safe123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'test-instance', 'Environment': 'dev'},
            state='stopped',
            creation_date='2024-01-01T12:00:00'
        )
    
    @pytest.fixture
    def production_resource(self):
        """Create a production resource."""
        return Resource(
            resource_id='i-prod123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'prod-instance', 'Environment': 'production'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
    
    def test_initialization(self, safety_guard):
        """Test SafetyGuard initialization."""
        assert safety_guard.config is not None
        assert len(safety_guard.protected_tags) == 3
        assert len(safety_guard.whitelist_ids) == 2
        assert safety_guard.dry_run_mode is False
    
    def test_check_tags_safe_resource(self, safety_guard, safe_resource):
        """Test tag checking for safe resource."""
        result = safety_guard.check_tags(safe_resource)
        
        assert result is True
    
    def test_check_tags_production_resource(self, safety_guard, production_resource):
        """Test tag checking for production resource."""
        result = safety_guard.check_tags(production_resource)
        
        assert result is False
    
    def test_check_tags_protected_tag(self, safety_guard):
        """Test tag checking for resource with CostGuard=protected."""
        resource = Resource(
            resource_id='i-protected123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'protected', 'CostGuard': 'protected'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.check_tags(resource)
        
        assert result is False
    
    def test_check_tags_exclude_tag(self, safety_guard):
        """Test tag checking for resource with CostGuard=exclude."""
        resource = Resource(
            resource_id='i-exclude123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Name': 'excluded', 'CostGuard': 'exclude'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.check_tags(resource)
        
        assert result is False
    
    def test_check_tags_no_tags(self, safety_guard):
        """Test tag checking for resource with no tags."""
        resource = Resource(
            resource_id='i-notags123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.check_tags(resource)
        
        assert result is True
    
    def test_check_whitelist_not_in_list(self, safety_guard, safe_resource):
        """Test whitelist checking for resource not in whitelist."""
        result = safety_guard.check_whitelist(safe_resource)
        
        assert result is True
    
    def test_check_whitelist_in_list(self, safety_guard):
        """Test whitelist checking for resource in whitelist."""
        resource = Resource(
            resource_id='i-whitelist123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.check_whitelist(resource)
        
        assert result is False
    
    def test_check_active_usage(self, safety_guard, safe_resource):
        """Test active usage checking."""
        result = safety_guard.check_active_usage(safe_resource)
        
        # Currently always returns True (conservative approach)
        assert result is True
    
    def test_validate_safe_state_stopped(self, safety_guard, safe_resource):
        """Test state validation for stopped resource."""
        result = safety_guard.validate_safe_state(safe_resource)
        
        assert result is True
    
    def test_validate_safe_state_terminating(self, safety_guard):
        """Test state validation for terminating resource."""
        resource = Resource(
            resource_id='i-terminating123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='terminating',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.validate_safe_state(resource)
        
        assert result is False
    
    def test_validate_safe_state_terminated(self, safety_guard):
        """Test state validation for terminated resource."""
        resource = Resource(
            resource_id='i-terminated123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='terminated',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.validate_safe_state(resource)
        
        assert result is False
    
    def test_is_action_safe_all_checks_pass(self, safety_guard, safe_resource):
        """Test is_action_safe when all checks pass."""
        result = safety_guard.is_action_safe(safe_resource, 'stop')
        
        assert isinstance(result, SafetyCheck)
        assert result.is_safe is True
        assert result.blocked_reason is None
        assert 'tag_check' in result.checks_performed
        assert 'whitelist_check' in result.checks_performed
    
    def test_is_action_safe_blocked_by_tag(self, safety_guard, production_resource):
        """Test is_action_safe blocked by protected tag."""
        result = safety_guard.is_action_safe(production_resource, 'stop')
        
        assert result.is_safe is False
        assert result.blocked_reason == "Resource has protected tag"
        assert 'tag_check' in result.checks_performed
    
    def test_is_action_safe_blocked_by_whitelist(self, safety_guard):
        """Test is_action_safe blocked by whitelist."""
        resource = Resource(
            resource_id='i-whitelist123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Environment': 'dev'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.is_action_safe(resource, 'stop')
        
        assert result.is_safe is False
        assert result.blocked_reason == "Resource is in whitelist"
        assert 'whitelist_check' in result.checks_performed
    
    def test_is_action_safe_dry_run_mode(self):
        """Test is_action_safe in dry run mode."""
        config = SafetyConfig(
            protected_tags=[],
            whitelist_ids=[],
            minimum_idle_minutes={},
            dry_run_mode=True
        )
        guard = SafetyGuard(config)
        
        resource = Resource(
            resource_id='i-test123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='stopped',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = guard.is_action_safe(resource, 'stop')
        
        assert result.is_safe is False
        assert result.blocked_reason == "Dry run mode enabled"
    
    def test_check_tags_multiple_protected_tags(self, safety_guard):
        """Test resource with multiple protected tags."""
        resource = Resource(
            resource_id='i-multi123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={
                'Environment': 'production',
                'CostGuard': 'protected'
            },
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.check_tags(resource)
        
        # Should be blocked by first matching tag
        assert result is False
    
    def test_check_tags_case_sensitive(self, safety_guard):
        """Test that tag checking is case-sensitive."""
        resource = Resource(
            resource_id='i-case123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Environment': 'Production'},  # Capital P
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.check_tags(resource)
        
        # Should be safe (case doesn't match)
        assert result is True
    
    def test_custom_protected_tags(self):
        """Test SafetyGuard with custom protected tags."""
        config = SafetyConfig(
            protected_tags=["Critical=yes", "DoNotTouch=true"],
            whitelist_ids=[],
            minimum_idle_minutes={},
            dry_run_mode=False
        )
        guard = SafetyGuard(config)
        
        resource = Resource(
            resource_id='i-custom123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={'Critical': 'yes'},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = guard.check_tags(resource)
        
        assert result is False
    
    def test_empty_whitelist(self):
        """Test SafetyGuard with empty whitelist."""
        config = SafetyConfig(
            protected_tags=[],
            whitelist_ids=[],
            minimum_idle_minutes={},
            dry_run_mode=False
        )
        guard = SafetyGuard(config)
        
        resource = Resource(
            resource_id='i-any123',
            resource_type='instance',
            service='ec2',
            region='us-east-1',
            tags={},
            state='running',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = guard.check_whitelist(resource)
        
        assert result is True
    
    def test_checks_performed_order(self, safety_guard, safe_resource):
        """Test that checks are performed in correct order."""
        result = safety_guard.is_action_safe(safe_resource, 'stop')
        
        # Checks should be performed in order
        expected_order = ['tag_check', 'whitelist_check', 'active_usage_check', 'idle_duration_check']
        assert result.checks_performed == expected_order
    
    def test_checks_stop_on_first_failure(self, safety_guard, production_resource):
        """Test that checks stop on first failure."""
        result = safety_guard.is_action_safe(production_resource, 'stop')
        
        # Should only have tag_check since it failed
        assert result.checks_performed == ['tag_check']
        assert result.is_safe is False
    
    def test_minimum_idle_duration_check(self, safety_guard, safe_resource):
        """Test minimum idle duration check."""
        result = safety_guard._check_minimum_idle_duration(safe_resource)
        
        # Currently always returns True
        assert result is True
    
    def test_different_actions(self, safety_guard, safe_resource):
        """Test safety check with different actions."""
        actions = ['stop', 'terminate', 'delete', 'modify']
        
        for action in actions:
            result = safety_guard.is_action_safe(safe_resource, action)
            # All should pass for safe resource
            assert result.is_safe is True
    
    def test_rds_resource_safety(self, safety_guard):
        """Test safety check for RDS resource."""
        resource = Resource(
            resource_id='db-test123',
            resource_type='db_instance',
            service='rds',
            region='us-east-1',
            tags={'Environment': 'dev'},
            state='available',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.is_action_safe(resource, 'stop')
        
        assert result.is_safe is True
    
    def test_lambda_resource_safety(self, safety_guard):
        """Test safety check for Lambda resource."""
        resource = Resource(
            resource_id='arn:aws:lambda:us-east-1:123456789012:function:test',
            resource_type='function',
            service='lambda',
            region='us-east-1',
            tags={},
            state='Active',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.is_action_safe(resource, 'limit_concurrency')
        
        assert result.is_safe is True
    
    def test_validate_safe_state_deleting(self, safety_guard):
        """Test state validation for deleting resource."""
        resource = Resource(
            resource_id='vol-deleting123',
            resource_type='volume',
            service='ebs',
            region='us-east-1',
            tags={},
            state='deleting',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.validate_safe_state(resource)
        
        assert result is False
    
    def test_validate_safe_state_deleted(self, safety_guard):
        """Test state validation for deleted resource."""
        resource = Resource(
            resource_id='vol-deleted123',
            resource_type='volume',
            service='ebs',
            region='us-east-1',
            tags={},
            state='deleted',
            creation_date='2024-01-01T12:00:00'
        )
        
        result = safety_guard.validate_safe_state(resource)
        
        assert result is False
