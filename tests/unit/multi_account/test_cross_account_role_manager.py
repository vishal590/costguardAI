"""
Unit tests for Cross-Account Role Manager
"""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.services.multi_account.cross_account_role_manager import (
    CrossAccountRoleManager,
    Credentials
)


class TestCrossAccountRoleManager:
    """Test suite for CrossAccountRoleManager"""
    
    @pytest.fixture
    def mock_sts(self):
        """Mock STS client"""
        return Mock()
    
    @pytest.fixture
    def manager(self, mock_sts):
        """Create manager instance with mocked STS"""
        return CrossAccountRoleManager(sts_client=mock_sts)
    
    def test_generate_role_template(self, manager):
        """Test CloudFormation template generation"""
        management_account_id = '123456789012'
        external_id = 'test-external-id-123'
        
        template_json = manager.generate_role_template(management_account_id, external_id)
        template = json.loads(template_json)
        
        # Verify template structure
        assert 'AWSTemplateFormatVersion' in template
        assert template['AWSTemplateFormatVersion'] == '2010-09-09'
        
        # Verify parameters
        assert 'Parameters' in template
        assert 'ManagementAccountId' in template['Parameters']
        assert 'ExternalId' in template['Parameters']
        assert template['Parameters']['ManagementAccountId']['Default'] == management_account_id
        assert template['Parameters']['ExternalId']['Default'] == external_id
        
        # Verify role resource
        assert 'Resources' in template
        assert 'CostGuardCollectorRole' in template['Resources']
        role = template['Resources']['CostGuardCollectorRole']
        assert role['Type'] == 'AWS::IAM::Role'
        
        # Verify trust policy
        assume_policy = role['Properties']['AssumeRolePolicyDocument']
        statement = assume_policy['Statement'][0]
        assert statement['Effect'] == 'Allow'
        assert statement['Action'] == 'sts:AssumeRole'
        assert f'arn:aws:iam::{management_account_id}:root' in statement['Principal']['AWS']
        
        # Verify external ID condition
        assert 'Condition' in statement
        assert 'StringEquals' in statement['Condition']
        assert 'sts:ExternalId' in statement['Condition']['StringEquals']
        
        # Verify permissions
        policies = role['Properties']['Policies']
        assert len(policies) > 0
        policy_doc = policies[0]['PolicyDocument']
        statements = policy_doc['Statement']
        
        # Check Cost Explorer permissions
        ce_statement = statements[0]
        assert 'ce:GetCostAndUsage' in ce_statement['Action']
        assert 'ce:GetCostForecast' in ce_statement['Action']
        
        # Check CloudWatch permissions
        cw_statement = statements[1]
        assert 'cloudwatch:GetMetricStatistics' in cw_statement['Action']
        assert 'cloudwatch:ListMetrics' in cw_statement['Action']
    
    def test_get_role_arn_default_name(self, manager):
        """Test getting role ARN with default name"""
        account_id = '111111111111'
        
        role_arn = manager.get_role_arn(account_id)
        
        assert role_arn == f'arn:aws:iam::{account_id}:role/CostGuardCollectorRole'
    
    def test_get_role_arn_custom_name(self, manager):
        """Test getting role ARN with custom name"""
        account_id = '111111111111'
        custom_role = 'CustomRoleName'
        
        role_arn = manager.get_role_arn(account_id, custom_role)
        
        assert role_arn == f'arn:aws:iam::{account_id}:role/{custom_role}'
    
    def test_assume_role_success(self, manager, mock_sts):
        """Test successful role assumption"""
        account_id = '111111111111'
        role_name = 'CostGuardCollectorRole'
        external_id = 'test-external-id'
        
        # Mock STS response
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'FwoGZXIvYXdzEBYaDH...',
                'Expiration': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        
        # Execute
        credentials = manager.assume_role(account_id, role_name, external_id)
        
        # Verify
        assert isinstance(credentials, Credentials)
        assert credentials.access_key_id == 'AKIAIOSFODNN7EXAMPLE'
        assert credentials.secret_access_key == 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
        assert credentials.session_token == 'FwoGZXIvYXdzEBYaDH...'
        
        # Verify STS was called correctly
        mock_sts.assume_role.assert_called_once()
        call_args = mock_sts.assume_role.call_args[1]
        assert call_args['RoleArn'] == f'arn:aws:iam::{account_id}:role/{role_name}'
        assert call_args['ExternalId'] == external_id
        assert call_args['DurationSeconds'] == 3600
    
    def test_assume_role_with_custom_session_name(self, manager, mock_sts):
        """Test role assumption with custom session name"""
        account_id = '111111111111'
        role_name = 'CostGuardCollectorRole'
        external_id = 'test-external-id'
        session_name = 'CustomSession'
        
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'FwoGZXIvYXdzEBYaDH...',
                'Expiration': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        
        credentials = manager.assume_role(account_id, role_name, external_id, session_name)
        
        call_args = mock_sts.assume_role.call_args[1]
        assert call_args['RoleSessionName'] == session_name
    
    def test_assume_role_access_denied(self, manager, mock_sts):
        """Test role assumption with access denied error"""
        account_id = '111111111111'
        role_name = 'CostGuardCollectorRole'
        external_id = 'wrong-external-id'
        
        # Mock access denied error
        mock_sts.assume_role.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'AssumeRole'
        )
        
        # Execute and verify exception
        with pytest.raises(ClientError) as exc_info:
            manager.assume_role(account_id, role_name, external_id)
        
        assert exc_info.value.response['Error']['Code'] == 'AccessDenied'
    
    def test_assume_role_no_such_entity(self, manager, mock_sts):
        """Test role assumption when role doesn't exist"""
        account_id = '111111111111'
        role_name = 'NonExistentRole'
        external_id = 'test-external-id'
        
        # Mock no such entity error
        mock_sts.assume_role.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchEntity', 'Message': 'Role not found'}},
            'AssumeRole'
        )
        
        # Execute and verify exception
        with pytest.raises(ClientError) as exc_info:
            manager.assume_role(account_id, role_name, external_id)
        
        assert exc_info.value.response['Error']['Code'] == 'NoSuchEntity'
    
    def test_validate_role_permissions_success(self, manager, mock_sts):
        """Test successful role permission validation"""
        account_id = '111111111111'
        external_id = 'test-external-id'
        
        # Mock successful assume role
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'FwoGZXIvYXdzEBYaDH...',
                'Expiration': datetime(2024, 1, 1, 12, 0, 0)
            }
        }
        
        result = manager.validate_role_permissions(account_id, external_id)
        
        assert result is True
    
    def test_validate_role_permissions_access_denied(self, manager, mock_sts):
        """Test role validation with access denied"""
        account_id = '111111111111'
        external_id = 'wrong-external-id'
        
        mock_sts.assume_role.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'AssumeRole'
        )
        
        result = manager.validate_role_permissions(account_id, external_id)
        
        assert result is False
    
    def test_validate_role_permissions_no_such_entity(self, manager, mock_sts):
        """Test role validation when role doesn't exist"""
        account_id = '111111111111'
        external_id = 'test-external-id'
        
        mock_sts.assume_role.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchEntity', 'Message': 'Role not found'}},
            'AssumeRole'
        )
        
        result = manager.validate_role_permissions(account_id, external_id)
        
        assert result is False
    
    @patch('src.services.multi_account.cross_account_role_manager.boto3.Session')
    def test_create_boto3_session(self, mock_session_class, manager):
        """Test creating boto3 session with credentials"""
        credentials = Credentials(
            access_key_id='AKIAIOSFODNN7EXAMPLE',
            secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            session_token='FwoGZXIvYXdzEBYaDH...',
            expiration='2024-01-01T12:00:00'
        )
        
        session = manager.create_boto3_session(credentials, region_name='us-west-2')
        
        # Verify Session was created with correct parameters
        mock_session_class.assert_called_once_with(
            aws_access_key_id='AKIAIOSFODNN7EXAMPLE',
            aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
            aws_session_token='FwoGZXIvYXdzEBYaDH...',
            region_name='us-west-2'
        )
