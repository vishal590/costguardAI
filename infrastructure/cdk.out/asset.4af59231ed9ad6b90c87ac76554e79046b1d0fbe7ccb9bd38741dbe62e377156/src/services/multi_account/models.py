"""
Data models for multi-account cost management
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from enum import Enum


class AccountStatus(Enum):
    """AWS Account status"""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_CLOSURE = "PENDING_CLOSURE"


class EntityType(Enum):
    """Entity type for budgets and aggregations"""
    ORGANIZATION = "ORGANIZATION"
    OU = "OU"
    ACCOUNT = "ACCOUNT"


class CollectionStatus(Enum):
    """Cost collection status"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"


@dataclass
class Organization:
    """AWS Organization structure"""
    id: str
    arn: str
    master_account_id: str
    feature_set: str  # "ALL" or "CONSOLIDATED_BILLING"


@dataclass
class Account:
    """AWS Account metadata"""
    id: str
    arn: str
    name: str
    email: str
    status: str
    joined_method: str
    joined_timestamp: datetime


@dataclass
class OrganizationalUnit:
    """AWS Organizational Unit"""
    id: str
    arn: str
    name: str
    parent_id: Optional[str] = None


@dataclass
class OUHierarchy:
    """Organizational Unit hierarchy"""
    root_id: str
    ous: List[OrganizationalUnit]
    accounts_by_ou: Dict[str, List[str]]  # ou_id -> [account_ids]


@dataclass
class AccountCostData:
    """Cost data for a single account"""
    account_id: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    total_cost: Decimal
    costs_by_service: Dict[str, Decimal]
    costs_by_day: Dict[str, Decimal]
    collection_timestamp: datetime
    status: str


@dataclass
class CollectionResult:
    """Result of multi-account cost collection"""
    total_accounts: int
    successful: int
    failed: int
    failed_accounts: List[str]
    collection_duration: float


@dataclass
class AggregatedCosts:
    """Aggregated costs across accounts"""
    entity_id: str  # org_id or ou_id
    entity_type: str  # "ORGANIZATION" or "OU"
    start_date: str
    end_date: str
    total_cost: Decimal
    account_count: int
    costs_by_account: Dict[str, Decimal]
    costs_by_service: Dict[str, Decimal]
    costs_by_day: Dict[str, Decimal]


@dataclass
class AccountSpending:
    """Account spending summary"""
    account_id: str
    account_name: str
    total_cost: Decimal
    percentage_of_total: float


@dataclass
class AllocationRule:
    """Cost allocation rule"""
    rule_id: str
    name: str
    priority: int
    rule_type: str  # "TAG_BASED", "PERCENTAGE", "FIXED"
    conditions: Dict[str, Any]
    allocation_target: str


@dataclass
class AllocationResult:
    """Result of cost allocation"""
    total_cost: Decimal
    allocated_cost: Decimal
    unallocated_cost: Decimal
    allocation_percentage: float
    allocations_by_category: Dict[str, Decimal]
