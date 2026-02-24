"""
Property-Based Tests for Organization Prevention

Tests universal properties of multi-account prevention policies.
"""
import pytest
from datetime import datetime
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock

from src.services.multi_account.organization_prevention_service import OrganizationPreventionService
from src.services.multi_account.models import Account


@given(
    num_accounts=st.integers(min_value=2, max_value=10)
)
@settings(max_examples=20)
def test_property_12_prevention_policy_inheritance(num_accounts):
    """
    Property 12: Prevention Policy Inheritance
    
    For any OU with accounts, when a policy is applied at the OU level,
    all accounts in that OU should receive the policy.
    
    Validates: Requirements 14.4, 14.5
    """
    # Create fresh mocks
    prevention_engine = Mock()
    account_repo = Mock()
    service = OrganizationPreventionService(prevention_engine, account_repo, max_workers=2)
    
    # Given: OU with multiple accounts
    ou_id = "ou-test123"
    account_ids = [f"acc{i:012d}" for i in range(num_accounts)]
    policy_name = "test-policy"
    policy_config = {"enabled": True, "dry_run_mode": False}
    
    # Mock account repository to return accounts
    accounts = [
        Account(
            id=account_id,
            arn="",
            name=f"Account {i}",
            email=f"account{i}@example.com",
            status="ACTIVE",
            joined_method="",
            joined_timestamp=datetime.utcnow()
        )
        for i, account_id in enumerate(account_ids)
    ]
    account_repo.get.side_effect = accounts
    
    # When: Apply policy at OU level
    result = service.create_ou_policy(ou_id, account_ids, policy_name, policy_config)
    
    # Then: All accounts should receive the policy
    assert result["success"] is True
    assert result["accounts_affected"] == num_accounts
    assert result["successful_applications"] == num_accounts
    
    # Verify prevention engine was updated for each account
    assert prevention_engine.update_config.call_count == num_accounts


@given(
    num_accounts=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=20)
def test_property_parallel_execution_consistency(num_accounts):
    """
    Property: Parallel Execution Consistency
    
    For any list of accounts, executing prevention in parallel should
    process all accounts exactly once.
    
    Validates: Requirements 14.7
    """
    # Create fresh mocks
    prevention_engine = Mock()
    account_repo = Mock()
    service = OrganizationPreventionService(prevention_engine, account_repo, max_workers=2)
    
    # Given: List of accounts
    account_ids = [f"acc{i:012d}" for i in range(num_accounts)]
    
    # Mock prevention engine to return success
    prevention_engine.run_prevention_cycle.return_value = {
        "success": True,
        "actions_taken": 1,
        "budget_events": 0,
        "timestamp": "2026-02-24T10:00:00Z"
    }
    
    # When: Execute prevention across accounts
    result = service.execute_prevention_across_accounts(account_ids)
    
    # Then: All accounts should be processed
    assert result["accounts_processed"] == num_accounts
    assert len(result["results"]) == num_accounts
    
    # Each account should be processed exactly once
    processed_accounts = [r["account_id"] for r in result["results"]]
    assert len(processed_accounts) == len(set(processed_accounts))  # No duplicates
    assert set(processed_accounts) == set(account_ids)  # All accounts processed


@given(
    policy_config=st.fixed_dictionaries({
        "enabled": st.booleans(),
        "dry_run_mode": st.booleans(),
        "approval_required": st.booleans()
    })
)
@settings(max_examples=20)
def test_property_policy_configuration_preservation(policy_config):
    """
    Property: Policy Configuration Preservation
    
    For any policy configuration, when applied to an account,
    the configuration should be passed to the prevention engine unchanged.
    
    Validates: Requirements 14.3, 14.6
    """
    # Create fresh mocks
    prevention_engine = Mock()
    account_repo = Mock()
    service = OrganizationPreventionService(prevention_engine, account_repo)
    
    # Given: Account and policy configuration
    account_id = "111111111111"
    policy_name = "test-policy"
    
    # When: Apply policy to account
    result = service.apply_account_policy(account_id, policy_name, policy_config)
    
    # Then: Configuration should be passed unchanged
    assert result["success"] is True
    prevention_engine.update_config.assert_called_once_with(policy_config)
