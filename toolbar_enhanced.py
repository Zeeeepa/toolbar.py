"""
Enhanced ModernTaskbar integration with all new features
This file contains the enhanced methods and functionality for the ModernTaskbar class
"""
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
import threading
import subprocess
import os
from pathlib import Path
import logging
from datetime import datetime
from toolbar_services import ExecutionStatus, EditorType
from toolbar_ui_components import StatusIndicatorWidget, EnhancedTooltip

logger = logging.getLogger(__name__)

class EnhancedTaskbarMixin:
    """Mixin class to add enhanced functionality to ModernTaskbar"""
    
    def setup_enhanced_services(self):
        """Initialize enhanced services"""
        from toolbar_services import SettingsManager, EnhancedFileManager, ExecutionStatusManager, AdvancedExecutionEngine
        from toolbar_ui_components import ProgressManager
        
        self.settings_manager = SettingsManager()
        self.file_manager = EnhancedFileManager()
        self.status_manager = ExecutionStatusManager()
        self.execution_engine = AdvancedExecutionEngine(self.status_manager, self.settings_manager)
        self.progress_manager = ProgressManager(self.root, self.theme)
        self.script_buttons = {}  # Track script buttons for status updates
        
        # Update transparency from settings
        self.transparency = self.settings_manager.getint('appearance', 'transparency', 95)
        self.root.attributes('-alpha', self.transparency / 100)
    
    def setup_status_callbacks(self):
        """Setup status change callbacks for all scripts"""
        for script in self.scripts:
            script_id = script.get('id', script.get('path', ''))
            self.status_manager.register_status_callback(script_id, self.on_execution_status_change)
    
    def on_execution_status_change(self, status, execution_data):
        """Handle execution status changes"""
        script_id = execution_data['script_id']
        if script_id in self.script_buttons:
            button_info = self.script_buttons[script_id]
            if 'status_indicator' in button_info:
                button_info['status_indicator'].update_status(status)
            
            # Update tooltip with execution info
            if 'tooltip' in button_info:
                tooltip_text = self.generate_script_tooltip(execution_data['script_path'], status, execution_data)
                button_info['tooltip'].update_text(tooltip_text)
    
    def generate_script_tooltip(self, script_path, status=None, execution_data=None):
        """Generate enhanced tooltip text for scripts"""
        try:
            file_props = self.file_manager.get_file_properties(script_path)
            if not file_props:
                return f"Script: {os.path.basename(script_path)}"
            
            tooltip_lines = [
                f"📄 {file_props['name']}",
                f"📁 {file_props['parent']}",
                f"📏 {file_props['size']} bytes",
                f"📅 Modified: {file_props['modified'].strftime('%Y-%m-%d %H:%M')}"
            ]
            
            if status and execution_data:
                if status == ExecutionStatus.RUNNING:
                    duration = (execution_data.get('start_time', None))
                    if duration:
                        elapsed = (datetime.now() - duration).total_seconds()
                        tooltip_lines.append(f"⏱️ Running for {elapsed:.1f}s")
                elif status == ExecutionStatus.SUCCESS:
                    duration = execution_data.get('duration', 0)
                    tooltip_lines.append(f"✅ Completed in {duration:.2f}s")
                elif status == ExecutionStatus.ERROR:
                    tooltip_lines.append("❌ Execution failed")
            
            # Add performance stats if available
            stats = self.status_manager.get_performance_stats(script_path)
            if stats:
                tooltip_lines.extend([
                    "",
                    f"📊 Executions: {stats['total_executions']}",
                    f"✅ Success Rate: {stats['success_rate']:.1f}%",
                    f"⏱️ Avg Duration: {stats['avg_duration']:.2f}s"
                ])
            
            return "\n".join(tooltip_lines)
        except Exception as e:
            logger.error(f"Error generating tooltip: {e}")
            return f"Script: {os.path.basename(script_path)}"
    
    def enhanced_execute_script(self, script_data):
        """Enhanced script execution with status tracking"""
        try:
            file_path = script_data.get('path', '')
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror("Error", f"Script file not found: {file_path}")
                return
            
            script_id = script_data.get('id', file_path)
            
            # Start execution tracking
            execution_id = self.status_manager.start_execution(script_id, file_path, f"Execute {file_path}")
            
            # Execute using advanced engine
            def execute_async():
                try:
                    process = self.execution_engine.execute_file(file_path, background=True)
                    
                    # Monitor process
                    def monitor_process():
                        try:
                            stdout, stderr = process.communicate()
                            
                            if process.returncode == 0:
                                self.status_manager.update_execution_status(
                                    execution_id, ExecutionStatus.SUCCESS, 
                                    output=stdout, error=stderr
                                )
                            else:
                                self.status_manager.update_execution_status(
                                    execution_id, ExecutionStatus.ERROR,
                                    output=stdout, error=stderr
                                )
                        except Exception as e:
                            logger.error(f"Error monitoring process: {e}")
                            self.status_manager.update_execution_status(
                                execution_id, ExecutionStatus.ERROR, error=str(e)
                            )
                    
                    threading.Thread(target=monitor_process, daemon=True).start()
                    
                except Exception as e:
                    logger.error(f"Error executing script: {e}")
                    self.status_manager.update_execution_status(
                        execution_id, ExecutionStatus.ERROR, error=str(e)
                    )
            
            threading.Thread(target=execute_async, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error in enhanced execute script: {e}")
            messagebox.showerror("Error", f"Failed to execute script: {e}")
    
    def enhanced_add_script_button(self, script_data):
        """Add script button with enhanced features"""
        try:
            button_frame = tk.Frame(self.scrollable_frame, bg=self.theme.get_color('bg'))
            button_frame.pack(side=tk.LEFT, padx=2, pady=2)
            
            # Create main button
            button = tk.Button(
                button_frame,
                text=os.path.basename(script_data.get('path', 'Script')),
                command=lambda: self.enhanced_execute_script(script_data),
                bg=self.theme.get_color('bg_secondary'),
                fg=self.theme.get_color('text'),
                activebackground=self.theme.get_color('bg_hover'),
                font=('Segoe UI', 9),
                relief=tk.FLAT,
                padx=8,
                pady=4
            )
            button.pack(side=tk.LEFT)
            
            # Add status indicator
            status_indicator = StatusIndicatorWidget(button_frame, self.theme)
            status_indicator.frame.pack(side=tk.RIGHT)
            
            # Add enhanced tooltip
            tooltip_text = self.generate_script_tooltip(script_data.get('path', ''))
            tooltip = EnhancedTooltip(button, tooltip_text, self.theme)
            
            # Bind right-click context menu
            button.bind("<Button-3>", lambda e: self.show_enhanced_context_menu(e, script_data))
            
            # Store button info for status updates
            script_id = script_data.get('id', script_data.get('path', ''))
            self.script_buttons[script_id] = {
                'button': button,
                'frame': button_frame,
                'status_indicator': status_indicator,
                'tooltip': tooltip,
                'script_data': script_data
            }
            
        except Exception as e:
            logger.error(f"Error adding enhanced script button: {e}")
    
    def show_enhanced_context_menu(self, event, item_data):
        """Show enhanced context menu with new options"""
        try:
            menu = tk.Menu(self.root, tearoff=0, bg=self.theme.get_color('bg_secondary'), fg=self.theme.get_color('text'))
            
            if item_data.get('type') == 'script' or 'path' in item_data:
                file_path = item_data.get('path', '')
                
                # Execution options
                menu.add_command(label="▶️ Execute", command=lambda: self.enhanced_execute_script(item_data))
                menu.add_separator()
                
                # Editor options
                editors_menu = tk.Menu(menu, tearoff=0, bg=self.theme.get_color('bg_secondary'), fg=self.theme.get_color('text'))
                for editor_type in self.file_manager.supported_editors:
                    editor_name = editor_type.value.title()
                    editors_menu.add_command(
                        label=f"📝 {editor_name}",
                        command=lambda et=editor_type: self.file_manager.open_in_editor(file_path, et)
                    )
                menu.add_cascade(label="📝 Edit with...", menu=editors_menu)
                
                # File operations
                menu.add_command(label="📁 Open Folder", command=lambda: self.file_manager.open_folder(os.path.dirname(file_path)))
                menu.add_command(label="💻 Open Terminal", command=lambda: self.file_manager.open_terminal(os.path.dirname(file_path)))
                menu.add_command(label="🏷️ Rename File", command=lambda: self.rename_script_file(item_data))
                menu.add_separator()
                
                # History and stats
                menu.add_command(label="📊 View History", command=lambda: self.show_script_history(file_path))
                menu.add_command(label="📈 Performance Stats", command=lambda: self.show_performance_stats(file_path))
                menu.add_separator()
                
                # Standard options
                menu.add_command(label="🎨 Edit Icon", command=lambda: self.edit_script_icon(item_data))
                menu.add_command(label="❌ Remove", command=lambda: self.remove_script(item_data))
            
            else:  # tray
                menu.add_command(label="📂 Open", command=lambda: self.toggle_tray(item_data))
                menu.add_command(label="🎨 Edit Icon", command=lambda: self.edit_tray_icon(item_data))
                menu.add_separator()
                menu.add_command(label="🏷️ Rename", command=lambda: self.rename_tray(item_data))
                menu.add_command(label="❌ Remove", command=lambda: self.remove_tray(item_data))
            
            menu.post(event.x_root, event.y_root)
            
        except Exception as e:
            logger.error(f"Error showing enhanced context menu: {e}")
    
    def rename_script_file(self, script_data):
        """Rename a script file"""
        try:
            old_path = script_data.get('path', '')
            if not old_path:
                return
            
            old_name = os.path.basename(old_path)
            new_name = simpledialog.askstring("Rename File", f"Enter new name for '{old_name}':", initialvalue=old_name)
            
            if new_name and new_name != old_name:
                try:
                    new_path = self.file_manager.rename_file(old_path, new_name)
                    
                    # Update script data
                    script_data['path'] = new_path
                    
                    # Update button text
                    script_id = script_data.get('id', old_path)
                    if script_id in self.script_buttons:
                        self.script_buttons[script_id]['button'].config(text=new_name)
                        # Update tooltip
                        tooltip_text = self.generate_script_tooltip(new_path)
                        self.script_buttons[script_id]['tooltip'].update_text(tooltip_text)
                    
                    # Save config
                    self.save_config()
                    
                    messagebox.showinfo("Success", f"File renamed to '{new_name}'")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to rename file: {e}")
        
        except Exception as e:
            logger.error(f"Error renaming script file: {e}")
    
    def show_script_history(self, script_path):
        """Show execution history for a specific script"""
        try:
            from toolbar_ui_components import ExecutionHistoryDialog
            dialog = ExecutionHistoryDialog(self.root, self.status_manager, self.theme)
        except Exception as e:
            logger.error(f"Error showing script history: {e}")
            messagebox.showerror("Error", f"Failed to show history: {e}")
    
    def show_performance_stats(self, script_path):
        """Show performance statistics for a script"""
        try:
            stats = self.status_manager.get_performance_stats(script_path)
            if not stats:
                messagebox.showinfo("Performance Stats", "No execution history available for this script.")
                return
            
            stats_text = f"""Performance Statistics for {os.path.basename(script_path)}

Total Executions: {stats['total_executions']}
Success Rate: {stats['success_rate']:.1f}%
Average Duration: {stats['avg_duration']:.2f} seconds
Fastest Execution: {stats['min_duration']:.2f} seconds
Slowest Execution: {stats['max_duration']:.2f} seconds
Last Execution: {stats['last_execution'].strftime('%Y-%m-%d %H:%M:%S')}"""
            
            messagebox.showinfo("Performance Statistics", stats_text)
            
        except Exception as e:
            logger.error(f"Error showing performance stats: {e}")
            messagebox.showerror("Error", f"Failed to show statistics: {e}")
    
    def show_settings_dialog(self):
        """Show the enhanced settings dialog"""
        try:
            from toolbar_ui_components import SettingsDialog
            dialog = SettingsDialog(self.root, self.settings_manager, self.theme)
            self.root.wait_window(dialog.dialog)
            
            if dialog.result:
                # Apply settings changes
                self.apply_settings_changes()
                
        except Exception as e:
            logger.error(f"Error showing settings dialog: {e}")
            messagebox.showerror("Error", f"Failed to show settings: {e}")
    
    def apply_settings_changes(self):
        """Apply settings changes to the application"""
        try:
            # Update transparency
            new_transparency = self.settings_manager.getint('appearance', 'transparency', 95)
            if new_transparency != self.transparency:
                self.transparency = new_transparency
                self.root.attributes('-alpha', self.transparency / 100)
            
            # Update stay on top
            stay_on_top = self.settings_manager.getboolean('behavior', 'stay_on_top', True)
            self.root.attributes('-topmost', stay_on_top)
            
            # Save legacy config to maintain compatibility
            self.save_config()
            
        except Exception as e:
            logger.error(f"Error applying settings changes: {e}")
    
    def enhanced_bind_events(self):
        """Bind enhanced keyboard shortcuts and events"""
        try:
            # Settings shortcut
            self.root.bind('<Control-comma>', lambda e: self.show_settings_dialog())
            
            # History shortcut
            self.root.bind('<Control-h>', lambda e: self.show_script_history(None))
            
            # Refresh shortcut
            self.root.bind('<F5>', lambda e: self.refresh_taskbar())
            
        except Exception as e:
            logger.error(f"Error binding enhanced events: {e}")
    
    def refresh_taskbar(self):
        """Refresh the taskbar display"""
        try:
            # Clear current buttons
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            self.script_buttons.clear()
            
            # Recreate buttons with enhanced features
            for script in self.scripts:
                self.enhanced_add_script_button(script)
            
            # Setup status callbacks
            self.setup_status_callbacks()
            
        except Exception as e:
            logger.error(f"Error refreshing taskbar: {e}")

def enhance_modern_taskbar(taskbar_instance):
    """Enhance an existing ModernTaskbar instance with new features"""
    # Add mixin methods to the instance
    for method_name in dir(EnhancedTaskbarMixin):
        if not method_name.startswith('_'):
            method = getattr(EnhancedTaskbarMixin, method_name)
            if callable(method):
                setattr(taskbar_instance, method_name, method.__get__(taskbar_instance, taskbar_instance.__class__))
    
    # Initialize enhanced services
    taskbar_instance.setup_enhanced_services()
    taskbar_instance.setup_status_callbacks()
    taskbar_instance.enhanced_bind_events()
    
    # Replace standard methods with enhanced versions
    taskbar_instance.execute_script = taskbar_instance.enhanced_execute_script
    taskbar_instance.add_script_button = taskbar_instance.enhanced_add_script_button
    
    return taskbar_instance
