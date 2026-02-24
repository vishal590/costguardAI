"""
Unit tests for Backward Compatibility Service.

Tests single-account mode detection, migration, and API compatibility.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

from src.services.multi_account.backward_compatibility import BackwardCompatibilityService
from src.services.multi_account.models import Organization


class TestBackwardCompatibilityService:
    """Test cases for backward compatibility service."""
    
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
    
    def test_is_multi_account_enabled_with_organization(self):
        """Test multi-account mode detection when organization exists."""
        # Given: Organization exists
        mock_organization = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        self.mock_org_service.discover_organization.return_value = mock_organization
        
        # When: Checking if multi-account is enabled
        result = self.service.is_multi_account_enabled()
        
        # Then: Multi-account mode should be enabled
        assert result is True
        self.mock_org_service.discover_organization.assert_called_once()
    
    def test_is_multi_account_enabled_without_organization(self):
        """Test multi-account mode detection when no organization exists."""
        # Given: No organization exists
        self.mock_org_service.discover_organization.return_value = None
        
        # When: Checking if multi-account is enabled
        result = self.service.is_multi_account_enabled()
        
        # Then: Multi-account mode should be disabled
        assert result is False
        self.mock_org_service.discover_organization.assert_called_once()
    
    def test_is_multi_account_enabled_with_exception(self):
        """Test multi-account mode detection when organization discovery fails."""
        # Given: Organization discovery raises exception
        self.mock_org_service.discover_organization.side_effect = Exception("AWS Organizations not accessible")
        
        # When: Checking if multi-account is enabled
        result = self.service.is_multi_account_enabled()
        
        # Then: Multi-account mode should be disabled
        assert result is False
        self.mock_org_service.discover_organization.assert_called_once()
    
    @patch.dict('os.environ', {'MULTI_ACCOUNT_ENABLED': 'false'})
    def test_is_multi_account_enabled_disabled_by_env_var(self):
        """Test multi-account mode disabled by environment variable."""
        # When: Checking if multi-account is enabled with env var set to false
        result = self.service.is_multi_account_enabled()
        
        # Then: Multi-account mode should be disabled
        assert result is False
        # Organization discovery should not be called
        self.mock_org_service.discover_organization.assert_not_called()
    
    def test_get_operation_mode_multi_account(self):
        """Test getting operation mode when multi-account is enabled."""
        # Given: Multi-account mode is enabled
        self.mock_org_service.discover_organization.return_value = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        # When: Getting operation mode
        result = self.service.get_operation_mode()
        
        # Then: Should return multi-account
        assert result == 'multi-account'
    
    def test_get_operation_mode_single_account(self):
        """Test getting operation mode when single-account mode is active."""
        # Given: Single-account mode is active
        self.mock_org_service.discover_organization.return_value = None
        
        # When: Getting operation mode
        result = self.service.get_operation_mode()
        
        # Then: Should return single-account
        assert result == 'single-account'
    
    def test_should_use_legacy_endpoints_true(self):
        """Test legacy endpoints should be used in single-account mode."""
        # Given: Single-account mode is active
        self.mock_org_service.discover_organization.return_value = None
        
        # When: Checking if legacy endpoints should be used
        result = self.service.should_use_legacy_endpoints()
        
        # Then: Should use legacy endpoints
        assert result is True
    
    def test_should_use_legacy_endpoints_false(self):
        """Test legacy endpoints should not be used in multi-account mode."""
        # Given: Multi-account mode is enabled
        self.mock_org_service.discover_organization.return_value = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        # When: Checking if legacy endpoints should be used
        result = self.service.should_use_legacy_endpoints()
        
        # Then: Should not use legacy endpoints
        assert result is False
    
    def test_migrate_to_multi_account_success(self):
        """Test successful migration to multi-account mode."""
        # Given: Single-account mode initially, but organization becomes available during migration
        # Multiple calls to discover_organization during migration process
        self.mock_org_service.discover_organization.side_effect = [
            None,  # First call - is_multi_account_enabled() returns single-account mode
            Organization(  # Second call - migration step finds organization
                id='o-example123456',
                arn='arn:aws:organizations::123456789012:organization/o-example123456',
                master_account_id='123456789012',
                feature_set='ALL'
            ),
            Organization(  # Third call - validation step confirms organization
                id='o-example123456',
                arn='arn:aws:organizations::123456789012:organization/o-example123456',
                master_account_id='123456789012',
                feature_set='ALL'
            )
        ]
        
        # When: Migrating to multi-account mode
        result = self.service.migrate_to_multi_account()
        
        # Then: Migration should succeed
        assert result['success'] is True
        assert result['mode_before'] == 'single-account'
        assert result['mode_after'] == 'multi-account'
        assert result['data_preserved'] is True
        assert result['validation_passed'] is True
        assert len(result['errors']) == 0
        assert 'migration_timestamp' in result
    
    def test_migrate_to_multi_account_already_enabled(self):
        """Test migration when already in multi-account mode."""
        # Given: Multi-account mode is already enabled
        mock_organization = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        self.mock_org_service.discover_organization.return_value = mock_organization
        
        # When: Migrating to multi-account mode
        result = self.service.migrate_to_multi_account()
        
        # Then: Should succeed with warning
        assert result['success'] is True
        assert result['mode_after'] == 'multi-account'
        assert len(result['warnings']) > 0
        assert 'already in multi-account mode' in result['warnings'][0]
    
    def test_migrate_to_multi_account_no_organization(self):
        """Test migration failure when no organization is available."""
        # Given: No organization available
        self.mock_org_service.discover_organization.return_value = None
        
        # When: Migrating to multi-account mode
        result = self.service.migrate_to_multi_account()
        
        # Then: Migration should fail
        assert result['success'] is False
        assert len(result['errors']) > 0
        assert 'No AWS Organization found' in result['errors'][0]
    
    def test_migrate_to_multi_account_organization_discovery_fails(self):
        """Test migration failure when organization discovery fails."""
        # Given: Organization discovery fails
        self.mock_org_service.discover_organization.side_effect = Exception("AWS Organizations not accessible")
        
        # When: Migrating to multi-account mode
        result = self.service.migrate_to_multi_account()
        
        # Then: Migration should fail
        assert result['success'] is False
        assert len(result['errors']) > 0
        assert 'Failed to discover organization' in result['errors'][0]
    
    def test_migrate_to_multi_account_without_data_preservation(self):
        """Test migration without data preservation."""
        # Given: Single-account mode initially, organization becomes available
        self.mock_org_service.discover_organization.side_effect = [
            None,  # First call - is_multi_account_enabled() returns single-account mode
            Organization(  # Second call - migration step finds organization
                id='o-example123456',
                arn='arn:aws:organizations::123456789012:organization/o-example123456',
                master_account_id='123456789012',
                feature_set='ALL'
            ),
            Organization(  # Third call - validation step confirms organization
                id='o-example123456',
                arn='arn:aws:organizations::123456789012:organization/o-example123456',
                master_account_id='123456789012',
                feature_set='ALL'
            )
        ]
        
        # When: Migrating without data preservation
        result = self.service.migrate_to_multi_account(preserve_data=False)
        
        # Then: Migration should succeed without data preservation
        assert result['success'] is True
        assert result['data_preserved'] is False
    
    def test_migrate_to_multi_account_without_validation(self):
        """Test migration without validation."""
        # Given: Single-account mode initially, organization becomes available
        self.mock_org_service.discover_organization.side_effect = [
            None,  # First call - is_multi_account_enabled() returns single-account mode
            Organization(  # Second call - migration step finds organization
                id='o-example123456',
                arn='arn:aws:organizations::123456789012:organization/o-example123456',
                master_account_id='123456789012',
                feature_set='ALL'
            )
        ]
        
        # When: Migrating without validation
        result = self.service.migrate_to_multi_account(validate_migration=False)
        
        # Then: Migration should succeed without validation
        assert result['success'] is True
        assert result['validation_passed'] is False
    
    def test_get_compatible_api_response_multi_account_mode(self):
        """Test API response compatibility in multi-account mode."""
        # Given: Multi-account mode is enabled
        self.mock_org_service.discover_organization.return_value = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        response = {'data': 'test', 'success': True}
        
        # When: Getting compatible API response
        result = self.service.get_compatible_api_response(response, legacy_format=True)
        
        # Then: Should return original response (no conversion needed)
        assert result == response
    
    def test_get_compatible_api_response_single_account_mode(self):
        """Test API response compatibility in single-account mode."""
        # Given: Single-account mode is active
        self.mock_org_service.discover_organization.return_value = None
        
        response = {'data': 'test', 'success': True}
        
        # When: Getting compatible API response with legacy format
        result = self.service.get_compatible_api_response(response, legacy_format=True)
        
        # Then: Should return converted response (for now, same as input)
        assert result == response
    
    def test_get_fallback_handler_single_account_mode(self):
        """Test getting fallback handler in single-account mode."""
        # Given: Single-account mode is active
        self.mock_org_service.discover_organization.return_value = None
        
        # When: Getting fallback handler for fetch operation
        result = self.service.get_fallback_handler('fetch_costs')
        
        # Then: Should return legacy handler
        assert result == 'lambda_handler.fetch_handler'
    
    def test_get_fallback_handler_multi_account_mode(self):
        """Test getting fallback handler in multi-account mode."""
        # Given: Multi-account mode is enabled
        self.mock_org_service.discover_organization.return_value = Organization(
            id='o-example123456',
            arn='arn:aws:organizations::123456789012:organization/o-example123456',
            master_account_id='123456789012',
            feature_set='ALL'
        )
        
        # When: Getting fallback handler
        result = self.service.get_fallback_handler('fetch_costs')
        
        # Then: Should return None (no fallback needed)
        assert result is None
    
    def test_get_fallback_handler_unknown_operation(self):
        """Test getting fallback handler for unknown operation."""
        # Given: Single-account mode is active
        self.mock_org_service.discover_organization.return_value = None
        
        # When: Getting fallback handler for unknown operation
        result = self.service.get_fallback_handler('unknown_operation')
        
        # Then: Should return None
        assert result is None