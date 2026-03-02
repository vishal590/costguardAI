#!/bin/bash

# CostGuard Multi-Account Infrastructure Rollback Script
#
# This script rolls back the CostGuard infrastructure deployment including:
# - Phase 5: Multi-account infrastructure rollback
# - Phase 1-4: Single-account infrastructure rollback (optional)
# - Cross-account roles cleanup
# - Deployment verification
#
# Usage:
#   ./rollback.sh [OPTIONS]
#
# Options:
#   --region REGION          AWS region (default: us-east-1)
#   --profile PROFILE        AWS profile to use
#   --rollback-all           Rollback both single-account and multi-account stacks
#   --rollback-single        Rollback only single-account stack (Phase 1-4)
#   --rollback-multi         Rollback only multi-account stack (Phase 5) [default]
#   --keep-data              Keep DynamoDB tables (don't delete data)
#   --skip-cross-account     Skip cross-account roles cleanup
#   --skip-verification      Skip rollback verification
#   --dry-run               Show what would be rolled back without actually doing it
#   --help                  Show this help message

set -e  # Exit on any error

# Default values
REGION="us-east-1"
PROFILE=""
ROLLBACK_ALL=false
ROLLBACK_SINGLE=false
ROLLBACK_MULTI=true  # Default to rolling back multi-account only
KEEP_DATA=false
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
CostGuard Multi-Account Infrastructure Rollback Script

This script rolls back the CostGuard infrastructure deployment.

Usage:
    ./rollback.sh [OPTIONS]

Options:
    --region REGION          AWS region (default: us-east-1)
    --profile PROFILE        AWS profile to use
    --rollback-all           Rollback both single-account and multi-account stacks
    --rollback-single        Rollback only single-account stack (Phase 1-4)
    --rollback-multi         Rollback only multi-account stack (Phase 5) [default]
    --keep-data              Keep DynamoDB tables (don't delete data)
    --skip-cross-account     Skip cross-account roles cleanup
    --skip-verification      Skip rollback verification
    --dry-run               Show what would be rolled back without actually doing it
    --help                  Show this help message

Examples:
    # Rollback multi-account stack only (default)
    ./rollback.sh

    # Rollback everything including single-account stack
    ./rollback.sh --rollback-all

    # Rollback but keep data in DynamoDB tables
    ./rollback.sh --keep-data

    # Dry run to see what would be rolled back
    ./rollback.sh --dry-run

    # Rollback with specific region and profile
    ./rollback.sh --region us-west-2 --profile production

WARNING:
    This script will delete AWS resources. Make sure you have backups
    of any important data before proceeding.

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
        --rollback-all)
            ROLLBACK_ALL=true
            ROLLBACK_SINGLE=true
            ROLLBACK_MULTI=true
            shift
            ;;
        --rollback-single)
            ROLLBACK_SINGLE=true
            ROLLBACK_MULTI=false
            shift
            ;;
        --rollback-multi)
            ROLLBACK_MULTI=true
            ROLLBACK_SINGLE=false
            shift
            ;;
        --keep-data)
            KEEP_DATA=true
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

# Confirm rollback with user
confirm_rollback() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No actual changes will be made"
        return
    fi
    
    log_warning "⚠️  WARNING: This will delete AWS resources!"
    echo ""
    echo "The following will be rolled back:"
    
    if [[ "$ROLLBACK_MULTI" == "true" ]]; then
        echo "  - Multi-Account Stack (Phase 5)"
        echo "    - Lambda functions (3)"
        echo "    - DynamoDB tables (5)"
        if [[ "$KEEP_DATA" == "false" ]]; then
            echo "    - ALL DATA IN TABLES WILL BE DELETED"
        fi
        echo "    - API Gateway endpoints"
        echo "    - EventBridge rules"
        echo "    - CloudWatch alarms"
        echo "    - SNS topics"
    fi
    
    if [[ "$ROLLBACK_SINGLE" == "true" ]]; then
        echo "  - Single-Account Stack (Phase 1-4)"
        echo "    - All Phase 1-4 resources"
    fi
    
    if [[ "$SKIP_CROSS_ACCOUNT" == "false" ]]; then
        echo "  - Cross-Account Roles (in member accounts)"
    fi
    
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Rollback cancelled by user"
        exit 0
    fi
}

# Backup DynamoDB tables
backup_dynamodb_tables() {
    if [[ "$KEEP_DATA" == "false" ]]; then
        log_info "Skipping DynamoDB backup (--keep-data not specified)"
        return
    fi
    
    log_info "Backing up DynamoDB tables..."
    
    TABLES=(
        "costguard-organizations"
        "costguard-accounts"
        "costguard-multi-account-costs"
        "costguard-allocation-rules"
        "costguard-budgets"
    )
    
    BACKUP_DIR="./dynamodb-backups-$(date +%Y%m%d-%H%M%S)"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create backups in: $BACKUP_DIR"
    else
        mkdir -p "$BACKUP_DIR"
        
        for table in "${TABLES[@]}"; do
            if aws dynamodb describe-table --table-name "$table" --region "$REGION" &> /dev/null; then
                log_info "Backing up table: $table"
                
                # Scan table and save to JSON
                aws dynamodb scan \
                    --table-name "$table" \
                    --region "$REGION" \
                    --output json > "$BACKUP_DIR/${table}.json"
                
                log_success "Backed up $table to $BACKUP_DIR/${table}.json"
            else
                log_warning "Table $table does not exist, skipping backup"
            fi
        done
        
        log_success "DynamoDB backups saved to: $BACKUP_DIR"
    fi
}

# Delete cross-account roles
delete_cross_account_roles() {
    if [[ "$SKIP_CROSS_ACCOUNT" == "true" ]]; then
        log_info "Skipping cross-account roles cleanup"
        return
    fi
    
    log_info "Cleaning up cross-account roles..."
    
    # Check if we're in an organization
    if ! aws organizations describe-organization &> /dev/null; then
        log_warning "Not in an AWS Organization. Cross-account roles must be deleted manually."
        log_info "Please delete the CostGuardCrossAccountRole from each member account."
        return
    fi
    
    # Get organization ID
    ORG_ID=$(aws organizations describe-organization --query Organization.Id --output text)
    log_info "Organization ID: $ORG_ID"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would delete cross-account roles from organization accounts"
    else
        # Delete StackSet instances
        STACKSET_NAME="CostGuardCrossAccountRoles"
        
        if aws cloudformation describe-stack-set --stack-set-name "$STACKSET_NAME" &> /dev/null; then
            log_info "Deleting StackSet instances..."
            
            # Get all stack instances
            INSTANCES=$(aws cloudformation list-stack-instances \
                --stack-set-name "$STACKSET_NAME" \
                --query 'Summaries[].{Account:Account,Region:Region}' \
                --output json)
            
            if [[ "$INSTANCES" != "[]" ]]; then
                # Delete all instances
                aws cloudformation delete-stack-instances \
                    --stack-set-name "$STACKSET_NAME" \
                    --deployment-targets OrganizationalUnitIds="$ORG_ID" \
                    --regions "$REGION" \
                    --no-retain-stacks \
                    --operation-preferences MaxConcurrentPercentage=100,FailureTolerancePercentage=10
                
                log_info "Waiting for stack instances to be deleted..."
                
                # Wait for deletion to complete (max 10 minutes)
                for i in {1..60}; do
                    REMAINING=$(aws cloudformation list-stack-instances \
                        --stack-set-name "$STACKSET_NAME" \
                        --query 'length(Summaries)' \
                        --output text)
                    
                    if [[ "$REMAINING" == "0" ]]; then
                        log_success "All stack instances deleted"
                        break
                    fi
                    
                    if [[ $i -eq 60 ]]; then
                        log_warning "Timeout waiting for stack instances to delete"
                        break
                    fi
                    
                    sleep 10
                done
            fi
            
            # Delete the StackSet
            log_info "Deleting StackSet: $STACKSET_NAME"
            aws cloudformation delete-stack-set --stack-set-name "$STACKSET_NAME"
            log_success "StackSet deleted"
        else
            log_info "StackSet $STACKSET_NAME does not exist"
        fi
    fi
}

# Rollback multi-account stack
rollback_multi_account() {
    if [[ "$ROLLBACK_MULTI" == "false" ]]; then
        log_info "Skipping multi-account stack rollback"
        return
    fi
    
    log_info "Rolling back multi-account infrastructure (Phase 5)..."
    
    cd infrastructure
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run: cdk destroy CostGuardMultiAccountStack"
    else
        # Check if stack exists
        if aws cloudformation describe-stacks --stack-name CostGuardMultiAccountStack --region "$REGION" &> /dev/null; then
            log_info "Destroying multi-account stack..."
            
            if [[ "$KEEP_DATA" == "true" ]]; then
                log_warning "Cannot preserve DynamoDB data with CDK destroy"
                log_warning "Data will be retained based on RemovalPolicy in stack definition"
            fi
            
            cdk destroy CostGuardMultiAccountStack --force --region "$REGION"
            log_success "Multi-account infrastructure rolled back successfully"
        else
            log_info "Multi-account stack does not exist, nothing to rollback"
        fi
    fi
    
    cd ..
}

# Rollback single-account stack
rollback_single_account() {
    if [[ "$ROLLBACK_SINGLE" == "false" ]]; then
        log_info "Skipping single-account stack rollback"
        return
    fi
    
    log_info "Rolling back single-account infrastructure (Phase 1-4)..."
    
    cd infrastructure
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run: cdk destroy CostGuardStack"
    else
        # Check if stack exists
        if aws cloudformation describe-stacks --stack-name CostGuardStack --region "$REGION" &> /dev/null; then
            log_info "Destroying single-account stack..."
            cdk destroy CostGuardStack --force --region "$REGION"
            log_success "Single-account infrastructure rolled back successfully"
        else
            log_info "Single-account stack does not exist, nothing to rollback"
        fi
    fi
    
    cd ..
}

# Verify rollback
verify_rollback() {
    if [[ "$SKIP_VERIFICATION" == "true" ]]; then
        log_info "Skipping rollback verification"
        return
    fi
    
    log_info "Verifying rollback..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would verify rollback completion"
        return
    fi
    
    VERIFICATION_FAILED=false
    
    # Check if multi-account stack is deleted
    if [[ "$ROLLBACK_MULTI" == "true" ]]; then
        if aws cloudformation describe-stacks --stack-name CostGuardMultiAccountStack --region "$REGION" &> /dev/null; then
            log_error "Multi-account stack still exists"
            VERIFICATION_FAILED=true
        else
            log_success "Multi-account stack successfully deleted"
        fi
        
        # Check if Lambda functions are deleted
        FUNCTIONS=(
            "CostGuard-MultiAccountCostCollector"
            "CostGuard-MultiAccountAPIHandler"
            "CostGuard-MultiAccountHandler"
        )
        
        for func in "${FUNCTIONS[@]}"; do
            if aws lambda get-function --function-name "$func" --region "$REGION" &> /dev/null; then
                log_error "Lambda function $func still exists"
                VERIFICATION_FAILED=true
            else
                log_success "Lambda function $func deleted"
            fi
        done
        
        # Check if DynamoDB tables are deleted (unless keeping data)
        if [[ "$KEEP_DATA" == "false" ]]; then
            TABLES=(
                "costguard-organizations"
                "costguard-accounts"
                "costguard-multi-account-costs"
                "costguard-allocation-rules"
                "costguard-budgets"
            )
            
            for table in "${TABLES[@]}"; do
                if aws dynamodb describe-table --table-name "$table" --region "$REGION" &> /dev/null; then
                    log_warning "DynamoDB table $table still exists (may have RETAIN policy)"
                else
                    log_success "DynamoDB table $table deleted"
                fi
            done
        fi
    fi
    
    # Check if single-account stack is deleted
    if [[ "$ROLLBACK_SINGLE" == "true" ]]; then
        if aws cloudformation describe-stacks --stack-name CostGuardStack --region "$REGION" &> /dev/null; then
            log_error "Single-account stack still exists"
            VERIFICATION_FAILED=true
        else
            log_success "Single-account stack successfully deleted"
        fi
    fi
    
    if [[ "$VERIFICATION_FAILED" == "true" ]]; then
        log_error "Rollback verification failed - some resources still exist"
        return 1
    else
        log_success "Rollback verification completed successfully"
        return 0
    fi
}

# Main rollback function
main() {
    log_info "Starting CostGuard Infrastructure Rollback"
    log_info "Region: $REGION"
    log_info "Dry Run: $DRY_RUN"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warning "DRY RUN MODE - No actual changes will be made"
    fi
    
    # Step 1: Check prerequisites
    check_prerequisites
    
    # Step 2: Confirm rollback with user
    confirm_rollback
    
    # Step 3: Backup DynamoDB tables if keeping data
    backup_dynamodb_tables
    
    # Step 4: Delete cross-account roles
    delete_cross_account_roles
    
    # Step 5: Rollback multi-account stack
    rollback_multi_account
    
    # Step 6: Rollback single-account stack
    rollback_single_account
    
    # Step 7: Verify rollback
    verify_rollback
    
    # Summary
    log_success "Rollback completed successfully!"
    
    if [[ "$DRY_RUN" == "false" ]]; then
        echo ""
        log_info "Rollback Summary:"
        
        if [[ "$ROLLBACK_MULTI" == "true" ]]; then
            log_info "✓ Multi-account infrastructure (Phase 5) rolled back"
        fi
        
        if [[ "$ROLLBACK_SINGLE" == "true" ]]; then
            log_info "✓ Single-account infrastructure (Phase 1-4) rolled back"
        fi
        
        if [[ "$SKIP_CROSS_ACCOUNT" == "false" ]]; then
            log_info "✓ Cross-account roles cleaned up"
        fi
        
        if [[ "$KEEP_DATA" == "true" ]] && [[ -d "./dynamodb-backups-"* ]]; then
            BACKUP_DIR=$(ls -dt ./dynamodb-backups-* | head -1)
            log_info "✓ DynamoDB backups saved to: $BACKUP_DIR"
        fi
        
        echo ""
        log_warning "Note: Some resources may have RETAIN policies and need manual deletion:"
        log_warning "- DynamoDB tables (if RemovalPolicy is RETAIN)"
        log_warning "- CloudWatch Log Groups"
        log_warning "- S3 buckets (if any)"
        echo ""
        log_info "To redeploy, run: ./deploy.sh"
    fi
}

# Run main function
main "$@"
