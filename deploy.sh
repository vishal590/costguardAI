#!/bin/bash
# Deployment script for Cost Data Pipeline (Unix/Linux/macOS)
# This script sets up the environment, packages the Lambda function, and deploys infrastructure

set -e  # Exit on error

echo "========================================="
echo "Cost Data Pipeline Deployment Script"
echo "========================================="
echo ""

# Step 1: Create Python virtual environment
echo "Step 1: Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Step 2: Activate virtual environment and install dependencies
echo "Step 2: Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Step 3: Run tests
echo "Step 3: Running tests..."
pytest --cov=src --cov-report=term-missing tests/
if [ $? -ne 0 ]; then
    echo "✗ Tests failed. Please fix errors before deploying."
    exit 1
fi
echo "✓ All tests passed"
echo ""

# Step 4: Package Lambda function
echo "Step 4: Packaging Lambda function..."
mkdir -p dist
cd dist
rm -rf lambda_package lambda_package.zip

# Create package directory
mkdir lambda_package

# Copy source code
cp -r ../src/* lambda_package/

# Install dependencies (excluding dev dependencies)
pip install -r ../requirements.txt -t lambda_package/ --no-deps

# Create zip file
cd lambda_package
zip -r ../lambda_package.zip . -q
cd ..
rm -rf lambda_package

echo "✓ Lambda package created: dist/lambda_package.zip"
cd ..
echo ""

# Step 5: Install CDK dependencies
echo "Step 5: Installing CDK dependencies..."
cd infrastructure
pip install -r requirements.txt
echo "✓ CDK dependencies installed"
echo ""

# Step 6: Deploy infrastructure
echo "Step 6: Deploying infrastructure with AWS CDK..."
echo "Note: This requires AWS credentials to be configured"
echo ""

# Check if CDK is bootstrapped
echo "Checking CDK bootstrap status..."
cdk bootstrap

# Deploy stack
echo "Deploying stack..."
cdk deploy --require-approval never

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Infrastructure deployed successfully!"
    echo ""
    echo "========================================="
    echo "Deployment Complete!"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "1. Note the API Gateway endpoint URL from the output above"
    echo "2. Retrieve your API key using:"
    echo "   aws apigateway get-api-key --api-key <API_KEY_ID> --include-value --query 'value' --output text"
    echo "3. Test the API using the examples in docs/API_EXAMPLES.md"
    echo ""
else
    echo "✗ Deployment failed. Check the error messages above."
    exit 1
fi

cd ..
