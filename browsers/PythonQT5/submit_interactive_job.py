#!/usr/bin/env python3

import sys
import subprocess
import argparse
import socket
import getpass
from datetime import datetime
from typing import Dict, List, Optional
from PyQt5 import QtWidgets, QtCore, QtGui


class PartitionInfo:
    """Container for partition constraint information."""
    def __init__(self):
        self.max_cpus = None
        self.max_mem_mb = None
        self.max_time_minutes = None
        self.default_time_minutes = 60
        self.max_gpus = None
        self.gpu_type = None
        self.has_gpus = False
        

class InteractiveJobDialog(QtWidgets.QDialog):
    """Dialog for submitting interactive Slurm jobs."""
    
    def __init__(self, partition_name: str):
        super().__init__()
        self.partition_name = partition_name
        self.partition_info = PartitionInfo()
        self.user_accounts = []
        self.username = getpass.getuser()
        self.hostname = socket.gethostname().split('.')[0]
        
        self.setWindowTitle(f"Submit Interactive Job - Partition: {partition_name}")
        self.setMinimumWidth(500)
        
        self.init_ui()
        self.load_partition_info()
        self.load_user_accounts()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel(f"Submit Interactive Job to Partition: {self.partition_name}")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px;")
        layout.addWidget(title)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Loading partition information...")
        self.status_label.setStyleSheet("color: blue; margin: 5px;")
        layout.addWidget(self.status_label)
        
        # Form layout for job parameters
        form_layout = QtWidgets.QFormLayout()
        form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        
        # Job Name
        self.job_name_input = QtWidgets.QLineEdit()
        default_job_name = self.generate_default_job_name()
        self.job_name_input.setText(default_job_name)
        self.job_name_input.setToolTip("Name for the job")
        form_layout.addRow("Job Name:", self.job_name_input)
        
        # Account/Allocation selection
        self.account_combo = QtWidgets.QComboBox()
        self.account_combo.setToolTip("Slurm account/allocation to use")
        form_layout.addRow("Account:", self.account_combo)
        
        # CPUs per task
        self.cpus_spinbox = QtWidgets.QSpinBox()
        self.cpus_spinbox.setMinimum(1)
        self.cpus_spinbox.setMaximum(9999)  # Will be updated with partition max
        self.cpus_spinbox.setValue(8)
        self.cpus_spinbox.setToolTip("Number of CPUs per task")
        form_layout.addRow("CPUs per Task:", self.cpus_spinbox)
        
        # Memory
        memory_layout = QtWidgets.QHBoxLayout()
        self.memory_spinbox = QtWidgets.QSpinBox()
        self.memory_spinbox.setMinimum(1)
        self.memory_spinbox.setMaximum(9999)  # Will be updated with partition max
        self.memory_spinbox.setValue(4)
        self.memory_spinbox.setToolTip("Memory in GB")
        memory_layout.addWidget(self.memory_spinbox)
        memory_unit_label = QtWidgets.QLabel("GB")
        memory_layout.addWidget(memory_unit_label)
        memory_layout.addStretch()
        form_layout.addRow("Memory:", memory_layout)
        
        # GPUs (will be hidden if partition has no GPUs)
        self.gpus_spinbox = QtWidgets.QSpinBox()
        self.gpus_spinbox.setMinimum(0)
        self.gpus_spinbox.setMaximum(8)  # Will be updated with partition max
        self.gpus_spinbox.setValue(0)
        self.gpus_spinbox.setToolTip("Number of GPUs (0 for no GPU)")
        self.gpu_row_label = QtWidgets.QLabel("GPUs:")
        form_layout.addRow(self.gpu_row_label, self.gpus_spinbox)
        # Initially hide GPU controls until we know if partition has GPUs
        self.gpu_row_label.setVisible(False)
        self.gpus_spinbox.setVisible(False)
        
        # Time limit
        time_layout = QtWidgets.QHBoxLayout()
        self.time_hours_spinbox = QtWidgets.QSpinBox()
        self.time_hours_spinbox.setMinimum(0)
        self.time_hours_spinbox.setMaximum(999)
        self.time_hours_spinbox.setValue(1)
        self.time_hours_spinbox.setToolTip("Hours")
        time_layout.addWidget(QtWidgets.QLabel("Hours:"))
        time_layout.addWidget(self.time_hours_spinbox)
        
        self.time_minutes_spinbox = QtWidgets.QSpinBox()
        self.time_minutes_spinbox.setMinimum(0)
        self.time_minutes_spinbox.setMaximum(59)
        self.time_minutes_spinbox.setValue(0)
        self.time_minutes_spinbox.setToolTip("Minutes")
        time_layout.addWidget(QtWidgets.QLabel("Minutes:"))
        time_layout.addWidget(self.time_minutes_spinbox)
        time_layout.addStretch()
        form_layout.addRow("Time Limit:", time_layout)
        
        layout.addLayout(form_layout)
        
        # Partition constraints info
        self.constraints_label = QtWidgets.QLabel()
        self.constraints_label.setWordWrap(True)
        self.constraints_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; margin: 10px 0;")
        layout.addWidget(self.constraints_label)
        
        # Command preview
        preview_group = QtWidgets.QGroupBox("Command Preview")
        preview_layout = QtWidgets.QVBoxLayout()
        self.command_preview = QtWidgets.QTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(80)
        self.command_preview.setStyleSheet("font-family: monospace; background-color: #f5f5f5;")
        preview_layout.addWidget(self.command_preview)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Connect signals to update preview
        self.job_name_input.textChanged.connect(self.update_command_preview)
        self.account_combo.currentTextChanged.connect(self.update_command_preview)
        self.cpus_spinbox.valueChanged.connect(self.update_command_preview)
        self.memory_spinbox.valueChanged.connect(self.update_command_preview)
        self.gpus_spinbox.valueChanged.connect(self.update_command_preview)
        self.time_hours_spinbox.valueChanged.connect(self.update_command_preview)
        self.time_minutes_spinbox.valueChanged.connect(self.update_command_preview)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.submit_button = QtWidgets.QPushButton("Submit Job")
        self.submit_button.clicked.connect(self.submit_job)
        self.submit_button.setEnabled(False)  # Disabled until info is loaded
        self.submit_button.setStyleSheet("font-weight: bold; padding: 10px;")
        button_layout.addWidget(self.submit_button)
        
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("padding: 10px;")
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
    def generate_default_job_name(self) -> str:
        """Generate default job name."""
        now = datetime.now()
        date_str = now.strftime("%m-%d_%H:%M:%S")
        return f"RED_InteractiveJob.{self.hostname}.{self.username}.{date_str}"
        
    def load_partition_info(self):
        """Load partition constraints from scontrol."""
        try:
            self.status_label.setText("Loading partition information...")
            QtWidgets.QApplication.processEvents()
            
            result = subprocess.run(
                ["scontrol", "show", "partition", self.partition_name],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                self.status_label.setText(f"Error: Partition '{self.partition_name}' not found")
                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    f"Partition '{self.partition_name}' not found or not accessible."
                )
                return
                
            # Parse partition info
            output = result.stdout
            
            import re
            
            # Get the first node in the partition to determine CPU and memory limits
            # Use word boundary to avoid matching "AllocNodes"
            nodes_match = re.search(r'\bNodes=(\S+)', output)
            if nodes_match:
                node_name = nodes_match.group(1)
                
                # If node is a range or list, just take the first one
                if '[' in node_name:
                    # Handle node ranges like "node[001-100]"
                    base = node_name.split('[')[0]
                    range_part = node_name.split('[')[1].split(']')[0]
                    if '-' in range_part:
                        first_num = range_part.split('-')[0]
                        node_name = base + first_num
                    else:
                        node_name = base + range_part.split(',')[0]
                elif ',' in node_name:
                    node_name = node_name.split(',')[0]
                
                # Get node info
                node_result = subprocess.run(
                    ["scontrol", "show", "node", node_name],
                    capture_output=True, text=True, timeout=10
                )
                if node_result.returncode == 0:
                    cpus_match = re.search(r'CPUTot=(\d+)', node_result.stdout)
                    if cpus_match:
                        self.partition_info.max_cpus = int(cpus_match.group(1))
                    
                    # Get memory info
                    mem_match = re.search(r'RealMemory=(\d+)', node_result.stdout)
                    if mem_match:
                        self.partition_info.max_mem_mb = int(mem_match.group(1))
                    
                    # Get GPU info from Gres field (e.g., Gres=gpu:v100:4)
                    gres_match = re.search(r'Gres=gpu:(\w+):(\d+)', node_result.stdout)
                    if gres_match:
                        self.partition_info.has_gpus = True
                        self.partition_info.gpu_type = gres_match.group(1)
                        self.partition_info.max_gpus = int(gres_match.group(2))
                    else:
                        # Try simpler pattern (e.g., Gres=gpu:4)
                        gres_simple_match = re.search(r'Gres=gpu:(\d+)', node_result.stdout)
                        if gres_simple_match:
                            self.partition_info.has_gpus = True
                            self.partition_info.max_gpus = int(gres_simple_match.group(1))
            
            # Look for MaxTime or DefaultTime
            max_time_match = re.search(r'MaxTime=(\S+)', output)
            if max_time_match:
                time_str = max_time_match.group(1)
                self.partition_info.max_time_minutes = self.parse_slurm_time(time_str)
            
            default_time_match = re.search(r'DefaultTime=(\S+)', output)
            if default_time_match:
                time_str = default_time_match.group(1)
                self.partition_info.default_time_minutes = self.parse_slurm_time(time_str)
            
            # Update UI with constraints
            self.update_constraints_display()
            self.apply_partition_limits()
            
            self.status_label.setText("Partition information loaded")
            
        except subprocess.TimeoutExpired:
            self.status_label.setText("Timeout loading partition information")
            QtWidgets.QMessageBox.warning(
                self, "Warning",
                "Timeout while loading partition information. Some limits may not be accurate."
            )
        except Exception as e:
            self.status_label.setText(f"Error loading partition info: {str(e)}")
            QtWidgets.QMessageBox.warning(
                self, "Warning",
                f"Error loading partition information: {str(e)}\nSome limits may not be accurate."
            )
            
    def parse_slurm_time(self, time_str: str) -> Optional[int]:
        """Parse Slurm time format (e.g., '7-00:00:00', '04:00:00', 'UNLIMITED') to minutes."""
        if time_str == 'UNLIMITED' or time_str == 'INFINITE':
            return None
            
        try:
            # Handle format: days-hours:minutes:seconds
            if '-' in time_str:
                days_part, time_part = time_str.split('-')
                days = int(days_part)
                parts = time_part.split(':')
            else:
                days = 0
                parts = time_str.split(':')
            
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
            elif len(parts) == 2:
                hours, minutes = map(int, parts)
                seconds = 0
            else:
                return None
                
            total_minutes = days * 24 * 60 + hours * 60 + minutes
            return total_minutes
            
        except (ValueError, AttributeError):
            return None
            
    def update_constraints_display(self):
        """Update the constraints information display."""
        constraints = []
        
        if self.partition_info.max_cpus:
            constraints.append(f"Max CPUs: {self.partition_info.max_cpus}")
        else:
            constraints.append("Max CPUs: Unknown")
            
        if self.partition_info.max_mem_mb:
            mem_gb = self.partition_info.max_mem_mb // 1024
            constraints.append(f"Max Memory: {mem_gb}GB")
        else:
            constraints.append("Max Memory: Unknown")
        
        if self.partition_info.has_gpus:
            if self.partition_info.gpu_type:
                constraints.append(f"Max GPUs: {self.partition_info.max_gpus} ({self.partition_info.gpu_type})")
            else:
                constraints.append(f"Max GPUs: {self.partition_info.max_gpus}")
            
        if self.partition_info.max_time_minutes:
            hours = self.partition_info.max_time_minutes // 60
            minutes = self.partition_info.max_time_minutes % 60
            constraints.append(f"Max Time: {hours}h {minutes}m")
        else:
            constraints.append("Max Time: Unlimited")
            
        self.constraints_label.setText("Partition Constraints: " + " | ".join(constraints))
        
    def apply_partition_limits(self):
        """Apply partition limits to the spinboxes."""
        if self.partition_info.max_cpus:
            self.cpus_spinbox.setMaximum(self.partition_info.max_cpus)
            
        if self.partition_info.max_mem_mb:
            # Convert MB to GB for the spinbox
            max_mem_gb = self.partition_info.max_mem_mb // 1024
            self.memory_spinbox.setMaximum(max_mem_gb)
        else:
            self.memory_spinbox.setMaximum(9999)
        
        # Show/hide GPU controls based on availability
        if self.partition_info.has_gpus:
            self.gpu_row_label.setVisible(True)
            self.gpus_spinbox.setVisible(True)
            if self.partition_info.max_gpus:
                self.gpus_spinbox.setMaximum(self.partition_info.max_gpus)
            # Update tooltip with GPU type if available
            if self.partition_info.gpu_type:
                self.gpus_spinbox.setToolTip(f"Number of {self.partition_info.gpu_type} GPUs (0 for no GPU)")
        else:
            self.gpu_row_label.setVisible(False)
            self.gpus_spinbox.setVisible(False)
            
        if self.partition_info.max_time_minutes:
            max_hours = self.partition_info.max_time_minutes // 60
            max_minutes = self.partition_info.max_time_minutes % 60
            self.time_hours_spinbox.setMaximum(max_hours)
        else:
            self.time_hours_spinbox.setMaximum(999)
            
        # Set default time if available
        if self.partition_info.default_time_minutes:
            default_hours = self.partition_info.default_time_minutes // 60
            default_minutes = self.partition_info.default_time_minutes % 60
            self.time_hours_spinbox.setValue(default_hours)
            self.time_minutes_spinbox.setValue(default_minutes)
            
    def load_user_accounts(self):
        """Load user's Slurm accounts/allocations."""
        try:
            result = subprocess.run(
                ["sacctmgr", "show", "associations", 
                 f"where", f"user={self.username}",
                 "format=account%30", "-n", "-P"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # Parse accounts and remove duplicates
                accounts = list(set([line.strip() for line in result.stdout.strip().split('\n') if line.strip()]))
                accounts.sort()
                self.user_accounts = accounts
                
                # Populate combo box
                self.account_combo.clear()
                self.account_combo.addItems(accounts)
                
                # Default to "staff" if available
                if "staff" in accounts:
                    staff_index = accounts.index("staff")
                    self.account_combo.setCurrentIndex(staff_index)
                    
                self.submit_button.setEnabled(True)
                self.status_label.setText(f"Found {len(accounts)} account(s)")
            else:
                # No accounts found, but allow submission (Slurm may have a default)
                self.status_label.setText("Warning: Could not load accounts. Default account will be used.")
                self.account_combo.addItem("(default)")
                self.submit_button.setEnabled(True)
                
            self.update_command_preview()
            
        except subprocess.TimeoutExpired:
            self.status_label.setText("Timeout loading accounts")
            self.account_combo.addItem("(default)")
            self.submit_button.setEnabled(True)
        except Exception as e:
            self.status_label.setText(f"Error loading accounts: {str(e)}")
            self.account_combo.addItem("(default)")
            self.submit_button.setEnabled(True)
            
    def build_srun_command(self) -> List[str]:
        """Build the srun command with specified parameters."""
        # Convert GB to MB for srun
        memory_mb = self.memory_spinbox.value() * 1024
        
        cmd = [
            "srun",
            f"--partition={self.partition_name}",
            "--nodes=1",
            f"--cpus-per-task={self.cpus_spinbox.value()}",
            f"--mem={memory_mb}M",
        ]
        
        # Add GPU request if GPUs are available and requested
        if self.partition_info.has_gpus and self.gpus_spinbox.value() > 0:
            gpu_count = self.gpus_spinbox.value()
            cmd.append(f"--gres=gpu:{gpu_count}")
        
        # Add time limit
        hours = self.time_hours_spinbox.value()
        minutes = self.time_minutes_spinbox.value()
        time_str = f"{hours:02d}:{minutes:02d}:00"
        cmd.append(f"--time={time_str}")
        
        # Add account if not default
        account = self.account_combo.currentText()
        if account and account != "(default)":
            cmd.append(f"--account={account}")
            
        # Add job name
        job_name = self.job_name_input.text().strip()
        if job_name:
            cmd.append(f"--job-name={job_name}")
            
        # Enable X11 forwarding
        cmd.append("--x11")
        
        # Enable interactive mode
        cmd.append("--pty")

        # Add the command to run (bash)
        cmd.append("bash")
        
        return cmd
        
    def update_command_preview(self):
        """Update the command preview display."""
        cmd = self.build_srun_command()
        cmd_str = " ".join(cmd)
        self.command_preview.setText(cmd_str)
        
    def submit_job(self):
        """Submit the interactive job."""
        # Validate inputs
        job_name = self.job_name_input.text().strip()
        if not job_name:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error",
                "Please provide a job name."
            )
            return
            
        # Check time limit
        if self.time_hours_spinbox.value() == 0 and self.time_minutes_spinbox.value() == 0:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error",
                "Time limit must be greater than 0."
            )
            return
            
        # Build command
        cmd = self.build_srun_command()
        
        try:
            self.status_label.setText("Submitting job...")
            QtWidgets.QApplication.processEvents()
            
            # Launch srun in a new terminal window using mate-terminal
            terminal_cmd = ["mate-terminal", "--"] + cmd
            
            # Launch in background
            subprocess.Popen(
                terminal_cmd,
                start_new_session=True
            )
            
            self.accept()
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Error submitting job: {str(e)}"
            )
            self.status_label.setText(f"Error: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="Submit interactive Slurm job with X11 forwarding"
    )
    parser.add_argument(
        "partition",
        help="Partition name to submit the job to"
    )
    args = parser.parse_args()
    
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Submit Interactive Job")
    
    dialog = InteractiveJobDialog(args.partition)
    result = dialog.exec_()
    
    sys.exit(0 if result == QtWidgets.QDialog.Accepted else 1)


if __name__ == "__main__":
    main()

