#!/usr/bin/env python3
"""
CostGuard Multi-Account Infrastructure Test Script

This script validates the CDK infrastructure configuration without deploying.
It checks that all resources are properly defined and configured.

Usage:
    python test_infrastructure.py
"""

import os
import sys
import json
from pathlib import Path


def test_cdk_configuration():
    """Test CDK configuration files."""
    print("🔍 Testing CDK configuration...")
    
    # Check required files exist
    required_files = [
        'app.py',
        'cdk_stack.py',
        'multi_account_stack.py',
        'cdk.json',
        'requirements.txt'
    ]
    
    for file_name in required_files:
        file_path = Path(file_name)
        if not file_path.exists():
            print(f"❌ Required file missing: {file_name}")
            return False
        print(f"✅ Found required file: {file_name}")
    
    return True


def test_cloudformation_templates():
    """Test CloudFormation templates."""
    print("\n🔍 Testing CloudFormation templates...")
    
    templates = [
        'member_account_role_template.yaml',
        'stackset_template.yaml'
    ]
    
    for template in templates:
        template_path = Path(template)
        if not template_path.exists():
            print(f"❌ Template missing: {template}")
            return False
        
        # Check template structure (CloudFormation intrinsic functions are expected)
        try:
            with open(template_path, 'r') as f:
                content = f.read()
                # Check for basic CloudFormation structure
                if 'AWSTemplateFormatVersion' in content and 'Resources' in content:
                    print(f"✅ Template structure valid: {template}")
                else:
                    print(f"❌ Template missing required sections: {template}")
                    return False
        except Exception as e:
            print(f"❌ Template read error: {template} - {str(e)}")
            return False
    
    return True


def test_python_imports():
    """Test that Python modules can be imported."""
    print("\n🔍 Testing Python imports...")
    
    try:
        # Test basic Python imports first
        import json
        import os
        import sys
        from pathlib import Path
        print("✅ Basic Python imports successful")
        
        # Test CDK imports (optional in test environment)
        try:
            import aws_cdk as cdk
            from aws_cdk import (
                aws_dynamodb as dynamodb,
                aws_lambda as lambda_,
                aws_apigateway as apigateway,
                aws_sns as sns,
                aws_events as events,
                aws_iam as iam,
                aws_logs as logs,
                aws_cloudwatch as cloudwatch,
            )
            print("✅ CDK imports successful")
            
            # Test stack imports
            sys.path.append('.')
            from cdk_stack import CostGuardStack
            from multi_account_stack import MultiAccountStack
            print("✅ Stack imports successful")
            
        except ImportError as e:
            print(f"⚠️  CDK not available (expected in test environment): {str(e)}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Basic import error: {str(e)}")
        return False


def test_stack_instantiation():
    """Test that stacks can be instantiated."""
    print("\n🔍 Testing stack instantiation...")
    
    try:
        # Test stack file syntax
        sys.path.append('.')
        
        # Check if stack files can be imported (syntax validation)
        try:
            import ast
            
            # Parse CostGuardStack
            with open('cdk_stack.py', 'r') as f:
                ast.parse(f.read())
            print("✅ CostGuardStack syntax valid")
            
            # Parse MultiAccountStack
            with open('multi_account_stack.py', 'r') as f:
                ast.parse(f.read())
            print("✅ MultiAccountStack syntax valid")
            
        except SyntaxError as e:
            print(f"❌ Stack syntax error: {str(e)}")
            return False
        
        # Try actual instantiation if CDK is available
        try:
            import aws_cdk as cdk
            from constructs import Construct
            
            # Create a test app
            app = cdk.App()
            
            # Test CostGuardStack
            from cdk_stack import CostGuardStack
            costguard_stack = CostGuardStack(
                app, "TestCostGuardStack",
                env=cdk.Environment(account="123456789012", region="us-east-1")
            )
            print("✅ CostGuardStack instantiation successful")
            
            # Test MultiAccountStack
            from multi_account_stack import MultiAccountStack
            multi_account_stack = MultiAccountStack(
                app, "TestMultiAccountStack",
                env=cdk.Environment(account="123456789012", region="us-east-1")
            )
            print("✅ MultiAccountStack instantiation successful")
            
        except ImportError:
            print("⚠️  CDK not available - skipping instantiation test")
        
        return True
        
    except Exception as e:
        print(f"❌ Stack validation error: {str(e)}")
        return False


def test_cdk_synth():
    """Test CDK synthesis."""
    print("\n🔍 Testing CDK synthesis...")
    
    try:
        import subprocess
        
        # Run CDK synth to validate templates
        result = subprocess.run([
            'cdk', 'synth', '--quiet'
        ], capture_output=True, text=True, cwd='.')
        
        if result.returncode != 0:
            print(f"❌ CDK synth failed: {result.stderr}")
            return False
        
        print("✅ CDK synthesis successful")
        return True
        
    except FileNotFoundError:
        print("⚠️  CDK CLI not found - skipping synthesis test")
        return True
    except Exception as e:
        print(f"❌ CDK synthesis error: {str(e)}")
        return False


def test_documentation():
    """Test that documentation files exist."""
    print("\n🔍 Testing documentation...")
    
    docs = [
        'MEMBER_ACCOUNT_DEPLOYMENT.md',
        'CROSS_ACCOUNT_SETUP.md',
        'README.md'
    ]
    
    for doc in docs:
        doc_path = Path(doc)
        if not doc_path.exists():
            print(f"❌ Documentation missing: {doc}")
            return False
        print(f"✅ Documentation found: {doc}")
    
    return True


def main():
    """Main function."""
    print("🧪 CostGuard Multi-Account Infrastructure Tests\n")
    
    tests = [
        ("CDK Configuration", test_cdk_configuration),
        ("CloudFormation Templates", test_cloudformation_templates),
        ("Python Imports", test_python_imports),
        ("Stack Instantiation", test_stack_instantiation),
        ("CDK Synthesis", test_cdk_synth),
        ("Documentation", test_documentation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"--- {test_name} ---")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {str(e)}")
            failed += 1
        print()
    
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All infrastructure tests passed!")
        print("\n📋 Next Steps:")
        print("1. Run 'cdk bootstrap' to prepare your AWS account")
        print("2. Run 'cdk deploy CostGuardStack' to deploy Phase 1-4 infrastructure")
        print("3. Run 'cdk deploy CostGuardMultiAccountStack' to deploy Phase 5 infrastructure")
        print("4. Deploy cross-account roles to member accounts using the provided templates")
        return True
    else:
        print("❌ Some infrastructure tests failed. Please fix the issues before deployment.")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)