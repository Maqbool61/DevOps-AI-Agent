"""
Enhanced safe executor with strict DevSecOps controls.

This executor NEVER executes dangerous operations. Instead, it sends
email notifications and provides manual commands for human execution.
"""

import os
import re
import logging
import subprocess
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from tools.email_notifier import send_dangerous_operation_alert

logger = logging.getLogger(__name__)


# PERMANENTLY BLOCKED OPERATIONS - NEVER ALLOWED
BLOCKED_PATTERNS = [
    # Deletion patterns
    r'\bdelete\b',
    r'\brm\s+-rf\b',
    r'\brm\s+.*\*',
    r'\bdrop\s+database\b',
    r'\bdrop\s+table\b',
    r'\btruncate\b',
    r'\bremove\b',
    r'\bdestroy\b',
    r'\bterminate\b',
    r'\bpurge\b',
    r'\bprune\b.*--all',
    r'\bwipe\b',
    
    # Kubernetes deletions
    r'kubectl\s+delete',
    r'helm\s+(uninstall|delete)',
    r'kubectl\s+drain',
    
    # Cloud deletions
    r'aws\s+.*\s+delete',
    r'aws\s+.*\s+terminate',
    r'aws\s+rds\s+delete-db',
    r'gcloud\s+.*\s+delete',
    r'az\s+.*\s+delete',
    
    # Formatting
    r'\bformat\b',
    r'\bmkfs\b',
    r'dd\s+if=/dev/zero',
    
    # Force operations
    r'--force-delete',
    r'--cascade.*delete',
    r'--no-preserve-root',
    
    # Dangerous SQL
    r'DELETE\s+FROM.*(?!WHERE)',  # DELETE without WHERE
    r'UPDATE.*(?!WHERE)',  # UPDATE without WHERE
    
    # Scaling to zero
    r'--replicas=0',
    r'--min-instances=0',
    r'scale.*=0',
]

# SAFE OPERATIONS - Allowed with approval
SAFE_OPERATIONS = [
    'kubectl get',
    'kubectl describe',
    'kubectl logs',
    'kubectl top',
    'kubectl apply',
    'kubectl rollout restart',
    'kubectl rollout undo',
    'kubectl scale --replicas=[1-9]',  # Scale UP only
    'docker logs',
    'docker ps',
    'docker inspect',
    'aws describe',
    'aws list',
    'gcloud describe',
    'gcloud list',
    'az show',
    'az list',
]


class SafeExecutorEnhanced:
    """
    Enhanced safe executor with strict safety controls.
    
    Key principles:
    1. NEVER delete anything
    2. NEVER destroy resources
    3. Send email for dangerous operations
    4. Provide manual commands instead
    5. Full audit trail
    """
    
    def __init__(self):
        self.dry_run_default = True
        self.auto_apply = os.getenv('AUTO_APPLY', 'false').lower() == 'true'
        self.blocked_commands_log = []
        
        logger.info("SafeExecutorEnhanced initialized with strict safety controls")
        logger.info(f"AUTO_APPLY = {self.auto_apply}")
    
    def execute_command(
        self,
        command: str,
        description: str = "",
        context: Optional[Dict] = None,
        dry_run: bool = True
    ) -> Dict:
        """
        Execute a command with safety checks.
        
        Args:
            command: Command to execute
            description: Human-readable description
            context: Additional context for logging
            dry_run: If True, simulate execution
        
        Returns:
            Result dictionary with status, output, and safety information
        """
        # Step 1: Check if command is dangerous
        is_dangerous, danger_reason = self._is_dangerous_command(command)
        
        if is_dangerous:
            return self._handle_dangerous_operation(
                command=command,
                reason=danger_reason,
                description=description,
                context=context or {}
            )
        
        # Step 2: Validate command is allowed
        if not self._is_command_allowed(command):
            return {
                "status": "blocked",
                "message": f"Command not in allowed list: {command}",
                "command": command,
                "dry_run": True,
                "danger_level": "medium"
            }
        
        # Step 3: Execute in dry-run mode first (if not already dry-run)
        if not dry_run and not self.auto_apply:
            # Force dry-run first
            dry_run_result = self._execute_safe(command, dry_run=True)
            if dry_run_result.get('status') != 'success':
                return dry_run_result
            
            # Require approval
            return {
                "status": "awaiting_approval",
                "message": f"Dry-run successful. Requires approval to execute: {command}",
                "dry_run_result": dry_run_result,
                "command": command,
                "approval_required": True
            }
        
        # Step 4: Execute the command
        return self._execute_safe(command, dry_run=dry_run)
    
    def _is_dangerous_command(self, command: str) -> Tuple[bool, str]:
        """
        Check if command matches any dangerous patterns.
        
        Returns:
            (is_dangerous, reason)
        """
        command_lower = command.lower()
        
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return True, f"Matches blocked pattern: {pattern}"
        
        # Additional custom checks
        if 'drop' in command_lower and ('database' in command_lower or 'table' in command_lower):
            return True, "Database DROP operation detected"
        
        if command_lower.startswith('rm ') and ('*' in command or '/' in command):
            return True, "Dangerous file deletion detected"
        
        if '--force' in command_lower and any(word in command_lower for word in ['delete', 'remove', 'destroy']):
            return True, "Force deletion detected"
        
        return False, ""
    
    def _is_command_allowed(self, command: str) -> bool:
        """Check if command is in the allowed operations list."""
        command_lower = command.lower()
        
        for safe_op in SAFE_OPERATIONS:
            if re.match(safe_op, command_lower):
                return True
        
        # Allow read-only operations
        read_only_keywords = ['get', 'describe', 'list', 'show', 'logs', 'status', 'info', 'inspect']
        if any(keyword in command_lower for keyword in read_only_keywords):
            return True
        
        return False
    
    def _handle_dangerous_operation(
        self,
        command: str,
        reason: str,
        description: str,
        context: Dict
    ) -> Dict:
        """
        Handle a dangerous operation by sending notifications instead of executing.
        
        Args:
            command: The dangerous command
            reason: Why it's dangerous
            description: Description of what this would do
            context: Incident context
        
        Returns:
            Result dictionary with notification details
        """
        incident_id = f"BLOCK-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        logger.warning(f"BLOCKED dangerous operation [{incident_id}]: {command}")
        logger.warning(f"Reason: {reason}")
        
        # Log to blocked commands
        self.blocked_commands_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "incident_id": incident_id,
            "command": command,
            "reason": reason,
            "description": description,
            "context": context
        })
        
        # Prepare email notification
        recommended_commands = [
            "# Review the situation first:",
            f"# {description}",
            "",
            "# If you decide this is necessary, execute manually:",
            command,
            "",
            "# Always backup first and test in staging!"
        ]
        
        # Send email alert
        email_sent = False
        try:
            email_sent = send_dangerous_operation_alert(
                incident_id=incident_id,
                operation=description or command,
                reason=reason,
                recommended_commands=recommended_commands,
                context=context,
                severity="HIGH"
            )
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
        
        return {
            "status": "blocked",
            "incident_id": incident_id,
            "message": f"DANGEROUS OPERATION BLOCKED: {reason}",
            "command": command,
            "reason": reason,
            "email_sent": email_sent,
            "manual_commands": recommended_commands,
            "ai_recommendation": (
                "This operation was blocked because it could cause data loss or "
                "service disruption. An email has been sent to the operations team "
                "with manual commands for execution after human review."
            ),
            "danger_level": "critical",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _execute_safe(self, command: str, dry_run: bool = True) -> Dict:
        """
        Execute a safe command (already validated).
        
        Args:
            command: Command to execute
            dry_run: If True, simulate execution
        
        Returns:
            Result dictionary
        """
        if dry_run:
            logger.info(f"[DRY-RUN] Would execute: {command}")
            return {
                "status": "success",
                "message": f"Dry-run: Would execute '{command}'",
                "command": command,
                "dry_run": True,
                "output": "(dry-run mode - no actual execution)"
            }
        
        try:
            # Execute command safely
            logger.info(f"Executing: {command}")
            
            # Parse command into list for safe execution (no shell injection)
            # For safety, we use shlex.split to properly parse the command
            import shlex
            try:
                cmd_list = shlex.split(command)
            except ValueError:
                # If parsing fails, it's likely a complex shell command - block it
                return {
                    "status": "failed",
                    "message": "Command contains invalid shell syntax",
                    "command": command,
                    "error": "Complex shell commands are not allowed for security"
                }
            
            # Execute without shell=True to prevent shell injection
            result = subprocess.run(
                cmd_list,
                shell=False,  # Security: Never use shell=True
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=False
            )
            
            success = result.returncode == 0
            
            return {
                "status": "success" if success else "failed",
                "message": f"Command executed: {command}",
                "command": command,
                "dry_run": False,
                "output": result.stdout,
                "error": result.stderr if not success else None,
                "exit_code": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return {
                "status": "failed",
                "message": "Command execution timed out (5 minutes)",
                "command": command,
                "error": "Timeout after 300 seconds"
            }
        
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                "status": "failed",
                "message": f"Execution failed: {str(e)}",
                "command": command,
                "error": str(e)
            }
    
    def get_blocked_commands_log(self) -> List[Dict]:
        """Get log of all blocked commands."""
        return self.blocked_commands_log
    
    def clear_blocked_commands_log(self):
        """Clear the blocked commands log."""
        self.blocked_commands_log = []


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create executor
    executor = SafeExecutorEnhanced()
    
    # Test cases
    test_commands = [
        # Safe commands
        ("kubectl get pods", "List pods"),
        ("kubectl describe pod myapp", "Describe pod"),
        ("kubectl logs myapp-pod", "Get logs"),
        
        # Dangerous commands (should be blocked)
        ("kubectl delete pod myapp", "Delete pod - DANGEROUS"),
        ("rm -rf /var/lib/data", "Delete directory - DANGEROUS"),
        ("DROP DATABASE production", "Drop database - DANGEROUS"),
        ("aws ec2 terminate-instances --instance-ids i-123", "Terminate instance - DANGEROUS"),
        ("kubectl scale deployment myapp --replicas=0", "Scale to zero - DANGEROUS"),
    ]
    
    print("\n" + "="*80)
    print("SAFE EXECUTOR ENHANCED - TEST CASES")
    print("="*80 + "\n")
    
    for command, description in test_commands:
        print(f"\nTest: {description}")
        print(f"Command: {command}")
        print("-" * 80)
        
        result = executor.execute_command(
            command=command,
            description=description,
            context={"test": True},
            dry_run=True
        )
        
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        
        if result['status'] == 'blocked':
            print(f"⛔ BLOCKED: {result['reason']}")
            print(f"Incident ID: {result['incident_id']}")
        
        print()
    
    print("\n" + "="*80)
    print(f"Total blocked commands: {len(executor.get_blocked_commands_log())}")
    print("="*80 + "\n")
