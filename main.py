import sys
import asyncio
from asyncio import Lock

from qasync import QEventLoop, asyncSlot
from PyQt6.QtCore import Qt, QSize, QPoint, QTimer
from PyQt6.QtGui import QIcon, QImage, QPixmap, QTransform, QPainter, QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSizePolicy, \
    QGridLayout, QDockWidget, QTreeView, QSpacerItem, QDialog
import cv2
from control import Controller, ActionsUi
from net import RpcClient, VideoStream
from user_config import UserConfig, CleanerTaskWindow


# *******************************************************************************************************
# ***********************************  自定义样式1 - 自定义标题栏  ********************************************
#
class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent  # 主窗口的引用

        # 创建标题栏布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题文本
        self.title_label = QLabel("     水下机器人上位机 v0.2.2.2501_Alpha")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 最小化按钮
        self.minimize_button = QPushButton("-")
        self.minimize_button.clicked.connect(self.parent.showMinimized)

        # 最大化按钮
        self.maximize_button = QPushButton("□")
        self.maximize_button.clicked.connect(self.toggle_maximize)

        # 关闭按钮
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("close_button")  # 设置 objectName
        self.close_button.clicked.connect(self.parent.close)

        # 设置标题栏的背景颜色
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: gray;  /* 按钮文字颜色 */
                font-size: 16px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;  /* 鼠标悬停时的背景颜色 */
            }
            QPushButton#close_button:hover {
                background-color: #ff0000;  /* 关闭按钮悬停时的背景颜色 */
            }
            QLabel {
                color: gray;  /* 标题文字颜色 */
                font-size: 12px;
            }
        """)

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

    def toggle_maximize(self):
        """切换最大化/还原窗口"""
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()


# *******************************************************************************************************
# ***********************************  自定义样式2 - 自定义浮动窗口  ******************************************
#
class FloatingWindow(QDialog):
    def __init__(self, user_layout: QVBoxLayout):
        super().__init__()
        # 启用可拉伸和最大化/最小化按钮
        self.setSizeGripEnabled(True)  # 允许右下角拉伸
        # 设置窗口标志：无边框、置顶、Tool类型（允许超出父窗口边界）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            # Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setLayout(user_layout)

        # 初始化用于拖动的变量
        self.dragging = False
        self.drag_position = QPoint()

    # 鼠标按下事件
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    # 鼠标移动事件
    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    # 鼠标释放事件
    def mouseReleaseEvent(self, event):
        self.dragging = False
        event.accept()


# *******************************************************************************************************
# ***********************************  主窗口类  **********************************************************
#
class MainWindow(QWidget):
    def __init__(self, my_user_config, controller, rpc_client):
        super().__init__()
        self.user_config = my_user_config
        self.controller = controller
        self.rpc_client = rpc_client
        self.actions_layout = ActionsUi()
        self.cleaner_configWindow = CleanerTaskWindow(self.rpc_client)
        self.video_thread = None
        self.init_ui()
        self.tasks = []  # 用于追踪所有任务


        # 用于窗口拖动和缩放的变量
        self.drag_position = QPoint()
        self.resizing = False
        self.dragging = False
        self.border_width = 10  # 可拖拽缩放的边框宽度
        self.resize_direction = None  # 缩放方向

        # 设置定时器刷新事件
        self.poll_lock = Lock()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_events)
        self.timer.start(10)  # 每 10 毫秒检查一次事件

    def init_ui(self):
        self.setWindowTitle("ROV-Host")
        self.setGeometry(100, 100, 900, 600)
        # 隐藏默认标题栏
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # 创建自定义标题栏
        self.title_bar = CustomTitleBar(self)
        self.title_bar.setFixedHeight(27)
        # 设置窗口的样式表
        # self.setStyleSheet("""
        #     QWidget {
        #         background-color: #ffd2d2;
        #     }
        # """)
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
        # self.video_label.setStyleSheet("background-color: #fff3af;")
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

        show_cleaner_button = QPushButton()
        show_cleaner_button.setIcon(
            QIcon("F:/my_gtk_rs/python-gtk/icons/Adwaita/32x32/devices/phone-apple-iphone-symbolic.symbolic.png")
        )
        show_cleaner_button.setFixedSize(30, 30)
        show_cleaner_button.clicked.connect(self.open_cleaner_task_window)

        user_layout = QHBoxLayout()
        user_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        user_layout.addWidget(connect_button)
        user_layout.addWidget(video_en_button)

        config_layout = QHBoxLayout()
        config_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        config_layout.addWidget(show_cleaner_button)
        config_layout.addWidget(config_sidebar_button)

        user_top_layout = QHBoxLayout()
        user_top_layout.addLayout(user_layout)
        user_top_layout.addLayout(config_layout)

        # *******************************************************************************************************
        # ***********************************  两种浮动窗口初始化  **************************************************
        #
        # 设置窗口内容
        layout = QVBoxLayout()
        label = QLabel("控制灵动岛")
        layout.addWidget(label)
        layout.addLayout(self.actions_layout.build_actions_gridlayout())
        control_box = FloatingWindow(layout)
        control_box.setGeometry(x + window_geometry.width(), y, 50, 100)
        self.control_box = control_box
        self.control_box.show()
        # self.control_box.hide()


        # 加载原始图片
        original_pixmap = QPixmap("./icons/machine/test_machine.png")
        # 创建一个QTransform对象并设置旋转角度
        transform = QTransform().rotate(0)  # 旋转角度
        # 应用旋转变换到原始图片
        rotated_pixmap = original_pixmap.transformed(transform)
        # 创建一个QLabel来显示机器图片
        self.machine_label = QLabel()
        self.machine_label.setFixedSize(90, 90)  # 设置QLabel的固定大小
        self.machine_label.setScaledContents(True)  # 启用图片自适应QLabel大小
        self.machine_label.setPixmap(rotated_pixmap)

        self.info_tree = QTreeView()
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.info_tree)

        info_show_layout = QVBoxLayout()
        label = QLabel("信息灵动岛")
        info_show_layout.addWidget(label)
        info_show_layout.addWidget(self.machine_label)
        info_show_layout.addLayout(info_layout)

        info_box = FloatingWindow(info_show_layout)
        info_box.setGeometry(x + window_geometry.width(), y+220, 100, 100)
        self.info_box = info_box
        self.info_box.show()
        # self.info_box.hide()

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

    def open_cleaner_task_window(self):
        self.cleaner_configWindow.show()

    # 侧边配置窗口隐藏函数
    def toggle_config_sidebar_view(self, state):
        if state:
            self.user_config.text_show_again()
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

        # 停止定时器
        if self.timer.isActive():
            self.timer.stop()
        self.timer.deleteLater()  # 删除定时器对象
        self.timer = None  # 释放引用

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

    # 控制台 动作按钮状态更新 同时发送控制
    def update_action_buttons(self, actions, track, track_hat, brush, brush_button, light, light_button):
        if self.controller.last_actions != actions:
            self.rpc_client.send_jsonrpc("axis", actions)
            self.controller.last_actions = actions
            self.actions_layout.update_action_buttons(actions)
        if self.controller.last_track != track:
            self.rpc_client.send_jsonrpc("track", track)
            self.controller.last_track = track
            self.actions_layout.update_action_buttons(track_hat)
        if self.controller.last_brush_button != brush_button:
            self.actions_layout.update_action_buttons(brush_button)
            self.controller.last_brush_button = brush_button
            if self.controller.last_brush != brush:
                self.rpc_client.send_jsonrpc("brush", brush)
                self.controller.last_brush = brush
        if self.controller.last_light_button != light_button:
            self.actions_layout.update_action_buttons(light_button)
            self.controller.last_light_button = light_button
            if self.controller.last_light != light:
                self.rpc_client.send_jsonrpc("light", light)
                self.controller.last_light = light

    # 上位机 - 机器 链接？
    def toggle_jsonrpc_connect(self, state):
        if state:
            if self.rpc_client.is_url_accessible() :
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

    @asyncSlot()
    async def poll_events(self):
        async with self.poll_lock:
            await self.rpc_client.send_get_info(self.machine_label, self.info_tree,
                                                self.cleaner_configWindow.tree_view)
            await self.controller.poll_events()

            actions = self.controller.get_actions()
            track, track_hat = self.controller.get_track()
            brush, brush_button = self.controller.get_brush()
            light, light_button = self.controller.get_light()
            self.update_action_buttons(actions, track, track_hat, brush, brush_button, light, light_button)


async def main():
    app = QApplication(sys.argv)

    my_user_config = UserConfig()
    controller = Controller()
    rpc_client = RpcClient(my_user_config.rpc_url)
    main_window = MainWindow(my_user_config, controller,  rpc_client)

    # Show the window
    main_window.show()

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.run_forever()

        print(f"quit")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}")
