"""
Property-based tests for Backward Compatibility Service.

Tests backward compatibility between single-account and multi-account modes.
"""
import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime, UTC

from src.services.multi_account.backward_compatibility import BackwardCompatibilityService
from src.services.multi_account.models import Organization, Account


class TestBackwardCompatibilityProperties:
    """Property-based tests for backward compatibility service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_org_service = Mock()
        self.mock_org_repo = Mock()
        self.mock_account_repo = Mock()
        
        self.service = BackwardCompatibilityService(
            org_service=self.mock_org_service,
            org_repo=self.mock_org_repo,
            account_repo=self.mock_account_repo
        )
    
    @given(
        service_names=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
        amounts=st.lists(st.decimals(min_value=0, max_value=10000, places=2), min_size=1, max_size=5)
    )
    def test_backward_compatibility_property(self, service_names, amounts):
        """
        Property 14: Backward Compatibility
        
        Validates: Requirements 20.2, 20.3
        
        When querying cost data:
        - With multi-account disabled: should use single-account mode
        - With multi-account enabled: should use multi-account mode
        - Results should be consistent for the same underlying data
        """
        # Create valid cost data from the generated inputs
        valid_cost_data = []
        for i, (service, amount) in enumerate(zip(service_names, amounts)):
            if service and amount is not None:
                valid_cost_data.append({
                    'service': service,
                    'amount': amount,
                    'date': datetime(2024, 1, 1 + i)
                })
        
        assume(len(valid_cost_data) > 0)
        
        # Test single-account mode (no organization)
        self.mock_org_service.discover_organization.return_value = None
        
        single_account_mode = self.service.get_operation_mode()
        single_account_legacy = self.service.should_use_legacy_endpoints()
        single_account_fallback = self.service.get_fallback_handler('fetch_costs')
        
        # Test multi-account mode (organization exists)
        mock_organization = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        self.mock_org_service.discover_organization.return_value = mock_organization
        
        multi_account_mode = self.service.get_operation_mode()
        multi_account_legacy = self.service.should_use_legacy_endpoints()
        multi_account_fallback = self.service.get_fallback_handler('fetch_costs')
        
        # Verify backward compatibility properties
        assert single_account_mode == 'single-account'
        assert multi_account_mode == 'multi-account'
        
        assert single_account_legacy is True  # Should use legacy endpoints
        assert multi_account_legacy is False  # Should not use legacy endpoints
        
        assert single_account_fallback is not None  # Should have fallback handler
        assert multi_account_fallback is None  # Should not need fallback handler
        
        # Test API response compatibility
        sample_response = {
            'costs': valid_cost_data,
            'total': sum(entry['amount'] for entry in valid_cost_data),
            'success': True
        }
        
        # Single-account mode should convert to legacy format when requested
        self.mock_org_service.discover_organization.return_value = None
        legacy_response = self.service.get_compatible_api_response(
            sample_response, 
            legacy_format=True
        )
        
        # Multi-account mode should return original format
        self.mock_org_service.discover_organization.return_value = mock_organization
        modern_response = self.service.get_compatible_api_response(
            sample_response, 
            legacy_format=True
        )
        
        # Both responses should contain the same core data
        assert legacy_response['success'] == modern_response['success']
        assert len(legacy_response['costs']) == len(modern_response['costs'])
    
    @given(
        organization_suffix=st.text(min_size=5, max_size=15, alphabet=st.characters(min_codepoint=48, max_codepoint=122)),
        account_count=st.integers(min_value=1, max_value=10)
    )
    def test_migration_consistency_property(self, organization_suffix, account_count):
        """
        Property: Migration Consistency
        
        When migrating from single-account to multi-account mode:
        - Migration should be idempotent
        - Data should be preserved
        - Mode should change correctly
        """
        organization_id = f'o-{organization_suffix}'
        assume(len(organization_id) >= 10)
        
        # Create mock organization and accounts
        mock_organization = Organization(
            id=organization_id,
            arn=f'arn:aws:organizations::123456789012:organization/{organization_id}',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        # Test migration from single-account mode
        self.mock_org_service.discover_organization.side_effect = [
            None,  # Initial check - single-account mode
            mock_organization,  # Migration step - organization available
            mock_organization   # Validation step - organization confirmed
        ]
        
        # First migration
        result1 = self.service.migrate_to_multi_account()
        
        # Reset mock for second migration (already in multi-account mode)
        self.mock_org_service.discover_organization.side_effect = None
        self.mock_org_service.discover_organization.return_value = mock_organization
        
        # Second migration (should be idempotent)
        result2 = self.service.migrate_to_multi_account()
        
        # Verify migration consistency
        assert result1['success'] is True
        assert result2['success'] is True
        
        assert result1['mode_before'] == 'single-account'
        assert result1['mode_after'] == 'multi-account'
        
        assert result2['mode_after'] == 'multi-account'
        assert len(result2['warnings']) > 0  # Should warn about already being in multi-account mode
        
        # Both migrations should preserve data
        assert result1['data_preserved'] is True
        assert result2['data_preserved'] is True
    
    @given(
        operations=st.lists(
            st.sampled_from([
                'fetch_costs', 'query_costs', 'estimate_costs', 
                'forecast_costs', 'prevent_costs', 'advise_costs'
            ]),
            min_size=1,
            max_size=6,
            unique=True
        )
    )
    def test_fallback_handler_consistency_property(self, operations):
        """
        Property: Fallback Handler Consistency
        
        In single-account mode:
        - All known operations should have fallback handlers
        - Unknown operations should return None
        
        In multi-account mode:
        - All operations should return None (no fallback needed)
        """
        # Test single-account mode
        self.mock_org_service.discover_organization.return_value = None
        
        single_account_handlers = {}
        for operation in operations:
            handler = self.service.get_fallback_handler(operation)
            single_account_handlers[operation] = handler
            
            # All known operations should have handlers in single-account mode
            assert handler is not None
            assert isinstance(handler, str)
            assert 'lambda_handler.' in handler
        
        # Test multi-account mode
        mock_organization = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        self.mock_org_service.discover_organization.return_value = mock_organization
        
        multi_account_handlers = {}
        for operation in operations:
            handler = self.service.get_fallback_handler(operation)
            multi_account_handlers[operation] = handler
            
            # All operations should return None in multi-account mode
            assert handler is None
        
        # Verify consistency
        assert len(single_account_handlers) == len(operations)
        assert len(multi_account_handlers) == len(operations)
        assert all(h is not None for h in single_account_handlers.values())
        assert all(h is None for h in multi_account_handlers.values())
    
    @given(
        env_override=st.sampled_from(['true', 'false', 'TRUE', 'FALSE', '1', '0', ''])
    )
    def test_environment_override_property(self, env_override):
        """
        Property: Environment Override Consistency
        
        Environment variable MULTI_ACCOUNT_ENABLED should:
        - Override organization detection when set to 'false'
        - Allow normal detection otherwise
        """
        # Reset mock call count for this test
        self.mock_org_service.reset_mock()
        
        # Create mock organization
        mock_organization = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        self.mock_org_service.discover_organization.return_value = mock_organization
        
        with patch.dict('os.environ', {'MULTI_ACCOUNT_ENABLED': env_override}):
            is_enabled = self.service.is_multi_account_enabled()
            
            if env_override.lower() == 'false':
                # Should be disabled regardless of organization
                assert is_enabled is False
                # Organization discovery should not be called
                self.mock_org_service.discover_organization.assert_not_called()
            else:
                # Should follow normal organization detection
                assert is_enabled is True
                # Organization discovery should be called
                self.mock_org_service.discover_organization.assert_called()