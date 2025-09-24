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
        self.cpu_data = []
        self.memory_data = []
        self.time_data = []
        self.max_points = 60  # Keep last 60 data points
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_data)
        
        self.init_ui()
        self.get_job_info()
        
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
            
            self.info_label.setText(f"Monitoring Job: {self.job_id} on Node: {node_name}{alloc_info}")
            self.status_label.setText(f"Job State: {job_state} | Node: {node_name}")
            
        except subprocess.TimeoutExpired:
            self.status_label.setText("Timeout getting job information")
        except Exception as e:
            self.status_label.setText(f"Error getting job info: {str(e)}")
            
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
            
    def update_data(self):
        """Update CPU and memory usage data."""
        resource_usage = self.get_resource_usage()
        
        if resource_usage is not None:
            current_time = time.time()
            
            # Add new data points
            self.cpu_data.append(resource_usage["cpu"])
            self.memory_data.append(resource_usage["memory"])
            self.time_data.append(current_time)
            
            # Keep only the last max_points
            if len(self.cpu_data) > self.max_points:
                self.cpu_data.pop(0)
                self.memory_data.pop(0)
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
            
            self.status_label.setText(f"{cpu_text} | {mem_text} | Node: {self.node_name}")
            
    def plot_data(self):
        """Plot the CPU and memory usage data."""
        self.figure.clear()
        
        if self.cpu_data and self.time_data:
            # Convert timestamps to relative seconds from the most recent data point
            end_time = self.time_data[-1]
            relative_times = [(t - end_time) for t in self.time_data]
            
            # Create two subplots
            ax1 = self.figure.add_subplot(211)  # CPU plot
            ax2 = self.figure.add_subplot(212)  # Memory plot
            
            # CPU plot
            ax1.plot(relative_times, self.cpu_data, 'b-', linewidth=2, marker='o', markersize=3, label='CPU %')
            ax1.fill_between(relative_times, self.cpu_data, alpha=0.3, color='blue')
            ax1.set_ylabel('CPU Usage (%)')
            ax1.set_title(f'Job {self.job_id} Resource Usage (CPU: top %, Memory: % of allocation)')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Set CPU y-axis limits based on allocated CPUs
            if self.allocated_cpus and self.allocated_cpus > 1:
                # For multi-core jobs, top can show >100% CPU usage
                max_cpu_limit = self.allocated_cpus * 100
                current_max = max(self.cpu_data) if self.cpu_data else 0
                ax1.set_ylim(0, max(max_cpu_limit, current_max * 1.1))
                ax1.axhline(y=max_cpu_limit, color='gray', linestyle='--', alpha=0.7, 
                           label=f'Allocated: {self.allocated_cpus} CPUs ({max_cpu_limit}%)')
            else:
                # Single core or unknown allocation
                max_cpu = max(self.cpu_data) if self.cpu_data else 100
                ax1.set_ylim(0, max(100, max_cpu * 1.1))
                ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.7, label='100% (1 CPU)')
            
            ax1.legend()
            
            # Set x-axis to show last 60 seconds
            ax1.set_xlim(-60, 0)
            
            # Memory plot
            if self.memory_data:
                ax2.plot(relative_times, self.memory_data, 'r-', linewidth=2, marker='s', markersize=3, label='Memory %')
                ax2.fill_between(relative_times, self.memory_data, alpha=0.3, color='red')
                
                # Set memory y-axis limits - memory % is now relative to allocated memory
                max_mem = max(self.memory_data) if self.memory_data else 100
                ax2.set_ylim(0, max(100, max_mem * 1.1))
                
                # Add 100% allocation line
                ax2.axhline(y=100, color='gray', linestyle='--', alpha=0.7, 
                           label=f'100% of allocated memory')
                
                # Add allocation info
                if self.allocated_memory_mb:
                    ax2.text(0.02, 0.98, f'Allocated: {self.allocated_memory_mb}MB', 
                           transform=ax2.transAxes, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            ax2.set_xlabel('Time (seconds)')
            ax2.set_ylabel('Memory Usage (%)')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # Set x-axis to show last 60 seconds
            ax2.set_xlim(-60, 0)
            
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
            
        self.cpu_data.clear()
        self.memory_data.clear()
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
        if self.node_name:
            # Job is running on a node, start monitoring
            self.cpu_data.clear()
            self.memory_data.clear()
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
    parser.add_argument("job_id", help="Slurm job ID to monitor")
    args = parser.parse_args()
    
    # Check if another instance is already running for this job
    lock_manager = JobLockManager(args.job_id)
    if not lock_manager.acquire_lock():
        print(f"Error: Another instance of Job Usage Monitor is already running for job {args.job_id}")
        print(f"Lock file: {lock_manager.lock_file}")
        sys.exit(1)
    
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Job Usage Monitor")
    
    # Set application icon if available
    try:
        app.setWindowIcon(QtGui.QIcon("Resources/Job.png"))
    except:
        pass
    
    monitor = JobUsageMonitor(args.job_id)
    monitor.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
