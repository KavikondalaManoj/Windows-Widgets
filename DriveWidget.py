import sys, psutil, os, json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar,
    QHBoxLayout, QPushButton, QGraphicsDropShadowEffect, QLineEdit,
    QFrame, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QTimer, QRect, QSize
from PyQt6.QtGui import QColor

CONFIG_FILE = "drive_data.json"

class DriveWidget(QWidget):
    # Fixed sizes and margins for stability
    MIN_ICON_SIZE = QSize(40, 40)
    ICON_PADDING = 10 # Padding around the icon when visible
    
    # Space reserved at the bottom for the icon when restored
    BOTTOM_RESERVE = MIN_ICON_SIZE.height() + ICON_PADDING

    def __init__(self):
        super().__init__()
        self.custom_names = {}
        self.custom_drives = []
        self.is_minimized = False
        self.drag_position = None
        
        # Default position and size
        self.initial_pos = QPoint(100, 100) 
        # Increased height for icon space when restored
        self.full_geometry = QRect(self.initial_pos.x(), self.initial_pos.y(), 400, 250) 

        self.load_data()
        self.initUI()
        self.refresh_drives()
        
        self.move(self.initial_pos)

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set a minimum size to prevent the window from collapsing to 0x0
        self.setMinimumSize(self.MIN_ICON_SIZE)

        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(25)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(0, 0)

        # Main Layout (responsible for the entire window)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Content Frame (The large, main body of the UI)
        self.frame = QFrame()
        self.frame.setGraphicsEffect(self.shadow)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 80);
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 5px; 
                border-bottom-right-radius: 5px;
            }
        """)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(15, 15, 15, 15)
        self.frame_layout.setSpacing(10)

        # --- Top bar ---
        topbar = QHBoxLayout()
        self.title = QLabel("Drive Monitor")
        self.title.setStyleSheet("font-weight: bold; font-size: 16px; color: #000; background: transparent;")

        self.addBtn = self._create_button("+", self.add_drive)
        self.removeBtn = self._create_button("-", self.remove_drive)
        self.saveBtn = self._create_button("💾", self.save_data)
        self.closeBtn = QPushButton("x")
        self.closeBtn.setFixedSize(25, 25)
        self.closeBtn.setStyleSheet(self._close_btn_style())
        self.closeBtn.clicked.connect(self.close)


        topbar.addWidget(self.title)
        topbar.addStretch()
        topbar.addWidget(self.addBtn)
        topbar.addWidget(self.removeBtn)
        topbar.addWidget(self.saveBtn)
        topbar.addWidget(self.closeBtn)
        self.frame_layout.addLayout(topbar)

        # --- Drives list ---
        self.drive_layout = QVBoxLayout()
        self.frame_layout.addLayout(self.drive_layout)
        self.drive_layout.addStretch(1)

        frame_wrapper = QWidget()
        frame_wrapper_layout = QVBoxLayout(frame_wrapper)
        frame_wrapper_layout.setContentsMargins(0,0,0,0)
        frame_wrapper_layout.addWidget(self.frame)
        
        self.main_layout.addWidget(frame_wrapper) 
        
        # --- Spacer for the Icon Area ---
        self.main_layout.addSpacing(self.BOTTOM_RESERVE)

        # --- Toggle Button (Child Widget) ---
        self.toggleBtn = QPushButton("📊", self) 
        self.toggleBtn.setFixedSize(self.MIN_ICON_SIZE)
        self.toggleBtn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7; 
                color: white;
                border: 2px solid rgba(255, 255, 255, 180);
                border-radius: 20px;
                font-size: 18px;
            }
            QPushButton:hover { background-color: #0056a3; }
        """)
        self.toggleBtn.clicked.connect(self.toggle_window)
        
        # Initial position of button (bottom right)
        self.toggleBtn.move(
            self.full_geometry.width() - self.MIN_ICON_SIZE.width() - self.ICON_PADDING, 
            self.full_geometry.height() - self.MIN_ICON_SIZE.height() - self.ICON_PADDING
        )
        self.toggleBtn.show()


        # --- Hover Timer for Auto-Restore ---
        self.restore_timer = QTimer(self)
        self.restore_timer.setInterval(500) 
        self.restore_timer.setSingleShot(True)
        self.restore_timer.timeout.connect(self._auto_restore)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_drives)
        self.timer.start(5000)

    # --- Utility Functions ---

    def _create_button(self, text, handler):
        btn = QPushButton(text)
        btn.setFixedSize(25, 25)
        btn.setStyleSheet(self.btnStyle(is_move_button=False))
        btn.clicked.connect(handler)
        return btn

    def btnStyle(self, is_move_button=False):
        if is_move_button:
            return """
                QPushButton {
                    background-color: rgba(255,255,255,50);
                    border-radius: 11px;
                    font-size: 14px;
                    color: black;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,100);
                    color: black;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: rgba(255,255,255,120);
                    border-radius: 12px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(100,100,100,120);
                    color: white;
                }
            """

    def _close_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(255,255,255,120);
                border-radius: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #FF3B30;
                color: white;
            }
        """
        
    def load_data(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.custom_names = data.get("names", {})
                    self.custom_drives = data.get("drives", [])
        except Exception:
            self.custom_names = {}
            self.custom_drives = []

    def save_data(self):
        data = {"names": self.custom_names, "drives": self.custom_drives}
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clear_layout(item.layout())

    def move_drive(self, drive, direction):
        if drive in self.custom_drives:
            idx = self.custom_drives.index(drive)
            new_idx = idx + direction
            if 0 <= new_idx < len(self.custom_drives):
                self.custom_drives[idx], self.custom_drives[new_idx] = self.custom_drives[new_idx], self.custom_drives[idx]
                self.refresh_drives()

    def update_name(self, drive, edit):
        text = edit.text()
        if text.startswith("💾 ") or text.startswith("🌐 "):
            text = text[2:]

        self.custom_names[drive] = text
        self.save_data()
        
    def refresh_drives(self):
        for i in reversed(range(self.drive_layout.count())):
            item = self.drive_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                if i < self.drive_layout.count() - 1 or item.layout().count() > 0:
                     self._clear_layout(item.layout())

        if self.drive_layout.count() > 0:
            stretch_item = self.drive_layout.takeAt(self.drive_layout.count() - 1)
            if stretch_item and stretch_item.spacerItem():
                del stretch_item

        system_drives = [d.device for d in psutil.disk_partitions(all=False) if 'removable' not in d.opts and d.device.startswith(('A:', 'B:', 'C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:', '//', '\\\\'))]

        final_drives = []
        for d in self.custom_drives:
            if d not in final_drives:
                final_drives.append(d)

        for d in system_drives:
            if d not in final_drives:
                 final_drives.append(d)

        if sys.platform.startswith('win'):
            c_drive = next((drive for drive in final_drives if drive.lower().startswith('c:')), None)
            if c_drive and final_drives.index(c_drive) != 0:
                final_drives.remove(c_drive)
                final_drives.insert(0, c_drive)


        self.custom_drives = [d for d in final_drives if d not in system_drives]

        for d in final_drives:
            try:
                usage = psutil.disk_usage(d)
                total_gb = usage.total / (1024**3)
                free_gb = usage.free / (1024**3)
                used_percent = usage.percent

                if free_gb < 20.0:
                    progress_color = "#FF3B30"
                else:
                    progress_color = "#0078D7"

                mapped_icon = "🌐 " if d.startswith("\\\\") or d.startswith("//") else "💾 "
                drive_name = self.custom_names.get(d, mapped_icon + d)

                nameEdit = QLineEdit(drive_name)
                nameEdit.setStyleSheet("QLineEdit { border: none; background: transparent; font-size: 14px; color: #000; }")
                nameEdit.editingFinished.connect(lambda d=d, e=nameEdit: self.update_name(d, e))

                space_label = QLabel(f"{free_gb:.1f} GB free of {total_gb:.1f} GB")
                space_label.setStyleSheet("background: transparent;")

                up_btn = QPushButton("△")
                down_btn = QPushButton("▽")

                is_custom = d in self.custom_drives

                for btn in [up_btn, down_btn]:
                    btn.setFixedSize(22, 22)
                    btn.setStyleSheet(self.btnStyle(is_move_button=True))
                    btn.setEnabled(is_custom)

                if is_custom:
                    up_btn.clicked.connect(lambda _, d=d: self.move_drive(d, -1))
                    down_btn.clicked.connect(lambda _, d=d: self.move_drive(d, 1))

                progress = QProgressBar()
                progress.setRange(0, 100)
                progress.setValue(int(used_percent))
                progress.setTextVisible(False)
                progress.setFixedHeight(8)

                progress.setStyleSheet(f"""
                    QProgressBar {{
                        border: none; border-radius: 4px; background: rgba(255,255,255,80);
                    }}
                    QProgressBar::chunk {{
                        border-radius: 4px; background-color: {progress_color};
                    }}
                """)

                row = QHBoxLayout()
                row.addWidget(nameEdit)
                row.addWidget(space_label)
                if is_custom:
                    row.addWidget(up_btn)
                    row.addWidget(down_btn)

                row.setSpacing(5)

                col = QVBoxLayout()
                col.addLayout(row)
                col.addWidget(progress)
                col.setSpacing(5)
                col.setContentsMargins(10, 10, 10, 10)

                frame = QFrame()
                frame.setLayout(col)
                frame.setStyleSheet("""
                    QFrame {
                        background-color: rgba(255,255,255,140);
                        border-radius: 10px;
                    }
                """)

                self.drive_layout.addWidget(frame)

            except Exception:
                pass

        self.drive_layout.addStretch(1)

        self.adjustSize()
        self.save_data()
        
        # Reposition the button to the bottom right corner of the dedicated space
        if not self.is_minimized:
            self.toggleBtn.move(self.width() - self.MIN_ICON_SIZE.width() - self.ICON_PADDING, 
                                self.height() - self.MIN_ICON_SIZE.height() - self.ICON_PADDING)


    def add_drive(self):
        path, ok = QInputDialog.getText(self, "Add Drive", "Enter drive path (e.g. D:\\ or \\\\network\\share):")
        if ok and path:
            path = path.strip()
            if not path: return

            normalized_path = os.path.normpath(path)
            if os.path.exists(normalized_path):
                is_system_drive = normalized_path in [d.device for d in psutil.disk_partitions(all=False)]
                if normalized_path not in self.custom_drives and not is_system_drive:
                    self.custom_drives.append(normalized_path)
                self.refresh_drives()
            else:
                QMessageBox.warning(self, "Invalid", "Drive path not found or is inaccessible.")

    def remove_drive(self):
        if not self.custom_drives:
            QMessageBox.information(self, "Info", "No custom drives to remove.")
            return

        drive_names = [self.custom_names.get(d, d) for d in self.custom_drives]
        drive_name, ok = QInputDialog.getItem(
            self, "Remove Drive", "Select drive to remove:", drive_names, 0, False
        )

        if ok and drive_name:
            original_path = None
            for path, name in self.custom_names.items():
                if name == drive_name:
                    original_path = path
                    break

            if not original_path:
                for path in self.custom_drives:
                     mapped_icon = "🌐 " if path.startswith("\\\\") or path.startswith("//") else "💾 "
                     default_name = mapped_icon + path
                     if drive_name == default_name:
                         original_path = path
                         break

            if original_path and original_path in self.custom_drives:
                self.custom_drives.remove(original_path)
                if original_path in self.custom_names:
                    del self.custom_names[original_path]
                self.refresh_drives()
            else:
                QMessageBox.warning(self, "Error", "Could not identify the drive to remove.")


    # --- Drag, Hover, and Toggle Logic (Finalized Fixes) ---
    
    def mousePressEvent(self, event):
        if (not self.is_minimized and self.frame.geometry().contains(event.pos())) or \
           (self.is_minimized and self.toggleBtn.geometry().contains(event.pos())):
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            try:
                self.move(new_pos)
                self.full_geometry = self.geometry()
            except Exception as e:
                print(f"Move Error: {e}")
                pass 

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        if not self.is_minimized:
            self.full_geometry = self.geometry()

    def enterEvent(self, event):
        if self.is_minimized:
            self.restore_timer.start()

    def leaveEvent(self, event):
        if self.restore_timer.isActive():
            self.restore_timer.stop()

    def _auto_restore(self):
        if self.is_minimized:
            self.toggle_window()

    def toggle_window(self):
        button_size = self.MIN_ICON_SIZE
        icon_padding = self.ICON_PADDING
        
        if not self.is_minimized:
            # ---------------------
            # MINIMIZE
            # ---------------------
            
            self.full_geometry = self.geometry() 
            
            # Calculate minimized position to keep the button exactly where it is on screen
            target_x = self.full_geometry.x() + self.full_geometry.width() - button_size.width() - icon_padding
            target_y = self.full_geometry.y() + self.full_geometry.height() - button_size.height() - icon_padding
            
            # Minimized window size is exactly the size of the button
            target_rect = QRect(
                target_x,
                target_y,
                button_size.width(),
                button_size.height()
            )

            self.frame.hide()
            
            # Apply minimized geometry with crash prevention
            try:
                self.setGeometry(target_rect)
            except Exception as e:
                print(f"Minimize SetGeometry Failed (Ignored): {e}")
                
            self.toggleBtn.move(0, 0) # Button is moved to the top-left of the new, tiny window
            self.update() # Explicit repaint to force visibility (New)

            self.is_minimized = True
            
        else:
            # ---------------------
            # RESTORE
            # ---------------------
            
            current_x = self.geometry().x()
            current_y = self.geometry().y()
            
            # Calculate the position where the button *was* placed inside the full window
            button_offset_x = self.full_geometry.width() - button_size.width() - icon_padding
            button_offset_y = self.full_geometry.height() - button_size.height() - icon_padding
            
            # Calculate the new top-left corner of the full window
            new_full_x = current_x - button_offset_x
            new_full_y = current_y - button_offset_y
            
            final_rect = QRect(new_full_x, new_full_y, self.full_geometry.width(), self.full_geometry.height())
            
            # Apply restored geometry with crash prevention
            try:
                self.setGeometry(final_rect)
            except Exception as e:
                print(f"Restore SetGeometry Failed (Ignored): {e}")
                
            # Button is moved back to the bottom-right corner of the restored window
            self.toggleBtn.move(self.width() - button_size.width() - icon_padding, 
                                self.height() - button_size.height() - icon_padding)
            self.frame.show()
            self.update() # Explicit repaint (New)
            self.is_minimized = False

# --- Application Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DriveWidget()
    window.show()
    sys.exit(app.exec())