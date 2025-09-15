# Modern Taskbar - Enhanced Edition 🚀

A comprehensive, feature-rich taskbar application built with Python and Tkinter, now with advanced execution tracking, multi-editor support, and extensive customization options.

## ✨ Enhanced Features

### 🎯 **Execution Status Tracking**
- Real-time visual status indicators (idle, running, success, error)
- Animated spinning indicators for active executions
- Comprehensive execution history with timestamps and duration
- Performance statistics and success rate tracking
- Detailed execution logs with output capture

### 🛠️ **Advanced File Management**
- **Multi-Editor Support**: VS Code, Notepad++, Sublime Text, Atom, Vim, Nano, Gedit
- **File Operations**: Rename files directly from the taskbar
- **Folder Integration**: Open containing folders and terminals
- **File Properties**: Detailed file information in tooltips
- **Smart Editor Detection**: Automatically detects available editors

### ⚙️ **Comprehensive Settings System**
- **Tabbed Settings Dialog**: Appearance, Behavior, Execution, Editors
- **Transparency Control**: Smooth slider with real-time preview
- **Behavior Options**: Auto-start, stay-on-top, exit confirmation
- **Execution Settings**: Timeout, concurrent limits, output display
- **Editor Preferences**: Default editor selection and arguments

### 🚀 **Advanced Execution Engine**
- **Multi-Language Support**: Python, JavaScript, TypeScript, Rust, Go, Java, C++, C, Ruby, PHP
- **Compilation Support**: Automatic compilation for compiled languages
- **Execution Modes**: Background, elevated, with custom arguments
- **Environment Management**: Virtual environments and containers
- **Smart File Type Detection**: Automatic execution method selection

### 📊 **Monitoring & Analytics**
- **Execution History Dialog**: Sortable history with color-coded status
- **Performance Statistics**: Success rates, average duration, trends
- **Real-time Monitoring**: Active execution tracking
- **Resource Usage**: Memory and CPU monitoring for processes

### 🎨 **Enhanced User Interface**
- **Status Indicators**: Visual execution status on each button
- **Rich Tooltips**: File properties, execution stats, performance data
- **Progress Feedback**: Progress bars for long-running operations
- **Animated Elements**: Smooth transitions and visual feedback
- **Context Menus**: Comprehensive right-click options

### ⌨️ **Keyboard Shortcuts**
- `Ctrl+,` - Open Settings Dialog
- `Ctrl+H` - View Execution History
- `F5` - Refresh Taskbar
- `Right-click` - Enhanced Context Menu

## 🏗️ Architecture

The enhanced version uses a modular architecture:

- **`toolbar.py`** - Core application and UI components
- **`toolbar_services.py`** - Backend services (execution, file management, settings)
- **`toolbar_ui_components.py`** - Enhanced UI widgets and dialogs
- **`toolbar_enhanced.py`** - Integration layer and enhanced functionality
- **`main_enhancement.py`** - Enhanced main function with welcome screen

## 📋 Requirements

### Core Dependencies
- Python 3.7+
- tkinter (included with Python)

### Enhanced Features Dependencies
```bash
pip install psutil configparser pathlib
```

### Optional Dependencies
```bash
pip install Pillow pywin32 tkinterdnd2
```

## 🚀 Installation & Usage

### Quick Start
```bash
# Clone the repository
git clone <repository-url>
cd toolbar.py

# Run with enhanced features
python main_enhancement.py

# Or run the original version
python toolbar.py
```

### Enhanced Mode
When running `main_enhancement.py`, you'll get:
- Welcome screen with feature overview
- All enhanced functionality enabled
- Keyboard shortcuts active
- Advanced context menus
- Real-time status tracking

### Basic Mode
Running `toolbar.py` directly provides:
- Original functionality
- Basic script execution
- Standard UI components
- Legacy configuration support

## 🎛️ Configuration Files

The enhanced version uses multiple configuration files:

- **`taskbar_config.json`** - Legacy script and tray configuration
- **`taskbar_settings.ini`** - Enhanced settings (appearance, behavior, execution)
- **Execution History** - Stored in memory with configurable limits

## 🔧 Supported File Types

### Direct Execution
- **Python** (`.py`) - `python script.py`
- **JavaScript** (`.js`) - `node script.js`
- **TypeScript** (`.ts`) - `ts-node script.ts`
- **Batch** (`.bat`, `.cmd`) - Direct execution
- **PowerShell** (`.ps1`) - `powershell -ExecutionPolicy Bypass`
- **Shell Scripts** (`.sh`) - `bash script.sh`
- **Executables** (`.exe`) - Direct execution

### Compile & Run
- **Rust** (`.rs`) - `rustc` → execute
- **Go** (`.go`) - `go run`
- **Java** (`.java`) - `javac` → `java`
- **C++** (`.cpp`) - `g++` → execute
- **C** (`.c`) - `gcc` → execute
- **Ruby** (`.rb`) - `ruby script.rb`
- **PHP** (`.php`) - `php script.php`

## 🎨 Customization

### Themes
- Modern violet/purple theme (VS Code inspired)
- Customizable transparency (10-100%)
- Configurable colors and fonts

### Layout
- Horizontal scrollable button layout
- Resizable and repositionable
- Auto-positioning relative to system taskbar

### Icons
- Custom icon support for scripts and trays
- Windows native icon extraction
- Icon editor with preview

## 🔍 Troubleshooting

### Enhanced Features Not Loading
```bash
# Check if all service files are present
ls toolbar_services.py toolbar_ui_components.py toolbar_enhanced.py

# Run with error output
python main_enhancement.py 2>&1
```

### Missing Dependencies
```bash
# Install missing packages
pip install psutil configparser

# For Windows features
pip install pywin32

# For image processing
pip install Pillow
```

### Performance Issues
- Reduce execution history limit in settings
- Disable animations in appearance settings
- Lower transparency for better performance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with both basic and enhanced modes
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with Python and Tkinter
- Inspired by VS Code's design language
- Enhanced with modern software engineering practices
- Community-driven feature development

---

## 📝 Original Project Notes

### projects.py
When adding project - need to select:
- Project root folder
- setup.bat or setup.sh if in wsl2
- preview.bat or preview.sh if in wsl2
- Input port that is used for project

Pressing on projects icon representative would simply run setup.bat/sh & preview.bat/sh & open local chrome browser with set port - in other words to start project properly and open it's gui. User inputs 2 scripts locations + project root + gui port. Allows adding removing projects /changing their icons in tooltaskbar/ opening their folders from right click context menu selection in menu.

### tray.py (to create)
Trays - mini desktops - allows drag-drop from desktop/ moving to required places. Dialog tray should remember its last opened place and size. Should execute codefiles when pressed on, if right click show context menu and allow opening in editor to edit codefiles. Folders to open when clicked on - urls to open in new browser when clicked on / images to open when clicked on.
