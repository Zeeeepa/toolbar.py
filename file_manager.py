"""
FileManager - Enhanced file management with renaming, folder opening, and editor integration
"""
import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FileManager:
    """Manages file operations including renaming, folder opening, and editor integration"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.config_file = self.data_dir / "file_manager_config.json"
        self.config = self._load_config()
        
        # Default editor configurations
        self.default_editors = {
            'vscode': {
                'name': 'Visual Studio Code',
                'executable': 'code',
                'args': ['{file_path}'],
                'check_command': 'code --version'
            },
            'notepadpp': {
                'name': 'Notepad++',
                'executable': 'notepad++',
                'args': ['{file_path}'],
                'check_command': 'notepad++ --version'
            },
            'sublime': {
                'name': 'Sublime Text',
                'executable': 'subl',
                'args': ['{file_path}'],
                'check_command': 'subl --version'
            },
            'atom': {
                'name': 'Atom',
                'executable': 'atom',
                'args': ['{file_path}'],
                'check_command': 'atom --version'
            },
            'vim': {
                'name': 'Vim',
                'executable': 'vim',
                'args': ['{file_path}'],
                'check_command': 'vim --version'
            },
            'notepad': {
                'name': 'Notepad',
                'executable': 'notepad',
                'args': ['{file_path}'],
                'check_command': None  # Always available on Windows
            }
        }
        
        # Detect available editors
        self.available_editors = self._detect_editors()
    
    def _load_config(self) -> Dict:
        """Load file manager configuration"""
        default_config = {
            'default_editor': 'vscode',
            'custom_editors': {},
            'file_associations': {},
            'recent_folders': [],
            'max_recent_folders': 10
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception as e:
            logger.error(f"Error loading file manager config: {e}")
        
        return default_config
    
    def _save_config(self):
        """Save file manager configuration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving file manager config: {e}")
    
    def _detect_editors(self) -> Dict[str, Dict]:
        """Detect available editors on the system"""
        available = {}
        
        for editor_id, editor_info in self.default_editors.items():
            if self._is_editor_available(editor_info):
                available[editor_id] = editor_info
        
        # Add custom editors from config
        for editor_id, editor_info in self.config.get('custom_editors', {}).items():
            if self._is_editor_available(editor_info):
                available[editor_id] = editor_info
        
        logger.info(f"Detected {len(available)} available editors: {list(available.keys())}")
        return available
    
    def _is_editor_available(self, editor_info: Dict) -> bool:
        """Check if an editor is available on the system"""
        if not editor_info.get('check_command'):
            # For editors without version check (like notepad), assume available on Windows
            return os.name == 'nt' if editor_info['executable'] == 'notepad' else True
        
        try:
            result = subprocess.run(
                editor_info['check_command'].split(),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False
    
    def rename_file(self, old_path: str, new_name: str) -> Tuple[bool, str]:
        """Rename a file"""
        try:
            old_path = Path(old_path)
            if not old_path.exists():
                return False, f"File not found: {old_path}"
            
            # Validate new name
            if not new_name or '/' in new_name or '\\' in new_name:
                return False, "Invalid filename"
            
            new_path = old_path.parent / new_name
            
            if new_path.exists():
                return False, f"File already exists: {new_name}"
            
            old_path.rename(new_path)
            logger.info(f"Renamed file: {old_path} -> {new_path}")
            return True, str(new_path)
            
        except Exception as e:
            error_msg = f"Error renaming file: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def open_folder(self, file_path: str) -> bool:
        """Open the folder containing the file in file explorer"""
        try:
            path = Path(file_path)
            folder_path = path.parent if path.is_file() else path
            
            if not folder_path.exists():
                logger.error(f"Folder not found: {folder_path}")
                return False
            
            # Add to recent folders
            self._add_recent_folder(str(folder_path))
            
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', str(folder_path)], check=True)
            elif os.name == 'posix':  # Linux/Mac
                if shutil.which('xdg-open'):  # Linux
                    subprocess.run(['xdg-open', str(folder_path)], check=True)
                elif shutil.which('open'):  # Mac
                    subprocess.run(['open', str(folder_path)], check=True)
                else:
                    logger.error("No file manager found")
                    return False
            
            logger.info(f"Opened folder: {folder_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error opening folder: {e}")
            return False
    
    def open_in_editor(self, file_path: str, editor_id: str = None, line_number: int = None) -> bool:
        """Open file in specified editor"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False
            
            # Use default editor if none specified
            if not editor_id:
                editor_id = self.config.get('default_editor', 'vscode')
            
            # Check if editor is available
            if editor_id not in self.available_editors:
                logger.error(f"Editor not available: {editor_id}")
                return False
            
            editor_info = self.available_editors[editor_id]
            
            # Build command
            cmd = [editor_info['executable']]
            
            # Add arguments
            for arg in editor_info['args']:
                if '{file_path}' in arg:
                    cmd.append(arg.replace('{file_path}', file_path))
                elif '{line_number}' in arg and line_number:
                    cmd.append(arg.replace('{line_number}', str(line_number)))
                else:
                    cmd.append(arg)
            
            # Add line number for supported editors
            if line_number and editor_id == 'vscode':
                cmd.extend(['--goto', f"{file_path}:{line_number}"])
            elif line_number and editor_id == 'sublime':
                cmd.append(f"{file_path}:{line_number}")
            
            # Execute command
            subprocess.Popen(cmd, cwd=os.path.dirname(file_path))
            logger.info(f"Opened file in {editor_info['name']}: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error opening file in editor: {e}")
            return False
    
    def get_available_editors(self) -> Dict[str, str]:
        """Get list of available editors"""
        return {editor_id: info['name'] for editor_id, info in self.available_editors.items()}
    
    def set_default_editor(self, editor_id: str) -> bool:
        """Set default editor"""
        if editor_id not in self.available_editors:
            return False
        
        self.config['default_editor'] = editor_id
        self._save_config()
        return True
    
    def add_custom_editor(self, editor_id: str, name: str, executable: str, 
                         args: List[str], check_command: str = None) -> bool:
        """Add custom editor configuration"""
        editor_info = {
            'name': name,
            'executable': executable,
            'args': args,
            'check_command': check_command
        }
        
        # Test if editor is available
        if not self._is_editor_available(editor_info):
            return False
        
        self.config['custom_editors'][editor_id] = editor_info
        self.available_editors[editor_id] = editor_info
        self._save_config()
        return True
    
    def remove_custom_editor(self, editor_id: str) -> bool:
        """Remove custom editor"""
        if editor_id in self.config.get('custom_editors', {}):
            del self.config['custom_editors'][editor_id]
            if editor_id in self.available_editors:
                del self.available_editors[editor_id]
            self._save_config()
            return True
        return False
    
    def set_file_association(self, file_extension: str, editor_id: str) -> bool:
        """Set file association for specific extension"""
        if editor_id not in self.available_editors:
            return False
        
        self.config['file_associations'][file_extension] = editor_id
        self._save_config()
        return True
    
    def get_editor_for_file(self, file_path: str) -> str:
        """Get appropriate editor for file based on extension"""
        ext = Path(file_path).suffix.lower()
        return self.config.get('file_associations', {}).get(ext, self.config.get('default_editor', 'vscode'))
    
    def _add_recent_folder(self, folder_path: str):
        """Add folder to recent folders list"""
        recent = self.config.get('recent_folders', [])
        
        # Remove if already exists
        if folder_path in recent:
            recent.remove(folder_path)
        
        # Add to beginning
        recent.insert(0, folder_path)
        
        # Limit size
        max_recent = self.config.get('max_recent_folders', 10)
        self.config['recent_folders'] = recent[:max_recent]
        self._save_config()
    
    def get_recent_folders(self) -> List[str]:
        """Get list of recent folders"""
        return self.config.get('recent_folders', [])
    
    def clear_recent_folders(self):
        """Clear recent folders list"""
        self.config['recent_folders'] = []
        self._save_config()
    
    def copy_file(self, source_path: str, dest_path: str) -> Tuple[bool, str]:
        """Copy file to destination"""
        try:
            source = Path(source_path)
            dest = Path(dest_path)
            
            if not source.exists():
                return False, f"Source file not found: {source_path}"
            
            if dest.exists():
                return False, f"Destination already exists: {dest_path}"
            
            # Create destination directory if needed
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source, dest)
            logger.info(f"Copied file: {source} -> {dest}")
            return True, str(dest)
            
        except Exception as e:
            error_msg = f"Error copying file: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def move_file(self, source_path: str, dest_path: str) -> Tuple[bool, str]:
        """Move file to destination"""
        try:
            source = Path(source_path)
            dest = Path(dest_path)
            
            if not source.exists():
                return False, f"Source file not found: {source_path}"
            
            if dest.exists():
                return False, f"Destination already exists: {dest_path}"
            
            # Create destination directory if needed
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(source), str(dest))
            logger.info(f"Moved file: {source} -> {dest}")
            return True, str(dest)
            
        except Exception as e:
            error_msg = f"Error moving file: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def delete_file(self, file_path: str, to_trash: bool = True) -> Tuple[bool, str]:
        """Delete file (optionally to trash)"""
        try:
            path = Path(file_path)
            if not path.exists():
                return False, f"File not found: {file_path}"
            
            if to_trash:
                # Try to use system trash
                try:
                    if os.name == 'nt':  # Windows
                        import winshell
                        winshell.delete_file(str(path))
                    else:
                        # For Linux/Mac, try using trash-cli or similar
                        if shutil.which('trash'):
                            subprocess.run(['trash', str(path)], check=True)
                        elif shutil.which('gio'):
                            subprocess.run(['gio', 'trash', str(path)], check=True)
                        else:
                            # Fallback to permanent deletion
                            path.unlink()
                except ImportError:
                    # Fallback to permanent deletion
                    path.unlink()
            else:
                path.unlink()
            
            logger.info(f"Deleted file: {file_path}")
            return True, "File deleted successfully"
            
        except Exception as e:
            error_msg = f"Error deleting file: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """Get detailed file information"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            stat = path.stat()
            
            return {
                'name': path.name,
                'path': str(path.absolute()),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'extension': path.suffix.lower(),
                'is_file': path.is_file(),
                'is_directory': path.is_dir(),
                'parent': str(path.parent)
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    def create_backup(self, file_path: str, backup_dir: str = None) -> Tuple[bool, str]:
        """Create backup of file"""
        try:
            source = Path(file_path)
            if not source.exists():
                return False, f"File not found: {file_path}"
            
            if not backup_dir:
                backup_dir = source.parent / "backups"
            
            backup_dir = Path(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source.stem}_{timestamp}{source.suffix}"
            backup_path = backup_dir / backup_name
            
            shutil.copy2(source, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return True, str(backup_path)
            
        except Exception as e:
            error_msg = f"Error creating backup: {e}"
            logger.error(error_msg)
            return False, error_msg
