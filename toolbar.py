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

# Import our new modules
from execution_manager import ExecutionManager, ExecutionStatus, ExecutionTask
from file_manager import FileManager
from settings_manager import SettingsManager

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
    from PIL import Image, ImageTk, ImageDraw
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
                return None
            
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
            
            elif os.path.isdir(file_path):
                img = Image.new('RGBA', (size, size), (255, 215, 0, 255))
                draw = ImageDraw.Draw(img)
                draw.rectangle([2, 8, size-2, size-2], fill=(255, 215, 0, 255))
                draw.rectangle([2, 4, size-2, 10], fill=(255, 235, 59, 255))
                return img
            
            else:
                img = Image.new('RGBA', (size, size), (187, 134, 252, 255))
                draw = ImageDraw.Draw(img)
                draw.rectangle([2, 2, size-2, size-2], fill=(187, 134, 252, 255))
                draw.rectangle([2, 2, size-2, 8], fill=(206, 147, 216, 255))
                return img
                
        except Exception as e:
            logger.error(f"Error extracting icon for {file_path}: {e}")
            return None
    
    def create_custom_icon(self, text, bg_color="#bb86fc", text_color="#1e1e2f", size=32):
        try:
            if not PIL_AVAILABLE:
                return None
            
            img = Image.new('RGBA', (size, size), bg_color)
            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (size - text_width) // 2
            y = (size - text_height) // 2
            draw.text((x, y), text, fill=text_color)
            return img
        except Exception as e:
            logger.error(f"Error creating custom icon: {e}")
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
            
            icon_frame = tk.Frame(main_frame, bg=self.theme.get_color('bg_tertiary'), relief='solid', bd=1)
            icon_frame.pack(pady=10, fill=tk.X)
            
            self.icon_display = tk.Label(icon_frame,
                                        text="No Icon",
                                        bg=self.theme.get_color('bg_tertiary'),
                                        fg=self.theme.get_color('text_secondary'),
                                        width=10, height=5, relief='flat')
            self.icon_display.pack(pady=10)
            
            self.load_current_icon()
            
            options_frame = tk.Frame(main_frame, bg=self.theme.get_color('bg'))
            options_frame.pack(fill=tk.X, pady=10)
            
            tk.Button(options_frame, text="Use File Icon",
                      command=self.use_file_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text')).pack(fill=tk.X, pady=2)
            
            tk.Button(options_frame, text="Create Text Icon",
                      command=self.create_text_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text')).pack(fill=tk.X, pady=2)
            
            tk.Button(options_frame, text="Load Image Icon",
                      command=self.load_image_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text')).pack(fill=tk.X, pady=2)
            
            tk.Button(options_frame, text="Remove Custom Icon",
                      command=self.remove_icon,
                      bg=self.theme.get_color('bg_tertiary'),
                      fg=self.theme.get_color('text')).pack(fill=tk.X, pady=2)
            
            btn_frame = tk.Frame(main_frame, bg=self.theme.get_color('bg'))
            btn_frame.pack(fill=tk.X, pady=20)
            
            tk.Button(btn_frame, text="Save",
                     command=self.save_icon,
                     bg=self.theme.get_color('bg_tertiary'),
                     fg=self.theme.get_color('text')).pack(side=tk.RIGHT, padx=5)
            
            tk.Button(btn_frame, text="Cancel",
                     command=self.cancel,
                     bg=self.theme.get_color('bg_tertiary'),
                     fg=self.theme.get_color('text')).pack(side=tk.RIGHT, padx=5)
            
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
            text = simpledialog.askstring("Text Icon", "Enter text for icon:")
            if text:
                img = icon_extractor.create_custom_icon(text, "#bb86fc", "#1e1e2f", 48)
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
    
    def save_icon(self):
        self.result = self.item_data
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()

class DesktopTray:
    def __init__(self, parent, tray_data, toolbar_instance=None):
        self.parent = parent
        self.tray_data = tray_data
        self.toolbar_instance = toolbar_instance
        self.theme = ModernVioletTheme()
        self.items = []
        self.selected_item = None
        self.drag_data = {"x": 0, "y": 0, "item": None}
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Desktop: {tray_data['name']}")
        self.window.configure(bg=self.theme.get_color('bg'))
        self.window.attributes('-topmost', True)
        
        geometry = tray_data.get('geometry', "1000x700+100+100")
        self.window.geometry(geometry)
        
        self.canvas = tk.Canvas(
            self.window,
            bg=self.theme.get_color('bg_secondary'),
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.grid_size = 100
        self.grid_items = {}
        
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<Configure>", self.save_geometry)
        
        # Setup drag and drop
        if DND_AVAILABLE:
            try:
                self.canvas.drop_target_register(tkdnd.DND_FILES)
                self.canvas.dnd_bind('<<Drop>>', self.on_drop)
                self.canvas.dnd_bind('<<DragEnter>>', self.on_drag_enter)
                self.canvas.dnd_bind('<<DragLeave>>', self.on_drag_leave)
                logger.info("Drag and drop enabled for tray")
            except Exception as e:
                logger.error(f"Error setting up drag and drop: {e}")
        
        self.load_items()
        self.create_desktop_pattern()
        
        self.window.bind("<Configure>", self.save_geometry)
    
    def setup_drag_drop(self):
        """Setup drag and drop functionality"""
        try:
            self.canvas.drop_target_register(tkdnd.DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self.on_drop)
            self.canvas.dnd_bind('<<DragEnter>>', self.on_drag_enter)
            self.canvas.dnd_bind('<<DragLeave>>', self.on_drag_leave)
        except Exception as e:
            logger.error(f"Error setting up drag and drop: {e}")
    
    def on_drop(self, event):
        """Handle dropped files"""
        try:
            logger.info(f"Drop event received: {event.data}")
            files = self.tk.splitlist(event.data)
            logger.info(f"Files dropped: {files}")
            for file_path in files:
                logger.info(f"Processing file: {file_path}")
                self.add_item_from_path(file_path)
        except Exception as e:
            logger.error(f"Error handling drop: {e}")
    
    def on_drag_enter(self, event):
        """Handle drag enter"""
        self.canvas.config(bg=self.theme.get_color('bg_hover'))
    
    def on_drag_leave(self, event):
        """Handle drag leave"""
        self.canvas.config(bg=self.theme.get_color('bg_secondary'))
    
    def add_item_from_path(self, file_path):
        """Add item from file path"""
        try:
            logger.info(f"Adding item from path: {file_path}")
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return
            
            item_name = os.path.basename(file_path)
            is_executable = file_path.lower().endswith(('.exe', '.bat', '.py', '.ps1', '.js'))
            is_folder = os.path.isdir(file_path)
            
            item = {
                'id': str(uuid.uuid4()),
                'name': item_name,
                'path': file_path,
                'type': 'executable' if is_executable else 'folder' if is_folder else 'file',
                'custom_icon': None,
                'description': f"Added from: {file_path}",
                'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'modified': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'x': 50 + len(self.items) * 100,
                'y': 50 + len(self.items) * 100
            }
            
            self.add_item(item)
            self.save_tray_data()
            logger.info(f"Successfully added item: {item_name}")
        except Exception as e:
            logger.error(f"Error adding item from path: {e}")
    
    def create_desktop_pattern(self):
        """Create desktop-like background pattern"""
        try:
            width = self.window.winfo_width()
            height = self.window.winfo_height()
            
            for x in range(0, width, self.grid_size):
                self.canvas.create_line(x, 0, x, height, fill=self.theme.get_color('bg_tertiary'), width=1)
            for y in range(0, height, self.grid_size):
                self.canvas.create_line(0, y, width, y, fill=self.theme.get_color('bg_tertiary'), width=1)
        except Exception as e:
            logger.error(f"Error creating desktop pattern: {e}")
    
    def load_items(self):
        """Load items from tray data"""
        try:
            items = self.tray_data.get('items', [])
            for item_data in items:
                self.add_item(item_data)
        except Exception as e:
            logger.error(f"Error loading items: {e}")
    
    def add_item(self, item_data):
        """Add item to desktop tray"""
        try:
            icon_image = self.get_item_icon(item_data)
            
            x = item_data.get('x', 50)
            y = item_data.get('y', 50)
            
            icon_frame = tk.Frame(self.canvas, bg=self.theme.get_color('bg_tertiary'), relief='raised', bd=2)
            icon_frame.place(x=x, y=y, width=80, height=80)
            
            icon_label = tk.Label(
                icon_frame,
                image=icon_image,
                bg=self.theme.get_color('bg_tertiary'),
                width=40,
                height=40
            )
            icon_label.pack(pady=5)
            
            name_label = tk.Label(
                icon_frame,
                text=item_data.get('name', 'Item'),
                bg=self.theme.get_color('bg_tertiary'),
                fg=self.theme.get_color('text'),
                font=('Segoe UI', 8),
                wraplength=70
            )
            name_label.pack()
            
            item = {
                'data': item_data,
                'frame': icon_frame,
                'icon': icon_label,
                'name': name_label,
                'x': x,
                'y': y
            }
            
            self.items.append(item)
            
            icon_frame.bind("<Button-1>", lambda e, i=item: self.on_item_click(e, i))
            icon_frame.bind("<Button-3>", lambda e, i=item: self.on_item_right_click(e, i))
            icon_frame.bind("<Double-Button-1>", lambda e, i=item: self.on_item_double_click(e, i))
            icon_frame.bind("<B1-Motion>", lambda e, i=item: self.on_item_drag(e, i))
            icon_frame.bind("<ButtonRelease-1>", lambda e, i=item: self.on_item_release(e, i))
            
            if icon_image:
                icon_label.image = icon_image
                
        except Exception as e:
            logger.error(f"Error adding item: {e}")
    
    def get_item_icon(self, item_data):
        """Get icon for item"""
        try:
            if item_data.get('custom_icon') and os.path.exists(item_data['custom_icon']):
                if PIL_AVAILABLE:
                    img = Image.open(item_data['custom_icon'])
                    img = icon_extractor.make_square_thumbnail(img, 32)
                    return ImageTk.PhotoImage(img)
            
            if item_data.get('path') and os.path.exists(item_data['path']):
                win_icon = icon_extractor.get_file_icon(item_data['path'], 32)
                if win_icon and PIL_AVAILABLE:
                    return ImageTk.PhotoImage(win_icon)
            
            if PIL_AVAILABLE:
                item_type = item_data.get('type', 'file')
                if item_type == 'folder':
                    img = icon_extractor.create_custom_icon("📁", "#ffd700", "#1e1e2f", 32)
                elif item_type == 'executable':
                    img = icon_extractor.create_custom_icon("⚙", "#4fc3f7", "#1e1e2f", 32)
                elif item_type == 'url':
                    img = icon_extractor.create_custom_icon("🌐", "#4fc3f7", "#1e1e2f", 32)
                else:
                    img = icon_extractor.create_custom_icon("📄", "#bb86fc", "#1e1e2f", 32)
                return ImageTk.PhotoImage(img)
            
            return None
        except Exception as e:
            logger.error(f"Error getting item icon: {e}")
            return None
    
    def on_item_click(self, event, item):
        """Handle item click"""
        self.selected_item = item
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.drag_data["item"] = item
    
    def on_item_drag(self, event, item):
        """Handle item drag"""
        try:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            
            new_x = item['x'] + dx
            new_y = item['y'] + dy
            
            item['frame'].place(x=new_x, y=new_y)
            item['x'] = new_x
            item['y'] = new_y
            
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
        except Exception as e:
            logger.error(f"Error dragging item: {e}")
    
    def on_item_release(self, event, item):
        """Handle item release"""
        try:
            item['data']['x'] = item['x']
            item['data']['y'] = item['y']
            self.save_tray_data()
        except Exception as e:
            logger.error(f"Error releasing item: {e}")
    
    def on_item_right_click(self, event, item):
        """Handle item right-click"""
        self.show_item_context_menu(event, item)
    
    def on_item_double_click(self, event, item):
        """Handle item double-click"""
        self.execute_item(item)
    
    def on_canvas_click(self, event):
        """Handle canvas click"""
        self.selected_item = None
    
    def on_canvas_right_click(self, event):
        """Handle canvas right-click"""
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="Add File", command=self.add_file)
        menu.add_command(label="Add Folder", command=self.add_folder)
        menu.add_command(label="Add URL", command=self.add_url)
        menu.add_separator()
        menu.add_command(label="Edit Tray Icon", command=self.edit_tray_icon)
        menu.post(event.x_root, event.y_root)
    
    def on_canvas_double_click(self, event):
        """Handle canvas double-click"""
        pass
    
    def show_item_context_menu(self, event, item):
        """Show context menu for item"""
        try:
            menu = tk.Menu(self.window, tearoff=0)
            
            if item['data'].get('path'):
                menu.add_command(label="Open", command=lambda: self.execute_item(item))
                
                if item['data'].get('type') != 'folder' and item['data'].get('type') != 'url':
                    menu.add_command(label="Edit in VS Code", command=lambda: self.edit_in_vscode(item))
                
                menu.add_separator()
            
            menu.add_command(label="Edit Icon", command=lambda: self.edit_item_icon(item))
            menu.add_command(label="Properties", command=lambda: self.show_item_properties(item))
            menu.add_command(label="Remove", command=lambda: self.delete_item(item))
            menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Error showing item context menu: {e}")
    
    def execute_item(self, item):
        """Execute item"""
        try:
            file_path = item['data'].get('path', '')
            item_type = item['data'].get('type', 'file')
            
            if item_type == 'url':
                webbrowser.open(file_path)
            elif file_path and os.path.exists(file_path):
                if item_type == 'executable':
                    if file_path.endswith('.py'):
                        subprocess.Popen(['python', file_path])
                    elif file_path.endswith('.bat'):
                        subprocess.Popen([file_path], shell=True)
                    elif file_path.endswith('.ps1'):
                        subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', file_path])
                    elif file_path.endswith('.js'):
                        subprocess.Popen(['node', file_path])
                    elif file_path.endswith('.exe'):
                        subprocess.Popen([file_path])
                elif item_type == 'folder':
                    if os.name == 'nt':
                        subprocess.Popen(['explorer', file_path])
                    else:
                        subprocess.Popen(['xdg-open', file_path])
                else:
                    if os.name == 'nt':
                        subprocess.Popen(['start', file_path], shell=True)
                    else:
                        subprocess.Popen(['xdg-open', file_path])
        except Exception as e:
            logger.error(f"Error executing item: {e}")
    
    def edit_in_vscode(self, item):
        """Edit item in VS Code"""
        try:
            file_path = item['data'].get('path', '')
            if file_path:
                subprocess.Popen(['code', file_path])
        except FileNotFoundError:
            messagebox.showerror("Error", "VS Code not found. Please make sure VS Code is installed and 'code' command is available in PATH.")
        except Exception as e:
            logger.error(f"Error opening in VS Code: {e}")
    
    def show_item_properties(self, item):
        """Show item properties"""
        try:
            name = simpledialog.askstring("Item Properties", "Name:", initialvalue=item['data'].get('name', ''))
            if name:
                item['data']['name'] = name
                item['name'].config(text=name)
                self.save_tray_data()
        except Exception as e:
            logger.error(f"Error showing item properties: {e}")
    
    def delete_item(self, item):
        """Delete item"""
        try:
            item['frame'].destroy()
            self.items.remove(item)
            self.save_tray_data()
        except Exception as e:
            logger.error(f"Error deleting item: {e}")
    
    def add_file(self):
        """Add file to tray"""
        try:
            file_path = filedialog.askopenfilename()
            if file_path:
                item_data = {
                    'id': str(uuid.uuid4()),
                    'name': os.path.basename(file_path),
                    'path': file_path,
                    'type': 'file',
                    'x': 50 + len(self.items) * 100,
                    'y': 50 + len(self.items) * 100,
                    'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.add_item(item_data)
                self.save_tray_data()
        except Exception as e:
            logger.error(f"Error adding file: {e}")
    
    def add_folder(self):
        """Add folder to tray"""
        try:
            folder_path = filedialog.askdirectory()
            if folder_path:
                item_data = {
                    'id': str(uuid.uuid4()),
                    'name': os.path.basename(folder_path),
                    'path': folder_path,
                    'type': 'folder',
                    'x': 50 + len(self.items) * 100,
                    'y': 50 + len(self.items) * 100,
                    'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.add_item(item_data)
                self.save_tray_data()
        except Exception as e:
            logger.error(f"Error adding folder: {e}")
    
    def add_url(self):
        """Add URL to tray"""
        try:
            url = simpledialog.askstring("Add URL", "Enter URL:")
            if url:
                item_data = {
                    'id': str(uuid.uuid4()),
                    'name': url,
                    'path': url,
                    'type': 'url',
                    'x': 50 + len(self.items) * 100,
                    'y': 50 + len(self.items) * 100,
                    'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.add_item(item_data)
                self.save_tray_data()
        except Exception as e:
            logger.error(f"Error adding URL: {e}")
    
    def edit_item_icon(self, item):
        """Edit item icon"""
        try:
            dialog = IconEditorDialog(self.window, item['data'])
            self.window.wait_window(dialog.dialog)
            if dialog.result:
                item['data'] = dialog.result
                item['frame'].destroy()
                self.add_item(item['data'])
                self.save_tray_data()
        except Exception as e:
            logger.error(f"Error editing item icon: {e}")
    
    def edit_tray_icon(self):
        """Edit tray icon"""
        try:
            temp_item_data = {
                'id': self.tray_data['id'],
                'custom_icon': self.tray_data.get('custom_icon')
            }
            
            dialog = IconEditorDialog(self.window, temp_item_data)
            self.window.wait_window(dialog.dialog)
            if dialog.result:
                self.tray_data['custom_icon'] = dialog.result.get('custom_icon')
                self.save_tray_data()
                if self.toolbar_instance:
                    self.toolbar_instance.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error editing tray icon: {e}")
    
    def save_tray_data(self):
        """Save tray data"""
        try:
            if self.toolbar_instance:
                items_data = []
                for item in self.items:
                    item_data = item['data'].copy()
                    item_data['x'] = item['x']
                    item_data['y'] = item['y']
                    items_data.append(item_data)
                
                for tray in self.toolbar_instance.trays:
                    if tray['id'] == self.tray_data['id']:
                        tray['items'] = items_data
                        tray['geometry'] = self.window.geometry()
                        break
                
                self.toolbar_instance.save_config()
        except Exception as e:
            logger.error(f"Error saving tray data: {e}")
    
    def save_geometry(self, event):
        """Save window geometry"""
        try:
            if event.widget == self.window:
                self.tray_data['geometry'] = self.window.geometry()
                self.save_tray_data()
        except Exception as e:
            logger.error(f"Error saving geometry: {e}")

class TaskbarButton:
    def __init__(self, parent, text, icon_image=None, command=None, item_data=None):
        self.parent = parent
        self.text = text
        self.icon_image = icon_image
        self.command = command
        self.item_data = item_data
        self.theme = ModernVioletTheme()
        
        self.frame = tk.Frame(parent, bg=self.theme.get_color('bg_tertiary'), relief='raised', bd=1)
        self.frame.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.button = tk.Button(
            self.frame,
            text=text if not icon_image else " ",
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
        
        self.button.pack(fill=tk.BOTH, expand=True)
        
        # Bind events
        self.button.bind("<Button-3>", self.on_right_click)
        
        if icon_image:
            self.button.image = icon_image
    
    def on_click(self):
        """Handle button click"""
        if self.command:
            self.command()
    
    def on_right_click(self, event):
        """Handle right-click"""
        if self.item_data:
            self.parent.show_context_menu(event, self.item_data)

class ModernTaskbar:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern Taskbar")
        self.theme = ModernVioletTheme()
        
        # Initialize managers
        self.execution_manager = ExecutionManager()
        self.file_manager = FileManager()
        self.settings_manager = SettingsManager()
        
        self.config_file = "taskbar_config.json"
        self.scripts = []
        self.trays = []
        self.tray_windows = {}
        self.transparency = self.settings_manager.get('ui.transparency', 0.95) * 100
        
        # Status tracking
        self.file_status = {}  # file_path -> ExecutionStatus
        self.status_indicators = {}  # file_path -> widget
        
        # Setup callbacks
        self.execution_manager.add_status_callback(self.on_execution_status_change)
        self.settings_manager.add_change_callback('ui.transparency', self.on_transparency_change)
        self.settings_manager.add_change_callback('ui.always_on_top', self.on_always_on_top_change)
        
        self.load_config()
        self.setup_window()
        self.create_taskbar()
        self.position_taskbar()
        self.bind_events()
        self.load_file_statuses()
    
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
            
            self.center_container = tk.Frame(self.main_frame, bg=self.theme.get_color('bg'))
            self.center_container.pack(expand=True)
            
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
            
            for script in self.scripts:
                self.add_script_button(script)
            
            for tray in self.trays:
                self.add_tray_button(tray)
                
        except Exception as e:
            logger.error(f"Error creating taskbar: {e}")
    
    def add_script_button(self, script_data):
        """Add script button to taskbar"""
        try:
            icon_image = None
            if script_data.get('custom_icon') and os.path.exists(script_data['custom_icon']):
                if PIL_AVAILABLE:
                    img = Image.open(script_data['custom_icon'])
                    img = icon_extractor.make_square_thumbnail(img, 24)
                    icon_image = ImageTk.PhotoImage(img)
            elif script_data.get('path') and os.path.exists(script_data['path']):
                win_icon = icon_extractor.get_file_icon(script_data['path'], 24)
                if win_icon and PIL_AVAILABLE:
                    icon_image = ImageTk.PhotoImage(win_icon)
            
            button = TaskbarButton(
                self.scrollable_frame,
                script_data['name'],
                icon_image=icon_image,
                command=lambda: self.execute_script(script_data),
                item_data=script_data
            )
            
            if icon_image:
                button.button.image = icon_image
                
        except Exception as e:
            logger.error(f"Error adding script button: {e}")
    
    def add_tray_button(self, tray_data):
        """Add tray button to taskbar"""
        try:
            icon_image = None
            if tray_data.get('custom_icon') and os.path.exists(tray_data['custom_icon']):
                if PIL_AVAILABLE:
                    img = Image.open(tray_data['custom_icon'])
                    img = icon_extractor.make_square_thumbnail(img, 24)
                    icon_image = ImageTk.PhotoImage(img)
            else:
                if PIL_AVAILABLE:
                    img = icon_extractor.create_custom_icon("📁", "#ffd700", "#1e1e2f", 24)
                    icon_image = ImageTk.PhotoImage(img)
            
            button = TaskbarButton(
                self.scrollable_frame,
                tray_data['name'],
                icon_image=icon_image,
                command=lambda: self.toggle_tray(tray_data),
                item_data=tray_data
            )
            
            if icon_image:
                button.button.image = icon_image
                
        except Exception as e:
            logger.error(f"Error adding tray button: {e}")
    
    def execute_script(self, script_data):
        """Execute script"""
        try:
            file_path = script_data.get('path', '')
            if not file_path or not os.path.exists(file_path):
                messagebox.showerror("Error", f"Script file not found: {file_path}")
                return
            
            if file_path.endswith('.py'):
                subprocess.Popen(['python', file_path])
            elif file_path.endswith('.bat'):
                subprocess.Popen([file_path], shell=True)
            elif file_path.endswith('.ps1'):
                subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', file_path])
            elif file_path.endswith('.js'):
                subprocess.Popen(['node', file_path])
            elif file_path.endswith('.exe'):
                subprocess.Popen([file_path])
            else:
                subprocess.Popen([file_path], shell=True)
                
        except Exception as e:
            logger.error(f"Error executing script: {e}")
            messagebox.showerror("Error", f"Failed to execute script: {e}")
    
    def toggle_tray(self, tray_data):
        """Toggle tray window"""
        try:
            tray_id = tray_data['id']
            if tray_id in self.tray_windows:
                self.tray_windows[tray_id].window.destroy()
                del self.tray_windows[tray_id]
            else:
                tray_window = DesktopTray(self.root, tray_data, self)
                self.tray_windows[tray_id] = tray_window
                
        except Exception as e:
            logger.error(f"Error toggling tray: {e}")
    
    def show_context_menu(self, event, item_data):
        """Show context menu for item"""
        try:
            menu = tk.Menu(self.root, tearoff=0)
            
            if item_data.get('type') == 'script':
                menu.add_command(label="Execute", command=lambda: self.execute_script(item_data))
                menu.add_command(label="Edit in VS Code", command=lambda: self.edit_in_vscode(item_data['path']))
                menu.add_command(label="Edit Icon", command=lambda: self.edit_script_icon(item_data))
                menu.add_separator()
                menu.add_command(label="Remove", command=lambda: self.remove_script(item_data))
            else:  # tray
                menu.add_command(label="Open", command=lambda: self.toggle_tray(item_data))
                menu.add_command(label="Edit Icon", command=lambda: self.edit_tray_icon(item_data))
                menu.add_separator()
                menu.add_command(label="Rename", command=lambda: self.rename_tray(item_data))
                menu.add_command(label="Remove", command=lambda: self.remove_tray(item_data))
            
            menu.post(event.x_root, event.y_root)
            
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
    
    def edit_in_vscode(self, file_path):
        """Edit file in VS Code"""
        try:
            if file_path:
                subprocess.Popen(['code', file_path])
        except FileNotFoundError:
            messagebox.showerror("Error", "VS Code not found. Please make sure VS Code is installed and 'code' command is available in PATH.")
        except Exception as e:
            logger.error(f"Error opening in VS Code: {e}")
            messagebox.showerror("Error", f"Failed to open in VS Code: {e}")
    
    def edit_script_icon(self, script_data):
        """Edit script icon"""
        try:
            dialog = IconEditorDialog(self.root, script_data)
            self.root.wait_window(dialog.dialog)
            if dialog.result:
                for i, script in enumerate(self.scripts):
                    if script['id'] == script_data['id']:
                        self.scripts[i] = dialog.result
                        break
                self.save_config()
                self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error editing script icon: {e}")
    
    def edit_tray_icon(self, tray_data):
        """Edit tray icon"""
        try:
            dialog = IconEditorDialog(self.root, tray_data)
            self.root.wait_window(dialog.dialog)
            if dialog.result:
                for i, tray in enumerate(self.trays):
                    if tray['id'] == tray_data['id']:
                        self.trays[i] = dialog.result
                        break
                self.save_config()
                self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error editing tray icon: {e}")
    
    def remove_script(self, script_data):
        """Remove script"""
        try:
            self.scripts = [s for s in self.scripts if s['id'] != script_data['id']]
            self.save_config()
            self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error removing script: {e}")
    
    def remove_tray(self, tray_data):
        """Remove tray"""
        try:
            tray_id = tray_data['id']
            if tray_id in self.tray_windows:
                self.tray_windows[tray_id].window.destroy()
                del self.tray_windows[tray_id]
            
            self.trays = [t for t in self.trays if t['id'] != tray_data['id']]
            self.save_config()
            self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error removing tray: {e}")
    
    def rename_tray(self, tray_data):
        """Rename tray"""
        try:
            new_name = simpledialog.askstring("Rename Tray", "Enter new name:", initialvalue=tray_data['name'])
            if new_name:
                tray_data['name'] = new_name
                self.save_config()
                self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error renaming tray: {e}")
    
    def refresh_toolbar(self):
        """Refresh taskbar"""
        try:
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            for script in self.scripts:
                self.add_script_button(script)
            for tray in self.trays:
                self.add_tray_button(tray)
                
        except Exception as e:
            logger.error(f"Error refreshing taskbar: {e}")
    
    def bind_events(self):
        """Bind event handlers"""
        try:
            self.root.bind("<Button-3>", self.show_main_context_menu)
        except Exception as e:
            logger.error(f"Error binding events: {e}")
    
    def show_main_context_menu(self, event):
        """Show main context menu"""
        try:
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Add Script", command=self.add_script)
            menu.add_command(label="Add Tray", command=self.add_tray)
            menu.add_separator()
            menu.add_command(label="Settings", command=self.show_settings)
            menu.add_separator()
            menu.add_command(label="Exit", command=self.root.quit)
            menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")
    
    def add_script(self):
        """Add new script"""
        try:
            file_path = filedialog.askopenfilename(
                title="Select Script",
                filetypes=[
                    ("Python files", "*.py"),
                    ("Batch files", "*.bat"),
                    ("PowerShell files", "*.ps1"),
                    ("JavaScript files", "*.js"),
                    ("Executable files", "*.exe"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                script_data = {
                    'id': str(uuid.uuid4()),
                    'name': os.path.splitext(os.path.basename(file_path))[0],
                    'path': file_path,
                    'type': 'executable' if file_path.lower().endswith(('.exe', '.bat', '.py', '.ps1', '.js')) else 'file',
                    'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                self.scripts.append(script_data)
                self.save_config()
                self.add_script_button(script_data)
                
        except Exception as e:
            logger.error(f"Error adding script: {e}")
    
    def add_tray(self):
        """Add new tray"""
        try:
            tray_name = simpledialog.askstring("Add Tray", "Enter tray name:")
            if tray_name:
                tray_data = {
                    'id': str(uuid.uuid4()),
                    'name': tray_name,
                    'items': [],
                    'geometry': "1000x700+100+100",
                    'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                self.trays.append(tray_data)
                self.save_config()
                self.add_tray_button(tray_data)
                
        except Exception as e:
            logger.error(f"Error adding tray: {e}")
    
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
            
            info_text = f"Scripts: {len(self.scripts)}\nTrays: {len(self.trays)}\nOpen Trays: {len(self.tray_windows)}"
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
                    self.scripts = config.get('scripts', [])
                    self.trays = config.get('trays', [])
                    self.transparency = config.get('transparency', 95)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration"""
        try:
            config = {
                'scripts': self.scripts,
                'trays': self.trays,
                'transparency': self.transparency
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    # Enhanced methods for execution tracking and file management
    def load_file_statuses(self):
        """Load execution statuses for all files"""
        try:
            for script in self.scripts:
                file_path = script.get('path')
                if file_path:
                    status = self.execution_manager.get_file_last_status(file_path)
                    if status:
                        self.file_status[file_path] = status
        except Exception as e:
            logger.error(f"Error loading file statuses: {e}")
    
    def on_execution_status_change(self, task: ExecutionTask):
        """Handle execution status changes"""
        try:
            file_path = task.file_path
            self.file_status[file_path] = task.status
            
            # Update status indicator if it exists
            if file_path in self.status_indicators:
                self.update_status_indicator(file_path, task.status)
            
        except Exception as e:
            logger.error(f"Error handling status change: {e}")
    
    def update_status_indicator(self, file_path: str, status: ExecutionStatus):
        """Update visual status indicator"""
        try:
            if file_path not in self.status_indicators:
                return
            
            indicator = self.status_indicators[file_path]
            
            # Color mapping for status
            status_colors = {
                ExecutionStatus.IDLE: self.theme.get_color('text_secondary'),
                ExecutionStatus.RUNNING: self.theme.get_color('text_warning'),
                ExecutionStatus.SUCCESS: self.theme.get_color('text_success'),
                ExecutionStatus.ERROR: self.theme.get_color('text_error'),
                ExecutionStatus.TIMEOUT: self.theme.get_color('text_error'),
                ExecutionStatus.CANCELLED: self.theme.get_color('text_secondary')
            }
            
            # Status symbols
            status_symbols = {
                ExecutionStatus.IDLE: "●",
                ExecutionStatus.RUNNING: "⟳",
                ExecutionStatus.SUCCESS: "✓",
                ExecutionStatus.ERROR: "✗",
                ExecutionStatus.TIMEOUT: "⏱",
                ExecutionStatus.CANCELLED: "⊘"
            }
            
            color = status_colors.get(status, self.theme.get_color('text_secondary'))
            symbol = status_symbols.get(status, "●")
            
            indicator.config(text=symbol, fg=color)
            
        except Exception as e:
            logger.error(f"Error updating status indicator: {e}")
    
    def execute_file_enhanced(self, file_path: str):
        """Execute file with enhanced tracking"""
        try:
            if not os.path.exists(file_path):
                messagebox.showerror("Error", f"File not found: {file_path}")
                return
            
            # Get execution settings
            timeout = self.settings_manager.get('execution.default_timeout', 30.0)
            
            # Execute with status tracking
            task_id = self.execution_manager.execute_file(
                file_path=file_path,
                timeout=timeout
            )
            
            logger.info(f"Started execution of {file_path} with task ID {task_id}")
            
        except Exception as e:
            logger.error(f"Error executing file: {e}")
            messagebox.showerror("Execution Error", f"Failed to execute file: {e}")
    
    def on_transparency_change(self, key_path: str, old_value: float, new_value: float):
        """Handle transparency setting change"""
        try:
            self.transparency = new_value * 100
            self.root.attributes('-alpha', new_value)
        except Exception as e:
            logger.error(f"Error changing transparency: {e}")
    
    def on_always_on_top_change(self, key_path: str, old_value: bool, new_value: bool):
        """Handle always on top setting change"""
        try:
            self.root.attributes('-topmost', new_value)
        except Exception as e:
            logger.error(f"Error changing always on top: {e}")

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
