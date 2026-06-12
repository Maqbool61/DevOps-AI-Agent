"""
AWS Cloud Resource Collector
Fetches diagnostic information from AWS resources (EC2, ECS, Lambda, RDS, etc.)
Focuses on safe read-only operations.
"""
import os
from typing import Optional, Dict, Any

import structlog

log = structlog.get_logger()


class AWSCollector:
    def __init__(self):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        # AWS credentials should be set via environment or IAM role
        # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or use IAM role

    async def collect(self, resource_type: str, resource_id: str, **kwargs) -> dict:
        """
        Collect diagnostic info for AWS resources.
        
        Args:
            resource_type: 'ec2', 'ecs', 'lambda', 'rds', 'alb', 'cloudwatch'
            resource_id: Instance ID, task ARN, function name, etc.
        """
        try:
            if resource_type == "ec2":
                return await self._collect_ec2(resource_id)
            elif resource_type == "ecs":
                return await self._collect_ecs(kwargs.get("cluster"), resource_id)
            elif resource_type == "lambda":
                return await self._collect_lambda(resource_id)
            elif resource_type == "rds":
                return await self._collect_rds(resource_id)
            elif resource_type == "cloudwatch":
                return await self._collect_cloudwatch_logs(kwargs.get("log_group"), kwargs.get("log_stream"))
            else:
                return {"error": f"Unsupported AWS resource type: {resource_type}"}
        except Exception as e:
            log.error("AWS collection failed", resource_type=resource_type, error=str(e))
            return {"error": str(e)}

    async def _collect_ec2(self, instance_id: str) -> dict:
        """Collect EC2 instance diagnostics."""
        try:
            import boto3
            ec2 = boto3.client("ec2", region_name=self.region)
            
            # Get instance details
            response = ec2.describe_instances(InstanceIds=[instance_id])
            if not response["Reservations"]:
                return {"error": f"Instance {instance_id} not found"}
            
            instance = response["Reservations"][0]["Instances"][0]
            
            # Get instance status checks
            status = ec2.describe_instance_status(InstanceIds=[instance_id])
            status_checks = status["InstanceStatuses"][0] if status["InstanceStatuses"] else {}
            
            # Get console output (last 64KB - useful for boot issues)
            try:
                console_output = ec2.get_console_output(InstanceId=instance_id)
                console_text = console_output.get("Output", "")
                # Get last 4000 chars
                console_text = console_text[-4000:] if len(console_text) > 4000 else console_text
            except Exception:
                console_text = "Console output not available"
            
            return {
                "instance_id": instance_id,
                "state": instance.get("State", {}).get("Name"),
                "instance_type": instance.get("InstanceType"),
                "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                "private_ip": instance.get("PrivateIpAddress"),
                "public_ip": instance.get("PublicIpAddress"),
                "launch_time": str(instance.get("LaunchTime")),
                "tags": {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])},
                "status_checks": {
                    "system_status": status_checks.get("SystemStatus", {}).get("Status"),
                    "instance_status": status_checks.get("InstanceStatus", {}).get("Status"),
                },
                "console_output": console_text,
            }
        except ImportError:
            return {"error": "boto3 not installed. Run: pip install boto3"}
        except Exception as e:
            return {"error": f"EC2 collection failed: {str(e)}"}

    async def _collect_ecs(self, cluster: str, task_arn: str) -> dict:
        """Collect ECS task diagnostics."""
        try:
            import boto3
            ecs = boto3.client("ecs", region_name=self.region)
            
            # Describe task
            tasks = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
            if not tasks["tasks"]:
                return {"error": f"Task {task_arn} not found in cluster {cluster}"}
            
            task = tasks["tasks"][0]
            
            # Get container logs from CloudWatch if available
            container_logs = {}
            for container in task.get("containers", []):
                container_name = container.get("name")
                if container.get("logConfiguration", {}).get("logDriver") == "awslogs":
                    log_options = container["logConfiguration"]["options"]
                    log_group = log_options.get("awslogs-group")
                    log_stream = log_options.get("awslogs-stream-prefix", "")
                    
                    if log_group:
                        # Get recent logs
                        logs_data = await self._collect_cloudwatch_logs(
                            log_group,
                            f"{log_stream}/{container_name}/{task_arn.split('/')[-1]}"
                        )
                        container_logs[container_name] = logs_data.get("logs", "")
            
            return {
                "cluster": cluster,
                "task_arn": task_arn,
                "task_definition": task.get("taskDefinitionArn"),
                "last_status": task.get("lastStatus"),
                "desired_status": task.get("desiredStatus"),
                "started_at": str(task.get("startedAt")),
                "stopped_at": str(task.get("stoppedAt")) if task.get("stoppedAt") else None,
                "stopped_reason": task.get("stoppedReason"),
                "containers": [
                    {
                        "name": c.get("name"),
                        "status": c.get("lastStatus"),
                        "exit_code": c.get("exitCode"),
                        "reason": c.get("reason"),
                    }
                    for c in task.get("containers", [])
                ],
                "container_logs": container_logs,
            }
        except ImportError:
            return {"error": "boto3 not installed. Run: pip install boto3"}
        except Exception as e:
            return {"error": f"ECS collection failed: {str(e)}"}

    async def _collect_lambda(self, function_name: str) -> dict:
        """Collect Lambda function diagnostics."""
        try:
            import boto3
            lambda_client = boto3.client("lambda", region_name=self.region)
            logs_client = boto3.client("logs", region_name=self.region)
            
            # Get function configuration
            func = lambda_client.get_function(FunctionName=function_name)
            config = func["Configuration"]
            
            # Get recent error logs
            log_group = f"/aws/lambda/{function_name}"
            
            try:
                # Get recent log streams
                streams = logs_client.describe_log_streams(
                    logGroupName=log_group,
                    orderBy="LastEventTime",
                    descending=True,
                    limit=3
                )
                
                recent_logs = []
                for stream in streams.get("logStreams", [])[:2]:
                    events = logs_client.get_log_events(
                        logGroupName=log_group,
                        logStreamName=stream["logStreamName"],
                        limit=50,
                        startFromHead=False
                    )
                    
                    for event in events.get("events", []):
                        if "ERROR" in event.get("message", ""):
                            recent_logs.append(event.get("message"))
                
                log_summary = "\n".join(recent_logs[-10:])  # Last 10 error lines
            except Exception:
                log_summary = "Unable to fetch recent logs"
            
            return {
                "function_name": function_name,
                "runtime": config.get("Runtime"),
                "state": config.get("State"),
                "last_update_status": config.get("LastUpdateStatus"),
                "memory_size": config.get("MemorySize"),
                "timeout": config.get("Timeout"),
                "handler": config.get("Handler"),
                "role": config.get("Role"),
                "recent_error_logs": log_summary,
            }
        except ImportError:
            return {"error": "boto3 not installed. Run: pip install boto3"}
        except Exception as e:
            return {"error": f"Lambda collection failed: {str(e)}"}

    async def _collect_rds(self, db_instance_id: str) -> dict:
        """Collect RDS instance diagnostics."""
        try:
            import boto3
            rds = boto3.client("rds", region_name=self.region)
            
            # Get instance details
            response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
            if not response["DBInstances"]:
                return {"error": f"RDS instance {db_instance_id} not found"}
            
            db = response["DBInstances"][0]
            
            # Get recent events
            events = rds.describe_events(
                SourceIdentifier=db_instance_id,
                SourceType="db-instance",
                MaxRecords=20
            )
            
            return {
                "db_instance_id": db_instance_id,
                "status": db.get("DBInstanceStatus"),
                "engine": db.get("Engine"),
                "engine_version": db.get("EngineVersion"),
                "instance_class": db.get("DBInstanceClass"),
                "availability_zone": db.get("AvailabilityZone"),
                "multi_az": db.get("MultiAZ"),
                "storage_encrypted": db.get("StorageEncrypted"),
                "endpoint": db.get("Endpoint", {}).get("Address"),
                "port": db.get("Endpoint", {}).get("Port"),
                "recent_events": [
                    {
                        "date": str(e.get("Date")),
                        "message": e.get("Message"),
                    }
                    for e in events.get("Events", [])[:10]
                ],
            }
        except ImportError:
            return {"error": "boto3 not installed. Run: pip install boto3"}
        except Exception as e:
            return {"error": f"RDS collection failed: {str(e)}"}

    async def _collect_cloudwatch_logs(self, log_group: str, log_stream: Optional[str] = None) -> dict:
        """Collect recent CloudWatch logs."""
        try:
            import boto3
            logs = boto3.client("logs", region_name=self.region)
            
            if log_stream:
                # Get specific log stream
                events = logs.get_log_events(
                    logGroupName=log_group,
                    logStreamName=log_stream,
                    limit=100,
                    startFromHead=False
                )
                
                log_lines = [e.get("message") for e in events.get("events", [])]
                log_text = "\n".join(log_lines[-50:])  # Last 50 lines
            else:
                # Get recent streams
                streams = logs.describe_log_streams(
                    logGroupName=log_group,
                    orderBy="LastEventTime",
                    descending=True,
                    limit=1
                )
                
                if not streams.get("logStreams"):
                    return {"logs": "No log streams found"}
                
                stream_name = streams["logStreams"][0]["logStreamName"]
                events = logs.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream_name,
                    limit=100,
                    startFromHead=False
                )
                
                log_lines = [e.get("message") for e in events.get("events", [])]
                log_text = "\n".join(log_lines[-50:])
            
            return {
                "log_group": log_group,
                "log_stream": log_stream,
                "logs": log_text,
            }
        except ImportError:
            return {"error": "boto3 not installed. Run: pip install boto3"}
        except Exception as e:
            return {"error": f"CloudWatch logs collection failed: {str(e)}"}
