#!/bin/bash

# CostGuard Multi-Account Infrastructure Deployment Script
#
# This script deploys the complete CostGuard infrastructure including:
# - Phase 1-4: Single-account infrastructure (existing)
# - Phase 5: Multi-account infrastructure (new)
# - Cross-account roles deployment
# - Organization discovery initialization
# - Deployment verification
#
# Usage:
#   ./deploy.sh [OPTIONS]
#
# Options:
#   --region REGION          AWS region (default: us-east-1)
#   --profile PROFILE        AWS profile to use
#   --skip-single-account    Skip Phase 1-4 deployment (deploy only multi-account)
#   --skip-multi-account     Skip Phase 5 deployment (deploy only single-account)
#   --skip-cross-account     Skip cross-account roles deployment
#   --skip-verification      Skip deployment verification
#   --dry-run               Show what would be deployed without actually deploying
#   --help                  Show this help message

set -e  # Exit on any error

# Default values
REGION="us-east-1"
PROFILE=""
SKIP_SINGLE_ACCOUNT=false
SKIP_MULTI_ACCOUNT=false
SKIP_CROSS_ACCOUNT=false
SKIP_VERIFICATION=false
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
CostGuard Multi-Account Infrastructure Deployment Script

This script deploys the complete CostGuard infrastructure including both
single-account (Phase 1-4) and multi-account (Phase 5) components.

Usage:
    ./deploy.sh [OPTIONS]

Options:
    --region REGION          AWS region (default: us-east-1)
    --profile PROFILE        AWS profile to use
    --skip-single-account    Skip Phase 1-4 deployment (deploy only multi-account)
    --skip-multi-account     Skip Phase 5 deployment (deploy only single-account)
    --skip-cross-account     Skip cross-account roles deployment
    --skip-verification      Skip deployment verification
    --dry-run               Show what would be deployed without actually deploying
    --help                  Show this help message

Examples:
    # Deploy everything with default settings
    ./deploy.sh

    # Deploy to specific region with profile
    ./deploy.sh --region us-west-2 --profile production

    # Deploy only multi-account components
    ./deploy.sh --skip-single-account

    # Dry run to see what would be deployed
    ./deploy.sh --dry-run

Prerequisites:
    - AWS CLI configured with appropriate permissions
    - CDK CLI installed (npm install -g aws-cdk)
    - Python 3.11+ with required dependencies
    - Organization admin permissions for cross-account setup

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --skip-single-account)
            SKIP_SINGLE_ACCOUNT=true
            shift
            ;;
        --skip-multi-account)
            SKIP_MULTI_ACCOUNT=true
            shift
            ;;
        --skip-cross-account)
            SKIP_CROSS_ACCOUNT=true
            shift
            ;;
        --skip-verification)
            SKIP_VERIFICATION=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Set AWS profile if provided
if [[ -n "$PROFILE" ]]; then
    export AWS_PROFILE="$PROFILE"
    log_info "Using AWS profile: $PROFILE"
fi

# Set AWS region
export AWS_DEFAULT_REGION="$REGION"
log_info "Using AWS region: $REGION"

# Validate prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check CDK CLI
    if ! command -v cdk &> /dev/null; then
        log_error "CDK CLI is not installed. Please install it with: npm install -g aws-cdk"
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3.11+."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid. Please run 'aws configure'."
        exit 1
    fi
    
    # Get account ID and user info
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    USER_ARN=$(aws sts get-caller-identity --query Arn --output text)
    
    log_success "Prerequisites check passed"
    log_info "AWS Account ID: $ACCOUNT_ID"
    log_info "User/Role: $USER_ARN"
}

# Bootstrap CDK if needed
bootstrap_cdk() {
    log_info "Checking CDK bootstrap status..."
    
    # Check if CDK is already bootstrapped
    if aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" &> /dev/null; then
        log_info "CDK already bootstrapped in region $REGION"
    else
        log_info "Bootstrapping CDK in region $REGION..."
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would run: cdk bootstrap aws://$ACCOUNT_ID/$REGION"
        else
            cdk bootstrap "aws://$ACCOUNT_ID/$REGION"
            log_success "CDK bootstrap completed"
        fi
    fi
}

# Deploy single-account infrastructure (Phase 1-4)
deploy_single_account() {
    if [[ "$SKIP_SINGLE_ACCOUNT" == "true" ]]; then
        log_info "Skipping single-account infrastructure deployment"
        return
    fi
    
    log_info "Deploying single-account infrastructure (Phase 1-4)..."
    
    cd infrastructure
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run: cdk deploy CostGuardStack --require-approval never"
    else
        cdk deploy CostGuardStack --require-approval never --region "$REGION"
        log_success "Single-account infrastructure deployed successfully"
    fi
    
    cd ..
}

# Deploy multi-account infrastructure (Phase 5)
deploy_multi_account() {
    if [[ "$SKIP_MULTI_ACCOUNT" == "true" ]]; then
        log_info "Skipping multi-account infrastructure deployment"
        return
    fi
    
    log_info "Deploying multi-account infrastructure (Phase 5)..."
    
    cd infrastructure
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run: cdk deploy CostGuardMultiAccountStack --require-approval never"
    else
        cdk deploy CostGuardMultiAccountStack --require-approval never --region "$REGION"
        log_success "Multi-account infrastructure deployed successfully"
    fi
    
    cd ..
}

# Deploy cross-account roles
deploy_cross_account_roles() {
    if [[ "$SKIP_CROSS_ACCOUNT" == "true" ]]; then
        log_info "Skipping cross-account roles deployment"
        return
    fi
    
    log_info "Deploying cross-account roles..."
    
    # Check if we're in an organization
    if ! aws organizations describe-organization &> /dev/null; then
        log_warning "Not in an AWS Organization. Cross-account roles must be deployed manually."
        log_info "Please see infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md for instructions."
        return
    fi
    
    # Get organization ID
    ORG_ID=$(aws organizations describe-organization --query Organization.Id --output text)
    log_info "Organization ID: $ORG_ID"
    
    # Get list of accounts
    ACCOUNTS=$(aws organizations list-accounts --query 'Accounts[?Status==`ACTIVE`].[Id,Name]' --output text)
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would deploy cross-account roles to organization accounts"
        echo "$ACCOUNTS" | while read -r account_id account_name; do
            log_info "[DRY RUN] Would deploy to account: $account_id ($account_name)"
        done
    else
        # Deploy using StackSets (requires organization admin permissions)
        log_info "Deploying cross-account roles using StackSets..."
        
        # Create StackSet if it doesn't exist
        STACKSET_NAME="CostGuardCrossAccountRoles"
        
        if ! aws cloudformation describe-stack-set --stack-set-name "$STACKSET_NAME" &> /dev/null; then
            log_info "Creating StackSet: $STACKSET_NAME"
            aws cloudformation create-stack-set \
                --stack-set-name "$STACKSET_NAME" \
                --template-body file://infrastructure/stackset_template.yaml \
                --capabilities CAPABILITY_IAM \
                --parameters ParameterKey=MasterAccountId,ParameterValue="$ACCOUNT_ID" \
                --administration-role-arn "arn:aws:iam::$ACCOUNT_ID:role/AWSCloudFormationStackSetAdministrationRole" \
                --execution-role-name "AWSCloudFormationStackSetExecutionRole"
        else
            log_info "Updating existing StackSet: $STACKSET_NAME"
            aws cloudformation update-stack-set \
                --stack-set-name "$STACKSET_NAME" \
                --template-body file://infrastructure/stackset_template.yaml \
                --capabilities CAPABILITY_IAM \
                --parameters ParameterKey=MasterAccountId,ParameterValue="$ACCOUNT_ID"
        fi
        
        # Deploy to all organization accounts
        log_info "Deploying StackSet to organization accounts..."
        aws cloudformation create-stack-instances \
            --stack-set-name "$STACKSET_NAME" \
            --deployment-targets OrganizationalUnitIds="$ORG_ID" \
            --regions "$REGION" \
            --operation-preferences MaxConcurrentPercentage=100,FailureTolerancePercentage=10
        
        log_success "Cross-account roles deployment initiated"
        log_info "Monitor progress in CloudFormation StackSets console"
    fi
}

# Initialize organization discovery
initialize_organization_discovery() {
    if [[ "$SKIP_MULTI_ACCOUNT" == "true" ]]; then
        log_info "Skipping organization discovery initialization"
        return
    fi
    
    log_info "Initializing organization discovery..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would invoke organization discovery Lambda function"
    else
        # Invoke the organization discovery function
        FUNCTION_NAME="CostGuard-MultiAccountHandler"
        
        # Create test event for organization discovery
        cat > /tmp/org_discovery_event.json << EOF
{
    "operation": "discover_organization",
    "source": "deployment-script"
}
EOF
        
        log_info "Invoking organization discovery function..."
        aws lambda invoke \
            --function-name "$FUNCTION_NAME" \
            --payload file:///tmp/org_discovery_event.json \
            --region "$REGION" \
            /tmp/org_discovery_response.json
        
        # Check response
        if grep -q "errorMessage" /tmp/org_discovery_response.json; then
            log_warning "Organization discovery returned an error (this may be expected in test environments)"
            cat /tmp/org_discovery_response.json
        else
            log_success "Organization discovery completed successfully"
        fi
        
        # Clean up temp files
        rm -f /tmp/org_discovery_event.json /tmp/org_discovery_response.json
    fi
}

# Verify deployment
verify_deployment() {
    if [[ "$SKIP_VERIFICATION" == "true" ]]; then
        log_info "Skipping deployment verification"
        return
    fi
    
    log_info "Verifying deployment..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run deployment verification tests"
    else
        # Run infrastructure tests
        cd infrastructure
        python deploy_multi_account.py --test-only --region "$REGION"
        cd ..
        
        log_success "Deployment verification completed"
    fi
}

# Main deployment function
main() {
    log_info "Starting CostGuard Multi-Account Infrastructure Deployment"
    log_info "Region: $REGION"
    log_info "Dry Run: $DRY_RUN"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No actual changes will be made"
    fi
    
    # Step 1: Check prerequisites
    check_prerequisites
    
    # Step 2: Bootstrap CDK
    bootstrap_cdk
    
    # Step 3: Deploy single-account infrastructure
    deploy_single_account
    
    # Step 4: Deploy multi-account infrastructure
    deploy_multi_account
    
    # Step 5: Deploy cross-account roles
    deploy_cross_account_roles
    
    # Step 6: Initialize organization discovery
    initialize_organization_discovery
    
    # Step 7: Verify deployment
    verify_deployment
    
    # Summary
    log_success "Deployment completed successfully!"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        echo ""
        log_info "Next Steps:"
        log_info "1. Configure SNS topic subscriptions for alerts"
        log_info "2. Set up cross-account roles in member accounts (if not using StackSets)"
        log_info "3. Test multi-account cost collection"
        log_info "4. Configure cost allocation rules"
        log_info "5. Set up organization-wide budgets"
        echo ""
        log_info "Documentation:"
        log_info "- Member account setup: infrastructure/MEMBER_ACCOUNT_DEPLOYMENT.md"
        log_info "- Cross-account setup: infrastructure/CROSS_ACCOUNT_SETUP.md"
        log_info "- API documentation: docs/API_EXAMPLES.md"
    fi
}

# Run main function
main "$@"