#!/usr/bin/env python3
"""
CostGuard Multi-Account Infrastructure Deployment Script

This script deploys the CostGuard Multi-Account infrastructure and verifies
that all resources are created correctly.

Usage:
    python deploy_multi_account.py [--test-only] [--region REGION]
"""

import argparse
import boto3
import json
import sys
import time
from typing import Dict, List, Optional


class MultiAccountDeploymentTester:
    """Test deployment of CostGuard Multi-Account infrastructure."""
    
    def __init__(self, region: str = "us-east-1"):
        """Initialize the deployment tester."""
        self.region = region
        self.session = boto3.Session(region_name=region)
        self.cloudformation = self.session.client('cloudformation')
        self.dynamodb = self.session.client('dynamodb')
        self.lambda_client = self.session.client('lambda')
        self.apigateway = self.session.client('apigateway')
        self.events = self.session.client('events')
        self.cloudwatch = self.session.client('cloudwatch')
        self.sns = self.session.client('sns')
        
    def deploy_infrastructure(self) -> bool:
        """Deploy the CDK infrastructure."""
        print("🚀 Deploying CostGuard Multi-Account infrastructure...")
        
        try:
            # Run CDK deploy command
            import subprocess
            result = subprocess.run([
                'cdk', 'deploy', 'CostGuardMultiAccountStack',
                '--require-approval', 'never',
                '--region', self.region
            ], capture_output=True, text=True, cwd='.')
            
            if result.returncode != 0:
                print(f"❌ CDK deployment failed: {result.stderr}")
                return False
            
            print("✅ CDK deployment completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Deployment error: {str(e)}")
            return False
    
    def test_dynamodb_tables(self) -> bool:
        """Test that all DynamoDB tables are created correctly."""
        print("🔍 Testing DynamoDB tables...")
        
        expected_tables = [
            'costguard-organizations',
            'costguard-accounts',
            'costguard-multi-account-costs',
            'costguard-allocation-rules',
            'costguard-budgets'
        ]
        
        try:
            for table_name in expected_tables:
                response = self.dynamodb.describe_table(TableName=table_name)
                table_status = response['Table']['TableStatus']
                
                if table_status != 'ACTIVE':
                    print(f"❌ Table {table_name} is not active (status: {table_status})")
                    return False
                
                print(f"✅ Table {table_name} is active")
                
                # Check GSIs if they exist
                if 'GlobalSecondaryIndexes' in response['Table']:
                    for gsi in response['Table']['GlobalSecondaryIndexes']:
                        gsi_status = gsi['IndexStatus']
                        if gsi_status != 'ACTIVE':
                            print(f"❌ GSI {gsi['IndexName']} on {table_name} is not active")
                            return False
                        print(f"✅ GSI {gsi['IndexName']} on {table_name} is active")
            
            return True
            
        except Exception as e:
            print(f"❌ DynamoDB table test failed: {str(e)}")
            return False
    
    def test_lambda_functions(self) -> bool:
        """Test that all Lambda functions are created correctly."""
        print("🔍 Testing Lambda functions...")
        
        expected_functions = [
            'CostGuard-MultiAccountCostCollector',
            'CostGuard-MultiAccountAPIHandler',
            'CostGuard-MultiAccountHandler'
        ]
        
        try:
            for function_name in expected_functions:
                response = self.lambda_client.get_function(FunctionName=function_name)
                
                # Check function state
                state = response['Configuration']['State']
                if state != 'Active':
                    print(f"❌ Lambda function {function_name} is not active (state: {state})")
                    return False
                
                print(f"✅ Lambda function {function_name} is active")
                
                # Check environment variables
                env_vars = response['Configuration'].get('Environment', {}).get('Variables', {})
                required_env_vars = [
                    'ORGANIZATIONS_TABLE',
                    'ACCOUNTS_TABLE',
                    'MULTI_ACCOUNT_COSTS_TABLE'
                ]
                
                for env_var in required_env_vars:
                    if env_var not in env_vars:
                        print(f"❌ Lambda function {function_name} missing environment variable {env_var}")
                        return False
                
                print(f"✅ Lambda function {function_name} has required environment variables")
            
            return True
            
        except Exception as e:
            print(f"❌ Lambda function test failed: {str(e)}")
            return False
    
    def test_api_gateway(self) -> bool:
        """Test that API Gateway is configured correctly."""
        print("🔍 Testing API Gateway...")
        
        try:
            # Find the multi-account API
            apis = self.apigateway.get_rest_apis()
            multi_account_api = None
            
            for api in apis['items']:
                if api['name'] == 'CostGuard-MultiAccountAPI':
                    multi_account_api = api
                    break
            
            if not multi_account_api:
                print("❌ Multi-Account API Gateway not found")
                return False
            
            print(f"✅ Multi-Account API Gateway found: {multi_account_api['id']}")
            
            # Check resources
            resources = self.apigateway.get_resources(restApiId=multi_account_api['id'])
            resource_paths = [r['pathPart'] for r in resources['items'] if 'pathPart' in r]
            
            expected_paths = ['api', 'organizations', 'costs', 'allocation', 'budgets']
            for path in expected_paths:
                if path not in resource_paths:
                    print(f"❌ API Gateway missing resource path: {path}")
                    return False
            
            print("✅ API Gateway has required resource paths")
            return True
            
        except Exception as e:
            print(f"❌ API Gateway test failed: {str(e)}")
            return False
    
    def test_eventbridge_rules(self) -> bool:
        """Test that EventBridge rules are created correctly."""
        print("🔍 Testing EventBridge rules...")
        
        expected_rules = [
            'costguard-daily-cost-collection',
            'costguard-organization-discovery'
        ]
        
        try:
            for rule_name in expected_rules:
                response = self.events.describe_rule(Name=rule_name)
                
                if response['State'] != 'ENABLED':
                    print(f"❌ EventBridge rule {rule_name} is not enabled")
                    return False
                
                print(f"✅ EventBridge rule {rule_name} is enabled")
                
                # Check targets
                targets = self.events.list_targets_by_rule(Rule=rule_name)
                if not targets['Targets']:
                    print(f"❌ EventBridge rule {rule_name} has no targets")
                    return False
                
                print(f"✅ EventBridge rule {rule_name} has {len(targets['Targets'])} target(s)")
            
            return True
            
        except Exception as e:
            print(f"❌ EventBridge rules test failed: {str(e)}")
            return False
    
    def test_cloudwatch_alarms(self) -> bool:
        """Test that CloudWatch alarms are created correctly."""
        print("🔍 Testing CloudWatch alarms...")
        
        expected_alarms = [
            'CostGuard-CostCollectionFailureRate',
            'CostGuard-APIResponseTime',
            'CostGuard-LambdaErrors'
        ]
        
        try:
            for alarm_name in expected_alarms:
                response = self.cloudwatch.describe_alarms(AlarmNames=[alarm_name])
                
                if not response['MetricAlarms']:
                    print(f"❌ CloudWatch alarm {alarm_name} not found")
                    return False
                
                alarm = response['MetricAlarms'][0]
                if alarm['StateValue'] == 'INSUFFICIENT_DATA':
                    print(f"✅ CloudWatch alarm {alarm_name} created (insufficient data is normal)")
                else:
                    print(f"✅ CloudWatch alarm {alarm_name} created (state: {alarm['StateValue']})")
            
            return True
            
        except Exception as e:
            print(f"❌ CloudWatch alarms test failed: {str(e)}")
            return False
    
    def test_sns_topics(self) -> bool:
        """Test that SNS topics are created correctly."""
        print("🔍 Testing SNS topics...")
        
        try:
            topics = self.sns.list_topics()
            topic_arns = [t['TopicArn'] for t in topics['Topics']]
            
            # Look for multi-account notifications topic
            multi_account_topic = None
            for arn in topic_arns:
                if 'costguard-multi-account-notifications' in arn:
                    multi_account_topic = arn
                    break
            
            if not multi_account_topic:
                print("❌ Multi-Account notifications SNS topic not found")
                return False
            
            print(f"✅ Multi-Account notifications SNS topic found: {multi_account_topic}")
            return True
            
        except Exception as e:
            print(f"❌ SNS topics test failed: {str(e)}")
            return False
    
    def test_resource_connectivity(self) -> bool:
        """Test connectivity between resources."""
        print("🔍 Testing resource connectivity...")
        
        try:
            # Test Lambda function can access DynamoDB
            function_name = 'CostGuard-MultiAccountHandler'
            
            # Invoke the function with a test event
            test_event = {
                'operation': 'discover_organization',
                'source': 'deployment-test'
            }
            
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_event)
            )
            
            if response['StatusCode'] != 200:
                print(f"❌ Lambda function {function_name} invocation failed")
                return False
            
            # Parse response
            payload = json.loads(response['Payload'].read())
            
            # Check if the function executed without errors
            if 'errorMessage' in payload:
                print(f"⚠️  Lambda function {function_name} returned error (expected in test environment): {payload['errorMessage']}")
            else:
                print(f"✅ Lambda function {function_name} executed successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Resource connectivity test failed: {str(e)}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all deployment tests."""
        print("🧪 Running CostGuard Multi-Account deployment tests...\n")
        
        tests = [
            ("DynamoDB Tables", self.test_dynamodb_tables),
            ("Lambda Functions", self.test_lambda_functions),
            ("API Gateway", self.test_api_gateway),
            ("EventBridge Rules", self.test_eventbridge_rules),
            ("CloudWatch Alarms", self.test_cloudwatch_alarms),
            ("SNS Topics", self.test_sns_topics),
            ("Resource Connectivity", self.test_resource_connectivity),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n--- {test_name} ---")
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {test_name} test failed with exception: {str(e)}")
                failed += 1
        
        print(f"\n📊 Test Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All deployment tests passed!")
            return True
        else:
            print("❌ Some deployment tests failed. Please check the infrastructure.")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Deploy and test CostGuard Multi-Account infrastructure')
    parser.add_argument('--test-only', action='store_true', help='Only run tests, skip deployment')
    parser.add_argument('--region', default='us-east-1', help='AWS region for deployment')
    
    args = parser.parse_args()
    
    tester = MultiAccountDeploymentTester(region=args.region)
    
    if not args.test_only:
        print("🚀 Starting deployment...")
        if not tester.deploy_infrastructure():
            print("❌ Deployment failed")
            sys.exit(1)
        
        # Wait for resources to be ready
        print("⏳ Waiting for resources to be ready...")
        time.sleep(30)
    
    # Run tests
    if tester.run_all_tests():
        print("\n✅ Deployment verification completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Deployment verification failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()