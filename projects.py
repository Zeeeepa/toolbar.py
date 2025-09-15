import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLineEdit,
    QMenu,
    QLabel,
    QTextEdit,
)
from PyQt5.QtWidgets import (
    QDialog,
    QSizePolicy,
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal, QPoint, QSize
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout
import json
from PyQt5.QtCore import QTimer
import logging
import webbrowser
import os


class projectWidget(QWidget):
    taskChanged = pyqtSignal()

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.tasks = []
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(2)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.project_button = QPushButton(self.name)
        self.project_button.clicked.connect(self.toggle_tasks_display)
        self.project_button.setStyleSheet(
            "font-weight: bold; background-color: #0c231e;"
        )
        self.project_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_button.customContextMenuRequested.connect(self.on_right_click)
        self.layout.addWidget(self.project_button)
        self.setLayout(self.layout)
        for func_widget in self.tasks:
            func_widget.setVisible(False)

    def toggle_tasks_display(self):
        for func_widget in self.tasks:
            func_widget.setVisible(not func_widget.isVisible())
        QTimer.singleShot(50, self.parent().adjust_size)

    def on_right_click(self, position):
        context_menu = QMenu(self)
        add_action = context_menu.addAction("Add task")
        move_up_action = context_menu.addAction("Move Up")
        move_down_action = context_menu.addAction("Move Down")
        edit_name_action = context_menu.addAction("Edit Name")
        action = context_menu.exec_(self.mapToGlobal(position))

        if action == add_action:
            self.add_task()
        elif action == move_up_action:
            self.move_up()
        elif action == move_down_action:
            self.move_down()
        elif action == edit_name_action:
            self.edit_name()

    def edit_name(self):
        new_name, ok = QInputDialog.getText(
            self,
            "Edit project Name",
            "Enter the new name:",
            QLineEdit.Normal,
            self.name,
        )
        if ok and new_name:
            self.name = new_name
            self.project_button.setText(new_name)
            self.parent()

    def move_up(self):
        index = self.parent().project_widgets.index(self)
        if index > 0:
            self.parent().project_widgets.insert(
                index - 1, self.parent().project_widgets.pop(index)
            )
            self.parent().layout().insertWidget(index - 1, self)
            self.taskChanged.emit()
        else:
            QMessageBox.warning(self, "Move Up", "Not Possible to move further up.")

    def move_down(self):
        index = self.parent().project_widgets.index(self)
        if index < len(self.parent().project_widgets) - 1:
            self.parent().project_widgets.insert(
                index + 1, self.parent().project_widgets.pop(index)
            )
            self.parent().layout().insertWidget(index + 1, self)
            self.taskChanged.emit()
        else:
            QMessageBox.warning(self, "Move Down", "Not Possible to move further down.")

    def add_task(self):
        task_name, ok = InputDialog.get_input("Enter task Name:", self)
        if ok:
            task_widget = taskWidget(task_name, self)
            self.tasks.append(task_widget)
            self.layout.addWidget(task_widget)
            task_widget.setVisible(True)
            logging.info(f"Task '{task_name}' added to project '{self.name}'.")
            self.taskChanged.emit()
            self.parent().save_combined_data()

    def delete_project(self):
        for task_widget in self.tasks:
            task_widget.deleteLater()
        self.deleteLater()
        self.parent().load_combined_data()
        self.taskChanged.emit()


class taskWidget(QWidget):
    def __init__(self, name, parent=None):
        super(taskWidget, self).__init__(parent)
        self.name = name
        self.url = ""
        self.noteText = ""
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.task_label = QLabel(self.name, self)
        self.task_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.url_button = QPushButton("URL", self)
        self.url_button.setMaximumSize(
            QSize(
                self.url_button.sizeHint().width(), self.url_button.sizeHint().height()
            )
        )
        self.url_button.clicked.connect(self.open_url)
        self.url_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.url_button.customContextMenuRequested.connect(
            self.on_url_button_right_click
        )
        self.update_url_button_appearance()

        self.note_button = QPushButton("Note", self)
        self.note_button.clicked.connect(self.edit_note)
        self.note_button.setMaximumSize(
            QSize(
                self.note_button.sizeHint().width(),
                self.note_button.sizeHint().height(),
            )
        )
        self.update_note_button_appearance()

        self.copy_button = QPushButton("Copy", self)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setMaximumSize(
            QSize(
                self.copy_button.sizeHint().width(),
                self.copy_button.sizeHint().height(),
            )
        )

        self.edit_button = QPushButton("Edit", self)
        self.edit_button.clicked.connect(self.edit_task)
        self.edit_button.setMaximumSize(
            QSize(
                self.edit_button.sizeHint().width(),
                self.edit_button.sizeHint().height(),
            )
        )

        self.delete_button = QPushButton("Delete", self)
        self.delete_button.clicked.connect(self.delete_task)
        self.delete_button.setMaximumSize(
            QSize(
                self.delete_button.sizeHint().width(),
                self.delete_button.sizeHint().height(),
            )
        )

        layout.addWidget(self.task_label)
        layout.addWidget(self.url_button)
        layout.addWidget(self.note_button)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.edit_button)
        layout.addWidget(self.delete_button)

        self.setLayout(layout)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_right_click)

    def open_url(self):
        if self.url:
            webbrowser.open(self.url)
        else:
            QMessageBox.warning(self, "URL", "No URL provided.")

    def edit_url(self):
        url, ok = QInputDialog.getText(
            self, "Edit URL", "Enter URL:", QLineEdit.Normal, self.url
        )
        if ok and url:
            self.url = url
            self.update_url_button_appearance()

    def on_url_button_right_click(self, position):
        context_menu = QMenu(self)
        edit_action = context_menu.addAction("Edit URL")
        action = context_menu.exec_(self.url_button.mapToGlobal(position))
        if action == edit_action:
            self.edit_url()

    def update_url_button_appearance(self):
        if self.url:
            self.url_button.setStyleSheet("""
                QPushButton {
                    background-color: #ff2a00;
                    color: #153c33;
                    border: 1px solid #ff2a00;
                }
                QPushButton:hover {
                    background-color: #ff2a00;
                    color: #153c33;
                }
            """)
        else:
            self.url_button.setStyleSheet("")

    def edit_note(self):
        self.noteDialog = QDialog(self)
        layout = QVBoxLayout(self.noteDialog)
        self.noteTextEditor = QTextEdit()
        self.noteTextEditor.setText(self.noteText)
        layout.addWidget(self.noteTextEditor)

        if self.name in self.parent().parent().dialogSizes:
            width, height = self.parent().parent().dialogSizes[self.name]
            self.noteDialog.resize(width, height)
        else:
            self.noteDialog.resize(400, 200)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(
            lambda: self.save_note_and_size(self.noteTextEditor.toPlainText())
        )
        buttonBox.rejected.connect(self.noteDialog.reject)
        layout.addWidget(buttonBox)
        self.noteDialog.setLayout(layout)
        self.noteDialog.setWindowTitle("Edit Note")
        self.noteDialog.exec_()
        self.update_note_button_appearance()

    def update_note_button_appearance(self):
        if self.noteText:
            self.note_button.setStyleSheet("""
                QPushButton {
                    background-color: #ff2a00;
                    color: #153c33;
                    border: 1px solid #ff2a00;
                }
                QPushButton:hover {
                    background-color: #ff2a00;
                    color: #153c33;
                }
            """)
        else:
            self.note_button.setStyleSheet("")

    def save_note_and_size(self, text):
        self.noteText = text
        self.parent().parent().dialogSizes[self.name] = (
            self.noteDialog.width(),
            self.noteDialog.height(),
        )
        self.parent().parent()
        self.noteDialog.accept()

    def on_right_click(self, position):
        context_menu = QMenu(self)
        add_action = context_menu.addAction("Add Function")
        action = context_menu.exec_(self.mapToGlobal(position))
        if action == add_action:
            self.add_function()

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.name)

    def edit_task(self):
        new_name, ok = InputDialog.get_input("Edit task Name:", self, self.name)
        if ok:
            self.name = new_name
            self.task_label.setText(new_name)
            self.parent().parent()

    def delete_task(self):
        self.parent().tasks.remove(self)
        self.deleteLater()
        self.parent().parent()


class InputDialog(QDialog):
    def __init__(self, prompt, default_text=""):
        super(InputDialog, self).__init__()
        self.setWindowTitle(prompt)
        self.input = QLineEdit(self)
        self.input.setText(default_text)
        layout = QVBoxLayout()
        layout.addWidget(self.input)
        add_button = QPushButton("OK", self)
        add_button.clicked.connect(self.accept)
        layout.addWidget(add_button)
        self.setLayout(layout)

    @staticmethod
    def get_input(prompt, parent=None, default_text=""):
        dialog = InputDialog(prompt, default_text)
        result = dialog.exec_()
        return (dialog.input.text(), result == QDialog.Accepted)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.data_folder = r"C:\Database\Notes"
        self.combined_file_name = "comments.json"
        self.dialogSizes = {}
        self.project_widgets = []
        self.last_saved_state = {}

        self.ensure_data_folder_exists()
        self.init_ui()
        self.apply_stylesheet()
        self.load_combined_data()
        self.setup_auto_save()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowOpacity(0.78)
        self.oldPos = self.pos()

    def ensure_data_folder_exists(self):
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()

    def init_ui(self):
        self.setWindowTitle("Modular Notebook")
        main_layout = QVBoxLayout(self)
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(4)

        self.add_project_button = QPushButton("Add")
        self.add_project_button.clicked.connect(self.add_project)
        self.add_project_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        action_buttons_layout.addWidget(self.add_project_button)

        self.delete_project_button = QPushButton("Delete")
        self.delete_project_button.clicked.connect(self.delete_project)
        self.delete_project_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        action_buttons_layout.addWidget(self.delete_project_button)

        self.export_project_button = QPushButton("Export")
        self.export_project_button.clicked.connect(self.export_project)
        self.export_project_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        action_buttons_layout.addWidget(self.export_project_button)

        self.import_project_button = QPushButton("Import")
        self.import_project_button.clicked.connect(self.import_project)
        self.import_project_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        action_buttons_layout.addWidget(self.import_project_button)

        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.close)
        self.exit_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        action_buttons_layout.addWidget(self.exit_button)

        main_layout.addLayout(action_buttons_layout)
        main_layout.setSpacing(2)
        main_layout.addLayout(action_buttons_layout)

        self.setLayout(main_layout)

    def save_combined_data(self):
        combined_data = {
            "projects": {
                project_widget.name: [
                    task_widget.name for task_widget in project_widget.tasks
                ]
                for project_widget in self.project_widgets
            },
            "notes": {
                task_widget.name: task_widget.noteText
                for project_widget in self.project_widgets
                for task_widget in project_widget.tasks
                if task_widget.noteText
            },
            "urls": {
                task_widget.name: task_widget.url
                for project_widget in self.project_widgets
                for task_widget in project_widget.tasks
                if task_widget.url
            },
        }
        with open(os.path.join(self.data_folder, self.combined_file_name), "w") as file:
            json.dump(combined_data, file, indent=4)

    def load_combined_data(self):
        try:
            with open(
                os.path.join(self.data_folder, self.combined_file_name), "r"
            ) as file:
                combined_data = json.load(file)
                for project_name, tasks in combined_data.get("projects", {}).items():
                    project_widget = projectWidget(project_name, self)
                    for task_name in tasks:
                        task_widget = taskWidget(task_name, project_widget)
                        project_widget.tasks.append(task_widget)
                        project_widget.layout.addWidget(task_widget)
                        task_widget.setVisible(False)
                    self.layout().addWidget(project_widget)
                    self.project_widgets.append(project_widget)
                for task_name, noteText in combined_data.get("notes", {}).items():
                    for project_widget in self.project_widgets:
                        for task_widget in project_widget.tasks:
                            if task_widget.name == task_name:
                                task_widget.noteText = noteText
                                task_widget.update_note_button_appearance()
                for task_name, url in combined_data.get("urls", {}).items():
                    for project_widget in self.project_widgets:
                        for task_widget in project_widget.tasks:
                            if task_widget.name == task_name:
                                task_widget.url = url
                                task_widget.update_url_button_appearance()
        except FileNotFoundError:
            pass

    def closeEvent(self, event):
        if self.state_has_changed():
            reply = QMessageBox.question(
                self,
                "Save Changes",
                "There are unsaved changes. Would you like to save before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Yes:
                self.save_combined_data()
                event.accept()
            elif reply == QMessageBox.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def setup_auto_save(self):
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.save_combined_data)
        self.auto_save_timer.start(300000)

    def export_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "Text Files (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as file:
                for project_widget in self.project_widgets:
                    file.write("'" + project_widget.name + "'\n")
                    for func_widget in project_widget.tasks:
                        file.write(func_widget.name + "\n")
                    file.write(".\n")

    def get_current_state(self):
        return {
            project_widget.name: [
                func_widget.name for func_widget in project_widget.tasks
            ]
            for project_widget in self.project_widgets
        }

    def state_has_changed(self):
        current_state = self.get_current_state()
        return current_state != self.last_saved_state

    def import_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "JSON Files (*.json)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
                for project_name, tasks in data.get("projects", {}).items():
                    project_widget = projectWidget(project_name, self)
                    self.project_widgets.append(project_widget)
                    self.layout().addWidget(project_widget)
                    for task_name in tasks:
                        task_widget = taskWidget(task_name, project_widget)
                        project_widget.tasks.append(task_widget)
                        project_widget.layout.addWidget(task_widget)
                self.setUpdatesEnabled(True)
                self.save_combined_data()
                QMessageBox.information(
                    self, "Import Successful", "Projects imported successfully."
                )
                self.adjust_size()
                self.update_last_saved_state()
                logging.info("Imported projects from " + path)

    def update_last_saved_state(self):
        self.last_saved_state = self.get_current_state()
        logging.info("Updated last saved state.")

    def delete_project(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Delete project")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget(dialog)
        for project_widget in self.project_widgets:
            QListWidgetItem(project_widget.name, list_widget)
        layout.addWidget(list_widget)
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.rejected.connect(dialog.reject)
        layout.addWidget(buttonBox)

        if dialog.exec_() == QDialog.Accepted:
            selected_items = list_widget.selectedItems()
            if selected_items:
                selected_project_name = selected_items[0].text()
                for project_widget in self.project_widgets:
                    if project_widget.name == selected_project_name:
                        self.project_widgets.remove(project_widget)
                        project_widget.deleteLater()
                        self.update_last_saved_state()
                        logging.info(f"Deleted project: {selected_project_name}")
                        break
                QMessageBox.information(
                    self, "Deletion", f"project '{selected_project_name}' deleted."
                )
            else:
                QMessageBox.warning(
                    self, "Deletion", "No project selected for deletion."
                )

    def add_project(self):
        project_name, ok = InputDialog.get_input("Enter project Name:", self)
        if (
            ok
            and project_name
            and not any(
                project_widget.name == project_name
                for project_widget in self.project_widgets
            )
        ):
            project_widget = projectWidget(project_name, self)
            self.layout().addWidget(project_widget)
            self.project_widgets.append(project_widget)
            logging.info(f"project '{project_name}' added.")
            self.save_combined_data()
        else:
            QMessageBox.warning(
                self, "Warning", "project name must be unique and not empty."
            )

    def adjust_size(self):
        self.resize(self.layout().sizeHint())

    def apply_stylesheet(self):
        stylesheet = """
        QWidget {
            background-color: rgba(0, 10, 0, 0.85);
        }
        QPushButton {
            background-color: #0a1a0a;
            color: #39FF14;
            border: 1px solid #39FF14;
            padding: 2px 2px;
        }
        QPushButton:disabled {
            background-color: #1a2a1a;
            color: #2a5a2a;
        }
        QPushButton:hover {
            background-color: #39FF14;
            color: #0a1a0a;
        }
        QComboBox, QTextEdit, QLineEdit {
            background-color: #0a1a0a;
            color: #39FF14;
            border: 1px solid #39FF14;
        }
        QLabel {
            color: #39FF14;
        }
        """
        self.setStyleSheet(stylesheet)


logging.basicConfig(
    level=logging.DEBUG,
    filename="app.log",
    filemode="w",
    format="%(name)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    stylesheet = """
        QDialog {
            background-color: #0E1131;
            color: #ff2a00;
        }
    """
    app.setStyleSheet(stylesheet)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
