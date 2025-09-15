"""
Enhanced UI components for the Modern Taskbar application
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
from datetime import datetime
from toolbar_services import ExecutionStatus, EditorType
import logging

logger = logging.getLogger(__name__)

class StatusIndicatorWidget:
    """Visual status indicator for script execution"""
    def __init__(self, parent, theme):
        self.parent = parent
        self.theme = theme
        self.current_status = ExecutionStatus.IDLE
        
        self.frame = tk.Frame(parent, bg=theme.get_color('bg'))
        self.status_canvas = tk.Canvas(
            self.frame, 
            width=12, 
            height=12, 
            bg=theme.get_color('bg'),
            highlightthickness=0
        )
        self.status_canvas.pack(side=tk.RIGHT, padx=2)
        
        self.update_status(ExecutionStatus.IDLE)
    
    def update_status(self, status):
        """Update the visual status indicator"""
        self.current_status = status
        self.status_canvas.delete("all")
        
        colors = {
            ExecutionStatus.IDLE: self.theme.get_color('text_secondary'),
            ExecutionStatus.RUNNING: self.theme.get_color('text_warning'),
            ExecutionStatus.SUCCESS: self.theme.get_color('text_success'),
            ExecutionStatus.ERROR: self.theme.get_color('text_error'),
            ExecutionStatus.CANCELLED: self.theme.get_color('text_secondary')
        }
        
        color = colors.get(status, self.theme.get_color('text_secondary'))
        
        if status == ExecutionStatus.RUNNING:
            # Animated spinning indicator for running status
            self._create_spinning_indicator(color)
        else:
            # Static circle for other statuses
            self.status_canvas.create_oval(2, 2, 10, 10, fill=color, outline=color)
    
    def _create_spinning_indicator(self, color):
        """Create animated spinning indicator"""
        def animate():
            angle = 0
            while self.current_status == ExecutionStatus.RUNNING:
                self.status_canvas.delete("all")
                # Create spinning arc
                self.status_canvas.create_arc(
                    2, 2, 10, 10,
                    start=angle,
                    extent=90,
                    outline=color,
                    width=2,
                    style='arc'
                )
                angle = (angle + 30) % 360
                time.sleep(0.1)
        
        threading.Thread(target=animate, daemon=True).start()

class ProgressManager:
    """Manages progress bars and feedback for long operations"""
    def __init__(self, parent, theme):
        self.parent = parent
        self.theme = theme
        self.active_operations = {}
    
    def start_operation(self, operation_id, title="Processing..."):
        """Start a progress operation"""
        if operation_id in self.active_operations:
            return
        
        progress_window = tk.Toplevel(self.parent)
        progress_window.title(title)
        progress_window.geometry("300x100")
        progress_window.configure(bg=self.theme.get_color('bg'))
        progress_window.attributes('-topmost', True)
        progress_window.resizable(False, False)
        
        # Center the window
        progress_window.transient(self.parent)
        progress_window.grab_set()
        
        label = tk.Label(
            progress_window,
            text=title,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        )
        label.pack(pady=10)
        
        progress_bar = ttk.Progressbar(
            progress_window,
            mode='indeterminate',
            length=250
        )
        progress_bar.pack(pady=10)
        progress_bar.start()
        
        self.active_operations[operation_id] = {
            'window': progress_window,
            'progress_bar': progress_bar,
            'label': label
        }
    
    def update_operation(self, operation_id, message):
        """Update operation message"""
        if operation_id in self.active_operations:
            self.active_operations[operation_id]['label'].config(text=message)
    
    def finish_operation(self, operation_id):
        """Finish and close operation"""
        if operation_id in self.active_operations:
            operation = self.active_operations[operation_id]
            operation['progress_bar'].stop()
            operation['window'].destroy()
            del self.active_operations[operation_id]

class SettingsDialog:
    """Comprehensive settings dialog"""
    def __init__(self, parent, settings_manager, theme):
        self.parent = parent
        self.settings_manager = settings_manager
        self.theme = theme
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Taskbar Settings")
        self.dialog.geometry("500x600")
        self.dialog.configure(bg=theme.get_color('bg'))
        self.dialog.attributes('-topmost', True)
        self.dialog.resizable(False, False)
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.center_on_parent()
        
        self.create_widgets()
        self.load_current_settings()
    
    def center_on_parent(self):
        """Center dialog on parent window"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Create the settings interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.dialog)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Appearance tab
        self.appearance_frame = tk.Frame(self.notebook, bg=self.theme.get_color('bg'))
        self.notebook.add(self.appearance_frame, text="Appearance")
        self.create_appearance_tab()
        
        # Behavior tab
        self.behavior_frame = tk.Frame(self.notebook, bg=self.theme.get_color('bg'))
        self.notebook.add(self.behavior_frame, text="Behavior")
        self.create_behavior_tab()
        
        # Execution tab
        self.execution_frame = tk.Frame(self.notebook, bg=self.theme.get_color('bg'))
        self.notebook.add(self.execution_frame, text="Execution")
        self.create_execution_tab()
        
        # Editors tab
        self.editors_frame = tk.Frame(self.notebook, bg=self.theme.get_color('bg'))
        self.notebook.add(self.editors_frame, text="Editors")
        self.create_editors_tab()
        
        # Buttons
        self.create_buttons()
    
    def create_appearance_tab(self):
        """Create appearance settings tab"""
        # Transparency
        tk.Label(
            self.appearance_frame,
            text="Transparency:",
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.transparency_var = tk.IntVar()
        self.transparency_scale = tk.Scale(
            self.appearance_frame,
            from_=10,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.transparency_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            highlightthickness=0,
            length=300
        )
        self.transparency_scale.pack(padx=10, pady=5)
        
        # Show tooltips
        self.show_tooltips_var = tk.BooleanVar()
        tk.Checkbutton(
            self.appearance_frame,
            text="Show tooltips",
            variable=self.show_tooltips_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            selectcolor=self.theme.get_color('bg_secondary'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=5)
        
        # Animation enabled
        self.animation_var = tk.BooleanVar()
        tk.Checkbutton(
            self.appearance_frame,
            text="Enable animations",
            variable=self.animation_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            selectcolor=self.theme.get_color('bg_secondary'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=5)
    
    def create_behavior_tab(self):
        """Create behavior settings tab"""
        # Auto start
        self.auto_start_var = tk.BooleanVar()
        tk.Checkbutton(
            self.behavior_frame,
            text="Start with Windows",
            variable=self.auto_start_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            selectcolor=self.theme.get_color('bg_secondary'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=10)
        
        # Stay on top
        self.stay_on_top_var = tk.BooleanVar()
        tk.Checkbutton(
            self.behavior_frame,
            text="Always stay on top",
            variable=self.stay_on_top_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            selectcolor=self.theme.get_color('bg_secondary'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=5)
        
        # Confirm exit
        self.confirm_exit_var = tk.BooleanVar()
        tk.Checkbutton(
            self.behavior_frame,
            text="Confirm before exit",
            variable=self.confirm_exit_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            selectcolor=self.theme.get_color('bg_secondary'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=5)
    
    def create_execution_tab(self):
        """Create execution settings tab"""
        # Show output
        self.show_output_var = tk.BooleanVar()
        tk.Checkbutton(
            self.execution_frame,
            text="Show execution output",
            variable=self.show_output_var,
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            selectcolor=self.theme.get_color('bg_secondary'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=10)
        
        # Timeout
        tk.Label(
            self.execution_frame,
            text="Execution timeout (seconds):",
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.timeout_var = tk.IntVar()
        timeout_frame = tk.Frame(self.execution_frame, bg=self.theme.get_color('bg'))
        timeout_frame.pack(anchor=tk.W, padx=10, pady=5)
        
        tk.Entry(
            timeout_frame,
            textvariable=self.timeout_var,
            width=10,
            bg=self.theme.get_color('input_bg'),
            fg=self.theme.get_color('text'),
            insertbackground=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        ).pack(side=tk.LEFT)
        
        # Max concurrent
        tk.Label(
            self.execution_frame,
            text="Maximum concurrent executions:",
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        self.max_concurrent_var = tk.IntVar()
        concurrent_frame = tk.Frame(self.execution_frame, bg=self.theme.get_color('bg'))
        concurrent_frame.pack(anchor=tk.W, padx=10, pady=5)
        
        tk.Entry(
            concurrent_frame,
            textvariable=self.max_concurrent_var,
            width=10,
            bg=self.theme.get_color('input_bg'),
            fg=self.theme.get_color('text'),
            insertbackground=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        ).pack(side=tk.LEFT)
    
    def create_editors_tab(self):
        """Create editors settings tab"""
        tk.Label(
            self.editors_frame,
            text="Default Editor:",
            bg=self.theme.get_color('bg'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 10)
        ).pack(anchor=tk.W, padx=10, pady=10)
        
        self.editor_var = tk.StringVar()
        editor_options = ['vscode', 'notepad++', 'sublime', 'atom', 'vim', 'nano', 'gedit']
        
        editor_combo = ttk.Combobox(
            self.editors_frame,
            textvariable=self.editor_var,
            values=editor_options,
            state='readonly',
            width=20
        )
        editor_combo.pack(anchor=tk.W, padx=10, pady=5)
    
    def create_buttons(self):
        """Create dialog buttons"""
        button_frame = tk.Frame(self.dialog, bg=self.theme.get_color('bg'))
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            bg=self.theme.get_color('bg_secondary'),
            fg=self.theme.get_color('text'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            padx=20
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            button_frame,
            text="Apply",
            command=self.apply_settings,
            bg=self.theme.get_color('selection_bg'),
            fg=self.theme.get_color('text'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            padx=20
        ).pack(side=tk.RIGHT, padx=5)
    
    def load_current_settings(self):
        """Load current settings into the dialog"""
        # Appearance
        self.transparency_var.set(self.settings_manager.getint('appearance', 'transparency', 95))
        self.show_tooltips_var.set(self.settings_manager.getboolean('appearance', 'show_tooltips', True))
        self.animation_var.set(self.settings_manager.getboolean('appearance', 'animation_enabled', True))
        
        # Behavior
        self.auto_start_var.set(self.settings_manager.getboolean('behavior', 'auto_start', False))
        self.stay_on_top_var.set(self.settings_manager.getboolean('behavior', 'stay_on_top', True))
        self.confirm_exit_var.set(self.settings_manager.getboolean('behavior', 'confirm_exit', True))
        
        # Execution
        self.show_output_var.set(self.settings_manager.getboolean('execution', 'show_output', True))
        self.timeout_var.set(self.settings_manager.getint('execution', 'timeout_seconds', 300))
        self.max_concurrent_var.set(self.settings_manager.getint('execution', 'max_concurrent', 5))
        
        # Editors
        self.editor_var.set(self.settings_manager.get('editors', 'default_editor', 'vscode'))
    
    def apply_settings(self):
        """Apply the settings"""
        try:
            # Appearance
            self.settings_manager.set('appearance', 'transparency', self.transparency_var.get())
            self.settings_manager.set('appearance', 'show_tooltips', self.show_tooltips_var.get())
            self.settings_manager.set('appearance', 'animation_enabled', self.animation_var.get())
            
            # Behavior
            self.settings_manager.set('behavior', 'auto_start', self.auto_start_var.get())
            self.settings_manager.set('behavior', 'stay_on_top', self.stay_on_top_var.get())
            self.settings_manager.set('behavior', 'confirm_exit', self.confirm_exit_var.get())
            
            # Execution
            self.settings_manager.set('execution', 'show_output', self.show_output_var.get())
            self.settings_manager.set('execution', 'timeout_seconds', self.timeout_var.get())
            self.settings_manager.set('execution', 'max_concurrent', self.max_concurrent_var.get())
            
            # Editors
            self.settings_manager.set('editors', 'default_editor', self.editor_var.get())
            
            self.settings_manager.save_settings()
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            messagebox.showerror("Error", f"Failed to apply settings: {e}")
    
    def cancel(self):
        """Cancel the dialog"""
        self.result = False
        self.dialog.destroy()

class ExecutionHistoryDialog:
    """Dialog to show execution history and statistics"""
    def __init__(self, parent, status_manager, theme):
        self.parent = parent
        self.status_manager = status_manager
        self.theme = theme
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Execution History")
        self.dialog.geometry("700x500")
        self.dialog.configure(bg=theme.get_color('bg'))
        self.dialog.attributes('-topmost', True)
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.center_on_parent()
        
        self.create_widgets()
        self.load_history()
    
    def center_on_parent(self):
        """Center dialog on parent window"""
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Create the history interface"""
        # Create treeview for history
        columns = ('Time', 'Script', 'Status', 'Duration')
        self.tree = ttk.Treeview(self.dialog, columns=columns, show='headings', height=15)
        
        # Configure columns
        self.tree.heading('Time', text='Time')
        self.tree.heading('Script', text='Script')
        self.tree.heading('Status', text='Status')
        self.tree.heading('Duration', text='Duration (s)')
        
        self.tree.column('Time', width=150)
        self.tree.column('Script', width=300)
        self.tree.column('Status', width=100)
        self.tree.column('Duration', width=100)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.dialog, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Close button
        tk.Button(
            self.dialog,
            text="Close",
            command=self.dialog.destroy,
            bg=self.theme.get_color('bg_secondary'),
            fg=self.theme.get_color('text'),
            activebackground=self.theme.get_color('bg_hover'),
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            padx=20
        ).pack(side=tk.BOTTOM, pady=10)
    
    def load_history(self):
        """Load execution history into the tree"""
        history = self.status_manager.get_execution_history(limit=100)
        
        for item in reversed(history):  # Show most recent first
            time_str = item['start_time'].strftime('%Y-%m-%d %H:%M:%S')
            script_name = item['script_path'].split('/')[-1] if '/' in item['script_path'] else item['script_path'].split('\\')[-1]
            status_str = item['status'].value.title()
            duration_str = f"{item.get('duration', 0):.2f}"
            
            # Color code by status
            tags = []
            if item['status'] == ExecutionStatus.SUCCESS:
                tags = ['success']
            elif item['status'] == ExecutionStatus.ERROR:
                tags = ['error']
            elif item['status'] == ExecutionStatus.RUNNING:
                tags = ['running']
            
            self.tree.insert('', 'end', values=(time_str, script_name, status_str, duration_str), tags=tags)
        
        # Configure tag colors
        self.tree.tag_configure('success', foreground='green')
        self.tree.tag_configure('error', foreground='red')
        self.tree.tag_configure('running', foreground='orange')

class EnhancedTooltip:
    """Enhanced tooltip with rich information"""
    def __init__(self, widget, text, theme, delay=500):
        self.widget = widget
        self.text = text
        self.theme = theme
        self.delay = delay
        self.tooltip_window = None
        self.after_id = None
        
        self.widget.bind('<Enter>', self.on_enter)
        self.widget.bind('<Leave>', self.on_leave)
        self.widget.bind('<Motion>', self.on_motion)
    
    def on_enter(self, event=None):
        """Handle mouse enter"""
        self.after_id = self.widget.after(self.delay, self.show_tooltip)
    
    def on_leave(self, event=None):
        """Handle mouse leave"""
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hide_tooltip()
    
    def on_motion(self, event=None):
        """Handle mouse motion"""
        if self.tooltip_window:
            self.update_position(event)
    
    def show_tooltip(self):
        """Show the tooltip"""
        if self.tooltip_window:
            return
        
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.configure(bg=self.theme.get_color('bg_tertiary'))
        
        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            bg=self.theme.get_color('bg_tertiary'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 9),
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=4
        )
        label.pack()
    
    def hide_tooltip(self):
        """Hide the tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    
    def update_position(self, event):
        """Update tooltip position"""
        if self.tooltip_window:
            x = event.x_root + 20
            y = event.y_root + 20
            self.tooltip_window.wm_geometry(f"+{x}+{y}")
    
    def update_text(self, new_text):
        """Update tooltip text"""
        self.text = new_text
