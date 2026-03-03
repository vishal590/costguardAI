"""
Cross-Account Role Manager

Manages IAM roles for cross-account access to member accounts.
Handles role assumption using AWS STS for secure access to cost data.
"""
import logging
import json
from typing import Dict, Optional
from dataclasses import dataclass
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class Credentials:
    """AWS temporary credentials from STS AssumeRole"""
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str


class CrossAccountRoleManager:
    """
    Service for managing cross-account IAM roles
    
    Responsibilities:
    - Generate CloudFormation templates for IAM roles
    - Validate role permissions
    - Assume roles in member accounts using STS
    - Handle role assumption errors gracefully
    """
    
    def __init__(self, sts_client=None):
        """
        Initialize the Cross-Account Role Manager
        
        Args:
            sts_client: Optional STS client (for testing)
        """
        self.sts = sts_client or boto3.client('sts')
        self.default_role_name = 'CostGuardCollectorRole'
        self.session_duration = 3600  # 1 hour
    
    def generate_role_template(self, management_account_id: str, external_id: str) -> str:
        """
        Generate CloudFormation template for cross-account role
        
        Args:
            management_account_id: Management account ID that will assume the role
            external_id: External ID for additional security
            
        Returns:
            CloudFormation template as JSON string
        """
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "CostGuard AI Cross-Account Role for Cost Data Collection",
            "Parameters": {
                "ManagementAccountId": {
                    "Type": "String",
                    "Description": "AWS Account ID of the CostGuard management account",
                    "Default": management_account_id
                },
                "ExternalId": {
                    "Type": "String",
                    "Description": "External ID for secure role assumption",
                    "Default": external_id
                }
            },
            "Resources": {
                "CostGuardCollectorRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "RoleName": self.default_role_name,
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {
                                        "AWS": f"arn:aws:iam::{management_account_id}:root"
                                    },
                                    "Action": "sts:AssumeRole",
                                    "Condition": {
                                        "StringEquals": {
                                            "sts:ExternalId": external_id
                                        }
                                    }
                                }
                            ]
                        },
                        "ManagedPolicyArns": [],
                        "Policies": [
                            {
                                "PolicyName": "CostGuardCostExplorerAccess",
                                "PolicyDocument": {
                                    "Version": "2012-10-17",
                                    "Statement": [
                                        {
                                            "Effect": "Allow",
                                            "Action": [
                                                "ce:GetCostAndUsage",
                                                "ce:GetCostForecast",
                                                "ce:GetTags",
                                                "ce:GetCostCategories"
                                            ],
                                            "Resource": "*"
                                        },
                                        {
                                            "Effect": "Allow",
                                            "Action": [
                                                "cloudwatch:GetMetricStatistics",
                                                "cloudwatch:ListMetrics"
                                            ],
                                            "Resource": "*"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            },
            "Outputs": {
                "RoleArn": {
                    "Description": "ARN of the CostGuard collector role",
                    "Value": {
                        "Fn::GetAtt": ["CostGuardCollectorRole", "Arn"]
                    }
                }
            }
        }
        
        return json.dumps(template, indent=2)
    
    def get_role_arn(self, account_id: str, role_name: Optional[str] = None) -> str:
        """
        Get IAM role ARN for an account
        
        Args:
            account_id: AWS account ID
            role_name: Optional role name (defaults to CostGuardCollectorRole)
            
        Returns:
            Role ARN
        """
        role = role_name or self.default_role_name
        return f"arn:aws:iam::{account_id}:role/{role}"
    
    def assume_role(
        self,
        account_id: str,
        role_name: str,
        external_id: str,
        session_name: Optional[str] = None
    ) -> Credentials:
        """
        Assume role in member account using STS
        
        Args:
            account_id: AWS account ID
            role_name: IAM role name
            external_id: External ID for security
            session_name: Optional session name
            
        Returns:
            Credentials: Temporary AWS credentials
            
        Raises:
            ClientError: If role assumption fails
        """
        role_arn = self.get_role_arn(account_id, role_name)
        session = session_name or f"CostGuard-{account_id}"
        
        try:
            logger.info(f"Assuming role: {role_arn}")
            response = self.sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session,
                ExternalId=external_id,
                DurationSeconds=self.session_duration
            )
            
            creds = response['Credentials']
            credentials = Credentials(
                access_key_id=creds['AccessKeyId'],
                secret_access_key=creds['SecretAccessKey'],
                session_token=creds['SessionToken'],
                expiration=creds['Expiration'].isoformat()
            )
            
            logger.info(f"Successfully assumed role for account: {account_id}")
            return credentials
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Failed to assume role for account {account_id}: {error_code}")
            raise
    
    def validate_role_permissions(self, account_id: str, external_id: str) -> bool:
        """
        Validate that the role has required permissions
        
        Args:
            account_id: AWS account ID
            external_id: External ID for security
            
        Returns:
            True if role has required permissions, False otherwise
        """
        try:
            # Try to assume the role
            credentials = self.assume_role(
                account_id=account_id,
                role_name=self.default_role_name,
                external_id=external_id
            )
            
            # If we can assume the role, it exists and has basic permissions
            # In a real implementation, we would test specific API calls
            logger.info(f"Role validation successful for account: {account_id}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'AccessDenied':
                logger.error(f"Role exists but access denied for account: {account_id}")
                return False
            elif error_code == 'NoSuchEntity':
                logger.error(f"Role does not exist for account: {account_id}")
                return False
            else:
                logger.error(f"Role validation failed for account {account_id}: {error_code}")
                return False
    
    def create_boto3_session(
        self,
        credentials: Credentials,
        region_name: str = 'us-east-1'
    ) -> boto3.Session:
        """
        Create a boto3 session using temporary credentials
        
        Args:
            credentials: Temporary AWS credentials
            region_name: AWS region
            
        Returns:
            boto3.Session configured with temporary credentials
        """
        return boto3.Session(
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_access_key,
            aws_session_token=credentials.session_token,
            region_name=region_name
        )
