from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QStandardItemModel, QStandardItem, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QFrame, QSplitter, QLineEdit, QCheckBox, QHBoxLayout,
                             QLabel, QProgressBar, QTreeView)


class UserConfig(QWidget):
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
        self.setFixedHeight(220)  # 增加高度以容纳拨动开关

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


class CleanerTaskWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动清刷监控窗口")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)

        # 设置主水平布局
        main_layout = QHBoxLayout()

        # 左侧状态栏
        status_widget = QWidget()
        status_layout = QVBoxLayout()

        # 加载图片
        self.image_label = QLabel()
        pixmap = QPixmap("./icons/machine/test_machine.png")  # 机器机型图
        self.image_label.setPixmap(pixmap)
        self.image_label.setFixedSize(300, 300)
        self.image_label.setScaledContents(True)
        # self.image_label.setMinimumSize(100, 100)

        # 状态文字
        self.status_label = QLabel("工作状态")
        # 设置字体和大小
        font = QFont("Arial", 20)  # 字体为 Arial，大小为 16
        font.setBold(True)  # 设置为加粗
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: black;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 测试文字
        # self.status_label.setText("无任务")
        # self.status_label.setStyleSheet("color: black;")
        # self.status_label.setText("工作中")
        # self.status_label.setStyleSheet("color: green;")
        # self.status_label.setText("工作异常")
        # self.status_label.setStyleSheet("color: red;")

        status_layout.addStretch(0)
        status_layout.addWidget(self.image_label)
        status_layout.addStretch(0)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(0)
        status_widget.setLayout(status_layout)

        # 右侧内容部分
        content_widget = QWidget()
        content_layout = QVBoxLayout()

        # 状态文字
        self.task_label = QLabel("任务进度")
        # 设置字体和大小
        font = QFont("Arial", 20)  # 字体为 Arial，大小为 16
        font.setBold(True)  # 设置为加粗
        self.task_label.setFont(font)

        # 设置文字颜色为绿色
        self.task_label.setStyleSheet("color: green;")
        self.task_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        content_layout.addStretch(0)
        content_layout.addWidget(self.task_label)

        # 进度条
        self.progress_bar = QProgressBar()
        content_layout.addStretch()
        content_layout.addWidget(self.progress_bar)

        # 测试设置进度值（71%）
        self.progress_bar.setValue(71)

        # 水平布局，包含左侧垂直布局和右侧垂直布局
        bottom_layout = QHBoxLayout()

        # 左侧垂直布局
        left_layout = QVBoxLayout()

        # 按钮
        self.button = QPushButton("自动清刷")
        left_layout.addWidget(self.button)

        # 复选框
        self.checkbox1 = QCheckBox("模式1")
        self.checkbox2 = QCheckBox("模式2")
        self.checkbox3 = QCheckBox("模式3")
        left_layout.addWidget(self.checkbox1)
        left_layout.addWidget(self.checkbox2)
        left_layout.addWidget(self.checkbox3)

        # 添加左侧布局到水平布局
        bottom_layout.addLayout(left_layout)

        # 右侧垂直布局
        right_layout = QVBoxLayout()

        # 树形控件
        self.tree_view = QTreeView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['水下机器人', ' '])
        self.tree_view.setModel(self.model)

        # 添加示例数据
        root = QStandardItem("实时信息")

        # 测试数值
        root.appendRow([QStandardItem('CPU'), QStandardItem('34%')])
        root.appendRow([QStandardItem('内存'), QStandardItem('77%')])
        root.appendRow([QStandardItem('航向角'), QStandardItem('16.92')])
        root.appendRow([QStandardItem('温度(℃)'), QStandardItem('24.97')])
        root.appendRow([QStandardItem('深度（cm）'), QStandardItem('100')])
        root.appendRow([QStandardItem('异常'), QStandardItem('0')])

        self.model.appendRow(root)

        # 将树形控件添加到右侧布局
        right_layout.addWidget(self.tree_view)

        # 添加右侧布局到水平布局
        bottom_layout.addStretch(0)
        bottom_layout.addLayout(right_layout)
        content_layout.addStretch(0)
        content_layout.addLayout(bottom_layout)
        content_layout.addStretch(0)
        content_widget.setLayout(content_layout)

        # 把左右两部分加入主水平布局
        # main_layout.addStretch(0)
        main_layout.addWidget(status_widget)
        main_layout.addStretch(0)
        main_layout.addWidget(content_widget)
        main_layout.addStretch(1)

        # 设置布局的伸缩因子
        main_layout.setStretch(0, 1)
        main_layout.setStretch(1, 2)

        # 设置布局的间距和边距
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.setLayout(main_layout)





