from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QFrame, QSplitter, QLineEdit)


class user_config(QWidget):
    def __init__(self):
        super().__init__()
        self.rpc_url = "http://192.168.137.219:8888/"
        self.video_url = "rtsp://rov:rov@192.168.137.132:554/"
        self.rpc_url_edit_line = QLineEdit()
        self.video_url_edit_line = QLineEdit()
        self.init_ui()

    def init_ui(self):

        rpc_save_button = QPushButton('保存')
        rpc_save_button.setFixedWidth(40)
        rpc_save_button.clicked.connect(self.save_rpc_url)
        video_save_button = QPushButton('保存')
        video_save_button.setFixedWidth(40)
        video_save_button.clicked.connect(self.save_video_url)

        rpc_url_edit_line = self.rpc_url_edit_line
        rpc_url_edit_line.setFixedWidth(250)
        rpc_url_edit_line.setText(self.rpc_url)

        video_url_edit_line = self.video_url_edit_line
        video_url_edit_line.setFixedWidth(250)
        video_url_edit_line.setText(self.video_url)

        main_layout = QVBoxLayout()
        main_layout.addWidget(rpc_url_edit_line)
        main_layout.addWidget(rpc_save_button)
        main_layout.addWidget(video_url_edit_line)
        main_layout.addWidget(video_save_button)

        self.setFixedWidth(300)
        self.setFixedHeight(200)

        self.setLayout(main_layout)

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








