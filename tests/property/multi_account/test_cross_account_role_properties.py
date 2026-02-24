"""
Property-based tests for Cross-Account Role Manager

Feature: multi-account-cost-management
"""
import pytest
from datetime import datetime
from unittest.mock import Mock
from hypothesis import given, strategies as st, settings

from src.services.multi_account.cross_account_role_manager import (
    CrossAccountRoleManager,
    Credentials
)


# Custom strategies
@st.composite
def account_id_strategy(draw):
    """Generate valid AWS account IDs (12 digits)"""
    return ''.join([str(draw(st.integers(min_value=0, max_value=9))) for _ in range(12)])


@st.composite
def external_id_strategy(draw):
    """Generate valid external IDs (8-64 characters)"""
    length = draw(st.integers(min_value=8, max_value=64))
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='+=,.@:/-'),
        min_size=length,
        max_size=length
    ))


class TestCrossAccountRoleProperties:
    """Property-based tests for Cross-Account Role Manager"""
    
    @given(
        account_id=account_id_strategy(),
        external_id=external_id_strategy(),
        call_count=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_2_role_assumption_idempotence(self, account_id, external_id, call_count):
        """
        Property 2: Cross-Account Role Assumption Idempotence
        
        For any account with a valid cross-account role, assuming the role
        multiple times should return equivalent credentials (same permissions,
        different session tokens).
        
        Validates: Requirements 2.5
        
        Feature: multi-account-cost-management, Property 2: Cross-Account Role Assumption Idempotence
        """
        # Setup mock STS
        mock_sts = Mock()
        
        # Mock STS to return different session tokens but same structure
        def mock_assume_role(**kwargs):
            return {
                'Credentials': {
                    'AccessKeyId': f'AKIA{account_id[:16]}',
                    'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                    'SessionToken': f'FwoGZXIvYXdzEBYaDH{kwargs.get("RoleSessionName", "default")}',
                    'Expiration': datetime(2024, 1, 1, 12, 0, 0)
                }
            }
        
        mock_sts.assume_role.side_effect = mock_assume_role
        
        # Create manager
        manager = CrossAccountRoleManager(sts_client=mock_sts)
        
        # Execute: Assume role multiple times
        credentials_list = []
        for i in range(call_count):
            creds = manager.assume_role(
                account_id=account_id,
                role_name='CostGuardCollectorRole',
                external_id=external_id,
                session_name=f'session-{i}'
            )
            credentials_list.append(creds)
        
        # Property 1: All calls should succeed
        assert len(credentials_list) == call_count, "All assume role calls should succeed"
        
        # Property 2: All credentials should have the same access key ID
        access_keys = [creds.access_key_id for creds in credentials_list]
        assert all(key == access_keys[0] for key in access_keys), \
            "All credentials should have same access key ID"
        
        # Property 3: All credentials should have the same secret access key
        secret_keys = [creds.secret_access_key for creds in credentials_list]
        assert all(key == secret_keys[0] for key in secret_keys), \
            "All credentials should have same secret access key"
        
        # Property 4: Session tokens can be different (new sessions)
        # This is expected behavior - each assume role call gets a new session
        session_tokens = [creds.session_token for creds in credentials_list]
        # We just verify they all exist
        assert all(token for token in session_tokens), \
            "All credentials should have session tokens"
        
        # Property 5: STS should be called the correct number of times
        assert mock_sts.assume_role.call_count == call_count, \
            f"STS should be called {call_count} times"
    
    @given(
        account_ids=st.lists(account_id_strategy(), min_size=1, max_size=10, unique=True),
        external_id=external_id_strategy()
    )
    @settings(max_examples=20, deadline=None)
    def test_property_role_arn_uniqueness(self, account_ids, external_id):
        """
        Property: Role ARN Uniqueness
        
        For any set of unique account IDs, the generated role ARNs should
        all be unique.
        
        Validates: Requirements 2.1
        
        Feature: multi-account-cost-management, Property: Role ARN Uniqueness
        """
        manager = CrossAccountRoleManager()
        
        # Generate role ARNs for all accounts
        role_arns = [manager.get_role_arn(account_id) for account_id in account_ids]
        
        # Property: All ARNs should be unique
        assert len(role_arns) == len(set(role_arns)), \
            "All role ARNs should be unique for unique account IDs"
        
        # Property: Each ARN should contain its account ID
        for account_id, role_arn in zip(account_ids, role_arns):
            assert account_id in role_arn, \
                f"Role ARN should contain account ID {account_id}"
    
    @given(
        account_id=account_id_strategy(),
        management_account_id=account_id_strategy(),
        external_id=external_id_strategy()
    )
    @settings(max_examples=20, deadline=None)
    def test_property_template_validity(self, account_id, management_account_id, external_id):
        """
        Property: CloudFormation Template Validity
        
        For any valid account IDs and external ID, the generated CloudFormation
        template should be valid JSON and contain required elements.
        
        Validates: Requirements 2.1, 2.2, 2.3, 2.4
        
        Feature: multi-account-cost-management, Property: Template Validity
        """
        import json
        
        manager = CrossAccountRoleManager()
        
        # Generate template
        template_json = manager.generate_role_template(management_account_id, external_id)
        
        # Property 1: Template should be valid JSON
        try:
            template = json.loads(template_json)
        except json.JSONDecodeError:
            pytest.fail("Template should be valid JSON")
        
        # Property 2: Template should have required top-level keys
        required_keys = ['AWSTemplateFormatVersion', 'Description', 'Parameters', 'Resources', 'Outputs']
        for key in required_keys:
            assert key in template, f"Template should have {key}"
        
        # Property 3: Template should have CostGuardCollectorRole resource
        assert 'CostGuardCollectorRole' in template['Resources'], \
            "Template should define CostGuardCollectorRole"
        
        # Property 4: Role should have trust policy with management account
        role = template['Resources']['CostGuardCollectorRole']
        assume_policy = role['Properties']['AssumeRolePolicyDocument']
        principal_arn = assume_policy['Statement'][0]['Principal']['AWS']
        assert management_account_id in principal_arn, \
            "Trust policy should reference management account"
        
        # Property 5: Role should have external ID condition
        condition = assume_policy['Statement'][0]['Condition']
        assert 'StringEquals' in condition, \
            "Trust policy should have StringEquals condition"
        assert 'sts:ExternalId' in condition['StringEquals'], \
            "Trust policy should check external ID"
    
    @given(
        account_id=account_id_strategy(),
        role_names=st.lists(
            st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-')),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_property_role_arn_format(self, account_id, role_names):
        """
        Property: Role ARN Format Consistency
        
        For any account ID and role names, generated ARNs should follow
        the correct AWS ARN format.
        
        Validates: Requirements 2.1
        
        Feature: multi-account-cost-management, Property: Role ARN Format
        """
        manager = CrossAccountRoleManager()
        
        for role_name in role_names:
            role_arn = manager.get_role_arn(account_id, role_name)
            
            # Property 1: ARN should start with arn:aws:iam::
            assert role_arn.startswith('arn:aws:iam::'), \
                "ARN should start with arn:aws:iam::"
            
            # Property 2: ARN should contain account ID
            assert account_id in role_arn, \
                "ARN should contain account ID"
            
            # Property 3: ARN should contain role name
            assert role_name in role_arn, \
                "ARN should contain role name"
            
            # Property 4: ARN should have correct format
            expected_arn = f'arn:aws:iam::{account_id}:role/{role_name}'
            assert role_arn == expected_arn, \
                f"ARN should match expected format: {expected_arn}"
    
    @given(
        account_id=account_id_strategy(),
        external_id=external_id_strategy()
    )
    @settings(max_examples=20, deadline=None)
    def test_property_credentials_structure(self, account_id, external_id):
        """
        Property: Credentials Structure Consistency
        
        For any successful role assumption, returned credentials should
        have all required fields.
        
        Validates: Requirements 2.5
        
        Feature: multi-account-cost-management, Property: Credentials Structure
        """
        # Setup mock STS
        mock_sts = Mock()
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': f'AKIA{account_id[:16]}',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'FwoGZXIvYXdzEBYaDH...',
                'Expiration': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        
        manager = CrossAccountRoleManager(sts_client=mock_sts)
        
        # Execute
        credentials = manager.assume_role(
            account_id=account_id,
            role_name='CostGuardCollectorRole',
            external_id=external_id
        )
        
        # Property 1: Credentials should have access_key_id
        assert hasattr(credentials, 'access_key_id'), \
            "Credentials should have access_key_id"
        assert credentials.access_key_id, \
            "access_key_id should not be empty"
        
        # Property 2: Credentials should have secret_access_key
        assert hasattr(credentials, 'secret_access_key'), \
            "Credentials should have secret_access_key"
        assert credentials.secret_access_key, \
            "secret_access_key should not be empty"
        
        # Property 3: Credentials should have session_token
        assert hasattr(credentials, 'session_token'), \
            "Credentials should have session_token"
        assert credentials.session_token, \
            "session_token should not be empty"
        
        # Property 4: Credentials should have expiration
        assert hasattr(credentials, 'expiration'), \
            "Credentials should have expiration"
        assert credentials.expiration, \
            "expiration should not be empty"
