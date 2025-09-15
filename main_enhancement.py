"""
Enhanced main function for toolbar.py
This replaces the original main function with enhanced functionality
"""
import tkinter as tk
from tkinter import messagebox
import sys
import logging

logger = logging.getLogger(__name__)

def enhanced_main():
    """Enhanced main function with all new features"""
    try:
        root = tk.Tk()
        
        # Import the original ModernTaskbar class
        from toolbar import ModernTaskbar
        app = ModernTaskbar(root)
        
        # Enhance the taskbar with new features
        try:
            from toolbar_enhanced import enhance_modern_taskbar
            app = enhance_modern_taskbar(app)
            logger.info("✅ Enhanced features loaded successfully")
            print("🚀 Modern Taskbar Enhanced - All features loaded!")
        except ImportError as e:
            logger.warning(f"Enhanced features not available: {e}")
            print("⚠️ Running in basic mode - enhanced features not available")
        except Exception as e:
            logger.error(f"Error loading enhanced features: {e}")
            print(f"❌ Error loading enhanced features: {e}")
        
        def on_closing():
            try:
                # Check if enhanced settings are available
                if hasattr(app, 'settings_manager'):
                    confirm_exit = app.settings_manager.getboolean('behavior', 'confirm_exit', True)
                    if confirm_exit:
                        if not messagebox.askyesno("Confirm Exit", "Are you sure you want to exit the taskbar?"):
                            return
                
                app.save_config()
                root.quit()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
                root.quit()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Add system tray menu if enhanced features are available
        if hasattr(app, 'show_settings_dialog'):
            def show_tray_menu(event):
                try:
                    menu = tk.Menu(root, tearoff=0)
                    menu.add_command(label="⚙️ Settings", command=app.show_settings_dialog)
                    menu.add_command(label="📊 History", command=lambda: app.show_script_history(None))
                    menu.add_separator()
                    menu.add_command(label="🔄 Refresh", command=app.refresh_taskbar)
                    menu.add_command(label="❌ Exit", command=on_closing)
                    menu.post(event.x_root, event.y_root)
                except Exception as e:
                    logger.error(f"Error showing tray menu: {e}")
            
            root.bind("<Button-3>", show_tray_menu)
            
            # Show welcome message with keyboard shortcuts
            def show_welcome():
                welcome_msg = """🎉 Modern Taskbar Enhanced is ready!

🔥 New Features Available:
✅ Real-time execution status tracking
✅ Multi-editor support (VS Code, Notepad++, etc.)
✅ Advanced file management & renaming
✅ Comprehensive settings dialog
✅ Execution history & performance stats
✅ Enhanced tooltips & visual feedback

⌨️ Keyboard Shortcuts:
• Ctrl+, : Open Settings
• Ctrl+H : View History  
• F5 : Refresh Taskbar
• Right-click : Context Menu

🚀 Ready to boost your productivity!"""
                
                messagebox.showinfo("Welcome to Enhanced Taskbar!", welcome_msg)
            
            # Show welcome message after a short delay
            root.after(1000, show_welcome)
        
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    enhanced_main()
