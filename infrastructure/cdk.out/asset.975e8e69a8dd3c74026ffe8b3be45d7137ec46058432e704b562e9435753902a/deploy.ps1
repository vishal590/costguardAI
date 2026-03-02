# Deployment script for Cost Data Pipeline (Windows PowerShell)
# This script sets up the environment, packages the Lambda function, and deploys infrastructure

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Cost Data Pipeline Deployment Script" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create Python virtual environment
Write-Host "Step 1: Creating Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}
Write-Host ""

# Step 2: Activate virtual environment and install dependencies
Write-Host "Step 2: Installing dependencies..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt
Write-Host "✓ Dependencies installed" -ForegroundColor Green
Write-Host ""

# Step 3: Run tests
Write-Host "Step 3: Running tests..." -ForegroundColor Yellow
pytest --cov=src --cov-report=term-missing tests/
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Tests failed. Please fix errors before deploying." -ForegroundColor Red
    exit 1
}
Write-Host "✓ All tests passed" -ForegroundColor Green
Write-Host ""

# Step 4: Package Lambda function
Write-Host "Step 4: Packaging Lambda function..." -ForegroundColor Yellow
if (-not (Test-Path "dist")) {
    New-Item -ItemType Directory -Path "dist" | Out-Null
}
Set-Location dist

# Remove old package if exists
if (Test-Path "lambda_package") {
    Remove-Item -Recurse -Force lambda_package
}
if (Test-Path "lambda_package.zip") {
    Remove-Item -Force lambda_package.zip
}

# Create package directory
New-Item -ItemType Directory -Path "lambda_package" | Out-Null

# Copy source code
Copy-Item -Recurse -Path "..\src\*" -Destination "lambda_package\"

# Install dependencies (excluding dev dependencies)
pip install -r ..\requirements.txt -t lambda_package\ --no-deps

# Create zip file
Compress-Archive -Path "lambda_package\*" -DestinationPath "lambda_package.zip" -Force
Remove-Item -Recurse -Force lambda_package

Write-Host "✓ Lambda package created: dist\lambda_package.zip" -ForegroundColor Green
Set-Location ..
Write-Host ""

# Step 5: Install CDK dependencies
Write-Host "Step 5: Installing CDK dependencies..." -ForegroundColor Yellow
Set-Location infrastructure
pip install -r requirements.txt
Write-Host "✓ CDK dependencies installed" -ForegroundColor Green
Write-Host ""

# Step 6: Deploy infrastructure
Write-Host "Step 6: Deploying infrastructure with AWS CDK..." -ForegroundColor Yellow
Write-Host "Note: This requires AWS credentials to be configured" -ForegroundColor Cyan
Write-Host ""

# Check if CDK is bootstrapped
Write-Host "Checking CDK bootstrap status..." -ForegroundColor Yellow
cdk bootstrap

# Deploy stack
Write-Host "Deploying stack..." -ForegroundColor Yellow
cdk deploy --require-approval never

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Infrastructure deployed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "Deployment Complete!" -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Note the API Gateway endpoint URL from the output above"
    Write-Host "2. Retrieve your API key using:"
    Write-Host "   aws apigateway get-api-key --api-key <API_KEY_ID> --include-value --query 'value' --output text"
    Write-Host "3. Test the API using the examples in docs\API_EXAMPLES.md"
    Write-Host ""
} else {
    Write-Host "✗ Deployment failed. Check the error messages above." -ForegroundColor Red
    exit 1
}

Set-Location ..
