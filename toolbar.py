import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
import json
import os
import subprocess
import uuid
import sys
import logging
import threading
from datetime import datetime, timedelta
import time
import codecs

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
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


def check_vscode_installed():
    """Check if VS Code is installed and available in PATH"""
    try:
        result = subprocess.run(
            ["code", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        # Try common installation paths
        common_paths = [
            r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(
                os.getenv("USERNAME", "")
            ),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return False


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
        self.success_color = "#4caf50"
        self.error_color = "#f44336"

        self.colors = {
            "bg": self.bg_primary,
            "bg_secondary": self.bg_secondary,
            "bg_tertiary": self.bg_tertiary,
            "bg_hover": self.bg_hover,
            "bg_active": self.bg_active,
            "text": self.text_primary,
            "text_secondary": self.text_secondary,
            "text_accent": self.text_accent,
            "text_success": self.text_success,
            "text_warning": self.text_warning,
            "text_error": self.text_error,
            "border": self.border_color,
            "selection_bg": self.selection_bg,
            "input_bg": self.input_bg,
            "input_border": self.input_border,
            "success": self.success_color,
            "error": self.error_color,
        }

    def get_color(self, name):
        return self.colors.get(name, self.colors["bg"])


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

            if file_path.lower().endswith(".exe"):
                hicon = win32gui.ExtractIcon(0, file_path, 0)
                if hicon:
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, size, size)
                    hdc_mem = hdc.CreateCompatibleDC()
                    hdc_mem.SelectObject(hbmp)

                    win32gui.DrawIconEx(
                        hdc_mem.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, 0x0003
                    )

                    bmp_info = hbmp.GetInfo()
                    bmp_str = hbmp.GetBitmapBits(True)
                    img = Image.frombuffer(
                        "RGB",
                        (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                        bmp_str,
                        "raw",
                        "BGRX",
                        0,
                        1,
                    )

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
                img = Image.new("RGBA", (size, size), (255, 215, 0, 200))
                draw = ImageDraw.Draw(img)
                draw.rectangle(
                    [2, size // 4, size - 2, size - 2],
                    fill=(255, 215, 0, 255),
                    outline=(255, 235, 59, 255),
                )
                draw.rectangle(
                    [2, 2, size // 2, size // 4 + 4], fill=(255, 235, 59, 255)
                )
                return img

            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext in [".py"]:
                return self.create_text_icon("PY", "#4fc3f7", size)
            elif file_ext in [".js"]:
                return self.create_text_icon("JS", "#ffb74d", size)
            elif file_ext in [".bat", ".cmd"]:
                return self.create_text_icon("BAT", "#f48fb1", size)
            elif file_ext in [".ps1"]:
                return self.create_text_icon("PS", "#4fc3f7", size)
            elif file_ext in [".exe"]:
                return self.create_text_icon("EXE", "#bb86fc", size)
            elif file_ext in [".txt", ".log"]:
                return self.create_text_icon("TXT", "#e0e0f0", size)
            elif file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
                return self.create_text_icon("IMG", "#4fc3f7", size)
            else:
                return self.create_text_icon("FILE", "#bb86fc", size)

        except Exception as e:
            logger.error(f"Error creating fallback icon: {e}")
            return None

    def create_text_icon(self, text, bg_color="#bb86fc", size=32):
        try:
            if not PIL_AVAILABLE:
                return None

            img = Image.new("RGBA", (size, size), bg_color)
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", size // 4)
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
            square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            x = (size - img.width) // 2
            y = (size - img.height) // 2
            square.paste(img, (x, y))
            return square
        except Exception as e:
            logger.error(f"Error making square thumbnail: {e}")
            return img

    def create_full_width_image(self, image_path, width, height):
        """Create a full-width image for taskbar background"""
        try:
            if not PIL_AVAILABLE:
                return None

            img = Image.open(image_path)
            # Resize to fit the taskbar height while maintaining aspect ratio
            img_ratio = img.width / img.height
            new_width = int(height * img_ratio)
            img = img.resize((new_width, height), Image.LANCZOS)

            # If the image is wider than needed, crop it
            if img.width > width:
                left = (img.width - width) // 2
                img = img.crop((left, 0, left + width, height))

            return img
        except Exception as e:
            logger.error(f"Error creating full-width image: {e}")
            return None


icon_extractor = WindowsIconExtractor()


def setup_unicode_console():
    """Configure console output for proper Unicode handling"""
    if sys.stdout.encoding != "utf-8":
        try:
            # Try to reconfigure stdout with UTF-8 encoding
            sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
        except:
            # Fallback to replacing problematic characters
            sys.stdout = codecs.getwriter(sys.stdout.encoding)(
                sys.stdout.buffer, errors="replace"
            )


def log(message):
    """Enhanced log function with Unicode handling"""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    except UnicodeEncodeError:
        # Fallback: Replace problematic Unicode characters
        safe_message = message.encode("ascii", errors="replace").decode("ascii")
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {safe_message}")


class EnhancedExecutionLogger:
    def __init__(self):
        self.logs = []
        self.max_logs = 1000
        self.logs_file = "execution_logs.json"
        self.active_executions = {}
        self.load_logs()

    def add_log(
        self,
        item_name,
        command,
        status,
        output="",
        error="",
        file_path="",
        execution_time=0,
    ):
        """Enhanced with comprehensive Unicode handling"""
        try:
            # Ensure strings are properly encoded
            safe_output = self.safe_encode(output)
            safe_error = self.safe_encode(error)
            safe_item_name = self.safe_encode(item_name)
            safe_command = self.safe_encode(command)

            log_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "item_name": safe_item_name,
                "command": safe_command,
                "status": status,
                "output": safe_output[:1000] if safe_output else "",
                "error": safe_error[:1000] if safe_error else "",
                "file_path": file_path,
                "execution_time": round(execution_time, 2),
                "file_size": self._get_file_size(file_path),
                "file_type": os.path.splitext(file_path)[1].lower()
                if file_path
                else "",
            }

            self.logs.insert(0, log_entry)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[: self.max_logs]

            self.save_logs()
        except Exception as e:
            logger.error(f"Error adding log: {e}")

    def safe_encode(self, text):
        """Safely encode text for storage, handling Unicode issues"""
        if not text:
            return ""

        try:
            if isinstance(text, bytes):
                # If it's already bytes, decode first
                text = text.decode("utf-8", errors="replace")

            # Ensure it's a string and replace any problematic characters
            return str(text).encode("utf-8", errors="replace").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Fallback: replace problematic characters
            try:
                return text.encode("utf-8", errors="replace").decode("utf-8")
            except:
                return "Encoding error: Could not process text content"

    def save_logs(self):
        """Save logs with proper Unicode handling"""
        try:
            with open(self.logs_file, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving logs: {e}")

    def load_logs(self):
        """Load logs with proper Unicode handling"""
        try:
            if os.path.exists(self.logs_file):
                with open(self.logs_file, "r", encoding="utf-8") as f:
                    self.logs = json.load(f)
        except Exception as e:
            logger.error(f"Error loading logs: {e}")
            self.logs = []

    def add_active_execution(self, execution_id, item_name, file_path):
        """Track active execution"""
        self.active_executions[execution_id] = {
            "item_name": item_name,
            "file_path": file_path,
            "start_time": time.time(),
        }

    def remove_active_execution(self, execution_id):
        """Remove completed execution"""
        if execution_id in self.active_executions:
            del self.active_executions[execution_id]

    def get_active_count(self):
        """Get number of currently running executions"""
        return len(self.active_executions)

    def _get_file_size(self, file_path):
        try:
            if file_path and os.path.exists(file_path):
                return os.path.getsize(file_path)
        except:
            pass
        return 0

    def get_logs(self, filter_type=None, limit=None):
        filtered_logs = self.logs

        if filter_type:
            if filter_type == "python":
                filtered_logs = [
                    log for log in self.logs if log.get("file_type") == ".py"
                ]
            elif filter_type == "success":
                filtered_logs = [
                    log for log in self.logs if log.get("status") == "success"
                ]
            elif filter_type == "error":
                filtered_logs = [
                    log for log in self.logs if log.get("status") == "error"
                ]
            elif filter_type == "recent":
                recent_time = datetime.now() - timedelta(hours=24)
                filtered_logs = [
                    log
                    for log in self.logs
                    if datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S")
                    > recent_time
                ]

        if limit:
            filtered_logs = filtered_logs[:limit]

        return filtered_logs

    def get_python_programs(self, limit=100):
        python_logs = [log for log in self.logs if log.get("file_type") == ".py"]
        return python_logs[:limit]

    def get_statistics(self):
        if not self.logs:
            return {}

        total_executions = len(self.logs)
        successful = len([log for log in self.logs if log.get("status") == "success"])
        failed = total_executions - successful
        python_executions = len(
            [log for log in self.logs if log.get("file_type") == ".py"]
        )
        recent_logs = self.get_logs("recent")
        recent_executions = len(recent_logs)

        return {
            "total_executions": total_executions,
            "successful": successful,
            "failed": failed,
            "success_rate": round((successful / total_executions) * 100, 1)
            if total_executions > 0
            else 0,
            "python_executions": python_executions,
            "recent_executions": recent_executions,
            "active_executions": self.get_active_count(),
        }

    def clear_logs(self):
        self.logs = []
        self.save_logs()

    def save_logs(self):
        try:
            with open(self.logs_file, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving logs: {e}")

    def load_logs(self):
        try:
            if os.path.exists(self.logs_file):
                with open(self.logs_file, "r", encoding="utf-8") as f:
                    self.logs = json.load(f)
        except Exception as e:
            logger.error(f"Error loading logs: {e}")
            self.logs = []


class ExecutionHistoryDialog:
    def __init__(self, parent, logger_instance):
        self.parent = parent
        self.logger = logger_instance
        self.theme = ModernVioletTheme()
        self.config_file = "execution_history_config.json"

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Execution History & Monitoring")
        self.dialog.configure(bg=self.theme.get_color("bg"))
        self.dialog.attributes("-topmost", True)

        # Load previous position and size
        self.load_config()

        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.current_filter = "all"
        self.create_widgets()
        self.refresh_data()

        # Bind close event to save position
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)

        # Auto-refresh every 2 seconds
        self.auto_refresh()

    def load_config(self):
        """Load window position and size from config"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    geometry = config.get("geometry", "900x600+100+100")
                    self.dialog.geometry(geometry)
            else:
                # Default size and position (centered on parent)
                self.dialog.geometry("900x600")
                self.center_on_parent()
        except Exception as e:
            logger.error(f"Error loading execution history config: {e}")
            self.dialog.geometry("900x600")
            self.center_on_parent()

    def save_config(self):
        """Save window position and size to config"""
        try:
            config = {
                "geometry": self.dialog.geometry(),
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving execution history config: {e}")

    def center_on_parent(self):
        """Center the dialog on the parent window"""
        try:
            self.dialog.update_idletasks()
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()

            dialog_width = self.dialog.winfo_width()
            dialog_height = self.dialog.winfo_height()

            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2

            self.dialog.geometry(f"+{x}+{y}")
        except Exception as e:
            logger.error(f"Error centering execution history dialog: {e}")

    def on_close(self):
        """Handle window close event"""
        self.save_config()
        self.dialog.destroy()

    def auto_refresh(self):
        """Auto-refresh the dialog every 2 seconds"""
        self.refresh_data()
        self.dialog.after(2000, self.auto_refresh)

    def create_widgets(self):
        main_frame = tk.Frame(self.dialog, bg=self.theme.get_color("bg"))
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Configure ttk styles to match dark theme
        self.configure_styles()

        self.create_header(main_frame)
        self.create_filters(main_frame)
        self.create_data_view(main_frame)
        self.create_controls(main_frame)

    def configure_styles(self):
        """Configure ttk styles to match dark theme"""
        style = ttk.Style()
        style.theme_use("clam")  # Use clam theme which is more customizable

        # Configure colors
        bg_color = self.theme.get_color("bg")
        fg_color = self.theme.get_color("text")
        secondary_bg = self.theme.get_color("bg_secondary")
        tertiary_bg = self.theme.get_color("bg_tertiary")

        # Configure Treeview style
        style.configure(
            "Treeview",
            background=secondary_bg,
            foreground=fg_color,
            fieldbackground=secondary_bg,
            borderwidth=0,
        )

        style.configure(
            "Treeview.Heading",
            background=tertiary_bg,
            foreground=fg_color,
            relief="flat",
        )

        style.map(
            "Treeview", background=[("selected", self.theme.get_color("selection_bg"))]
        )

        # Configure Notebook style
        style.configure("TNotebook", background=bg_color)
        style.configure(
            "TNotebook.Tab",
            background=tertiary_bg,
            foreground=fg_color,
            padding=[10, 5],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", secondary_bg)],
            expand=[("selected", [1, 1, 1, 0])],
        )

    def create_header(self, parent):
        header_frame = tk.Frame(
            parent, bg=self.theme.get_color("bg_tertiary"), relief="solid", bd=1
        )
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = tk.Label(
            header_frame,
            text="Execution History & Real-time Monitoring",
            bg=self.theme.get_color("bg_tertiary"),
            fg=self.theme.get_color("text_accent"),
            font=("Segoe UI", 14, "bold"),
        )
        title_label.pack(pady=10)

        self.stats_frame = tk.Frame(
            header_frame, bg=self.theme.get_color("bg_tertiary")
        )
        self.stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    def create_filters(self, parent):
        filter_frame = tk.Frame(
            parent, bg=self.theme.get_color("bg_secondary"), relief="solid", bd=1
        )
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            filter_frame,
            text="Filter:",
            bg=self.theme.get_color("bg_secondary"),
            fg=self.theme.get_color("text"),
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=5)

        filters = [
            ("All", "all"),
            ("Python Files", "python"),
            ("Successful", "success"),
            ("Errors", "error"),
            ("Recent (24h)", "recent"),
        ]

        for text, filter_type in filters:
            btn = tk.Button(
                filter_frame,
                text=text,
                command=lambda f=filter_type: self.set_filter(f),
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
                font=("Segoe UI", 9),
                relief="flat",
            )
            btn.pack(side=tk.LEFT, padx=2, pady=5)

    def create_data_view(self, parent):
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure("TNotebook", background=self.theme.get_color("bg"))
        style.configure("TNotebook.Tab", background=self.theme.get_color("bg_tertiary"))

        # Execution History Tab
        history_frame = tk.Frame(self.notebook, bg=self.theme.get_color("bg"))
        self.notebook.add(history_frame, text="Execution History")

        tree_frame = tk.Frame(history_frame, bg=self.theme.get_color("bg"))
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("timestamp", "name", "type", "status", "duration", "size")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=15
        )

        self.tree.heading("timestamp", text="Time")
        self.tree.heading("name", text="File Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("status", text="Status")
        self.tree.heading("duration", text="Duration (s)")
        self.tree.heading("size", text="Size (bytes)")

        self.tree.column("timestamp", width=130)
        self.tree.column("name", width=200)
        self.tree.column("type", width=60)
        self.tree.column("status", width=80)
        self.tree.column("duration", width=100)
        self.tree.column("size", width=100)

        v_scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        h_scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set
        )

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.bind("<Double-1>", self.show_execution_details)

        # Python Programs Tab
        python_frame = tk.Frame(self.notebook, bg=self.theme.get_color("bg"))
        self.notebook.add(python_frame, text="Python Programs")

        python_tree_frame = tk.Frame(python_frame, bg=self.theme.get_color("bg"))
        python_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        python_columns = ("timestamp", "name", "path", "status", "output")
        self.python_tree = ttk.Treeview(
            python_tree_frame, columns=python_columns, show="headings", height=15
        )

        self.python_tree.heading("timestamp", text="Time")
        self.python_tree.heading("name", text="Script Name")
        self.python_tree.heading("path", text="Path")
        self.python_tree.heading("status", text="Status")
        self.python_tree.heading("output", text="Output Preview")

        self.python_tree.column("timestamp", width=130)
        self.python_tree.column("name", width=150)
        self.python_tree.column("path", width=250)
        self.python_tree.column("status", width=80)
        self.python_tree.column("output", width=200)

        python_v_scrollbar = ttk.Scrollbar(
            python_tree_frame, orient=tk.VERTICAL, command=self.python_tree.yview
        )
        python_h_scrollbar = ttk.Scrollbar(
            python_tree_frame, orient=tk.HORIZONTAL, command=self.python_tree.xview
        )
        self.python_tree.configure(
            yscrollcommand=python_v_scrollbar.set, xscrollcommand=python_h_scrollbar.set
        )

        self.python_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        python_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        python_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.python_tree.bind("<Double-1>", self.show_python_details)

    def create_controls(self, parent):
        controls_frame = tk.Frame(parent, bg=self.theme.get_color("bg"))
        controls_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            controls_frame,
            text="Refresh",
            command=self.refresh_data,
            bg=self.theme.get_color("bg_tertiary"),
            fg=self.theme.get_color("text"),
            font=("Segoe UI", 9),
            relief="flat",
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls_frame,
            text="Export to CSV",
            command=self.export_data,
            bg=self.theme.get_color("bg_tertiary"),
            fg=self.theme.get_color("text"),
            font=("Segoe UI", 9),
            relief="flat",
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls_frame,
            text="Clear All Logs",
            command=self.clear_logs,
            bg=self.theme.get_color("bg_tertiary"),
            fg=self.theme.get_color("text_error"),
            font=("Segoe UI", 9),
            relief="flat",
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls_frame,
            text="Close",
            command=self.dialog.destroy,
            bg=self.theme.get_color("bg_tertiary"),
            fg=self.theme.get_color("text"),
            font=("Segoe UI", 9),
            relief="flat",
        ).pack(side=tk.RIGHT, padx=5)

    def set_filter(self, filter_type):
        self.current_filter = filter_type
        self.refresh_data()

    def refresh_data(self):
        self.update_statistics()
        self.update_execution_history()
        self.update_python_programs()

    def update_statistics(self):
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        stats = self.logger.get_statistics()

        stats_text = f"Total: {stats.get('total_executions', 0)} | "
        stats_text += f"Success: {stats.get('successful', 0)} | "
        stats_text += f"Failed: {stats.get('failed', 0)} | "
        stats_text += f"Success Rate: {stats.get('success_rate', 0)}% | "
        stats_text += f"Python Scripts: {stats.get('python_executions', 0)} | "
        stats_text += f"Active: {stats.get('active_executions', 0)} | "
        stats_text += f"Recent (24h): {stats.get('recent_executions', 0)}"

        tk.Label(
            self.stats_frame,
            text=stats_text,
            bg=self.theme.get_color("bg_tertiary"),
            fg=self.theme.get_color("text_success"),
            font=("Segoe UI", 10),
        ).pack()

    def update_execution_history(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        logs = self.logger.get_logs(
            filter_type=self.current_filter if self.current_filter != "all" else None,
            limit=200,
        )

        for log in logs:
            status_color = "success" if log.get("status") == "success" else "error"
            file_size = self.format_file_size(log.get("file_size", 0))

            self.tree.insert(
                "",
                tk.END,
                values=(
                    log.get("timestamp", ""),
                    log.get("item_name", ""),
                    log.get("file_type", ""),
                    log.get("status", ""),
                    log.get("execution_time", ""),
                    file_size,
                ),
                tags=(status_color,),
            )

        self.tree.tag_configure("success", foreground="#4caf50")
        self.tree.tag_configure("error", foreground="#f44336")

    def update_python_programs(self):
        for item in self.python_tree.get_children():
            self.python_tree.delete(item)

        python_logs = self.logger.get_python_programs(100)

        for log in python_logs:
            status_color = "success" if log.get("status") == "success" else "error"
            output_preview = (
                (log.get("output", "")[:50] + "...")
                if len(log.get("output", "")) > 50
                else log.get("output", "")
            )

            self.python_tree.insert(
                "",
                tk.END,
                values=(
                    log.get("timestamp", ""),
                    os.path.basename(log.get("file_path", "")),
                    log.get("file_path", ""),
                    log.get("status", ""),
                    output_preview,
                ),
                tags=(status_color,),
            )

        self.python_tree.tag_configure("success", foreground="#4caf50")
        self.python_tree.tag_configure("error", foreground="#f44336")

    def format_file_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

    def show_execution_details(self, event):
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            timestamp = item["values"][0]
            self.show_log_details(timestamp)

    def show_python_details(self, event):
        selection = self.python_tree.selection()
        if selection:
            item = self.python_tree.item(selection[0])
            timestamp = item["values"][0]
            self.show_log_details(timestamp)

    def show_log_details(self, timestamp):
        log_entry = None
        for log in self.logger.get_logs():
            if log.get("timestamp") == timestamp:
                log_entry = log
                break

        if not log_entry:
            return

        details_window = tk.Toplevel(self.dialog)
        details_window.title("Execution Details")
        details_window.geometry("600x500")
        details_window.configure(bg=self.theme.get_color("bg"))

        details_frame = tk.Frame(details_window, bg=self.theme.get_color("bg"))
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_frame = tk.Frame(details_frame, bg=self.theme.get_color("bg"))
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            text_frame,
            bg=self.theme.get_color("input_bg"),
            fg=self.theme.get_color("text"),
            font=("Consolas", 10),
            wrap=tk.WORD,
        )

        scrollbar = tk.Scrollbar(
            text_frame, orient=tk.VERTICAL, command=text_widget.yview
        )
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        details_text = f"Execution Details\n{'=' * 50}\n\n"
        details_text += f"Timestamp: {log_entry.get('timestamp', 'N/A')}\n"
        details_text += f"File Name: {log_entry.get('item_name', 'N/A')}\n"
        details_text += f"File Path: {log_entry.get('file_path', 'N/A')}\n"
        details_text += f"Command: {log_entry.get('command', 'N/A')}\n"
        details_text += f"Status: {log_entry.get('status', 'N/A')}\n"
        details_text += (
            f"Execution Time: {log_entry.get('execution_time', 0)} seconds\n"
        )
        details_text += (
            f"File Size: {self.format_file_size(log_entry.get('file_size', 0))}\n\n"
        )

        if log_entry.get("output"):
            details_text += f"Output:\n{'-' * 30}\n{log_entry.get('output')}\n\n"

        if log_entry.get("error"):
            details_text += f"Error:\n{'-' * 30}\n{log_entry.get('error')}\n"

        text_widget.insert(tk.END, details_text)
        text_widget.config(state=tk.DISABLED)

    def export_data(self):
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Execution History",
            )

            if file_path:
                import csv

                with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = [
                        "timestamp",
                        "item_name",
                        "file_path",
                        "command",
                        "status",
                        "execution_time",
                        "file_size",
                        "output",
                        "error",
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    writer.writeheader()
                    for log in self.logger.get_logs():
                        writer.writerow(
                            {
                                "timestamp": log.get("timestamp", ""),
                                "item_name": log.get("item_name", ""),
                                "file_path": log.get("file_path", ""),
                                "command": log.get("command", ""),
                                "status": log.get("status", ""),
                                "execution_time": log.get("execution_time", ""),
                                "file_size": log.get("file_size", ""),
                                "output": log.get("output", ""),
                                "error": log.get("error", ""),
                            }
                        )

                messagebox.showinfo("Export Complete", f"Data exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")

    def clear_logs(self):
        if messagebox.askyesno(
            "Clear Logs", "Are you sure you want to clear all execution logs?"
        ):
            self.logger.clear_logs()
            self.refresh_data()


class WideStatusIndicator:
    def __init__(self, parent, on_click_callback):
        self.parent = parent
        self.theme = ModernVioletTheme()
        self.on_click_callback = on_click_callback

        # Much wider frame
        self.frame = tk.Frame(
            parent, bg=self.theme.get_color("bg"), width=120, height=30
        )
        self.frame.pack_propagate(False)

        self.canvas = tk.Canvas(
            self.frame,
            bg=self.theme.get_color("bg"),
            highlightthickness=0,
            width=120,
            height=30,
            cursor="hand2",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.status = "idle"
        self.fade_job = None
        self.active_count = 0
        self.create_indicator()

        # Bind click event
        self.canvas.bind("<Button-1>", lambda e: self.on_click_callback())

    def create_indicator(self):
        self.canvas.delete("all")

        # Wide glass background
        self.create_rounded_rectangle(
            5,
            5,
            115,
            25,
            fill=self.theme.get_color("bg_tertiary"),
            outline=self.theme.get_color("border"),
            width=1,
        )

        # Status indicator
        if self.status == "success":
            color = self.theme.get_color("success")
            text = "SUCCESS"
        elif self.status == "error":
            color = self.theme.get_color("error")
            text = "ERROR"
        elif self.status == "running":
            color = self.theme.get_color("text_warning")
            text = f"RUNNING ({self.active_count})"
        else:
            color = self.theme.get_color("bg_hover")
            text = "MONITOR"

        # Wide status indicator
        self.create_rounded_rectangle(10, 8, 110, 22, fill=color, outline=color)

        # Status text
        self.canvas.create_text(
            60,
            15,
            text=text,
            fill="#1e1e2f" if self.status in ["success", "running"] else "#ffffff",
            font=("Segoe UI", 8, "bold"),
        )

        # Glass highlight effect
        self.canvas.create_arc(
            8, 8, 25, 18, start=45, extent=90, outline="white", width=1, style="arc"
        )

    def create_rounded_rectangle(self, x1, y1, x2, y2, fill="", outline="", width=1):
        """Helper method to create rounded rectangles"""
        # Simple rectangle for now, can be enhanced
        return self.canvas.create_rectangle(
            x1, y1, x2, y2, fill=fill, outline=outline, width=width
        )

    def set_status(self, status, active_count=0):
        self.status = status
        self.active_count = active_count
        self.create_indicator()

        # Instant response - no delay
        if status in ["success", "error"]:
            if self.fade_job:
                self.parent.after_cancel(self.fade_job)
            self.fade_job = self.parent.after(3000, self.fade_to_idle)

    def fade_to_idle(self):
        if self.active_count > 0:
            self.status = "running"
        else:
            self.status = "idle"
        self.create_indicator()


class HoverTooltip:
    """Tooltip that shows on hover with file information"""

    def __init__(self, widget, item_data):
        self.widget = widget
        self.item_data = item_data
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        self.widget.bind("<ButtonPress>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """Show tooltip with file information"""
        if self.tooltip:
            return

        # Get widget position relative to screen
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 5
        y = self.widget.winfo_rooty()

        # Create tooltip window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        self.tooltip.attributes("-topmost", True)  # Ensure it's always on top

        # Apply theme
        theme = ModernVioletTheme()
        self.tooltip.configure(bg=theme.get_color("bg_tertiary"))

        # Create content
        frame = tk.Frame(
            self.tooltip, bg=theme.get_color("bg_tertiary"), padx=10, pady=10
        )
        frame.pack(fill=tk.BOTH, expand=True)

        # File name
        name_label = tk.Label(
            frame,
            text=f"Name: {self.item_data.get('name', 'Unknown')}",
            bg=theme.get_color("bg_tertiary"),
            fg=theme.get_color("text"),
            font=("Segoe UI", 10, "bold"),
            justify=tk.LEFT,
        )
        name_label.pack(anchor=tk.W)

        # File path
        path_label = tk.Label(
            frame,
            text=f"Path: {self.item_data.get('path', 'Unknown')}",
            bg=theme.get_color("bg_tertiary"),
            fg=theme.get_color("text_secondary"),
            font=("Segoe UI", 9),
            justify=tk.LEFT,
            wraplength=300,
        )
        path_label.pack(anchor=tk.W, pady=(5, 0))

        # File type and size
        if self.item_data.get("file_size", 0) > 0:
            size_label = tk.Label(
                frame,
                text=f"Size: {self.format_file_size(self.item_data.get('file_size', 0))}",
                bg=theme.get_color("bg_tertiary"),
                fg=theme.get_color("text_secondary"),
                font=("Segoe UI", 9),
                justify=tk.LEFT,
            )
            size_label.pack(anchor=tk.W, pady=(5, 0))

        type_label = tk.Label(
            frame,
            text=f"Type: {self.item_data.get('type', 'Unknown')}",
            bg=theme.get_color("bg_tertiary"),
            fg=theme.get_color("text_secondary"),
            font=("Segoe UI", 9),
            justify=tk.LEFT,
        )
        type_label.pack(anchor=tk.W, pady=(5, 0))

    def format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

    def hide_tooltip(self, event=None):
        """Hide the tooltip"""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class DraggableIcon:
    def __init__(
        self, parent, taskbar_ref, text, icon_image=None, command=None, item_data=None
    ):
        self.parent = parent
        self.taskbar_ref = taskbar_ref
        self.text = text
        self.icon_image = icon_image
        self.command = command
        self.item_data = item_data
        self.theme = ModernVioletTheme()

        # Get position from item_data
        self.x = item_data.get("x", 0)
        self.y = item_data.get("y", 5)

        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_threshold = 5  # Minimum distance to start drag

        # Create enhanced square frame with better visual feedback - LARGER SIZE
        self.frame = tk.Frame(
            parent,
            bg=self.theme.get_color("bg_tertiary"),
            relief="flat",
            bd=2,
            highlightbackground=self.theme.get_color("border"),
            highlightthickness=1,
        )
        # Increased size from 48x48 to 60x60 for larger icons
        self.frame.place(x=self.x, y=self.y, width=60, height=60)

        # Create canvas for better visual control - LARGER SIZE
        self.canvas = tk.Canvas(
            self.frame,
            bg=self.theme.get_color("bg_tertiary"),
            highlightthickness=0,
            width=58,  # Increased from 46 to 58
            height=58,  # Increased from 46 to 58
            cursor="hand2",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Draw square with icon/text
        self.draw_icon()

        # Enhanced drag events
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Enter>", self.on_enter)
        self.canvas.bind("<Leave>", self.on_leave)

        # Bind to frame as well for complete coverage
        self.frame.bind("<Button-1>", self.start_drag)
        self.frame.bind("<B1-Motion>", self.on_drag)
        self.frame.bind("<ButtonRelease-1>", self.end_drag)
        self.frame.bind("<Button-3>", self.on_right_click)
        self.frame.bind("<Enter>", self.on_enter)
        self.frame.bind("<Leave>", self.on_leave)

        # Add hover tooltip
        self.tooltip = HoverTooltip(self.frame, item_data)

    def draw_icon(self):
        """Draw the icon in the square canvas"""
        self.canvas.delete("all")

        # Draw background square with rounded corners effect - LARGER SIZE
        self.canvas.create_rectangle(
            2,
            2,
            56,  # Increased from 44 to 56
            56,  # Increased from 44 to 56
            fill=self.theme.get_color("bg_tertiary"),
            outline=self.theme.get_color("border"),
            width=1,
        )

        if self.icon_image:
            # Center the icon - adjusted for larger size
            self.canvas.create_image(
                29, 29, image=self.icon_image
            )  # Increased from 23 to 29
        else:
            # Draw text-based icon - larger font for larger icon
            short_text = (
                self.text[:4].upper() if len(self.text) > 4 else self.text.upper()
            )
            self.canvas.create_text(
                29,  # Increased from 23 to 29
                29,  # Increased from 23 to 29
                text=short_text,
                fill=self.theme.get_color("text"),
                font=("Segoe UI", 10, "bold"),  # Increased font size from 8 to 10
            )

    def start_drag(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.dragging = False  # Will be set to True when threshold is exceeded

        # Visual feedback - darken the icon
        self.canvas.configure(bg=self.theme.get_color("bg_hover"))
        self.frame.configure(relief="raised", bd=3)

    def on_drag(self, event):
        # Calculate distance from start point
        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y
        distance = (dx * dx + dy * dy) ** 0.5

        # Only start dragging if we've moved beyond threshold
        if not self.dragging and distance > self.drag_threshold:
            self.dragging = True
            self.canvas.config(cursor="fleur")
            self.frame.configure(relief="raised", bd=4)

        if self.dragging:
            # Calculate new position relative to parent
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()

            # Adjust for larger icon size (60x60 instead of 48x48)
            new_x = max(
                0,
                min(
                    event.x_root - parent_x - 30, self.parent.winfo_width() - 60
                ),  # Adjusted for 60px width
            )
            new_y = max(
                5,
                min(
                    event.y_root - parent_y - 30, self.parent.winfo_height() - 60
                ),  # Adjusted for 60px height
            )

            # Snap to grid for cleaner positioning - adjust grid size for larger icons
            new_x = (new_x // 65) * 65  # Increased from 55 to 65 for larger icons

            self.x = new_x
            self.y = new_y
            self.frame.place(x=self.x, y=self.y)

            # Update item data immediately for real-time saving
            if self.item_data:
                self.item_data["x"] = self.x
                self.item_data["y"] = self.y

    def end_drag(self, event):
        if self.dragging:
            self.dragging = False
            self.canvas.config(cursor="hand2")
            self.frame.configure(relief="flat", bd=2)
            self.canvas.configure(bg=self.theme.get_color("bg_tertiary"))

            # Save configuration after drag
            if self.taskbar_ref:
                self.taskbar_ref.save_config()
        else:
            # If not dragging, it's a click
            self.on_click()

    def on_enter(self, event):
        if not self.dragging:
            self.canvas.configure(bg=self.theme.get_color("bg_hover"))
            # Add subtle glow effect
            self.frame.configure(
                highlightbackground=self.theme.get_color("text_accent")
            )

    def on_leave(self, event):
        if not self.dragging:
            self.canvas.configure(bg=self.theme.get_color("bg_tertiary"))
            self.frame.configure(highlightbackground=self.theme.get_color("border"))

    def on_click(self):
        if not self.dragging and self.command:
            self.command()

    def on_right_click(self, event):
        if self.item_data and self.taskbar_ref:
            self.taskbar_ref.show_context_menu(event, self.item_data)

    def destroy(self):
        self.frame.destroy()


class IconEditorDialog:
    def __init__(self, parent, item_data):
        self.parent = parent
        self.item_data = item_data
        self.theme = ModernVioletTheme()
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Icon")
        self.dialog.geometry("400x500")
        self.dialog.configure(bg=self.theme.get_color("bg"))
        self.dialog.attributes("-topmost", True)

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
            main_frame = tk.Frame(self.dialog, bg=self.theme.get_color("bg"))
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            tk.Label(
                main_frame,
                text="Edit Icon",
                bg=self.theme.get_color("bg"),
                fg=self.theme.get_color("text_accent"),
                font=("Segoe UI", 14, "bold"),
            ).pack(pady=(0, 15))

            icon_frame = tk.Frame(
                main_frame, bg=self.theme.get_color("bg_tertiary"), relief="solid", bd=1
            )
            icon_frame.pack(pady=10, fill=tk.X)

            self.icon_display = tk.Label(
                icon_frame,
                text="No Icon",
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text_secondary"),
                width=10,
                height=5,
                relief="flat",
            )
            self.icon_display.pack(pady=10)

            self.load_current_icon()

            options_frame = tk.Frame(main_frame, bg=self.theme.get_color("bg"))
            options_frame.pack(fill=tk.X, pady=10)

            buttons = [
                ("Use File Icon", self.use_file_icon),
                ("Create Text Icon", self.create_text_icon),
                ("Load Image Icon", self.load_image_icon),
                ("Remove Custom Icon", self.remove_icon),
            ]

            for text, command in buttons:
                tk.Button(
                    options_frame,
                    text=text,
                    command=command,
                    bg=self.theme.get_color("bg_tertiary"),
                    fg=self.theme.get_color("text"),
                    font=("Segoe UI", 9),
                    relief="flat",
                ).pack(fill=tk.X, pady=2)

            btn_frame = tk.Frame(main_frame, bg=self.theme.get_color("bg"))
            btn_frame.pack(fill=tk.X, pady=20)

            tk.Button(
                btn_frame,
                text="Save",
                command=self.save_icon,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
                font=("Segoe UI", 9),
                relief="flat",
            ).pack(side=tk.RIGHT, padx=5)

            tk.Button(
                btn_frame,
                text="Cancel",
                command=self.cancel,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
                font=("Segoe UI", 9),
                relief="flat",
            ).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            logger.error(f"Error creating icon editor widgets: {e}")

    def load_current_icon(self):
        try:
            if self.item_data.get("custom_icon") and os.path.exists(
                self.item_data["custom_icon"]
            ):
                img = Image.open(self.item_data["custom_icon"])
                img = icon_extractor.make_square_thumbnail(img, 48)
                photo = ImageTk.PhotoImage(img)
                self.icon_display.config(image=photo, text="")
                self.icon_display.image = photo
            elif self.item_data.get("path") and os.path.exists(self.item_data["path"]):
                img = icon_extractor.get_file_icon(self.item_data["path"], 48)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.icon_display.config(image=photo, text="")
                    self.icon_display.image = photo
        except Exception as e:
            logger.error(f"Error loading current icon: {e}")

    def use_file_icon(self):
        try:
            if self.item_data.get("path") and os.path.exists(self.item_data["path"]):
                img = icon_extractor.get_file_icon(self.item_data["path"], 48)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.icon_display.config(image=photo, text="")
                    self.icon_display.image = photo
                    self.item_data["custom_icon"] = None
        except Exception as e:
            logger.error(f"Error using file icon: {e}")

    def create_text_icon(self):
        try:
            text = simpledialog.askstring(
                "Text Icon", "Enter text for icon (max 4 chars):"
            )
            if text:
                text = text[:4].upper()
                color = colorchooser.askcolor(
                    title="Choose background color", color="#bb86fc"
                )
                bg_color = color[1] if color[1] else "#bb86fc"

                img = icon_extractor.create_text_icon(text, bg_color, 48)
                if img:
                    photo = ImageTk.PhotoImage(img)
                    self.icon_display.config(image=photo, text="")
                    self.icon_display.image = photo
                    self.item_data["custom_icon"] = icon_extractor.save_custom_icon(
                        img, self.item_data["id"]
                    )
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
                    ("All files", "*.*"),
                ],
            )
            if file_path and PIL_AVAILABLE:
                img = Image.open(file_path)
                img = icon_extractor.make_square_thumbnail(img, 48)
                photo = ImageTk.PhotoImage(img)
                self.icon_display.config(image=photo, text="")
                self.icon_display.image = photo
                self.item_data["custom_icon"] = icon_extractor.save_custom_icon(
                    img, self.item_data["id"]
                )
        except Exception as e:
            logger.error(f"Error loading image icon: {e}")

    def remove_icon(self):
        self.item_data["custom_icon"] = None
        self.icon_display.config(image="", text="No Icon")
        self.icon_display.image = None

    def save_icon(self):
        self.result = self.item_data
        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()


class SettingsDialog:
    def __init__(self, parent, taskbar_instance, theme):
        self.parent = parent
        self.taskbar = taskbar_instance
        self.theme = theme

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("450x400")
        self.dialog.configure(bg=self.theme.get_color("bg"))
        self.dialog.attributes("-topmost", True)

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
            main_frame = tk.Frame(self.dialog, bg=self.theme.get_color("bg"))
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            tk.Label(
                main_frame,
                text="Enhanced Taskbar Settings",
                bg=self.theme.get_color("bg"),
                fg=self.theme.get_color("text_accent"),
                font=("Segoe UI", 14, "bold"),
            ).pack(pady=10)

            trans_frame = tk.Frame(main_frame, bg=self.theme.get_color("bg"))
            trans_frame.pack(fill=tk.X, pady=10)

            tk.Label(
                trans_frame,
                text="Transparency:",
                bg=self.theme.get_color("bg"),
                fg=self.theme.get_color("text"),
            ).pack(side=tk.LEFT)

            trans_var = tk.IntVar(value=self.taskbar.transparency)
            trans_scale = tk.Scale(
                trans_frame,
                from_=50,
                to=100,
                orient=tk.HORIZONTAL,
                variable=trans_var,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
                activebackground=self.theme.get_color("bg_hover"),
                troughcolor=self.theme.get_color("bg_secondary"),
                highlightthickness=0,
            )
            trans_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

            # Statistics
            stats = self.taskbar.execution_logger.get_statistics()
            vscode_status = "Available" if self.taskbar.vscode_path else "Not Found"
            drag_drop_status = (
                "Enabled" if self.taskbar.drag_drop_enabled else "Disabled"
            )

            info_text = f"Total Items: {len(self.taskbar.items)}\n"
            info_text += f"Total Executions: {stats.get('total_executions', 0)}\n"
            info_text += f"Success Rate: {stats.get('success_rate', 0)}%\n"
            info_text += f"Python Executions: {stats.get('python_executions', 0)}\n"
            info_text += f"Active Executions: {stats.get('active_executions', 0)}\n"
            info_text += f"VS Code: {vscode_status}\n"
            info_text += f"Drag & Drop: {drag_drop_status}"

            tk.Label(
                main_frame,
                text=info_text,
                bg=self.theme.get_color("bg"),
                fg=self.theme.get_color("text_secondary"),
                font=("Segoe UI", 10),
                justify=tk.LEFT,
            ).pack(pady=20)

            btn_frame = tk.Frame(main_frame, bg=self.theme.get_color("bg"))
            btn_frame.pack(fill=tk.X, pady=20)

            tk.Button(
                btn_frame,
                text="Save Settings",
                command=self.save_settings,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
                font=("Segoe UI", 9),
                relief="flat",
            ).pack(side=tk.RIGHT, padx=5)

            tk.Button(
                btn_frame,
                text="Cancel",
                command=self.dialog.destroy,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
                font=("Segoe UI", 9),
                relief="flat",
            ).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            logger.error(f"Error creating settings widgets: {e}")

    def save_settings(self):
        try:
            self.taskbar.transparency = self.trans_var.get()
            self.taskbar.root.attributes("-alpha", self.taskbar.transparency / 100)
            self.taskbar.save_config()
            self.dialog.destroy()
        except Exception as e:
            logger.error(f"Error saving settings: {e}")


class ModernTaskbar:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Modern Taskbar")
        self.theme = ModernVioletTheme()

        self.config_file = "taskbar_config.json"
        self.items = []
        self.icons = []  # Store draggable icons
        self.transparency = 95
        self.execution_logger = EnhancedExecutionLogger()
        self.vscode_path = check_vscode_installed()
        self.drag_drop_enabled = False
        self.drop_indicator = None

        # Taskbar positioning - centered and auto-expanding
        self.taskbar_x = 200
        self.taskbar_y = 100
        self.min_width = 200
        # Increased taskbar height to accommodate larger icons
        self.taskbar_height = 70  # Increased from 45 to 70

        self.load_config()
        self.setup_window()
        self.create_taskbar()
        self.position_taskbar()
        self.bind_events()
        self.setup_drag_drop()

    def setup_window(self):
        try:
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.configure(bg=self.theme.get_color("bg"))
            self.root.attributes("-alpha", self.transparency / 100)

            # Make window draggable
            self.drag_data = {"x": 0, "y": 0}
        except Exception as e:
            logger.error(f"Error setting up window: {e}")

    def calculate_taskbar_width(self):
        """Calculate taskbar width based on number of items"""
        status_width = 130  # Wide status indicator
        # Increased item width from 55 to 65 to accommodate larger icons
        item_width = len(self.items) * 65 if self.items else 65
        padding = 40
        return max(self.min_width, status_width + item_width + padding)

    def position_taskbar(self):
        try:
            width = self.calculate_taskbar_width()

            # Center on screen if no saved position
            if not hasattr(self, "taskbar_x") or self.taskbar_x == 200:
                screen_width = self.root.winfo_screenwidth()
                self.taskbar_x = (screen_width - width) // 2

            self.root.geometry(
                f"{width}x{self.taskbar_height}+{self.taskbar_x}+{self.taskbar_y}"
            )
        except Exception as e:
            logger.error(f"Error positioning taskbar: {e}")

    def create_taskbar(self):
        try:
            self.main_frame = tk.Frame(self.root, bg=self.theme.get_color("bg"))
            self.main_frame.pack(fill=tk.BOTH, expand=True)

            # Wide status indicator (clickable)
            self.status_indicator = WideStatusIndicator(
                self.main_frame, self.show_execution_history
            )
            self.status_indicator.frame.pack(side=tk.LEFT, padx=5, pady=7)

            # Icons container - for draggable positioning
            self.icons_frame = tk.Frame(self.main_frame, bg=self.theme.get_color("bg"))
            self.icons_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Load existing items
            for item in self.items:
                self.add_item_icon(item)

            self.update_status_indicator()

        except Exception as e:
            logger.error(f"Error creating taskbar: {e}")

    def setup_drag_drop(self):
        """Enhanced drag and drop setup with better error handling and visual feedback"""
        self.drag_drop_enabled = False

        if not DND_AVAILABLE:
            logger.info("Drag and drop not available - tkinterdnd2 not installed")
            return

        try:
            # Enable drag and drop on multiple targets for better coverage
            targets = [self.main_frame, self.icons_frame, self.root]

            for target in targets:
                try:
                    target.drop_target_register(tkdnd.DND_FILES)
                    target.dnd_bind("<<Drop>>", self.on_drop)
                    target.dnd_bind("<<DragEnter>>", self.on_drag_enter)
                    target.dnd_bind("<<DragLeave>>", self.on_drag_leave)
                    target.dnd_bind("<<DragOver>>", self.on_drag_over)
                except Exception as e:
                    logger.error(f"Error setting up drag and drop on {target}: {e}")
                    continue

            self.drag_drop_enabled = True
            self.drop_indicator = None  # For visual feedback
            logger.info("Enhanced drag and drop enabled successfully")

        except Exception as e:
            logger.error(f"Error setting up enhanced drag and drop: {e}")
            self.drag_drop_enabled = False

    def on_drag_enter(self, event):
        """Enhanced drag enter with visual feedback"""
        if not self.drag_drop_enabled:
            return
        try:
            # Create drop indicator
            self.create_drop_indicator()
            # Change background to indicate drop zone
            self.main_frame.config(bg=self.theme.get_color("bg_hover"))
            self.icons_frame.config(bg=self.theme.get_color("bg_hover"))
        except Exception as e:
            logger.error(f"Error in drag enter: {e}")

    def on_drag_over(self, event):
        """Handle drag over events for better visual feedback"""
        if not self.drag_drop_enabled:
            return
        try:
            # Update drop indicator position based on mouse
            if hasattr(self, "drop_indicator") and self.drop_indicator:
                x = event.x_root - self.root.winfo_rootx()
                # Snap to grid position - increased from 55 to 65 for larger icons
                grid_x = (x // 65) * 65
                self.update_drop_indicator(grid_x)
        except Exception as e:
            logger.error(f"Error in drag over: {e}")

    def on_drag_leave(self, event):
        """Enhanced drag leave cleanup"""
        if not self.drag_drop_enabled:
            return
        try:
            # Remove drop indicator
            self.remove_drop_indicator()
            # Restore original background
            self.main_frame.config(bg=self.theme.get_color("bg"))
            self.icons_frame.config(bg=self.theme.get_color("bg"))
        except Exception as e:
            logger.error(f"Error in drag leave: {e}")

    def on_drop(self, event):
        """Enhanced drop handling with better file processing"""
        if not self.drag_drop_enabled:
            return

        try:
            # Remove drop indicator
            self.remove_drop_indicator()

            # Restore background
            self.main_frame.config(bg=self.theme.get_color("bg"))
            self.icons_frame.config(bg=self.theme.get_color("bg"))

            # Process dropped files
            files = self.root.tk.splitlist(event.data)

            # Calculate drop position
            drop_x = event.x_root - self.root.winfo_rootx()
            # Increased grid size from 55 to 65 for larger icons
            grid_x = (drop_x // 65) * 65

            for i, file_path in enumerate(files):
                if os.path.exists(file_path):
                    # Position each file with offset - increased from 55 to 65
                    pos_x = grid_x + (i * 65)
                    self.add_item_from_path(file_path, pos_x)

            # Show success feedback
            self.status_indicator.set_status("success")

        except Exception as e:
            logger.error(f"Error handling drop: {e}")
            self.status_indicator.set_status("error")

    def create_drop_indicator(self):
        """Create visual drop indicator"""
        try:
            if hasattr(self, "drop_indicator") and self.drop_indicator:
                return

            # Increased size from 48x48 to 60x60 for larger icons
            self.drop_indicator = tk.Frame(
                self.icons_frame,
                bg=self.theme.get_color("text_accent"),
                width=60,
                height=60,
                relief="dashed",
                bd=2,
            )
            # Position will be updated in drag_over

        except Exception as e:
            logger.error(f"Error creating drop indicator: {e}")

    def update_drop_indicator(self, x_pos):
        """Update drop indicator position"""
        try:
            if self.drop_indicator:
                self.drop_indicator.place(x=x_pos, y=5)
        except Exception as e:
            logger.error(f"Error updating drop indicator: {e}")

    def remove_drop_indicator(self):
        """Remove drop indicator"""
        try:
            if hasattr(self, "drop_indicator") and self.drop_indicator:
                self.drop_indicator.destroy()
                self.drop_indicator = None
        except Exception as e:
            logger.error(f"Error removing drop indicator: {e}")

    def add_item_from_path(self, file_path, custom_x=None):
        """Enhanced add item with better positioning and validation"""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return False

            # Check for duplicates
            for item in self.items:
                if item.get("path") == file_path:
                    logger.info(f"Item already exists: {file_path}")
                    return False

            item_name = os.path.basename(file_path)
            is_executable = file_path.lower().endswith(
                (".exe", ".bat", ".py", ".ps1", ".js", ".cmd", ".msi", ".sh")
            )
            is_folder = os.path.isdir(file_path)

            # Enhanced type detection
            if is_folder:
                item_type = "folder"
            elif is_executable:
                item_type = "executable"
            elif file_path.lower().endswith(
                (".txt", ".json", ".xml", ".html", ".css", ".md")
            ):
                item_type = "document"
            elif file_path.lower().endswith((".jpg", ".png", ".gif", ".bmp", ".ico")):
                item_type = "image"
            else:
                item_type = "file"

            # Smart positioning - use custom_x if provided (from drop), otherwise auto-position
            if custom_x is not None:
                # Increased from 10 to 5, and from 58 to 60 for larger icons
                next_x = max(5, min(custom_x, self.icons_frame.winfo_width() - 65))
            else:
                # Find next available position - increased grid size from 55 to 65
                occupied_positions = [item.get("x", 0) for item in self.items]
                next_x = 5
                while next_x in occupied_positions:
                    next_x += 65

            item = {
                "id": str(uuid.uuid4()),
                "name": item_name,
                "path": file_path,
                "type": item_type,
                "custom_icon": None,
                "description": f"Added from: {file_path}",
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "x": next_x,
                "y": 5,
                "file_size": self._get_file_size(file_path),
            }

            self.items.append(item)
            self.add_item_icon(item)
            self.update_taskbar_size()
            self.save_config()

            logger.info(f"Successfully added {item_type}: {item_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding item from path: {e}")
            return False

    def _get_file_size(self, file_path):
        """Helper to get file size safely"""
        try:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    return os.path.getsize(file_path)
                elif os.path.isdir(file_path):
                    total_size = 0
                    for dirpath, dirnames, filenames in os.walk(file_path):
                        for filename in filenames:
                            try:
                                total_size += os.path.getsize(
                                    os.path.join(dirpath, filename)
                                )
                            except (OSError, IOError):
                                continue
                    return total_size
        except Exception:
            pass
        return 0

    def add_item_icon(self, item_data):
        try:
            # Increased icon size from 24 to 32 for larger icons
            icon_image = self.get_item_icon(item_data, 32)

            # Check if this is a full-width image
            is_full_width = item_data.get("custom_icon") and item_data.get(
                "custom_icon"
            ).endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))

            if is_full_width:
                # For full-width images, we need to handle placement differently
                # They should span the entire width of the taskbar
                icon = DraggableIcon(
                    self.icons_frame,
                    self,
                    item_data["name"],
                    icon_image=icon_image,
                    command=lambda: self.execute_item(item_data),
                    item_data=item_data,
                )

                # Make sure full-width images are at the bottom of the stacking order
                self.icons_frame.lower(icon.frame)
            else:
                # Standard icon placement
                icon = DraggableIcon(
                    self.icons_frame,
                    self,
                    item_data["name"][:8] + "..."
                    if len(item_data["name"]) > 8
                    else item_data["name"],
                    icon_image=icon_image,
                    command=lambda: self.execute_item(item_data),
                    item_data=item_data,
                )

            self.icons.append(icon)

            # Force a refresh of the taskbar to ensure icons are visible
            self.root.update_idletasks()

        except Exception as e:
            logger.error(f"Error adding item icon: {e}")

    def get_item_icon(self, item_data, size=32):
        try:
            if item_data.get("custom_icon") and os.path.exists(
                item_data["custom_icon"]
            ):
                if PIL_AVAILABLE:
                    img = Image.open(item_data["custom_icon"])
                    # Ensure image has an alpha channel for transparency
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    img = icon_extractor.make_square_thumbnail(img, size)
                    return ImageTk.PhotoImage(img)

            if item_data.get("path") and os.path.exists(item_data["path"]):
                win_icon = icon_extractor.get_file_icon(item_data["path"], size)
                if win_icon and PIL_AVAILABLE:
                    # Ensure image has an alpha channel
                    if win_icon.mode != "RGBA":
                        win_icon = win_icon.convert("RGBA")
                    return ImageTk.PhotoImage(win_icon)

            # Create a fallback icon with proper transparency
            if PIL_AVAILABLE:
                img = Image.new("RGBA", (size, size), (0, 0, 0, 0))  # Fully transparent
                draw = ImageDraw.Draw(img)
                # Draw a simple document icon
                draw.rectangle(
                    [size // 4, size // 4, 3 * size // 4, 3 * size // 4],
                    fill=(100, 100, 100, 255),
                    outline=(200, 200, 200, 255),
                )
                return ImageTk.PhotoImage(img)

            return None
        except Exception as e:
            logger.error(f"Error getting item icon: {e}")
            return None

    def execute_item(self, item_data):
        """Execute item with async support and instant status update"""
        execution_id = str(uuid.uuid4())

        # Instant status update
        self.execution_logger.add_active_execution(
            execution_id, item_data.get("name"), item_data.get("path")
        )
        self.update_status_indicator()

        def run_execution():
            start_time = time.time()
            file_path = item_data.get("path", "")
            item_type = item_data.get("type", "file")
            item_name = item_data.get("name", "Unknown")
            command = ""
            result = None

            try:
                if not file_path or not os.path.exists(file_path):
                    self.execution_logger.add_log(
                        item_name,
                        file_path,
                        "error",
                        error="File not found",
                        file_path=file_path,
                    )
                    self.update_status_indicator_with_result("error")
                    return

                # Set UTF-8 encoding for subprocess
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                if item_type == "folder":
                    if os.name == "nt":
                        command = f'explorer "{file_path}"'
                        result = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=30,
                            encoding="utf-8",
                            errors="replace",
                        )
                    else:
                        command = f'xdg-open "{file_path}"'
                        result = subprocess.run(
                            [command],
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=30,
                            encoding="utf-8",
                            errors="replace",
                        )

                    execution_time = time.time() - start_time
                    self.execution_logger.add_log(
                        item_name,
                        command,
                        "success",
                        "Opened folder",
                        file_path=file_path,
                        execution_time=execution_time,
                    )
                    self.update_status_indicator_with_result("success")

                elif item_type == "executable":
                    if file_path.endswith(".py"):
                        command = f'python "{file_path}"'
                        result = subprocess.run(
                            ["python", file_path],
                            capture_output=True,
                            text=True,
                            timeout=120,  # Longer timeout for scripts
                            encoding="utf-8",
                            errors="replace",
                            env=env,
                        )
                    elif file_path.endswith((".bat", ".cmd")):
                        command = f'"{file_path}"'
                        result = subprocess.run(
                            [file_path],
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            encoding="utf-8",
                            errors="replace",
                            env=env,
                        )
                    elif file_path.endswith(".ps1"):
                        command = f'powershell -ExecutionPolicy Bypass "{file_path}"'
                        result = subprocess.run(
                            ["powershell", "-ExecutionPolicy", "Bypass", file_path],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            encoding="utf-8",
                            errors="replace",
                            env=env,
                        )
                    elif file_path.endswith(".js"):
                        command = f'node "{file_path}"'
                        result = subprocess.run(
                            ["node", file_path],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            encoding="utf-8",
                            errors="replace",
                            env=env,
                        )
                    elif file_path.endswith(".exe"):
                        command = f'"{file_path}"'
                        subprocess.Popen([file_path])
                        execution_time = time.time() - start_time
                        self.execution_logger.add_log(
                            item_name,
                            command,
                            "success",
                            "Executable started",
                            file_path=file_path,
                            execution_time=execution_time,
                        )
                        self.update_status_indicator_with_result("success")
                        return
                    else:
                        command = f'"{file_path}"'
                        result = subprocess.run(
                            [file_path],
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            encoding="utf-8",
                            errors="replace",
                            env=env,
                        )

                    execution_time = time.time() - start_time
                    status = "success" if result.returncode == 0 else "error"
                    self.execution_logger.add_log(
                        item_name,
                        command,
                        status,
                        result.stdout,
                        result.stderr,
                        file_path=file_path,
                        execution_time=execution_time,
                    )
                    self.update_status_indicator_with_result(status)

                else:
                    if os.name == "nt":
                        command = f'start "" "{file_path}"'
                        subprocess.run(["start", "", file_path], shell=True)
                    else:
                        command = f'xdg-open "{file_path}"'
                        subprocess.run(["xdg-open", file_path])

                    execution_time = time.time() - start_time
                    self.execution_logger.add_log(
                        item_name,
                        command,
                        "success",
                        "Opened with default application",
                        file_path=file_path,
                        execution_time=execution_time,
                    )
                    self.update_status_indicator_with_result("success")

            except subprocess.TimeoutExpired:
                execution_time = time.time() - start_time
                self.execution_logger.add_log(
                    item_name,
                    command,
                    "error",
                    error="Execution timeout",
                    file_path=file_path,
                    execution_time=execution_time,
                )
                self.update_status_indicator_with_result("error")
            except Exception as e:
                execution_time = time.time() - start_time
                self.execution_logger.add_log(
                    item_name,
                    command,
                    "error",
                    error=str(e),
                    file_path=file_path,
                    execution_time=execution_time,
                )
                self.update_status_indicator_with_result("error")
                logger.error(f"Error executing item: {e}")
            finally:
                self.execution_logger.remove_active_execution(execution_id)
                self.root.after(100, self.update_status_indicator)

        # Run in separate thread for true async execution
        thread = threading.Thread(target=run_execution, daemon=True)
        thread.start()

    def update_status_indicator(self):
        """Update status indicator based on current state"""
        active_count = self.execution_logger.get_active_count()
        if active_count > 0:
            self.status_indicator.set_status("running", active_count)
        # Don't change status if no active executions - let result status show

    def update_status_indicator_with_result(self, status):
        """Update status indicator with execution result"""
        self.root.after(0, lambda: self.status_indicator.set_status(status))

    def show_execution_history(self):
        """Show execution history dialog"""
        ExecutionHistoryDialog(self.root, self.execution_logger)

    def update_taskbar_size(self):
        """Update taskbar size and reposition"""
        self.position_taskbar()

    def show_context_menu(self, event, item_data):
        try:
            menu = tk.Menu(
                self.root,
                tearoff=0,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
            )

            if item_data["type"] == "folder":
                menu.add_command(
                    label="Open Folder", command=lambda: self.execute_item(item_data)
                )
            elif item_data["type"] == "executable":
                menu.add_command(
                    label="Execute", command=lambda: self.execute_item(item_data)
                )
            else:
                menu.add_command(
                    label="Open", command=lambda: self.execute_item(item_data)
                )

            menu.add_separator()

            if (
                item_data.get("path", "")
                .lower()
                .endswith(
                    (
                        ".py",
                        ".js",
                        ".bat",
                        ".ps1",
                        ".txt",
                        ".json",
                        ".xml",
                        ".html",
                        ".css",
                    )
                )
            ):
                if self.vscode_path:
                    menu.add_command(
                        label="Edit in VS Code",
                        command=lambda: self.edit_in_vscode(item_data["path"]),
                    )
                menu.add_command(
                    label="Edit in Notepad",
                    command=lambda: self.edit_in_notepad(item_data["path"]),
                )

            menu.add_command(
                label="Open Folder Location",
                command=lambda: self.open_folder_location(item_data["path"]),
            )
            menu.add_command(
                label="Copy Path",
                command=lambda: self.copy_path_to_clipboard(item_data["path"]),
            )

            menu.add_separator()

            menu.add_command(
                label="Change Icon", command=lambda: self.edit_item_icon(item_data)
            )
            menu.add_command(
                label="Properties", command=lambda: self.show_item_properties(item_data)
            )

            menu.add_separator()

            menu.add_command(
                label="Remove", command=lambda: self.remove_item(item_data)
            )

            menu.post(event.x_root, event.y_root)

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def edit_in_vscode(self, file_path):
        try:
            if self.vscode_path is True:
                # Use the 'code' command if available in PATH
                subprocess.Popen(["code", file_path])
            elif isinstance(self.vscode_path, str) and os.path.exists(self.vscode_path):
                # Use the full path to code.exe
                subprocess.Popen([self.vscode_path, file_path])
            else:
                # Fallback: try to find VS Code in common locations
                common_paths = [
                    os.path.expandvars(
                        r"%USERPROFILE%\AppData\Local\Programs\Microsoft VS Code\Code.exe"
                    ),
                    r"C:\Program Files\Microsoft VS Code\Code.exe",
                    r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
                ]

                for path in common_paths:
                    if os.path.exists(path):
                        subprocess.Popen([path, file_path])
                        return

                messagebox.showerror(
                    "Error",
                    "VS Code not found. Please install VS Code or add it to your PATH.",
                )
        except Exception as e:
            logger.error(f"Error opening in VS Code: {e}")
            messagebox.showerror("Error", f"Failed to open VS Code: {e}")

    def edit_in_notepad(self, file_path):
        try:
            subprocess.Popen(["notepad.exe", file_path])
        except Exception as e:
            logger.error(f"Error opening in Notepad: {e}")

    def open_folder_location(self, file_path):
        try:
            if os.name == "nt":
                subprocess.run(["explorer", "/select,", file_path])
            else:
                folder_path = os.path.dirname(file_path)
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            logger.error(f"Error opening folder location: {e}")

    def copy_path_to_clipboard(self, file_path):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(file_path)
        except Exception as e:
            logger.error(f"Error copying path to clipboard: {e}")

    def edit_item_icon(self, item_data):
        try:
            dialog = IconEditorDialog(self.root, item_data)
            self.root.wait_window(dialog.dialog)
            if dialog.result:
                for i, item in enumerate(self.items):
                    if item["id"] == item_data["id"]:
                        self.items[i] = dialog.result
                        break
                self.save_config()
                self.refresh_toolbar()
        except Exception as e:
            logger.error(f"Error editing item icon: {e}")

    def show_item_properties(self, item_data):
        try:
            props_window = tk.Toplevel(self.root)
            props_window.title("Item Properties")
            props_window.geometry("400x350")
            props_window.configure(bg=self.theme.get_color("bg"))
            props_window.attributes("-topmost", True)

            frame = tk.Frame(props_window, bg=self.theme.get_color("bg"))
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            name_frame = tk.Frame(frame, bg=self.theme.get_color("bg"))
            name_frame.pack(fill=tk.X, pady=5)
            tk.Label(
                name_frame,
                text="Name:",
                bg=self.theme.get_color("bg"),
                fg=self.theme.get_color("text"),
            ).pack(side=tk.LEFT)
            name_var = tk.StringVar(value=item_data.get("name", ""))
            name_entry = tk.Entry(
                name_frame,
                textvariable=name_var,
                bg=self.theme.get_color("input_bg"),
                fg=self.theme.get_color("text"),
            )
            name_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)

            properties = [
                ("Path", item_data.get("path", "N/A")),
                ("Type", item_data.get("type", "Unknown")),
                ("Position", f"({item_data.get('x', 0)}, {item_data.get('y', 0)})"),
                ("Created", item_data.get("created", "Unknown")),
                ("Modified", item_data.get("modified", "Unknown")),
            ]

            for prop_name, prop_value in properties:
                tk.Label(
                    frame,
                    text=f"{prop_name}: {prop_value}",
                    bg=self.theme.get_color("bg"),
                    fg=self.theme.get_color("text_secondary"),
                    wraplength=350,
                    justify=tk.LEFT,
                ).pack(fill=tk.X, pady=5)

            def save_properties():
                new_name = name_var.get().strip()
                if new_name:
                    item_data["name"] = new_name
                    item_data["modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_config()
                    self.refresh_toolbar()
                props_window.destroy()

            tk.Button(
                frame,
                text="Save",
                command=save_properties,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
            ).pack(pady=20)

        except Exception as e:
            logger.error(f"Error showing item properties: {e}")

    def remove_item(self, item_data):
        try:
            if messagebox.askyesno(
                "Confirm Remove", f"Remove '{item_data['name']}' from taskbar?"
            ):
                self.items = [
                    item for item in self.items if item["id"] != item_data["id"]
                ]
                self.refresh_toolbar()
                self.update_taskbar_size()
                self.save_config()
        except Exception as e:
            logger.error(f"Error removing item: {e}")

    def refresh_toolbar(self):
        try:
            # Clear existing icons
            for icon in self.icons:
                icon.destroy()
            self.icons = []

            # Add regular items first
            regular_items = [
                item
                for item in self.items
                if not (
                    item.get("custom_icon")
                    and item.get("custom_icon").endswith(
                        (".png", ".jpg", ".jpeg", ".gif", ".bmp")
                    )
                )
            ]

            # Add full-width image items last (so they appear behind)
            image_items = [
                item
                for item in self.items
                if (
                    item.get("custom_icon")
                    and item.get("custom_icon").endswith(
                        (".png", ".jpg", ".jpeg", ".gif", ".bmp")
                    )
                )
            ]

            for item in regular_items:
                self.add_item_icon(item)

            for item in image_items:
                self.add_item_icon(item)

            # Force a refresh of the taskbar
            self.root.update_idletasks()

        except Exception as e:
            logger.error(f"Error refreshing toolbar: {e}")

    def bind_events(self):
        try:
            self.root.bind("<Button-1>", self.start_move)
            self.root.bind("<B1-Motion>", self.do_move)
            self.root.bind("<ButtonRelease-1>", self.stop_move)
            self.root.bind("<Button-3>", self.show_main_context_menu)
        except Exception as e:
            logger.error(f"Error binding events: {e}")

    def start_move(self, event):
        """Start moving taskbar"""
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def do_move(self, event):
        """Move taskbar"""
        try:
            dx = event.x - self.drag_data["x"]
            dy = event.y - self.drag_data["y"]
            self.taskbar_x += dx
            self.taskbar_y += dy
            self.position_taskbar()
        except Exception as e:
            logger.error(f"Error moving taskbar: {e}")

    def stop_move(self, event):
        """Stop moving taskbar"""
        self.save_config()

    def show_main_context_menu(self, event):
        try:
            menu = tk.Menu(
                self.root,
                tearoff=0,
                bg=self.theme.get_color("bg_tertiary"),
                fg=self.theme.get_color("text"),
            )
            menu.add_command(label="Add File", command=self.add_file)
            menu.add_command(label="Add Folder", command=self.add_folder)
            menu.add_separator()
            menu.add_command(
                label="Execution History", command=self.show_execution_history
            )
            menu.add_command(label="Settings", command=self.show_settings)
            menu.add_separator()
            menu.add_command(label="Exit", command=self.root.quit)
            menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def add_file(self):
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
                ],
            )

            if file_path:
                self.add_item_from_path(file_path)

        except Exception as e:
            logger.error(f"Error adding file: {e}")

    def add_folder(self):
        try:
            folder_path = filedialog.askdirectory()
            if folder_path:
                self.add_item_from_path(folder_path)
        except Exception as e:
            logger.error(f"Error adding folder: {e}")

    def show_settings(self):
        """Show settings dialog"""
        SettingsDialog(self.root, self, self.theme)

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.items = config.get("items", [])
                    self.transparency = config.get("transparency", 95)
                    self.taskbar_x = config.get("taskbar_x", 200)
                    self.taskbar_y = config.get("taskbar_y", 100)
        except Exception as e:
            logger.error(f"Error loading config: {e}")

    def save_config(self):
        try:
            # Update item positions from icons
            for i, icon in enumerate(self.icons):
                if i < len(self.items):
                    self.items[i]["x"] = icon.x
                    self.items[i]["y"] = icon.y

            config = {
                "items": self.items,
                "transparency": self.transparency,
                "taskbar_x": self.taskbar_x,
                "taskbar_y": self.taskbar_y,
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")


# Add this function to handle file content reading with proper encoding
def read_file_with_encoding(file_path):
    """Read file content with automatic encoding detection"""
    encodings = ["utf-8", "cp1252", "latin-1", "iso-8859-1", "ascii"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return f"Error reading file: {str(e)}"

    # If all encodings fail, try with error handling
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


# Update the main function to set up Unicode handling
def main():
    try:
        # Setup Unicode handling first
        setup_unicode_console()

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
