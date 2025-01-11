import sys
import asyncio
from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import QIcon, QImage, QPixmap, QTransform, QPainter, QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSizePolicy, \
    QGridLayout, QDockWidget, QTreeView, QSpacerItem
import cv2
from control import Controller, ActionsUi
from net import RpcClient, VideoStream
from user_config import user_config


class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent  # 主窗口的引用

        # 创建标题栏布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题文本
        self.title_label = QLabel("水下机器人上位机")
        self.title_label.setStyleSheet("color: gray; font-size: 12px;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 最小化按钮
        self.minimize_button = QPushButton("-")
        self.minimize_button.clicked.connect(self.parent.showMinimized)

        # 最大化按钮
        self.maximize_button = QPushButton("□")
        self.maximize_button.clicked.connect(self.toggle_maximize)

        # 关闭按钮
        self.close_button = QPushButton("×")
        self.close_button.clicked.connect(self.parent.close)

        # 使用QSpacerItem在标题文本左右留白，使其居中
        left_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        right_spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # 将控件添加到布局中
        layout.addItem(left_spacer)
        layout.addWidget(self.title_label)
        layout.addItem(right_spacer)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

        # 设置标题栏样式
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: white;
                font-size: 16px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton#close_button:hover {
                background-color: #ff0000;
            }
        """)

    def toggle_maximize(self):
        """切换最大化/还原窗口"""
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

class MainWindow(QWidget):
    def __init__(self, my_user_config, controller, rpc_client):
        super().__init__()
        self.user_config = my_user_config
        self.controller = controller
        self.actions_layout = ActionsUi()
        self.rpc_client = rpc_client
        self.video_thread = None
        self.last_actions = {}
        self.init_ui()


        # 用于窗口拖动和缩放的变量
        self.drag_position = QPoint()
        self.resizing = False
        self.dragging = False
        self.border_width = 10  # 可拖拽缩放的边框宽度
        self.resize_direction = None  # 缩放方向

    def init_ui(self):
        self.setWindowTitle("ROV-Host")
        self.setGeometry(100, 100, 900, 600)
        # 隐藏默认标题栏
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # 创建自定义标题栏
        self.title_bar = CustomTitleBar(self)
        self.title_bar.setFixedHeight(27)
        # 设置窗口的样式表以实现圆角矩形
        self.setStyleSheet("""
            QWidget {
                background-color: #2E3440;
            }
        """)
        # 获取屏幕分辨率并计算居中坐标
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.geometry()

        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2
        self.setGeometry(x, y, window_geometry.width(), window_geometry.height())

        self.setMinimumSize(400, 300)  # Set a minimum size for the window

        # *******************************************************************************************************
        # ***********************************  视频窗口初始化  *****************************************************
        #
        self.video_label = QLabel("Video Stream")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setScaledContents(True)  # Allow QLabel to scale its contents
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )  # Allow QLabel to expand and shrink
        self.video_label.setMinimumSize(200, 150)  # Set a minimum size for the video display

        # *******************************************************************************************************
        # ***********************************  顶部交互按钮初始化  **************************************************
        #
        video_en_button = QPushButton()
        video_en_button.setIcon(QIcon("F:/my_gtk_rs/python-gtk/icons/Adwaita/32x32/devices/computer-symbolic.symbolic.png"))
        video_en_button.setCheckable(True)
        video_en_button.setFixedSize(30, 30)
        video_en_button.clicked[bool].connect(self.toggle_video_stream)

        connect_button = QPushButton()
        connect_button.setIcon(
            QIcon("F:/my_gtk_rs/python-gtk/icons/Adwaita/32x32/actions/mail-send-receive-symbolic.symbolic.png"))
        connect_button.setCheckable(True)
        connect_button.setFixedSize(30, 30)
        connect_button.clicked[bool].connect(self.toggle_jsonrpc_connect)

        config_sidebar_button = QPushButton()
        config_sidebar_button.setIcon(
            QIcon("F:/my_gtk_rs/python-gtk/icons/Adwaita/32x32/actions/sidebar-show-right-symbolic.symbolic.png")
        )
        config_sidebar_button.setCheckable(True)
        config_sidebar_button.setFixedSize(30, 30)
        config_sidebar_button.clicked[bool].connect(self.toggle_config_sidebar_view)

        user_layout = QHBoxLayout()
        user_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        user_layout.addWidget(connect_button)
        user_layout.addWidget(video_en_button)

        config_layout = QHBoxLayout()
        config_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        config_layout.addWidget(config_sidebar_button)

        user_top_layout = QHBoxLayout()
        user_top_layout.addLayout(user_layout)
        user_top_layout.addLayout(config_layout)

        # *******************************************************************************************************
        # ***********************************  两种浮动窗口初始化  **************************************************
        #

        # 创建一个QDockWidget -- 用来展示手柄动作信息
        actions_dock_widget = QDockWidget("云控制台", self)
        actions_dock_widget.setFloating(True)  # 设置为浮动状态
        actions_dock_widget.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)  # 允许移动
        actions_dock_widget.setGeometry(x + window_geometry.width(), y, 50, 100)
        # 创建一个QWidget作为QDockWidget的内容
        actions_dock_widget_content = QWidget()
        actions_dock_widget_content.setLayout(self.actions_layout.build_actions_gridlayout())
        actions_dock_widget.setWidget(actions_dock_widget_content)


        # 加载原始图片
        original_pixmap = QPixmap("./icons/machine/test_machine.png")
        # 创建一个QTransform对象并设置旋转角度
        transform = QTransform().rotate(0)  # 旋转角度
        # 应用旋转变换到原始图片
        rotated_pixmap = original_pixmap.transformed(transform)
        # 创建一个QLabel来显示机器图片
        self.machine_label = QLabel()
        self.machine_label.setFixedSize(90, 90)  # 设置QLabel的固定大小为64x64像素
        self.machine_label.setScaledContents(True)  # 启用图片自适应QLabel大小[^41^]
        self.machine_label.setPixmap(rotated_pixmap)

        self.info_tree = QTreeView()
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.info_tree)

        info_show_layout = QVBoxLayout()
        info_show_layout.addWidget(self.machine_label)
        info_show_layout.addLayout(info_layout)

        # 创建一个QDockWidget -- 用来展示手柄动作信息
        info_dock_widget = QDockWidget("ROV 状态监控岛", self)
        info_dock_widget.setFloating(True)  # 设置为浮动状态
        info_dock_widget.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)  # 允许移动
        info_dock_widget.setGeometry(x + window_geometry.width(), y+170, 100, 100)
        # 创建一个QWidget作为QDockWidget的内容
        info_dock_widget_content = QWidget()
        info_dock_widget_content.setLayout(info_show_layout)
        info_dock_widget.setWidget(info_dock_widget_content)

        # *******************************************************************************************************
        # ***********************************  初始界面最终构建  **************************************************
        #
        # 默认显示主界面
        visual_layout = QVBoxLayout()
        visual_layout.addLayout(user_top_layout)
        visual_layout.addWidget(self.video_label)

        system_layout = QHBoxLayout()
        system_layout.addLayout(visual_layout)
        system_layout.addWidget(self.user_config)
        self.user_config.hide()

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.title_bar)
        main_layout.addLayout(system_layout)

        self.setLayout(main_layout)

        pass

    # 侧边配置窗口隐藏函数
    def toggle_config_sidebar_view(self, state):
        if state:
            self.user_config.show()
        else:
            self.user_config.hide()

    # 视频流播放事件
    def toggle_video_stream(self, state):
        if state:
            self.video_thread = VideoStream(self.user_config.video_url)
            self.video_thread.frame_received.connect(self.update_video_frame)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self.video_thread.start)
        else:
            if self.video_thread:
                self.video_thread.stop()

    # 更新视频帧，发生视频流播放后进行
    def update_video_frame(self, frame):
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        resized_frame = cv2.resize(frame, (label_width, label_height))
        height, width, channel = resized_frame.shape
        bytes_per_line = 3 * width
        qt_image = QImage(resized_frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap)
        pass

    # 退出程序
    def closeEvent(self, event):
        # Stop video stream
        if self.video_thread:
            self.video_thread.stop()

        # Stop controller tasks
        self.controller.stop()

        # 停止网络任务
        self.rpc_client.rpc_server_stop()

        # Exit application
        QApplication.instance().quit()
        event.accept()

    # 控制台 动作按钮状态更新
    def update_action_buttons(self, actions):
        if self.last_actions != actions:
            self.rpc_client.send_joystick(actions)
            self.last_actions = actions
            self.actions_layout.update_action_buttons(actions)

    # 上位机 - 机器 链接？
    def toggle_jsonrpc_connect(self, state):
        if state:
            self.rpc_client.set_jsonrpc_client_url(self.user_config.rpc_url)
            self.rpc_client.connect_jsonrpc_server(True)
            self.user_config.lock_edit_line_all(True)
        else:
            self.rpc_client.connect_jsonrpc_server(False)
            self.user_config.lock_edit_line_all(False)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 判断点击的是边缘用于缩放还是标题栏用于拖动
            self.resize_direction = self.check_resize_area(event.pos())
            if self.resize_direction:
                self.resizing = True
                self.drag_position = event.globalPosition().toPoint()
            elif self.title_bar.geometry().contains(event.pos()):
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件"""
        if self.resizing and self.resize_direction:
            self.resize_window(event)
        elif self.dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        else:
            # 动态更改鼠标指针样式
            self.update_cursor_shape(event.pos())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def check_resize_area(self, pos):
        """检查鼠标是否位于可缩放区域，并返回方向"""
        rect = self.rect()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        if pos.x() < self.border_width and pos.y() < self.border_width:
            return "top_left"
        elif pos.x() > w - self.border_width and pos.y() < self.border_width:
            return "top_right"
        elif pos.x() < self.border_width and pos.y() > h - self.border_width:
            return "bottom_left"
        elif pos.x() > w - self.border_width and pos.y() > h - self.border_width:
            return "bottom_right"
        elif pos.x() < self.border_width:
            return "left"
        elif pos.x() > w - self.border_width:
            return "right"
        elif pos.y() < self.border_width:
            return "top"
        elif pos.y() > h - self.border_width:
            return "bottom"
        return None

    def update_cursor_shape(self, pos):
        """根据鼠标位置更新光标样式"""
        direction = self.check_resize_area(pos)
        if direction in ["top_left", "bottom_right"]:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif direction in ["top_right", "bottom_left"]:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif direction in ["left", "right"]:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif direction in ["top", "bottom"]:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def resize_window(self, event: QMouseEvent):
        """根据鼠标拖动调整窗口大小"""
        diff = event.globalPosition().toPoint() - self.drag_position
        rect = self.geometry()

        if self.resize_direction == "top_left":
            rect.setTopLeft(rect.topLeft() + diff)
        elif self.resize_direction == "top_right":
            rect.setTopRight(rect.topRight() + diff)
        elif self.resize_direction == "bottom_left":
            rect.setBottomLeft(rect.bottomLeft() + diff)
        elif self.resize_direction == "bottom_right":
            rect.setBottomRight(rect.bottomRight() + diff)
        elif self.resize_direction == "left":
            rect.setLeft(rect.left() + diff.x())
        elif self.resize_direction == "right":
            rect.setRight(rect.right() + diff.x())
        elif self.resize_direction == "top":
            rect.setTop(rect.top() + diff.y())
        elif self.resize_direction == "bottom":
            rect.setBottom(rect.bottom() + diff.y())

        self.setGeometry(rect)
        self.drag_position = event.globalPosition().toPoint()

# 更新控制台按钮 任务
async def update_ui(main_window):
    while True:
        if main_window.controller.joystick is None:
            await asyncio.sleep(1.0)
            continue
        actions = main_window.controller.get_actions()
        main_window.update_action_buttons(actions)
        await asyncio.sleep(0.01)  # Update interval


async def main():
    app = QApplication(sys.argv)

    my_user_config = user_config()
    controller = Controller()
    rpc_client = RpcClient(my_user_config.rpc_url)
    main_window = MainWindow(my_user_config, controller,  rpc_client)

    # Show the window
    main_window.show()

    # Async tasks
    tasks = [
        asyncio.create_task(controller.poll_events()),
        asyncio.create_task(update_ui(main_window)),
        asyncio.create_task(rpc_client.send_get_info(main_window.machine_label, main_window.info_tree)),
    ]

    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        loop = asyncio.get_event_loop()
        print(f"quit")
    # 在程序退出前关闭事件循环
        loop.close()
        sys.exit(app.exec())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
