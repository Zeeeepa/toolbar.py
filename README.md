# 🚀 Enhanced Toolbar.py - Comprehensive Taskbar Application

A powerful, modern taskbar-like application with advanced execution tracking, file management, and transparency controls.

## ✨ Features

### 🎯 Core Features
- **Execution Status Tracking** - Real-time visual indicators for Success/Error/Running states
- **Enhanced File Management** - Rename files, open folders, integrate with local editors
- **Transparency Controls** - Advanced settings with real-time preview
- **Local Editor Integration** - VS Code, Notepad++, Sublime Text, and custom editor support
- **Advanced Execution Framework** - Support for Python, Batch, PowerShell, JavaScript, and executables
- **Rich Context Menus** - Complete right-click functionality for all operations
- **Data Persistence** - Configuration and execution history storage
- **Robust Error Handling** - Comprehensive logging and recovery mechanisms

### 🎨 UI Enhancements
- **Status Indicators** - Color-coded symbols showing execution status
- **Tooltips** - Detailed information on hover
- **Modern Violet Theme** - Professional VS Code-inspired dark theme
- **Responsive Design** - Adapts to different screen sizes
- **Smooth Animations** - Configurable animation speeds

### ⚙️ Advanced Settings
- **Transparency Control** - Adjustable window opacity (30% - 100%)
- **Always on Top** - Keep toolbar visible above other windows
- **Execution Timeouts** - Configurable timeout settings
- **Editor Preferences** - Set default editors and file associations
- **Notification System** - Customizable execution notifications

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install tkinter pillow
   # Optional Windows dependencies
   pip install pywin32 tkinterdnd2
   ```

2. **Run the Application**
   ```bash
   python toolbar.py
   ```

3. **Add Scripts**
   - Right-click on the taskbar
   - Select "Add Script"
   - Choose your executable files

## 📁 Project Structure

```
toolbar.py/
├── toolbar.py              # Main application
├── execution_manager.py    # Execution tracking system
├── file_manager.py         # File operations and editor integration
├── settings_manager.py     # Settings and configuration management
├── data/                   # Application data
│   ├── execution_history.json
│   ├── file_manager_config.json
│   └── settings.json
├── config/                 # Configuration files
├── logs/                   # Application logs
└── README.md              # This file
```

## 🎮 Usage

### Basic Operations
- **Left-click** any script button to execute
- **Right-click** for context menu with advanced options
- **Status indicators** show execution state:
  - ● Idle (gray)
  - ⟳ Running (yellow)
  - ✓ Success (green)
  - ✗ Error (red)
  - ⏱ Timeout (red)
  - ⊘ Cancelled (gray)

### File Management
- **Rename files** through context menu
- **Open containing folder** in file explorer
- **Edit with preferred editor** (VS Code, Notepad++, etc.)
- **View execution history** for each file

### Settings
- Access advanced settings through the system tray
- Adjust transparency, timeouts, and editor preferences
- Configure notifications and UI behavior

## 🔧 Supported File Types

- **Python** (.py) - Executed with `python`
- **Batch** (.bat, .cmd) - Windows batch files
- **PowerShell** (.ps1) - PowerShell scripts
- **JavaScript** (.js) - Node.js execution
- **Executables** (.exe, .msi) - Direct execution

## 🎨 Customization

### Themes
The application uses a modern violet theme inspired by VS Code Dark. Colors can be customized in the `ModernVioletTheme` class.

### Editor Integration
Supported editors are automatically detected:
- Visual Studio Code
- Notepad++
- Sublime Text
- Atom
- Vim
- Notepad (Windows)

Add custom editors through the settings dialog.

## 📊 Execution Tracking

- **Real-time status updates** during execution
- **Execution history** with timestamps and results
- **Performance metrics** including duration and return codes
- **Error logging** with detailed error messages
- **Concurrent execution** support with configurable limits

## 🔒 Security Features

- **Confirmation dialogs** for potentially dangerous operations
- **File type restrictions** (configurable)
- **Execution logging** for audit trails
- **Timeout protection** to prevent runaway processes

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are installed
   - Optional modules (pywin32, tkinterdnd2) provide enhanced features but aren't required

2. **Execution Failures**
   - Check file permissions
   - Verify file paths are correct
   - Review execution history for error details

3. **UI Issues**
   - Try adjusting transparency settings
   - Check display scaling settings
   - Restart the application

### Logging
Application logs are stored in the `logs/` directory with detailed error information and execution traces.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with Python and Tkinter
- Inspired by modern taskbar applications
- Uses VS Code Dark theme color palette
- Icons and symbols from Unicode character set

---

**Made with ❤️ for productivity and automation**
