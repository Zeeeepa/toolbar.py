import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
import json
import os
import subprocess
import uuid
import sys
import logging
import webbrowser
import threading
from datetime import datetime
from pathlib import Path
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import optional modules
try:
    import win32gui
    import win32con
    import win32api
    import win32ui
    from win32com.shell import shell, shellcon
    WINDOWS_MODULES_AVAILABLE = True
except ImportError:
    WINDOWS_MODULES_AVAILABLE = False

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import tkinterdnd2 as tkdnd
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    logger.warning("tkinterdnd2 not available. Drag and drop will be disabled.")

class ModernVioletTheme:
    """Modern violet/purple theme inspired by VS Code dark"""
    def __init__(self):
        self.bg_primary = "#1e1e2f"
        self.bg_secondary = "#2a2a40"
        self.bg_tertiary = "#383852"
        self.bg_hover = "#4a4a66"
        self.bg_active = "#5a5a7a"
        self.text_primary = "#e0e0f0"
        self.text_secondary = "#b0b0d0"
        self.text_accent = "#bb86fc"
        self.text_success = "#4fc3f7"
        self.text_warning = "#ffb74d"
        self.text_error = "#f48fb1"
        self.border_color = "#4a4a66"
        self.selection_bg = "#6366f1"
        self.input_bg = "#2d2d47"
        self.input_border = "#5a5a7a"
        
        self.colors = {
            'bg': self.bg_primary,
            'bg_secondary': self.bg_secondary,
            'bg_tertiary': self.bg_tertiary,
            'bg_hover': self.bg_hover,
            'bg_active': self.bg_active,
            'text': self.text_primary,
            'text_secondary': self.text_secondary,
            'text_accent': self.text_accent,
            'text_success': self.text_success,
            'text_warning': self.text_warning,
            'text_error': self.text_error,
            'border': self.border_color,
            'selection_bg': self.selection_bg,
            'input_bg': self.input_bg,
            'input_border': self.input_border
        }
    
    def get_color(self, name):
        return self.colors.get(name, self.colors['bg'])

class WindowsIconExtractor:
    def __init__(self):
        self.icon_cache = {}
        self.custom_icons_dir = "custom_icons"
        if not os.path.exists(self.custom_icons_dir):
            os.makedirs(self.custom_icons_dir)
    
    def get_file_icon(self, file_path, size=32):
        try:
            if not WINDOWS_MODULES_AVAILABLE or not PIL_AVAILABLE:
                return self.create_fallback_icon(file_path, size)
            
            cache_key = f"{file_path}_{size}"
            if cache_key in self.icon_cache:
                return self.icon_cache[cache_key]
            
            if file_path.lower().endswith('.exe'):
                hicon = win32gui.ExtractIcon(0, file_path, 0)
                if hicon:
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, size, size)
                    hdc_mem = hdc.CreateCompatibleDC()
                    hdc_mem.SelectObject(hbmp)
                    
                    win32gui.DrawIconEx(hdc_mem.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, 0x0003)
                    
                    bmp_info = hbmp.GetInfo()
                    bmp_str = hbmp.GetBitmapBits(True)
                    img = Image.frombuffer('RGB', (bmp_info['bmWidth'], bmp_info['bmHeight']), bmp_str, 'raw', 'BGRX', 0, 1)
                    
                    win32gui.DestroyIcon(hicon)
                    hdc_mem.DeleteDC()
                    hdc.DeleteDC()
                    hbmp.DeleteObject()
                    
                    self.icon_cache[cache_key] = img
                    return img
            
            return self.create_fallback_icon(file_path, size)
                
        except Exception as e:
            logger.error(f"Error extracting icon for {file_path}: {e}")
            return self.create_fallback_icon(file_path, size)
    
    def create_fallback_icon(self, file_path, size=32):
        """Create fallback icon based on file type"""
        try:
            if not PIL_AVAILABLE:
                return None
            
            if os.path.isdir(file_path):
                # Folder icon
                img = Image.new('RGBA', (size, size), (255, 215, 0, 200))
                draw = ImageDraw.Draw(img)
                draw.rectangle([2, size//4, size-2, size-2], fill=(255, 215, 0, 255), outline=(255, 235, 59, 255))
                draw.rectangle([2, 2, size//2, size//4 + 4], fill=(255, 235, 59, 255))
                return img
            
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in ['.py']:
                # Python file
                return self.create_text_icon("PY", "#4fc3f7", size)
            elif file_ext in ['.js']:
                # JavaScript file
                return self.create_text_icon("JS", "#ffb74d", size)
            elif file_ext in ['.bat', '.cmd']:
                # Batch file
                return self.create_text_icon("BAT", "#f48fb1", size)
            elif file_ext in ['.ps1']:
                # PowerShell file
                return self.create_text_icon("PS", "#4fc3f7", size)
            elif file_ext in ['.exe']:
                # Executable
                return self.create_text_icon("EXE", "#bb86fc", size)
            elif file_ext in ['.txt', '.log']:
                # Text file
                return self.create_text_icon("TXT", "#e0e0f0", size)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                # Image file
                return self.create_text_icon("IMG", "#4fc3f7", size)
            else:
                # Generic file
                return self.create_text_icon("FILE", "#bb86fc", size)
                
        except Exception as e:
            logger.error(f"Error creating fallback icon: {e}")
            return None
    
    def create_text_icon(self, text, bg_color="#bb86fc", size=32):
        try:
            if not PIL_AVAILABLE:
                return None
            
            img = Image.new('RGBA', (size, size), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Try to use a font, fallback to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", size//4)
            except:
                font = ImageFont.load_default()
            
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (size - text_width) // 2
            y = (size - text_height) // 2
            draw.text((x, y), text, fill="#1e1e2f", font=font)
            return img
        except Exception as e:
            logger.error(f"Error creating text icon: {e}")
            return None
    
    def save_custom_icon(self, img, item_id):
        try:
            if img:
                icon_path = os.path.join(self.custom_icons_dir, f"{item_id}.png")
                img.save(icon_path, "PNG")
                return icon_path
        except Exception as e:
            logger.error(f"Error saving custom icon: {e}")
            return None
    
    def make_square_thumbnail(self, img, size):
        try:
            if not img:
                return None
            
            img.thumbnail((size, size), Image.LANCZOS)
            square = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            x = (size - img.width) // 2
            y = (size - img.height) // 2
            square.paste(img, (x, y))
            return square
        except Exception as e:
            logger.error(f"Error making square thumbnail: {e}")
            return img

icon_extractor = WindowsIconExtractor()

class IconEditorDialog:
    def __init__(self, parent, item_data):
        self.parent = parent
        self.item_data = item_data
        self.theme = ModernVioletTheme()
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Icon")
        self.dialog.geometry("400x500")
        self.dialog.configure(bg=self.theme.get_color('bg'))
        self.dialog.attributes('-topmost', True)
        
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.focus_force()
        self.center_on_parent(parent)
        
        self.create_widgets()
    
    def center_on_parent(self, parent):
        try:
            self.dialog.update_idletasks()
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
            dialog_width = self.dialog.winfo_width()
            dialog_height = self.dialog.winfo_height()
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2
            self.dialog.geometry(f"+{x}+{y}")
        except Exception as e:
            logger.error(f"Error centering dialog: {e}")
    
    def create_widgets(self):
        try:
            main_frame = tk.Frame(self.dialog, bg=self.theme.get_color('bg'))
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            tk.Label(main_frame, text="Edit Icon",
                    bg=self.theme.get_color('bg'),
                    fg=self.theme.get_color('text_accent'),
                    font=('Segoe UI', 14, 'bold')).pack(pady=(0, 15))
            
            # Icon display frame
            icon_frame = tk.Frame(main_frame, bg=self.theme.get_color('bg_tertiary'), relief='solid', bd=1)
            icon_frame.pack(pady=10, fill=tk.X)
            
            self.icon_display = tk.Label(icon_frame,
                                        text="No Icon",
                                        bg=self.theme.get_color('bg_tertiary'),
                                        fg=self.theme.get_color('text_secondary'),
                                        width=10, height=5, relief='flat')
            self.icon_display.pack(pady=10)
            
            self.load_current_icon()
            
            # Options frame
            options_frame = tk.Frame(main_frame, bg=self.theme.get_color('bg'))
            options_frame.pack(fill=tk.X, pady=10)
            
            tk.Button(options_frame, text="Use File Icon",
                      command=self.use_file_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text'),
                      font=('Segoe UI', 9),
                      relief='flat').pack(fill=tk.X, pady=2)
            
            tk.Button(options_frame, text="Create Text Icon",
                      command=self.create_text_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text'),
                      font=('Segoe UI', 9),
                      relief='flat').pack(fill=tk.X, pady=2)
            
            tk.Button(options_frame, text="Load Image Icon",
                      command=self.load_image_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text'),
                      font=('Segoe UI', 9),
                      relief='flat').pack(fill=tk.X, pady=2)
            
            tk.Button(options_frame, text="Remove Custom Icon",
                      command=self.remove_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text'),
                      font=('Segoe UI', 9),
                      relief='flat').pack(fill=tk.X, pady=2)
            
            # Button frame
            btn_frame = tk.Frame(main_frame, bg=self.theme.get_color('bg'))
            btn_frame.pack(fill=tk.X, pady=20)
            
            tk.Button(btn_frame, text="Save",
                     command=self.save_icon,
                     bg=self.theme.get_color('bg_tertiary'),
                     fg=self.theme.get_color('text'),
                     font=('Segoe UI', 9),
                     relief='flat').pack(side=tk.RIGHT, padx=5)
            
            tk.Button(btn_frame, text="Cancel",
                     command=self.cancel,
                     bg=self.theme.get_color('bg_tertiary'),
                     fg=self.theme.get_color('text'),
                     font=('Segoe UI', 9),
                     relief='flat').pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            logger.error(f"Error creating icon editor widgets: {e}")
    
    def load_current_icon(self):
        try:
            if self.item_data.get('custom_icon') and os.path.exists(self.item_data['custom_icon']):
                img = Image.open(self.item_data['custom_icon'])
                img = icon_extractor.make_square_thumbnail(img, 48)
                photo = ImageTk.PhotoImage(img)
                self.icon_display.config(image=photo, text="")
                self.icon_display.image = photo
            elif self.item_data.get('path') and os.path.exists(self.item_data['path']):
                img = icon_extractor.get_file_icon(self.item_data['path'], 48)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.icon_display.config(image=photo, text="")
                    self.icon_display.image = photo
        except Exception as e:
            logger.error(f"Error loading current icon: {e}")
    
    def use_file_icon(self):
        try:
            if self.item_data.get('path') and os.path.exists(self.item_data['path']):
                img = icon_extractor.get_file_icon(self.item_data['path'], 48)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.icon_display.config(image=photo, text="")
                    self.icon_display.image = photo
                    self.item_data['custom_icon'] = None
        except Exception as e:
            logger.error(f"Error using file icon: {e}")
    
    def create_text_icon(self):
        try:
            text = simpledialog.askstring("Text Icon", "Enter text for icon (max 4 chars):")
            if text:
                text = text[:4].upper()  # Limit to 4 characters
                color = colorchooser.askcolor(title="Choose background color", color="#bb86fc")
                bg_color = color[1] if color[1] else "#bb86fc"
                
                img = icon_extractor.create_text_icon(text, bg_color, 48)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.icon_display.config(image=photo, text="")
                    self.icon_display.image = photo
                    self.item_data['custom_icon'] = icon_extractor.save_custom_icon(img, self.item_data['id'])
        except Exception as e:
            logger.error(f"Error creating text icon: {e}")
    
    def load_image_icon(self):
        try:
            file_path = filedialog.askopenfilename(
                title="Select Icon Image",
                filetypes=[
                    ("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.ico"),
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg;*.jpeg"),
                    ("All files", "*.*")
                ]
            )
            if file_path and PIL_AVAILABLE:
                img = Image.open(file_path)
                img = icon_extractor.make_square_thumbnail(img, 48)
                photo = ImageTk.PhotoImage(img)
                self.icon_display.config(image=photo, text="")
                self.icon_display.image = photo
                self.item_data['custom_icon'] = icon_extractor.save_custom_icon(img, self.item_data['id'])
        except Exception as e:
            logger.error(f"Error loading image icon: {e}")
    
    def remove_icon(self):
        self.item_data['custom_icon'] = None
        self.icon_display.config(image="", text="No Icon")
        self.icon_display.image = None
    
    def save_icon(self):
        self.result = self.item_data
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()

class ExecutionLogger:
    def __init__(self):
        self.logs = []
        self.max_logs = 100
    
    def add_log(self, item_name, command, status, output="", error=""):
        log_entry = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'item_name': item_name,
            'command': command,
            'status': status,
            'output': output,
            'error': error
        }
        self.logs.insert(0, log_entry)  # Add to beginning
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[:self.max_logs]
    
    def get_logs(self):
        return self.logs
    
    def clear_logs(self):
        self.logs = []

class LogViewer:
    def __init__(self, parent, logger_instance):
        self.parent = parent
        self.logger = logger_instance
        self.theme = ModernVioletTheme()
        self.frame = None
        self.text_widget = None
        self.is_visible = False
    
    def create_viewer(self):
        if self.frame:
            return self.frame
        
        self.frame = tk.Frame(self.parent, bg=self.theme.get_color('bg_secondary'), width=300)
        
        # Header
        header_frame = tk.Frame(self.frame, bg=self.theme.get_color('bg_tertiary'))
        header_frame.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(header_frame, text="Execution Logs", 
                bg=self.theme.get_color('bg_tertiary'),
                fg=self.theme.get_color('text_accent'),
                font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        clear_btn = tk.Button(header_frame, text="Clear",
                             command=self.clear_logs,
                             bg=self.theme.get_color('bg_hover'),
                             fg=self.theme.get_color('text'),
                             font=('Segoe UI', 8),
                             relief='flat')
        clear_btn.pack(side=tk.RIGHT, padx=5)
        
        # Log display
        text_frame = tk.Frame(self.frame, bg=self.theme.get_color('bg_secondary'))
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        
        self.text_widget = tk.Text(text_frame, 
                                  bg=self.theme.get_color('input_bg'),
                                  fg=self.theme.get_color('text'),
                                  font=('Consolas', 8),
                                  wrap=tk.WORD,
                                  state=tk.DISABLED)
        
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.refresh_logs()
        return self.frame
    
    def refresh_logs(self):
        if not self.text_widget:
            return
        
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete('1.0', tk.END)
        
        logs = self.logger.get_logs()
        for log in logs[:50]:  # Show last 50 logs
            status_color = 'green' if log['status'] == 'success' else 'red'
            log_text = f"[{log['timestamp']}] {log['item_name']}\n"
            log_text += f"Command: {log['command']}\n"
            log_text += f"Status: {log['status']}\n"
            if log['output']:
                log_text += f"Output: {log['output'][:100]}...\n" if len(log['output']) > 100 else f"Output: {log['output']}\n"
            if log['error']:
                log_text += f"Error: {log['error'][:100]}...\n" if len(log['error']) > 100 else f"Error: {log['error']}\n"
            log_text += "-" * 50 + "\n\n"
            
            self.text_widget.insert(tk.END, log_text)
        
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.see(tk.END)
    
    def clear_logs(self):
        self.logger.clear_logs()
        self.refresh_logs()
    
    def toggle_visibility(self):
        if not self.frame:
            return
        
        if self.is_visible:
            self.frame.pack_forget()
        else:
            self.frame.pack(side=tk.LEFT, fill=tk.Y)
            self.refresh_logs()
        
        self.is_visible = not self.is_visible

class TaskbarButton:
    def __init__(self, parent, taskbar_ref, text, icon_image=None, command=None, item_data=None):
        self.parent = parent
        self.taskbar_ref = taskbar_ref  # Reference to main taskbar
        self.text = text
        self.icon_image = icon_image
        self.command = command
        self.item_data = item_data
        self.theme = ModernVioletTheme()
        
        self.frame = tk.Frame(parent, bg=self.theme.get_color('bg_tertiary'), relief='raised', bd=1)
        self.frame.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.button = tk.Button(
            self.frame,
            text=text if not icon_image else "",
            image=icon_image,
            compound=tk.LEFT if icon_image else tk.NONE,
            bg=self.theme.get_color('bg_tertiary'),
            fg=self.theme.get_color('text'),
            font=('Segoe UI', 9),
            relief='flat',
            bd=0,
            cursor='hand2',
            activebackground=self.theme.get_color('bg_hover'),
            activeforeground=self.theme.get_color('text'),
            command=self.on_click
        )
        
        self.button.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Bind events
        self.button.bind("<Button-3>", self.on_right_click)
        self.button.bind("<Enter>", self.on_enter)
        self.button.bind("<Leave>", self.on_leave)
        
        if icon_image:
            self.button.image = icon_image
    
    def on_click(self):
        """Handle button click"""
        if self.command:
            self.command()
    
    def on_right_click(self, event):
        """Handle right-click"""
        if self.item_data and self.taskbar_ref:
            self.taskbar_ref.show_context_menu(event, self.item_data)
    
    def on_enter(self, event):
        """Handle mouse enter"""
        self.button.config(bg=self.theme.get_color('bg_hover'))
    
    def on_leave(self, event):
        """Handle mouse leave"""
        self.button.config(bg=self.theme.get_color('bg_tertiary'))

class ModernTaskbar:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern Taskbar")
        self.theme = ModernVioletTheme()
        
        self.config_file = "taskbar_config.json"
        self.items = []
        self.transparency = 95
        self.execution_logger = ExecutionLogger()
        self.log_viewer = None
        
        self.load_config()
        self.setup_window()
        self.create_taskbar()
        self.position_taskbar()
        self.bind_events()
    
    def setup_window(self):
        """Setup main window"""
        try:
            self.root.overrideredirect(True)
            self.root.attributes('-topmost', True)
            self.root.configure(bg=self.theme.get_color('bg'))
            self.root.attributes('-alpha', self.transparency / 100)
        except Exception as e:
            logger.error(f"Error setting up window: {e}")
    
    def position_taskbar(self):
        """Position taskbar at bottom of screen"""
        try:
            if WINDOWS_MODULES_AVAILABLE:
                try:
                    hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
                    if hwnd:
                        rect = win32gui.GetWindowRect(hwnd)
                        screen_width = win32api.GetSystemMetrics(0)
                        screen_height = win32api.GetSystemMetrics(1)
                        taskbar_height = rect[3] - rect[1]
                        self.root.geometry(f"{screen_width}x45+0+{screen_height - taskbar_height - 45}")
                        return
                except:
                    pass
            
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x45+0+{screen_height - 90}")
        except Exception as e:
            logger.error(f"Error positioning taskbar: {e}")
    
    def create_taskbar(self):
        """Create the main taskbar interface"""
        try:
            self.main_frame = tk.Frame(self.root, bg=self.theme.get_color('bg'))
            self.main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Create log viewer
            self.log_viewer = LogViewer(self.main_frame, self.execution_logger)
            log_frame = self.log_viewer.create_viewer()
            
            # Log toggle button
            self.log_toggle_btn = tk.Button(
                self.main_frame,
                text="📋",
                command=self.toggle_log_viewer,
                bg=self.theme.get_color('bg_tertiary'),
                fg=self.theme.get_color('text'),
                font=('Segoe UI', 12),
                relief='flat',
                width=3
            )
            self.log_toggle_btn.pack(side=tk.LEFT, padx=2, pady=2)
            
            # Center container for items
            self.center_container = tk.Frame(self.main_frame, bg=self.theme.get_color('bg'))
            self.center_container.pack(expand=True, fill=tk.BOTH)
            
            self.canvas = tk.Canvas(self.center_container, bg=self.theme.get_color('bg'), highlightthickness=0)
            self.scrollbar = tk.Scrollbar(self.center_container, orient="horizontal", command=self.canvas.xview)
            self.scrollable_frame = tk.Frame(self.canvas, bg=self.theme.get_color('bg'))
            
            self.scrollable_frame.bind(
                "<Configure>",
                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            )
            
            self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
            self.canvas.configure(xscrollcommand=self.scrollbar.set)
            
            self.canvas.pack(side="top", fill="both", expand=True)
            self.scrollbar.pack(side="bottom", fill="x")
            
            # Setup drag and drop if available
            self.setup_drag_drop()
            
            # Load existing items
            for item in self.items:
                self.add_item_button(item)
                
        except Exception as e:
            logger.error(f"Error creating taskbar: {e}")
    
    def setup_drag_drop(self):
        """Setup drag and drop functionality"""
        if not DND_AVAILABLE:
            logger.info("Drag and drop not available - tkinterdnd2 not installed")
            return
            
        try:
            # Make canvas a drop target
            self.canvas.drop_target_register(tkdnd.DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self.on_drop)
            self.canvas.dnd_bind('<<DragEnter>>', self.on_drag_enter)
            self.canvas.dnd_bind('<<DragLeave>>', self.on_drag_leave)
            logger.info("Drag and drop enabled successfully")
        except Exception as e:
            logger.error(f"Error setting up drag and drop: {e}")
            logger.info("Drag and drop will not be available")
    
    def on_drop(self, event):
        """Handle dropped files"""
        try:
            files = self.root.tk.splitlist(event.data)
            for file_path in files:
                self.add_item_from_path(file_path)
        except Exception as e:
            logger.error(f"Error handling drop: {e}")
    
    def on_drag_enter(self, event):
        """Handle drag enter"""
        try:
            self.canvas.config(bg=self.theme.get_color('bg_hover'))
        except Exception as e:
            pass
    
    def on_drag_leave(self, event):
        """Handle drag leave"""
        try:
            self.canvas.config(bg=self.theme.get_color('bg'))
        except Exception as e:
            pass
    
    def add_item_from_path(self, file_path):
        """Add item from file path"""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return
            
            item_name = os.path.basename(file_path)
            is_executable = file_path.lower().endswith(('.exe', '.bat', '.py', '.ps1', '.js', '.cmd'))
            is_folder = os.path.isdir(file_path)
            
            item_type = 'folder' if is_folder else 'executable' if is_executable else 'file'
            
            item = {
                'id': str(uuid.uuid4()),
                'name': item_name,
                'path': file_path,
                'type': item_type,
                'custom_icon': None,
                'description': f"Added from: {file_path}",
                'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'modified': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.items.append(item)
            self.add_item_button(item)
            self.save_config()
            logger.info(f"Successfully added item: {item_name}")
        except Exception as e:
            logger.error(f"Error adding item from path: {e}")
    
    def add_item_button(self, item_data):
        """Add item button to taskbar"""
        try:
            icon_image = self.get_item_icon(item_data)
            
            button = TaskbarButton(
                self.scrollable_frame,
                self,  # Pass reference to taskbar
                item_data['name'],
                icon_image=icon_image,
                command=lambda: self.execute_item(item_data),
                item_data=item_data
            )
            
            if icon_image:
                button.button.image = icon_image
                
        except Exception as e:
            logger.error(f"Error adding item button: {e}")
    
    def get_item_icon(self, item_data):
        """Get icon for item"""
        try:
            # Try custom icon first
            if item_data.get('custom_icon') and os.path.exists(item_data['custom_icon']):
                if PIL_AVAILABLE:
                    img = Image.open(item_data['custom_icon'])
                    img = icon_extractor.make_square_thumbnail(img, 24)
                    return ImageTk.PhotoImage(img)
            
            # Try file icon
            if item_data.get('path') and os.path.exists(item_data['path']):
                win_icon = icon_extractor.get_file_icon(item_data['path'], 24)
                if win_icon and PIL_AVAILABLE:
                    return ImageTk.PhotoImage(win_icon)
            
            return None
        except Exception as e:
            logger.error(f"Error getting item icon: {e}")
            return None
    
    def execute_item(self, item_data):
        """Execute item"""
        def run_execution():
            try:
                file_path = item_data.get('path', '')
                item_type = item_data.get('type', 'file')
                item_name = item_data.get('name', 'Unknown')
                
                if not file_path or not os.path.exists(file_path):
                    self.execution_logger.add_log(item_name, file_path, 'error', error='File not found')
                    return
                
                if item_type == 'folder':
                    # Open folder
                    if os.name == 'nt':
                        command = f'explorer "{file_path}"'
                        result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    else:
                        command = f'xdg-open "{file_path}"'
                        result = subprocess.run([command], shell=True, capture_output=True, text=True)
                    
                    self.execution_logger.add_log(item_name, command, 'success', 'Opened folder')
                
                elif item_type == 'executable':
                    # Execute file
                    if file_path.endswith('.py'):
                        command = f'python "{file_path}"'
                        result = subprocess.run(['python', file_path], capture_output=True, text=True, timeout=30)
                    elif file_path.endswith(('.bat', '.cmd')):
                        command = f'"{file_path}"'
                        result = subprocess.run([file_path], shell=True, capture_output=True, text=True, timeout=30)
                    elif file_path.endswith('.ps1'):
                        command = f'powershell -ExecutionPolicy Bypass "{file_path}"'
                        result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', file_path], capture_output=True, text=True, timeout=30)
                    elif file_path.endswith('.js'):
                        command = f'node "{file_path}"'
                        result = subprocess.run(['node', file_path], capture_output=True, text=True, timeout=30)
                    elif file_path.endswith('.exe'):
                        command = f'"{file_path}"'
                        result = subprocess.Popen([file_path])
                        self.execution_logger.add_log(item_name, command, 'success', 'Executable started')
                        return
                    else:
                        command = f'"{file_path}"'
                        result = subprocess.run([file_path], shell=True, capture_output=True, text=True, timeout=30)
                    
                    status = 'success' if result.returncode == 0 else 'error'
                    self.execution_logger.add_log(item_name, command, status, result.stdout, result.stderr)
                
                else:
                    # Open file with default application
                    if os.name == 'nt':
                        command = f'start "" "{file_path}"'
                        subprocess.run(['start', '', file_path], shell=True)
                    else:
                        command = f'xdg-open "{file_path}"'
                        subprocess.run(['xdg-open', file_path])
                    
                    self.execution_logger.add_log(item_name, command, 'success', 'Opened with default application')
                
                # Refresh log viewer if visible
                if self.log_viewer and self.log_viewer.is_visible:
                    self.root.after(100, self.log_viewer.refresh_logs)
                    
            except subprocess.TimeoutExpired:
                self.execution_logger.add_log(item_name, command, 'error', error='Execution timeout')
            except Exception as e:
                self.execution_logger.add_log(item_name, file_path, 'error', error=str(e))
                logger.error(f"Error executing item: {e}")
        
        # Run execution in thread to avoid blocking UI
        thread = threading.Thread(target=run_execution, daemon=True)
        thread.start()
    
    def show_context_menu(self, event, item_data):
        """Show context menu for item"""
        try:
            menu = tk.Menu(self.root, tearoff=0, 
                          bg=self.theme.get_color('bg_tertiary'),
                          fg=self.theme.get_color('text'))
            
            # Execute/Open option
            if item_data['type'] == 'folder':
                menu.add_command(label="Open Folder", command=lambda: self.execute_item(item_data))
            elif item_data['type'] == 'executable':
                menu.add_command(label="Execute", command=lambda: self.execute_item(item_data))
            else:
                menu.add_command(label="Open", command=lambda: self.execute_item(item_data))
            
            menu.add_separator()
            
            # Edit in editor (for code files)
            if item_data.get('path', '').lower().endswith(('.py', '.js', '.bat', '.ps1', '.txt', '.json', '.xml', '.html', '.css')):
                menu.add_command(label="Edit in VS Code", command=lambda: self.edit_in_vscode(item_data['path']))
                menu.add_command(label="Edit in Notepad", command=lambda: self.edit_in_notepad(item_data['path']))
            
            # File operations
            menu.add_command(label="Open Folder Location", command=lambda: self.open_folder_location(item_data['path']))
            menu.add_command(label="Copy Path", command=lambda: self.copy_path_to_clipboard(item_data['path']))
            
            menu.add_separator()
            
            # Icon and properties
            menu.add_command(label="Change Icon", command=lambda: self.edit_item_icon(item_data))
            menu.add_command(label="Properties", command=lambda: self.show_item_properties(item_data))
            
            menu.add_separator()
            
            # Remove
            menu.add_command(label="Remove", command=lambda: self.remove_item(item_data))
            
            menu.post(event.x_root, event.y_root)
            
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
    
    def edit_in_vscode(self, file_path):
        """Edit file in VS Code"""
        try:
            subprocess.Popen(['code', file_path])
            self.execution_logger.add_log(os.path.basename(file_path), f'code "{file_path}"', 'success', 'Opened in VS Code')
        except FileNotFoundError:
            messagebox.showerror("Error", "VS Code not found. Please make sure VS Code is installed and 'code' command is available in PATH.")
        except Exception as e:
            logger.error(f"Error opening in VS Code: {e}")
    
    def edit_in_notepad(self, file_path):
        """Edit file in Notepad"""
        try:
            subprocess.Popen(['notepad.exe', file_path])
            self.execution_logger.add_log(os.path.basename(file_path), f'notepad "{file_path}"', 'success', 'Opened in Notepad')
        except Exception as e:
            logger.error(f"Error opening in Notepad: {e}")
    
    def open_folder_location(self, file_path):
        """Open folder location"""
        try:
            folder_path = os.path.dirname(file_path)
            if os.name == 'nt':
                subprocess.run(['explorer', '/select,', file_path])
            else:
                subprocess.run(['xdg-open', folder_path])
            self.execution_logger.add_log('System', f'Open location "{file_path}"', 'success', 'Opened folder location')
        except Exception as e:
            logger.error(f"Error opening folder location: {e}")
    
    def copy_path_to_clipboard(self, file_path):
        """Copy path to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(file_path)
            self.execution_logger.add_log('System', f'Copy path "{file_path}"', 'success', 'Path copied to clipboard')
        except Exception as e:
            logger.error(f"Error copying path to clipboard: {e}")
    
    def edit_item_icon(self, item_data):
        """Edit item icon"""
        try:
            dialog = IconEditorDialog(self.root, item_data)
            self.root.wait_window(dialog.dialog)
            if dialog.result:
                # Update the item data
                for i, item in enumerate(self.items):
                    if item['id'] == item_data['id']:
                        self.items[i] = dialog.result
                        break
                self.save_config()
                self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error editing item icon: {e}")
    
    def show_item_properties(self, item_data):
        """Show item properties"""
        try:
            props_window = tk.Toplevel(self.root)
            props_window.title("Item Properties")
            props_window.geometry("400x300")
            props_window.configure(bg=self.theme.get_color('bg'))
            props_window.attributes('-topmost', True)
            
            frame = tk.Frame(props_window, bg=self.theme.get_color('bg'))
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Name field
            name_frame = tk.Frame(frame, bg=self.theme.get_color('bg'))
            name_frame.pack(fill=tk.X, pady=5)
            tk.Label(name_frame, text="Name:", bg=self.theme.get_color('bg'), fg=self.theme.get_color('text')).pack(side=tk.LEFT)
            name_var = tk.StringVar(value=item_data.get('name', ''))
            name_entry = tk.Entry(name_frame, textvariable=name_var, bg=self.theme.get_color('input_bg'), fg=self.theme.get_color('text'))
            name_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
            
            # Path info
            tk.Label(frame, text=f"Path: {item_data.get('path', 'N/A')}", 
                    bg=self.theme.get_color('bg'), fg=self.theme.get_color('text_secondary'),
                    wraplength=350, justify=tk.LEFT).pack(fill=tk.X, pady=5)
            
            tk.Label(frame, text=f"Type: {item_data.get('type', 'Unknown')}", 
                    bg=self.theme.get_color('bg'), fg=self.theme.get_color('text_secondary')).pack(fill=tk.X, pady=5)
            
            tk.Label(frame, text=f"Created: {item_data.get('created', 'Unknown')}", 
                    bg=self.theme.get_color('bg'), fg=self.theme.get_color('text_secondary')).pack(fill=tk.X, pady=5)
            
            def save_properties():
                new_name = name_var.get().strip()
                if new_name:
                    item_data['name'] = new_name
                    item_data['modified'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_config()
                    self.refresh_toolbar()
                props_window.destroy()
            
            tk.Button(frame, text="Save", command=save_properties,
                     bg=self.theme.get_color('bg_tertiary'), fg=self.theme.get_color('text')).pack(pady=20)
            
        except Exception as e:
            logger.error(f"Error showing item properties: {e}")
    
    def remove_item(self, item_data):
        """Remove item"""
        try:
            if messagebox.askyesno("Confirm Remove", f"Remove '{item_data['name']}' from taskbar?"):
                self.items = [item for item in self.items if item['id'] != item_data['id']]
                self.save_config()
                self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error removing item: {e}")
    
    def refresh_toolbar(self):
        """Refresh taskbar"""
        try:
            # Clear existing buttons
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            # Add all items back
            for item in self.items:
                self.add_item_button(item)
                
        except Exception as e:
            logger.error(f"Error refreshing taskbar: {e}")
    
    def toggle_log_viewer(self):
        """Toggle log viewer visibility"""
        if self.log_viewer:
            self.log_viewer.toggle_visibility()
    
    def bind_events(self):
        """Bind event handlers"""
        try:
            self.root.bind("<Button-3>", self.show_main_context_menu)
            # Bind mouse wheel to horizontal scrolling
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        except Exception as e:
            logger.error(f"Error binding events: {e}")
    
    def on_mousewheel(self, event):
        """Handle mouse wheel for horizontal scrolling"""
        try:
            self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        except Exception as e:
            logger.error(f"Error handling mouse wheel: {e}")
    
    def show_main_context_menu(self, event):
        """Show main context menu"""
        try:
            menu = tk.Menu(self.root, tearoff=0,
                          bg=self.theme.get_color('bg_tertiary'),
                          fg=self.theme.get_color('text'))
            menu.add_command(label="Add File", command=self.add_file)
            menu.add_command(label="Add Folder", command=self.add_folder)
            menu.add_separator()
            menu.add_command(label="Clear Logs", command=lambda: self.execution_logger.clear_logs())
            menu.add_command(label="Settings", command=self.show_settings)
            menu.add_separator()
            menu.add_command(label="Exit", command=self.root.quit)
            menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
    
    def add_file(self):
        """Add new file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Select File",
                filetypes=[
                    ("All files", "*.*"),
                    ("Python files", "*.py"),
                    ("Batch files", "*.bat"),
                    ("PowerShell files", "*.ps1"),
                    ("JavaScript files", "*.js"),
                    ("Executable files", "*.exe"),
                    ("Text files", "*.txt"),
                ]
            )
            
            if file_path:
                self.add_item_from_path(file_path)
                
        except Exception as e:
            logger.error(f"Error adding file: {e}")
    
    def add_folder(self):
        """Add new folder"""
        try:
            folder_path = filedialog.askdirectory()
            if folder_path:
                self.add_item_from_path(folder_path)
        except Exception as e:
            logger.error(f"Error adding folder: {e}")
    
    def show_settings(self):
        """Show settings dialog"""
        try:
            settings_window = tk.Toplevel(self.root)
            settings_window.title("Settings")
            settings_window.geometry("400x300")
            settings_window.configure(bg=self.theme.get_color('bg'))
            settings_window.attributes('-topmost', True)
            
            frame = tk.Frame(settings_window, bg=self.theme.get_color('bg'))
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            tk.Label(frame, text="Taskbar Settings",
                    bg=self.theme.get_color('bg'),
                    fg=self.theme.get_color('text_accent'),
                    font=('Segoe UI', 14, 'bold')).pack(pady=10)
            
            # Transparency setting
            trans_frame = tk.Frame(frame, bg=self.theme.get_color('bg'))
            trans_frame.pack(fill=tk.X, pady=10)
            
            tk.Label(trans_frame, text="Transparency:",
                    bg=self.theme.get_color('bg'),
                    fg=self.theme.get_color('text')).pack(side=tk.LEFT)
            
            trans_var = tk.IntVar(value=self.transparency)
            trans_scale = tk.Scale(trans_frame, from_=50, to=100, orient=tk.HORIZONTAL,
                                 variable=trans_var,
                                 bg=self.theme.get_color('bg_tertiary'),
                                 fg=self.theme.get_color('text'),
                                 activebackground=self.theme.get_color('bg_hover'),
                                 troughcolor=self.theme.get_color('bg_secondary'),
                                 highlightthickness=0)
            trans_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            
            # Stats
            info_text = f"Total Items: {len(self.items)}\nExecution Logs: {len(self.execution_logger.get_logs())}"
            tk.Label(frame, text=info_text,
                    bg=self.theme.get_color('bg'),
                    fg=self.theme.get_color('text_secondary'),
                    font=('Segoe UI', 10), justify=tk.LEFT).pack(pady=20)
            
            def save_settings():
                self.transparency = trans_var.get()
                self.root.attributes('-alpha', self.transparency / 100)
                self.save_config()
                settings_window.destroy()
            
            tk.Button(frame, text="Save", command=save_settings,
                     bg=self.theme.get_color('bg_tertiary'),
                     fg=self.theme.get_color('text')).pack(pady=20)
            
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
    
    def load_config(self):
        """Load configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.items = config.get('items', [])
                    self.transparency = config.get('transparency', 95)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration"""
        try:
            config = {
                'items': self.items,
                'transparency': self.transparency
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

def main():
    try:
        root = tk.Tk()
        app = ModernTaskbar(root)
        
        def on_closing():
            try:
                app.save_config()
                root.quit()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
                root.quit()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
