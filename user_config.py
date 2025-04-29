from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QStandardItemModel, QStandardItem, QFont, QImage
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QProgressBar, QTreeView, QLineEdit, QCompleter)
import asyncio
from qasync import asyncSlot
import multilayer_auv
import cv2
import numpy as np


class UserConfig(QWidget):
    def __init__(self):
        super().__init__()
        self.rpc_url = "http://192.168.137.219:8888/  "
        self.video_url = "rtsp://rov:rov@192.168.137.132:554/"
        self.rpc_url_edit_line = QLineEdit()
        self.video_url_edit_line = QLineEdit()
        self.init_ui()

    def init_ui(self):
        rpc_text_tip = QLabel("通讯设置：机器URL")
        video_text_tip = QLabel("视频设置：RTSP视频流URL")

        rpc_save_button = QPushButton('保存')
        rpc_save_button.setFixedWidth(40)
        rpc_save_button.clicked.connect(self.save_rpc_url)
        video_save_button = QPushButton('保存')
        video_save_button.setFixedWidth(40)
        video_save_button.clicked.connect(self.save_video_url)

        rpc_url_edit_line = self.rpc_url_edit_line
        rpc_url_edit_line.setFixedWidth(250)
        rpc_url_edit_line.setText(self.rpc_url)
        rpc_url_edit_line.setCompleter(QCompleter(["http://192.168.137.219:8888/  "]))

        video_url_edit_line = self.video_url_edit_line
        video_url_edit_line.setFixedWidth(250)
        video_url_edit_line.setText(self.video_url)
        video_url_edit_line.setCompleter(QCompleter(["rtsp://rov:rov@192.168.137.123:554/",
                                                     "rtsp://rov:rov@192.168.137.132:554/"]))

        main_layout = QVBoxLayout()
        main_layout.addWidget(rpc_text_tip)
        main_layout.addWidget(rpc_url_edit_line)
        main_layout.addWidget(rpc_save_button)
        main_layout.addWidget(video_text_tip)
        main_layout.addWidget(video_url_edit_line)
        main_layout.addWidget(video_save_button)

        self.setFixedWidth(300)
        self.setFixedHeight(220)  # 增加高度以容纳拨动开关

        self.setLayout(main_layout)

    def text_show_again(self):
        self.rpc_url_edit_line.setText(self.rpc_url)
        self.video_url_edit_line.setText(self.video_url)

    def save_rpc_url(self):
        self.rpc_url = self.rpc_url_edit_line.text()
        self.rpc_url_edit_line.setText(self.rpc_url)

    def save_video_url(self):
        self.video_url = self.video_url_edit_line.text()
        self.video_url_edit_line.setText(self.video_url)

    def lock_rpc_url_edit(self, state: bool):
        self.rpc_url_edit_line.setReadOnly(state)
        if self.rpc_url_edit_line.isReadOnly():
            self.rpc_url_edit_line.setStyleSheet("""
                    background-color: gray;
                """)
        else:
            self.rpc_url_edit_line.setStyleSheet("""
                        background-color: white; 
                """)

    def lock_video_url_edit(self, state: bool):
        self.video_url_edit_line.setReadOnly(state)
        if self.video_url_edit_line.isReadOnly():
            self.video_url_edit_line.setStyleSheet("""
                    background-color: gray;
                """)
        else:
            self.video_url_edit_line.setStyleSheet("""
                        background-color: white; 
                """)

    def lock_edit_line_all(self, state: bool):
        self.lock_rpc_url_edit(state)
        self.lock_video_url_edit(state)

class CleanerTaskWindow(QWidget):
    def __init__(self, rpc_client):
        super().__init__()
        self.rpc_client = rpc_client
        self.mode = {"m": 0}  # default
        self.task_running = False  # Flag for cleaning task
        self.current_task = None  # Cleaning task
        self.video_running = False  # Flag for video capture
        self.video_task = None  # Video capture task
        self.setWindowTitle("自动清刷监控窗口")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(800, 600)

        # Main horizontal layout
        main_layout = QVBoxLayout()

        # Left status panel
        status_widget = QWidget()
        status_layout = QHBoxLayout()

        # Image label
        self.image_label = QLabel()
        pixmap = QPixmap("./icons/machine/test_machine.png")
        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(670, 400)
        self.image_label.setScaledContents(True)

        status_layout.addStretch(0)
        status_layout.addWidget(self.image_label)
        status_layout.addStretch(0)

        # Right content panel
        content_widget = QWidget()
        content_layout = QVBoxLayout()

        # Status label
        self.status_label = QLabel("工作状态")
        font = QFont("Arial", 20)
        font.setBold(True)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: black;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        content_layout.addStretch(0)
        content_layout.addWidget(self.status_label)


        # Bottom layout (buttons)
        buttons_layout = QHBoxLayout()

        # Global Monitor button
        self.monitor_button = QPushButton("全局监控")
        self.monitor_button.clicked.connect(self.toggle_video)

        # Cleaning button
        self.button = QPushButton("自动清刷")
        self.button.clicked.connect(self.toggle_task)

        buttons_layout.addWidget(self.monitor_button)
        buttons_layout.addWidget(self.button)

        content_layout.addLayout(buttons_layout)
        content_layout.addStretch(0)

        # Tree view
        self.tree_view = QTreeView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['水下机器人', ' '])
        self.tree_view.setModel(self.model)

        # Sample data
        root = QStandardItem("清刷情况")
        root.appendRow([QStandardItem('清刷面积'), QStandardItem('6m²')])
        root.appendRow([QStandardItem('清刷时间'), QStandardItem('h')])
        root.appendRow([QStandardItem('清刷效率'), QStandardItem('2m²/h')])
        self.model.appendRow(root)

        content_layout.addWidget(self.tree_view)
        content_layout.addStretch(0)
        content_widget.setLayout(content_layout)

        status_layout.addWidget(content_widget)
        status_layout.addStretch(0)

        status_widget.setLayout(status_layout)

        bottom_widget = QWidget()
        # Bottom layout (buttons)
        bottom_layout = QHBoxLayout()

        # Task label
        self.task_label = QLabel("任务进度:")
        font = QFont("Arial", 15)
        font.setBold(True)
        self.task_label.setFont(font)
        self.task_label.setStyleSheet("color: green;")
        # self.task_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        bottom_layout.addStretch(0)
        bottom_layout.addWidget(self.task_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        # self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        bottom_layout.addWidget(self.progress_bar)
        self.progress_bar.setValue(0)

        bottom_widget.setLayout(bottom_layout)

        # Add to main layout
        main_layout.addWidget(status_widget)
        main_layout.addWidget(bottom_widget)
        main_layout.addStretch(0)

        # Set stretch factors
        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 2)

        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)

    def update_status_label(self, text: str):
        self.status_label.setText(text)

    @asyncSlot()
    async def toggle_task(self):
        if not self.task_running:
            # Stop video capture if running
            if self.video_running:
                await self.stop_video()
            # Start cleaning task
            self.task_running = True
            self.button.setText("停止清刷")
            self.current_task = asyncio.create_task(self.run_c_main())
        else:
            # Stop cleaning task
            if self.current_task:
                self.current_task.cancel()
                try:
                    await self.current_task
                except asyncio.CancelledError:
                    pass
                self.current_task = None
            self.task_running = False
            self.button.setText("自动清刷")
            self.status_label.setText("任务已停止")
            self.status_label.setStyleSheet("color: black;")
            self.progress_bar.setValue(0)

    @asyncSlot()
    async def toggle_video(self):
        if not self.video_running:
            # Start video capture
            self.video_running = True
            self.monitor_button.setText("停止监控")
            self.video_task = asyncio.create_task(self.run_video_capture())
        else:
            # Stop video capture
            await self.stop_video()

    async def stop_video(self):
        if self.video_task:
            self.video_task.cancel()
            try:
                await self.video_task
            except asyncio.CancelledError:
                pass
            self.video_task = None
        self.video_running = False
        self.monitor_button.setText("全局监控")
        # Restore default image
        pixmap = QPixmap("./icons/machine/test_machine.png")
        self.image_label.setPixmap(pixmap)

    async def run_video_capture(self):
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.status_label.setText("摄像头打开失败")
                self.status_label.setStyleSheet("color: red;")
                return

            while self.video_running:
                ret, frame = cap.read()
                if not ret:
                    self.status_label.setText("视频帧读取失败")
                    self.status_label.setStyleSheet("color: red;")
                    break

                # Convert OpenCV BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Convert to QImage
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                qimage = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                # Convert to QPixmap and update label
                pixmap = QPixmap.fromImage(qimage)
                self.image_label.setPixmap(pixmap)

                # Control frame rate
                await asyncio.sleep(1.0 / 30)  # ~30 FPS

            cap.release()

        except asyncio.CancelledError:
            if 'cap' in locals():
                cap.release()
            raise
        except Exception as e:
            self.status_label.setText("监控异常")
            self.status_label.setStyleSheet("color: red;")
            print(f"Error in video capture: {e}")
        finally:
            self.video_running = False
            self.monitor_button.setText("全局监控")
            self.video_task = None
            # Restore default image
            pixmap = QPixmap("./icons/machine/test_machine.png")
            self.image_label.setPixmap(pixmap)

    async def run_c_main(self):
        try:
            self.status_label.setText("路径规划中")
            self.status_label.setStyleSheet("color: green;")
            self.progress_bar.setValue(50)

            await multilayer_auv.async_main(self.status_label)

            self.status_label.setText("任务完成")
            self.status_label.setStyleSheet("color: black;")
            self.progress_bar.setValue(100)
        except asyncio.CancelledError:
            self.status_label.setText("任务已停止")
            self.status_label.setStyleSheet("color: black;")
            self.progress_bar.setValue(0)
            raise
        except Exception as e:
            self.status_label.setText("工作异常")
            self.status_label.setStyleSheet("color: red;")
            self.progress_bar.setValue(0)
            print(f"Error running multilayer_auv.async_main(): {e}")
        finally:
            self.task_running = False
            self.button.setText("自动清刷")
            self.current_task = None