"""
Cloud services registry — all supported resource types across AWS, GCP, and Azure.
Use this for documentation, wrappers, and routing.

Database services (RDS, Cloud SQL, Azure SQL, etc.) require ENABLE_DATABASE_COLLECTION=true.
They are disabled by default for security — see collectors/database_policy.py.
"""

from collectors.database_policy import DATABASE_RESOURCE_TYPES, is_database_collection_enabled

AWS_SERVICES = {
    # Compute & VMs
    "ec2": "EC2 virtual machines",
    "autoscaling": "EC2 Auto Scaling groups",
    "elasticbeanstalk": "Elastic Beanstalk environments",
    # Containers & Kubernetes
    "ecs": "ECS tasks and services",
    "fargate": "ECS Fargate tasks (alias for ecs)",
    "eks": "Amazon EKS clusters",
    "eks_nodegroup": "EKS managed node groups",
    "ecr": "Elastic Container Registry repositories",
    "apprunner": "AWS App Runner services",
    "batch": "AWS Batch jobs",
    # Serverless
    "lambda": "Lambda functions",
    # Databases & Cache
    "rds": "RDS database instances",
    "elasticache": "ElastiCache (Redis/Memcached)",
    "dynamodb": "DynamoDB tables (status)",
    # Networking & Load Balancing
    "alb": "Application Load Balancers",
    "elb": "Classic/Network Load Balancers",
    "vpc": "VPC and subnet summary",
    # Storage & Messaging
    "s3": "S3 bucket status",
    "sqs": "SQS queue depth and status",
    "sns": "SNS topic status",
    # Monitoring
    "cloudwatch": "CloudWatch logs",
}

GCP_SERVICES = {
    # Compute & VMs
    "gce": "Compute Engine VMs",
    "compute": "Compute Engine VMs (alias for gce)",
    "instance_group": "Managed instance groups",
    # Containers & Kubernetes
    "gke": "Google Kubernetes Engine clusters",
    "gke_nodepool": "GKE node pools",
    "cloud_run": "Cloud Run services",
    "artifact_registry": "Artifact Registry / GCR",
    "cloud_build": "Cloud Build triggers (status)",
    # Serverless
    "cloud_function": "Cloud Functions",
    # Databases & Cache
    "cloud_sql": "Cloud SQL instances",
    "memorystore": "Memorystore (Redis)",
    "firestore": "Firestore database status",
    # Networking & Load Balancing
    "load_balancer": "Cloud Load Balancing",
    "cloud_armor": "Cloud Armor policies (summary)",
    # Storage & Messaging
    "cloud_storage": "Cloud Storage buckets",
    "pubsub": "Pub/Sub topics and subscriptions",
    # Orchestration
    "cloud_composer": "Cloud Composer (Airflow)",
}

AZURE_SERVICES = {
    # Compute & VMs
    "vm": "Virtual Machines",
    "vmss": "Virtual Machine Scale Sets",
    # Containers & Kubernetes
    "aks": "Azure Kubernetes Service clusters",
    "aci": "Azure Container Instances",
    "container_apps": "Azure Container Apps",
    "acr": "Azure Container Registry",
    "container_instance": "Azure Container Instances (alias for aci)",
    # App Hosting
    "app_service": "App Service web apps",
    "function": "Azure Functions",
    # Databases & Cache
    "sql": "Azure SQL Database",
    "cosmosdb": "Cosmos DB accounts",
    "redis": "Azure Cache for Redis",
    # Networking & Load Balancing
    "load_balancer": "Azure Load Balancers",
    "application_gateway": "Application Gateway",
    # Storage & Messaging
    "storage": "Storage accounts / blob",
    "service_bus": "Service Bus queues and topics",
    # Batch
    "batch": "Azure Batch accounts",
}

ALL_CLOUD_SERVICES = {
    "aws": AWS_SERVICES,
    "gcp": GCP_SERVICES,
    "azure": AZURE_SERVICES,
}

# Database services — require ENABLE_DATABASE_COLLECTION=true (off by default)
DATABASE_SERVICES = DATABASE_RESOURCE_TYPES
