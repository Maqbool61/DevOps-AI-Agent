"""
Database collection policy — optional by default for security and sensitive data.

When ENABLE_DATABASE_COLLECTION=false (default), the agent will NOT:
- Query RDS, Cloud SQL, Azure SQL, DynamoDB, Cosmos DB, etc.
- Collect database endpoints, connection metadata, or cache/redis internals
- Run any direct database diagnostics

The agent can still troubleshoot app-level issues (connection pool exhaustion,
timeouts, service restarts) without touching database systems.
"""
import os
from typing import Dict, List, Optional, Set

# Resource types that touch database / cache / sensitive data stores
DATABASE_RESOURCE_TYPES: Dict[str, Set[str]] = {
    "aws": {"rds", "elasticache", "dynamodb"},
    "gcp": {"cloud_sql", "firestore", "memorystore"},
    "azure": {"sql", "cosmosdb", "redis"},
}

ALL_DATABASE_RESOURCE_TYPES: Set[str] = set().union(*DATABASE_RESOURCE_TYPES.values())


def is_database_collection_enabled() -> bool:
    """Database diagnostics are OFF unless explicitly enabled."""
    return os.getenv("ENABLE_DATABASE_COLLECTION", "false").lower() in ("true", "1", "yes")


def is_database_resource_type(resource_type: str) -> bool:
    return resource_type.lower() in ALL_DATABASE_RESOURCE_TYPES


def database_collection_blocked_response(resource_type: str, cloud: Optional[str] = None) -> dict:
    return {
        "blocked": True,
        "error": "Database collection is disabled",
        "resource_type": resource_type,
        "cloud": cloud,
        "reason": (
            "ENABLE_DATABASE_COLLECTION is false. Database access is optional to protect "
            "sensitive data (credentials, PII, connection strings, query metadata)."
        ),
        "enable_if_allowed": "Set ENABLE_DATABASE_COLLECTION=true in .env only after security review",
        "alternatives": [
            "Troubleshoot connection pool / timeout settings at the application layer",
            "Restart app services or scale replicas",
            "Check network, firewall, and security group rules",
            "Notify DBA team via email for manual database investigation",
        ],
    }


def check_database_access(resource_type: str, cloud: Optional[str] = None) -> Optional[dict]:
    """Return a block response if database collection is disabled, else None."""
    if is_database_resource_type(resource_type) and not is_database_collection_enabled():
        return database_collection_blocked_response(resource_type, cloud)
    return None


def filter_supported_types(all_types: List[str]) -> List[str]:
    """Remove database resource types from a supported-types list when disabled."""
    if is_database_collection_enabled():
        return all_types
    return [t for t in all_types if t not in ALL_DATABASE_RESOURCE_TYPES]


def get_enabled_database_types(cloud: str) -> List[str]:
    """Return database types available for a cloud provider (empty if disabled)."""
    if not is_database_collection_enabled():
        return []
    return sorted(DATABASE_RESOURCE_TYPES.get(cloud, set()))


DB_INCIDENT_KEYWORDS = {
    "rds", "sql", "database", "postgres", "postgresql", "mysql", "mariadb",
    "redis", "dynamodb", "cosmos", "elasticache", "cloud_sql", "firestore",
    "memorystore", "db_", "mongodb", "oracle", "sqlite", "cassandra",
}


def is_database_incident(context: dict) -> bool:
    """Detect if an incident is database-related and likely needs human/DBA escalation."""
    if not context:
        return False

    resource_type = (context.get("resource_type") or "").lower()
    if is_database_resource_type(resource_type):
        return True

    searchable = " ".join([
        str(context.get("type", "")),
        str(context.get("alertname", "")),
        str(context.get("description", "")),
        str(context.get("summary", "")),
        str(context.get("service", "")),
    ]).lower()

    if any(kw in searchable for kw in DB_INCIDENT_KEYWORDS):
        return True

    labels = context.get("labels") or {}
    label_text = " ".join(str(v).lower() for v in labels.values())
    if any(kw in label_text for kw in DB_INCIDENT_KEYWORDS):
        return True

    return False


def incident_involves_blocked_database(actions: list) -> bool:
    """True if agent hit a blocked database collector during the run."""
    for action in actions or []:
        result = action.get("result") or {}
        if result.get("blocked") and (
            "database" in str(result.get("error", "")).lower()
            or result.get("resource_type") in ALL_DATABASE_RESOURCE_TYPES
        ):
            return True
    return False
