#!/usr/bin/env python3

import sys
import subprocess
import argparse
import time
import os
import atexit
from typing import Dict, Optional
from PyQt5 import QtWidgets, QtCore, QtGui
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class JobLockManager:
    """Manages file-based locking to ensure only one monitor per job ID."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.lock_file = f"/tmp/job_usage_monitor_{job_id}.lock"
        self.lock_acquired = False
        
    def acquire_lock(self) -> bool:
        """Try to acquire the lock for this job ID."""
        try:
            # Check if lock file exists
            if os.path.exists(self.lock_file):
                # Read existing lock info
                try:
                    with open(self.lock_file, 'r') as f:
                        content = f.read().strip()
                        if content:
                            existing_pid = int(content.split()[0])
                            
                            # Check if the process is still running
                            if self._is_process_running(existing_pid):
                                return False  # Another instance is running
                            else:
                                # Stale lock file, remove it
                                os.remove(self.lock_file)
                except (ValueError, IOError):
                    # Corrupted lock file, remove it
                    try:
                        os.remove(self.lock_file)
                    except OSError:
                        pass
            
            # Create new lock file
            with open(self.lock_file, 'w') as f:
                f.write(f"{os.getpid()} {time.time()}\n")
            
            self.lock_acquired = True
            # Register cleanup function
            atexit.register(self.release_lock)
            return True
            
        except (IOError, OSError):
            return False
    
    def release_lock(self):
        """Release the lock by removing the lock file."""
        if self.lock_acquired and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                self.lock_acquired = False
            except OSError:
                pass
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is running."""
        try:
            # Send signal 0 to check if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class JobUsageMonitor(QtWidgets.QMainWindow):
    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self.lock_manager = JobLockManager(job_id)
        self.node_name = None
        self.job_user = None
        self.allocated_cpus = None
        self.allocated_memory_mb = None
        self.allocated_gpus = None
        self.gpu_memory_mb = None
        self.multiple_gpu_job = False
        self.multiple_jobs_on_node = False
        self.cpu_data = []
        self.memory_data = []
        self.gpu_util_data = []
        self.gpu_mem_data = []
        self.time_data = []
        self.max_points = 60  # Keep last 60 data points
        self.has_nvidia_smi = False
        self.gpu_count = 0
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_data)
        
        self.init_ui()
        self.get_job_info()
        self.check_multiple_jobs_on_node()
        self.check_gpu_availability()
        
        # Start monitoring automatically after a short delay to allow UI to initialize
        QtCore.QTimer.singleShot(1000, self.auto_start_monitoring)
        
    def init_ui(self):
        self.setWindowTitle(f"Job {self.job_id} - Resource Usage Monitor")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Info label
        self.info_label = QtWidgets.QLabel(f"Monitoring Job: {self.job_id}")
        self.info_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px;")
        layout.addWidget(self.info_label)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Getting job information...")
        self.status_label.setStyleSheet("color: blue; margin: 5px;")
        layout.addWidget(self.status_label)
        
        # Matplotlib figure
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        # Control buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.start_button = QtWidgets.QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        # Will be disabled initially since auto-start is enabled
        self.start_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QtWidgets.QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        # Will be enabled initially since auto-start is enabled
        self.stop_button.setEnabled(True)
        button_layout.addWidget(self.stop_button)
        
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Initial plot
        self.plot_data()
        
    def get_job_info(self):
        """Get job information using scontrol."""
        try:
            self.status_label.setText("Getting job information...")
            QtWidgets.QApplication.processEvents()
            
            # Get job details
            result = subprocess.run(
                ["scontrol", "show", "job", self.job_id],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                self.status_label.setText(f"Error: Job {self.job_id} not found or not accessible")
                return
                
            # Parse job info
            job_info = result.stdout
            node_name = None
            job_state = None
            
            for line in job_info.split('\n'):
                line = line.strip()
                if 'NodeList=' in line:
                    node_name = line.split('NodeList=')[1].split()[0]
                elif 'JobState=' in line:
                    job_state = line.split('JobState=')[1].split()[0]
                elif 'UserId=' in line:
                    # Extract username from UserId=username(uid)
                    user_part = line.split('UserId=')[1].split()[0]
                    self.job_user = user_part.split('(')[0]
                elif 'NumCPUs=' in line:
                    # Extract allocated CPUs
                    try:
                        self.allocated_cpus = int(line.split('NumCPUs=')[1].split()[0])
                    except (ValueError, IndexError):
                        self.allocated_cpus = None
                elif 'mem=' in line.lower():
                    # Extract allocated memory (could be in different formats)
                    try:
                        # Look for patterns like "mem=4096M" or "mem=4G"
                        import re
                        mem_match = re.search(r'mem=(\d+)([MG])', line, re.IGNORECASE)
                        if mem_match:
                            mem_value = int(mem_match.group(1))
                            mem_unit = mem_match.group(2).upper()
                            if mem_unit == 'G':
                                self.allocated_memory_mb = mem_value * 1024
                            else:  # MB
                                self.allocated_memory_mb = mem_value
                    except (ValueError, AttributeError):
                        self.allocated_memory_mb = None
                elif 'gres' in line.lower() or 'tres=' in line.lower():
                    # Extract GPU allocation from GRES or TRES
                    try:
                        import re
                        # Look for patterns like "gres/gpu=2", "gres/gpu:v100=2", or "gpu:2"
                        gpu_match = re.search(r'gres/gpu[^=]*=(\d+)|gpu:(\d+)', line, re.IGNORECASE)
                        if gpu_match:
                            # Get the matched number from either group
                            gpu_count = gpu_match.group(1) if gpu_match.group(1) else gpu_match.group(2)
                            self.allocated_gpus = int(gpu_count)
                            # Check if this is a multiple GPU job
                            if self.allocated_gpus > 1:
                                self.multiple_gpu_job = True
                    except (ValueError, AttributeError):
                        self.allocated_gpus = None
                    
            if not node_name or node_name == '(null)' or node_name == 'None':
                self.status_label.setText(f"Job {self.job_id} is not running on any node (State: {job_state})")
                self.node_name = None
                return
                
            self.node_name = node_name
            
            # Update info label with allocation details
            alloc_info = ""
            if self.allocated_cpus:
                alloc_info += f" | CPUs: {self.allocated_cpus}"
            if self.allocated_memory_mb:
                if self.allocated_memory_mb >= 1024:
                    alloc_info += f" | Memory: {self.allocated_memory_mb//1024}GB"
                else:
                    alloc_info += f" | Memory: {self.allocated_memory_mb}MB"
            if self.allocated_gpus:
                alloc_info += f" | GPUs: {self.allocated_gpus}"
            
            self.info_label.setText(f"Monitoring Job: {self.job_id} on Node: {node_name}{alloc_info}")
            
            # Check for multiple GPU jobs and show warning
            if self.multiple_gpu_job:
                self.status_label.setText(f"WARNING: Multiple GPU job detected ({self.allocated_gpus} GPUs) - Monitoring disabled")
                QtWidgets.QMessageBox.warning(
                    self, "Multiple GPU Job Detected", 
                    f"This job has {self.allocated_gpus} GPUs allocated.\n\n"
                    "GPU monitoring is not supported for multiple GPU jobs."
                )
            else:
                self.status_label.setText(f"Job State: {job_state} | Node: {node_name}")
            
        except subprocess.TimeoutExpired:
            self.status_label.setText("Timeout getting job information")
        except Exception as e:
            self.status_label.setText(f"Error getting job info: {str(e)}")
    
    def check_multiple_jobs_on_node(self):
        """Check if the same user has multiple jobs running on the same node."""
        if not self.node_name or not self.job_user:
            return
            
        try:
            # Get all running jobs for the user on the specific node
            result = subprocess.run(
                ["squeue", "-u", self.job_user, "-h", "-t", "RUNNING", "-w", self.node_name, "-o", "%i"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # Count job IDs (excluding our current job)
                job_ids = [jid.strip() for jid in result.stdout.strip().split('\n') if jid.strip()]
                other_jobs = [jid for jid in job_ids if jid != self.job_id]
                
                if len(other_jobs) > 0:
                    self.multiple_jobs_on_node = True
                    # Show warning dialog
                    QtWidgets.QMessageBox.warning(
                        self, "Multiple Jobs on Node Detected", 
                        f"User '{self.job_user}' has {len(other_jobs) + 1} jobs running on node '{self.node_name}'.\n\n"
                        "Job monitoring is not supported when multiple jobs from the same user "
                        "are running on the same node to ensure accurate resource attribution."
                    )
                    
        except (subprocess.TimeoutExpired, Exception):
            pass  # If we can't check, assume it's okay to proceed
    
    def check_gpu_availability(self):
        """Check if nvidia-smi is available on the compute node."""
        if not self.node_name:
            return
            
        # Disable GPU monitoring for multiple GPU jobs or multiple jobs on node
        if self.multiple_gpu_job or self.multiple_jobs_on_node:
            self.has_nvidia_smi = False
            return
            
        try:
            # Check if nvidia-smi is available on the remote node
            ssh_cmd = [
                "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                self.node_name,
                "nvidia-smi --query-gpu=count --format=csv,noheader,nounits"
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    self.gpu_count = int(result.stdout.strip())
                    self.has_nvidia_smi = True
                    print(f"GPU monitoring enabled: {self.gpu_count} GPU(s) detected")
                except ValueError:
                    pass
            
        except (subprocess.TimeoutExpired, Exception):
            pass  # GPU monitoring will remain disabled
            
    def get_resource_usage(self) -> Optional[Dict[str, float]]:
        """Get CPU and memory usage for the job on the remote node using top command.
        
        Returns usage as percentage of allocated resources, not system resources.
        """
        if not self.node_name or not self.job_user:
            return None
            
        try:
            # Get memory usage with proper unit handling (g=GB, m=MB, k=KB, no suffix=KB)
            ssh_cmd = [
                "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                self.node_name,
                f"""top -b -n1 -u {self.job_user} | grep -E '^\\s*[0-9]+' | awk '{{
                    cpu += $9;
                    res = $6;
                    if (res ~ /g$/) {{ mem_mb += (res * 1024) }}
                    else if (res ~ /m$/) {{ mem_mb += res }}
                    else if (res ~ /k$/) {{ mem_mb += (res / 1024) }}
                    else {{ mem_mb += (res / 1024) }}
                }} END {{ print cpu " " mem_mb }}'"""
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    parts = result.stdout.strip().split()
                    if len(parts) >= 2:
                        cpu_pct = float(parts[0]) if parts[0] != "" else 0.0
                        mem_mb = float(parts[1]) if parts[1] != "" else 0.0
                        
                        # Calculate memory percentage relative to allocated memory
                        mem_pct = 0.0
                        if self.allocated_memory_mb and self.allocated_memory_mb > 0:
                            mem_pct = (mem_mb / self.allocated_memory_mb) * 100.0
                        
                        return {
                            "cpu": cpu_pct if cpu_pct >= 0 else 0.0,
                            "memory": mem_pct if mem_pct >= 0 else 0.0
                        }
                except ValueError:
                    pass
            
            return {"cpu": 0.0, "memory": 0.0}
            
        except subprocess.TimeoutExpired:
            self.status_label.setText("SSH timeout - node may be unreachable")
            return None
        except Exception as e:
            self.status_label.setText(f"Error getting resource data: {str(e)}")
            return None
    
    def get_gpu_usage(self) -> Optional[Dict[str, float]]:
        """Get GPU utilization and memory usage."""
        if not self.has_nvidia_smi or not self.node_name:
            return None
            
        try:
            # Get GPU utilization and memory usage
            ssh_cmd = [
                "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                self.node_name,
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                total_util = 0.0
                total_mem_used = 0.0
                total_mem_total = 0.0
                
                for line in lines:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        try:
                            util = float(parts[0].strip())
                            mem_used = float(parts[1].strip())
                            mem_total = float(parts[2].strip())
                            
                            total_util += util
                            total_mem_used += mem_used
                            total_mem_total += mem_total
                        except ValueError:
                            continue
                
                if self.gpu_count > 0:
                    avg_util = total_util / self.gpu_count
                    mem_pct = (total_mem_used / total_mem_total * 100.0) if total_mem_total > 0 else 0.0
                    
                    # Store total GPU memory in MB for display (only once)
                    if self.gpu_memory_mb is None and total_mem_total > 0:
                        self.gpu_memory_mb = int(total_mem_total)
                    
                    return {
                        "utilization": avg_util,
                        "memory": mem_pct
                    }
            
            return {"utilization": 0.0, "memory": 0.0}
            
        except (subprocess.TimeoutExpired, Exception):
            return None
            
    def update_data(self):
        """Update CPU, memory, and GPU usage data."""
        resource_usage = self.get_resource_usage()
        gpu_usage = self.get_gpu_usage() if self.has_nvidia_smi else None
        
        if resource_usage is not None:
            current_time = time.time()
            
            # Add new data points
            self.cpu_data.append(resource_usage["cpu"])
            self.memory_data.append(resource_usage["memory"])
            self.time_data.append(current_time)
            
            # Add GPU data if available
            if gpu_usage is not None:
                self.gpu_util_data.append(gpu_usage["utilization"])
                self.gpu_mem_data.append(gpu_usage["memory"])
            else:
                self.gpu_util_data.append(0.0)
                self.gpu_mem_data.append(0.0)
            
            # Keep only the last max_points
            if len(self.cpu_data) > self.max_points:
                self.cpu_data.pop(0)
                self.memory_data.pop(0)
                self.gpu_util_data.pop(0)
                self.gpu_mem_data.pop(0)
                self.time_data.pop(0)
                
            # Update plot
            self.plot_data()
            
            # Update status with allocation context
            cpu_text = f"CPU: {resource_usage['cpu']:.1f}%"
            if self.allocated_cpus and self.allocated_cpus > 1:
                cpu_efficiency = resource_usage['cpu'] / (self.allocated_cpus * 100) * 100
                cpu_text += f" ({cpu_efficiency:.1f}% of {self.allocated_cpus} cores)"
            
            mem_text = f"Memory: {resource_usage['memory']:.1f}%"
            if self.allocated_memory_mb:
                mem_text += f" of {self.allocated_memory_mb}MB allocated"
            
            status_text = f"{cpu_text} | {mem_text}"
            
            # Add GPU info if available
            if gpu_usage is not None:
                gpu_text = f"GPU: {gpu_usage['utilization']:.1f}% util, {gpu_usage['memory']:.1f}% mem"
                status_text += f" | {gpu_text}"
            
            status_text += f" | Node: {self.node_name}"
            self.status_label.setText(status_text)
            
    def plot_data(self):
        """Plot the CPU, memory, and GPU usage data."""
        self.figure.clear()
        
        if self.cpu_data and self.time_data:
            # Convert timestamps to relative seconds from the most recent data point
            end_time = self.time_data[-1]
            relative_times = [(t - end_time) for t in self.time_data]
            
            # Create subplots based on GPU availability
            if self.has_nvidia_smi:
                # 4 subplots: CPU, Memory, GPU Util, GPU Memory
                ax1 = self.figure.add_subplot(221)  # CPU plot
                ax2 = self.figure.add_subplot(222)  # Memory plot  
                ax3 = self.figure.add_subplot(223)  # GPU Utilization plot
                ax4 = self.figure.add_subplot(224)  # GPU Memory plot
            else:
                # 2 subplots: CPU, Memory
                ax1 = self.figure.add_subplot(211)  # CPU plot
                ax2 = self.figure.add_subplot(212)  # Memory plot
            
            # CPU plot
            ax1.plot(relative_times, self.cpu_data, 'b-', linewidth=2, marker='o', markersize=3, label='CPU Util %')
            ax1.fill_between(relative_times, self.cpu_data, alpha=0.3, color='blue')
            ax1.set_ylabel('CPU Usage (%)')
            if self.has_nvidia_smi:
                ax1.set_title(f'Job {self.job_id} Resource Usage')
            else:
                ax1.set_title(f'Job {self.job_id} Resource Usage (CPU: top %, Memory: % of allocation)')
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc='upper right')
            
            # Set CPU y-axis limits based on allocated CPUs
            if self.allocated_cpus and self.allocated_cpus > 1:
                # For multi-core jobs, top can show >100% CPU usage
                max_cpu_limit = self.allocated_cpus * 100
                current_max = max(self.cpu_data) if self.cpu_data else 0
                ax1.set_ylim(0, max(max_cpu_limit, current_max * 1.1))
                ax1.axhline(y=max_cpu_limit, color='gray', linestyle='--', alpha=0.7)
            else:
                # Single core or unknown allocation
                max_cpu = max(self.cpu_data) if self.cpu_data else 100
                ax1.set_ylim(0, max(100, max_cpu * 1.1))
                ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.7)
            
            ax1.legend(loc='upper right')
            
            # Set x-axis to show last 60 seconds
            ax1.set_xlim(-60, 0)
            
            # Memory plot
            if self.memory_data:
                ax2.plot(relative_times, self.memory_data, 'r-', linewidth=2, marker='s', markersize=3, label='CPU Mem %')
                ax2.fill_between(relative_times, self.memory_data, alpha=0.3, color='red')
                
                # Set memory y-axis limits - memory % is now relative to allocated memory
                max_mem = max(self.memory_data) if self.memory_data else 100
                ax2.set_ylim(0, max(100, max_mem * 1.1))
                
                # Add 100% allocation line
                ax2.axhline(y=100, color='gray', linestyle='--', alpha=0.7)
                
                # Add allocation info
                if self.allocated_memory_mb:
                    if self.allocated_memory_mb >= 1024:
                        mem_text = f'Available: {self.allocated_memory_mb//1024}GB'
                    else:
                        mem_text = f'Available: {self.allocated_memory_mb}MB'
                    ax2.text(0.02, 0.98, mem_text, 
                           transform=ax2.transAxes, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            ax2.set_xlabel('Time (seconds)')
            ax2.set_ylabel('Memory Usage (%)')
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='upper right')
            
            # Set x-axis to show last 60 seconds
            ax2.set_xlim(-60, 0)
            
            # GPU plots if available
            if self.has_nvidia_smi and self.gpu_util_data:
                # GPU Utilization plot
                ax3.plot(relative_times, self.gpu_util_data, 'g-', linewidth=2, marker='^', markersize=3, label='GPU Util %')
                ax3.fill_between(relative_times, self.gpu_util_data, alpha=0.3, color='green')
                ax3.set_ylabel('GPU Util (%)')
                ax3.set_xlabel('Time (seconds)')
                ax3.grid(True, alpha=0.3)
                ax3.legend(loc='upper right')
                ax3.set_ylim(0, 105)
                ax3.set_xlim(-60, 0)
                ax3.axhline(y=100, color='gray', linestyle='--', alpha=0.7)
                
                # GPU Memory plot
                ax4.plot(relative_times, self.gpu_mem_data, 'm-', linewidth=2, marker='d', markersize=3, label='GPU Mem %')
                ax4.fill_between(relative_times, self.gpu_mem_data, alpha=0.3, color='magenta')
                ax4.set_ylabel('GPU Memory (%)')
                ax4.set_xlabel('Time (seconds)')
                ax4.grid(True, alpha=0.3)
                ax4.legend(loc='upper right')
                ax4.set_ylim(0, 105)
                ax4.set_xlim(-60, 0)
                ax4.axhline(y=100, color='gray', linestyle='--', alpha=0.7)
                
                # Add GPU memory allocation info
                if self.gpu_memory_mb:
                    if self.gpu_memory_mb >= 1024:
                        gpu_mem_text = f'Available: {self.gpu_memory_mb//1024}GB'
                    else:
                        gpu_mem_text = f'Available: {self.gpu_memory_mb}MB'
                    ax4.text(0.02, 0.98, gpu_mem_text, 
                           transform=ax4.transAxes, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
        else:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No data available\nStart monitoring to see resource usage\n(CPU and Memory like in top command)',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=14, color='gray')
            ax.set_xlabel('Time (seconds)')
            ax.set_ylabel('Usage (%)')
            ax.set_title(f'Job {self.job_id} Resource Usage')
            
        self.figure.tight_layout()
        self.canvas.draw()
        
    def start_monitoring(self):
        """Start monitoring CPU usage."""
        if not self.node_name:
            QtWidgets.QMessageBox.warning(
                self, "Warning", 
                "Cannot start monitoring: Job is not running on any node"
            )
            return
            
        if self.multiple_gpu_job:
            QtWidgets.QMessageBox.warning(
                self, "Multiple GPU Job", 
                f"Monitoring is disabled for multiple GPU jobs ({self.allocated_gpus} GPUs).\n\n"
                "This limitation is in place to ensure accurate resource monitoring."
            )
            return
            
        if self.multiple_jobs_on_node:
            QtWidgets.QMessageBox.warning(
                self, "Multiple Jobs on Node", 
                f"Monitoring is disabled when multiple jobs from the same user "
                f"are running on the same node ({self.node_name}).\n\n"
                "This limitation ensures accurate resource attribution."
            )
            return
            
        self.cpu_data.clear()
        self.memory_data.clear()
        self.gpu_util_data.clear()
        self.gpu_mem_data.clear()
        self.time_data.clear()
        self.update_timer.start(2000)  # Update every 2 seconds
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Monitoring started...")
        
    def stop_monitoring(self):
        """Stop monitoring CPU usage."""
        self.update_timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Monitoring stopped")
        
    def closeEvent(self, event):
        """Handle window close event."""
        self.update_timer.stop()
        self.lock_manager.release_lock()
        event.accept()

    def auto_start_monitoring(self):
        """Automatically start monitoring if the job is running."""
        if self.multiple_gpu_job:
            # Multiple GPU job - disable monitoring
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.status_label.setText(f"Monitoring disabled - Multiple GPU job ({self.allocated_gpus} GPUs)")
        elif self.multiple_jobs_on_node:
            # Multiple jobs on node - disable monitoring
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.status_label.setText(f"Monitoring disabled - Multiple jobs on node ({self.node_name})")
        elif self.node_name:
            # Job is running on a node, start monitoring
            self.cpu_data.clear()
            self.memory_data.clear()
            self.gpu_util_data.clear()
            self.gpu_mem_data.clear()
            self.time_data.clear()
            self.update_timer.start(2000)  # Update every 2 seconds
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText("Auto-started monitoring...")
        else:
            # Job not running, enable start button for manual control
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setText("Job not running - monitoring not started")


def main():
    parser = argparse.ArgumentParser(description="Monitor Slurm job resource usage")
    parser.add_argument(
        "object_title",
        help="Title of the job object (job ID)"
    )
    parser.add_argument(
        "object_id",
        help="ID of the job object"
    )
    args = parser.parse_args()
    
    # Extract job ID from object_title (the title is the job ID)
    job_id = args.object_title
    
    # Check if another instance is already running for this job
    lock_manager = JobLockManager(job_id)
    if not lock_manager.acquire_lock():
        print(f"Error: Another instance of Job Usage Monitor is already running for job {job_id}")
        print(f"Lock file: {lock_manager.lock_file}")
        sys.exit(1)
    
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Job Usage Monitor")
    
    # Set application icon if available
    try:
        app.setWindowIcon(QtGui.QIcon("Resources/Job.png"))
    except:
        pass
    
    monitor = JobUsageMonitor(job_id)
    monitor.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
