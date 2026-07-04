"""
Enhanced Server Collector for Linux, Windows, and RHEL
Supports multiple operating systems and provides comprehensive diagnostics.
"""

import os
import platform
import asyncio
import subprocess
from typing import Dict, Optional
import structlog

log = structlog.get_logger()


class EnhancedServerCollector:
    """
    Collects server diagnostics for Linux, Windows, and RHEL systems.
    Automatically detects OS type and runs appropriate commands.
    """
    
    def __init__(self):
        self.os_type = platform.system().lower()  # 'linux', 'windows', 'darwin'
        self.os_release = self._detect_linux_distro()
        
        log.info(f"EnhancedServerCollector initialized", os_type=self.os_type, os_release=self.os_release)
    
    def _detect_linux_distro(self) -> str:
        """Detect Linux distribution (RHEL, Ubuntu, etc.)"""
        if self.os_type != 'linux':
            return self.os_type
        
        try:
            # Try to read /etc/os-release
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                if 'red hat' in content or 'rhel' in content:
                    return 'rhel'
                elif 'centos' in content:
                    return 'centos'
                elif 'ubuntu' in content:
                    return 'ubuntu'
                elif 'debian' in content:
                    return 'debian'
                elif 'amazon linux' in content:
                    return 'amazon-linux'
                return 'linux'
        except:
            return 'linux'
    
    async def collect(self, incident_data: Optional[Dict] = None) -> Dict:
        """
        Collect server diagnostics based on OS type.
        
        Returns comprehensive system information including:
        - CPU, memory, disk usage
        - Running processes
        - Service status
        - System logs
        - Network information
        """
        if self.os_type == 'windows':
            return await self._collect_windows()
        elif self.os_type == 'linux' or self.os_type == 'darwin':
            if self.os_release in ['rhel', 'centos', 'amazon-linux']:
                return await self._collect_rhel()
            else:
                return await self._collect_linux()
        else:
            return {"error": f"Unsupported OS type: {self.os_type}"}
    
    async def _collect_linux(self) -> Dict:
        """Collect diagnostics for Ubuntu/Debian Linux systems."""
        commands = {
            "os_info": "uname -a",
            "distribution": "cat /etc/os-release | grep PRETTY_NAME",
            "uptime": "uptime",
            "cpu_info": "lscpu | grep -E 'Model name|CPU\\(s\\):|Thread'",
            "memory_usage": "free -h",
            "memory_detailed": "cat /proc/meminfo | head -20",
            "disk_usage": "df -h",
            "disk_inodes": "df -i",
            "disk_io": "iostat -x 1 2 | tail -20",
            "top_processes_cpu": "ps aux --sort=-%cpu | head -15",
            "top_processes_memory": "ps aux --sort=-%mem | head -15",
            "load_average": "cat /proc/loadavg",
            "systemd_failed": "systemctl list-units --state=failed --no-pager",
            "systemd_services": "systemctl list-units --type=service --state=running --no-pager | head -30",
            "network_connections": "ss -tunap | head -30",
            "listening_ports": "ss -tlnp",
            "network_interfaces": "ip addr show",
            "routing_table": "ip route show",
            "system_logs": "journalctl -p err -n 50 --no-pager",
            "kernel_errors": "dmesg | grep -i error | tail -20",
            "nginx_status": "systemctl status nginx --no-pager -l | tail -30",
            "docker_status": "systemctl status docker --no-pager -l | tail -20",
            "disk_mounts": "mount | grep -v tmpfs | grep -v cgroup",
        }
        
        return await self._run_commands(commands)
    
    async def _collect_rhel(self) -> Dict:
        """Collect diagnostics for RHEL/CentOS/Amazon Linux systems."""
        commands = {
            "os_info": "uname -a",
            "distribution": "cat /etc/redhat-release",
            "uptime": "uptime",
            "cpu_info": "lscpu | grep -E 'Model name|CPU\\(s\\):|Thread'",
            "memory_usage": "free -h",
            "memory_detailed": "cat /proc/meminfo | head -20",
            "disk_usage": "df -h",
            "disk_inodes": "df -i",
            "top_processes_cpu": "ps aux --sort=-%cpu | head -15",
            "top_processes_memory": "ps aux --sort=-%mem | head -15",
            "load_average": "cat /proc/loadavg",
            "systemd_failed": "systemctl list-units --state=failed --no-pager",
            "systemd_services": "systemctl list-units --type=service --state=running --no-pager | head -30",
            "network_connections": "ss -tunap | head -30",
            "listening_ports": "ss -tlnp",
            "network_interfaces": "ip addr show",
            "routing_table": "ip route show",
            "system_logs": "journalctl -p err -n 50 --no-pager",
            "kernel_errors": "dmesg | grep -i error | tail -20",
            "selinux_status": "sestatus",
            "firewalld_status": "systemctl status firewalld --no-pager",
            "yum_updates": "yum check-update | tail -20",
            "nginx_status": "systemctl status nginx --no-pager -l | tail -30",
            "docker_status": "systemctl status docker --no-pager -l | tail -20",
        }
        
        return await self._run_commands(commands)
    
    async def _collect_windows(self) -> Dict:
        """Collect diagnostics for Windows systems."""
        commands = {
            "os_info": "systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\"",
            "uptime": "systeminfo | findstr /C:\"System Boot Time\"",
            "cpu_info": "wmic cpu get name,numberofcores,numberoflogicalprocessors",
            "memory_usage": "systeminfo | findstr /C:\"Total Physical Memory\" /C:\"Available Physical Memory\"",
            "disk_usage": "wmic logicaldisk get name,size,freespace,filesystem",
            "top_processes_memory": "powershell \"Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 15 | Format-Table Name,Id,CPU,WorkingSet -AutoSize\"",
            "services_running": "powershell \"Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object -First 30 | Format-Table Name,Status -AutoSize\"",
            "services_stopped": "powershell \"Get-Service | Where-Object {$_.Status -eq 'Stopped'} | Select-Object -First 10 | Format-Table Name,Status -AutoSize\"",
            "network_connections": "netstat -ano | findstr ESTABLISHED",
            "listening_ports": "netstat -ano | findstr LISTENING",
            "network_interfaces": "ipconfig /all",
            "event_log_errors": "powershell \"Get-EventLog -LogName System -EntryType Error -Newest 20 | Format-Table TimeGenerated,Source,Message -AutoSize\"",
            "event_log_warnings": "powershell \"Get-EventLog -LogName Application -EntryType Warning -Newest 10 | Format-Table TimeGenerated,Source,Message -AutoSize\"",
            "firewall_status": "netsh advfirewall show allprofiles state",
            "scheduled_tasks": "schtasks /query /fo LIST | findstr /C:\"TaskName\" /C:\"Status\"",
        }
        
        return await self._run_commands(commands)
    
    async def _run_commands(self, commands: Dict[str, str]) -> Dict:
        """Run multiple commands asynchronously and collect results."""
        results = {
            "os_type": self.os_type,
            "os_release": self.os_release,
            "timestamp": asyncio.get_event_loop().time(),
            "diagnostics": {}
        }
        
        tasks = []
        for key, cmd in commands.items():
            tasks.append(self._run_single_command(key, cmd))
        
        # Run all commands concurrently
        command_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in command_results:
            if isinstance(result, dict):
                results["diagnostics"].update(result)
        
        return results
    
    async def _run_single_command(self, key: str, cmd: str, timeout: int = 10) -> Dict:
        """Run a single command safely."""
        try:
            if self.os_type == 'windows':
                shell_cmd = ['cmd', '/c', cmd]
            else:
                shell_cmd = ['sh', '-c', cmd]
            
            proc = await asyncio.create_subprocess_exec(
                *shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            output = stdout.decode('utf-8', errors='ignore').strip()
            if not output and stderr:
                output = f"Error: {stderr.decode('utf-8', errors='ignore').strip()}"
            
            return {key: output if output else "(no output)"}
            
        except asyncio.TimeoutError:
            log.warning(f"Command timed out: {cmd}")
            return {key: f"Timeout after {timeout}s"}
        except FileNotFoundError:
            return {key: "Command not found"}
        except Exception as e:
            log.error(f"Command failed: {cmd}", error=str(e))
            return {key: f"Error: {str(e)}"}
    
    def get_critical_metrics(self, diagnostics: Dict) -> Dict:
        """
        Extract critical metrics from diagnostics for quick assessment.
        """
        metrics = {
            "cpu_load": None,
            "memory_usage_percent": None,
            "disk_usage_percent": None,
            "failed_services": [],
            "critical_errors": []
        }
        
        # Parse load average (Linux/RHEL)
        if "load_average" in diagnostics.get("diagnostics", {}):
            try:
                load = diagnostics["diagnostics"]["load_average"].split()[0]
                metrics["cpu_load"] = float(load)
            except:
                pass
        
        # Parse memory usage (Linux/RHEL)
        if "memory_usage" in diagnostics.get("diagnostics", {}):
            try:
                mem_lines = diagnostics["diagnostics"]["memory_usage"].split('\n')
                for line in mem_lines:
                    if 'Mem:' in line:
                        parts = line.split()
                        total = float(parts[1])
                        used = float(parts[2])
                        metrics["memory_usage_percent"] = (used / total) * 100
                        break
            except:
                pass
        
        # Parse failed services
        if "systemd_failed" in diagnostics.get("diagnostics", {}):
            failed = diagnostics["diagnostics"]["systemd_failed"]
            if "0 loaded units listed" not in failed:
                metrics["failed_services"] = failed.split('\n')[:10]
        
        return metrics


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test():
        collector = EnhancedServerCollector()
        print(f"Detected OS: {collector.os_type} ({collector.os_release})")
        
        results = await collector.collect()
        print("\n=== Server Diagnostics ===")
        for key, value in results.get("diagnostics", {}).items():
            print(f"\n{key}:")
            print(value[:200] if len(str(value)) > 200 else value)
    
    asyncio.run(test())
