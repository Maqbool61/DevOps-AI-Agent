"""
Automatic Documentation Generator for Fixes

This tool generates comprehensive documentation for any manual fix applied,
creating runbooks, postmortems, and knowledge base articles automatically.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import structlog

log = structlog.get_logger()


class DocumentationGenerator:
    """
    Generates documentation for incident fixes automatically.
    Creates runbooks, postmortems, and knowledge base articles.
    """
    
    def __init__(self, output_dir: str = "./documentation"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(f"{output_dir}/runbooks", exist_ok=True)
        os.makedirs(f"{output_dir}/postmortems", exist_ok=True)
        os.makedirs(f"{output_dir}/knowledge-base", exist_ok=True)
        
        log.info(f"DocumentationGenerator initialized", output_dir=output_dir)
    
    def generate_fix_documentation(
        self,
        incident_id: str,
        incident_type: str,
        problem_description: str,
        root_cause: str,
        fix_applied: str,
        verification_steps: List[str],
        manual_commands: List[str],
        context: Dict,
        success: bool = True
    ) -> Dict[str, str]:
        """
        Generate comprehensive documentation for a fix.
        
        Args:
            incident_id: Unique incident identifier
            incident_type: Type of incident (k8s, cicd, server, etc.)
            problem_description: What was the problem
            root_cause: What caused the problem
            fix_applied: What fix was applied
            verification_steps: How to verify the fix worked
            manual_commands: Commands that were run manually
            context: Additional context (logs, metrics, etc.)
            success: Whether the fix was successful
        
        Returns:
            Dictionary with paths to generated documentation files
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        date_str = datetime.utcnow().strftime("%Y%m%d")
        
        generated_files = {}
        
        # 1. Generate Runbook
        runbook = self._generate_runbook(
            incident_type, problem_description, root_cause, 
            fix_applied, verification_steps, manual_commands
        )
        runbook_path = f"{self.output_dir}/runbooks/{incident_type}_{incident_id}_{date_str}.md"
        with open(runbook_path, 'w') as f:
            f.write(runbook)
        generated_files['runbook'] = runbook_path
        
        # 2. Generate Postmortem
        postmortem = self._generate_postmortem(
            incident_id, incident_type, timestamp, problem_description,
            root_cause, fix_applied, success, context
        )
        postmortem_path = f"{self.output_dir}/postmortems/{incident_id}_{date_str}.md"
        with open(postmortem_path, 'w') as f:
            f.write(postmortem)
        generated_files['postmortem'] = postmortem_path
        
        # 3. Generate Knowledge Base Article
        kb_article = self._generate_knowledge_base_article(
            incident_type, problem_description, root_cause,
            fix_applied, verification_steps
        )
        kb_path = f"{self.output_dir}/knowledge-base/{incident_type}_{date_str}.md"
        with open(kb_path, 'w') as f:
            f.write(kb_article)
        generated_files['knowledge_base'] = kb_path
        
        # 4. Generate JSON metadata for searchability
        metadata = {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "timestamp": timestamp,
            "problem": problem_description,
            "root_cause": root_cause,
            "fix": fix_applied,
            "success": success,
            "tags": self._extract_tags(incident_type, problem_description, root_cause),
            "files": generated_files
        }
        metadata_path = f"{self.output_dir}/metadata_{incident_id}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        generated_files['metadata'] = metadata_path
        
        log.info(f"Generated documentation for incident {incident_id}", files=generated_files)
        
        return generated_files
    
    def _generate_runbook(
        self,
        incident_type: str,
        problem: str,
        root_cause: str,
        fix: str,
        verification: List[str],
        commands: List[str]
    ) -> str:
        """Generate a runbook document."""
        return f"""# Runbook: {incident_type.upper()} - {problem[:50]}

## Problem Statement
{problem}

## Root Cause
{root_cause}

## Solution

### Prerequisites
- Access to production environment
- Required permissions: {self._get_required_permissions(incident_type)}
- Backup created (if applicable)

### Steps to Fix

#### 1. Verify the Issue
```bash
# Check current status
{commands[0] if commands else '# Add verification command'}
```

#### 2. Apply the Fix
```bash
{self._format_commands(commands[1:] if len(commands) > 1 else commands)}
```

#### 3. Verify the Fix
{self._format_verification_steps(verification)}

### Verification Steps
{self._format_verification_checklist(verification)}

### Rollback Plan
If the fix doesn't work or causes issues:
```bash
# Rollback steps
{self._generate_rollback_steps(incident_type)}
```

## Additional Notes
- Always test in staging first
- Monitor logs after applying fix
- Document any deviations from this runbook

## Related Documents
- Postmortem: See postmortems directory
- Knowledge Base: See knowledge-base directory

---
Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
"""
    
    def _generate_postmortem(
        self,
        incident_id: str,
        incident_type: str,
        timestamp: str,
        problem: str,
        root_cause: str,
        fix: str,
        success: bool,
        context: Dict
    ) -> str:
        """Generate a postmortem document."""
        return f"""# Postmortem: {incident_id}

## Incident Summary
- **Incident ID**: {incident_id}
- **Type**: {incident_type}
- **Date**: {timestamp}
- **Status**: {'Resolved' if success else 'Investigating'}

## Timeline

### Detection
- **Time**: {timestamp}
- **Source**: {context.get('alert_source', 'Monitoring system')}
- **Severity**: {context.get('severity', 'Medium')}

### Response
- **Time to Detect**: {context.get('detection_time', 'N/A')}
- **Time to Resolve**: {context.get('resolution_time', 'N/A')}
- **Responders**: DevOps AI Agent + SRE Team

## Problem Description
{problem}

## Root Cause Analysis

### What Happened
{root_cause}

### Why It Happened
{self._analyze_root_cause(root_cause, incident_type)}

### Contributing Factors
{self._identify_contributing_factors(context)}

## Resolution

### Fix Applied
```
{fix}
```

### Verification
{context.get('verification', 'Fix verified through monitoring')}

## Impact Assessment
- **Services Affected**: {context.get('affected_services', 'See incident details')}
- **Users Impacted**: {context.get('users_impacted', 'Minimal')}
- **Duration**: {context.get('duration', 'N/A')}

## Action Items

### Immediate
- [ ] Verify fix is stable
- [ ] Update monitoring alerts
- [ ] Document in runbook

### Short-term (1 week)
- [ ] Review related systems for similar issues
- [ ] Update CI/CD pipelines if applicable
- [ ] Add automated tests

### Long-term (1 month)
- [ ] Implement preventive measures
- [ ] Update architecture if needed
- [ ] Conduct training session

## Lessons Learned

### What Went Well
- Automated detection worked correctly
- Issue was identified quickly
- Fix was applied safely

### What Could Be Improved
- {self._suggest_improvements(incident_type, context)}

### Questions for Follow-up
- Can this be prevented in the future?
- Should monitoring be enhanced?
- Are there related risks?

## Related Incidents
- Search knowledge base for: {', '.join(self._extract_tags(incident_type, problem, root_cause))}

---
Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
Status: {'Resolved' if success else 'In Progress'}
"""
    
    def _generate_knowledge_base_article(
        self,
        incident_type: str,
        problem: str,
        root_cause: str,
        fix: str,
        verification: List[str]
    ) -> str:
        """Generate a knowledge base article."""
        return f"""# Knowledge Base: {problem[:60]}

## Category
{incident_type.upper()}

## Problem
{problem}

## Symptoms
Common indicators of this issue:
- {self._extract_symptoms(problem)}

## Root Cause
{root_cause}

## Solution

### Quick Fix
{fix}

### Detailed Steps
{self._format_verification_checklist(verification)}

## Prevention
To prevent this issue in the future:
- {self._suggest_prevention(incident_type, root_cause)}

## Related Issues
- {incident_type} configuration
- Monitoring and alerting
- System resources

## Tags
{', '.join(self._extract_tags(incident_type, problem, root_cause))}

---
Last Updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
"""
    
    def _format_commands(self, commands: List[str]) -> str:
        """Format commands for documentation."""
        return '\n'.join([f"# Step {i+1}\n{cmd}\n" for i, cmd in enumerate(commands)])
    
    def _format_verification_steps(self, steps: List[str]) -> str:
        """Format verification steps."""
        return '\n'.join([f"{i+1}. {step}" for i, step in enumerate(steps)])
    
    def _format_verification_checklist(self, steps: List[str]) -> str:
        """Format verification as a checklist."""
        if not steps:
            return "- [ ] Verify service is running\n- [ ] Check logs for errors\n- [ ] Monitor for 5 minutes"
        return '\n'.join([f"- [ ] {step}" for step in steps])
    
    def _get_required_permissions(self, incident_type: str) -> str:
        """Get required permissions for incident type."""
        permissions = {
            'k8s': 'kubectl access, namespace permissions',
            'cicd': 'CI/CD platform access, repository permissions',
            'server': 'SSH access, sudo permissions',
            'cloud_aws': 'AWS console access, IAM permissions',
            'cloud_gcp': 'GCP console access, IAM permissions',
            'cloud_azure': 'Azure portal access, RBAC permissions',
            'argocd': 'ArgoCD access, namespace permissions'
        }
        return permissions.get(incident_type, 'System access, appropriate permissions')
    
    def _generate_rollback_steps(self, incident_type: str) -> str:
        """Generate rollback steps for incident type."""
        rollback = {
            'k8s': '# Rollback deployment\nkubectl rollout undo deployment/<name> -n <namespace>',
            'cicd': '# Revert commit\ngit revert <commit-hash>\ngit push',
            'server': '# Restore from backup\nsudo cp /backup/config /etc/config\nsudo systemctl restart service',
        }
        return rollback.get(incident_type, '# Restore previous configuration\n# Verify system state')
    
    def _extract_tags(self, incident_type: str, problem: str, root_cause: str) -> List[str]:
        """Extract searchable tags from incident details."""
        tags = [incident_type]
        
        keywords = ['crash', 'oom', 'memory', 'cpu', 'disk', 'network', 'timeout', 
                   'error', 'failed', 'permission', 'config', 'deployment']
        
        text = f"{problem} {root_cause}".lower()
        for keyword in keywords:
            if keyword in text:
                tags.append(keyword)
        
        return list(set(tags))
    
    def _analyze_root_cause(self, root_cause: str, incident_type: str) -> str:
        """Provide deeper analysis of root cause."""
        return f"The root cause was identified as: {root_cause}. " + \
               f"This is a common issue in {incident_type} environments and typically " + \
               "occurs due to configuration drift or resource constraints."
    
    def _identify_contributing_factors(self, context: Dict) -> str:
        """Identify contributing factors from context."""
        factors = []
        if context.get('recent_deployment'):
            factors.append("- Recent deployment may have introduced the issue")
        if context.get('high_load'):
            factors.append("- System under high load")
        if context.get('config_change'):
            factors.append("- Recent configuration change")
        
        return '\n'.join(factors) if factors else "- None identified"
    
    def _suggest_improvements(self, incident_type: str, context: Dict) -> str:
        """Suggest improvements based on incident."""
        improvements = [
            "Add automated recovery for this scenario",
            "Enhance monitoring to detect earlier",
            "Update runbooks with this example"
        ]
        return '\n- '.join([''] + improvements)
    
    def _extract_symptoms(self, problem: str) -> str:
        """Extract symptoms from problem description."""
        return problem.split('.')[0] if '.' in problem else problem
    
    def _suggest_prevention(self, incident_type: str, root_cause: str) -> str:
        """Suggest prevention measures."""
        suggestions = {
            'k8s': "Implement pod disruption budgets and resource limits",
            'cicd': "Add pre-deployment validation and automated tests",
            'server': "Set up proactive monitoring and automated remediation"
        }
        base = suggestions.get(incident_type, "Implement monitoring and automated alerts")
        return f"{base}\n- Regular configuration audits\n- Automated testing before deployment"


# Example usage
if __name__ == "__main__":
    generator = DocumentationGenerator()
    
    files = generator.generate_fix_documentation(
        incident_id="INC-2026-001",
        incident_type="k8s",
        problem_description="Pod in production namespace stuck in CrashLoopBackOff",
        root_cause="Missing environment variable in deployment configuration",
        fix_applied="Added missing ENV var to deployment.yaml and restarted pod",
        verification_steps=[
            "Check pod status is Running",
            "Verify application logs show no errors",
            "Test application endpoint responds correctly"
        ],
        manual_commands=[
            "kubectl get pods -n production",
            "kubectl edit deployment api-service -n production",
            "kubectl rollout restart deployment/api-service -n production"
        ],
        context={
            "alert_source": "Prometheus",
            "severity": "High",
            "affected_services": "API Service"
        },
        success=True
    )
    
    print("Generated documentation files:")
    for doc_type, path in files.items():
        print(f"  {doc_type}: {path}")
