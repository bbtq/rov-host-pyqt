import sys
import asyncio
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QIcon, QImage, QPixmap, QTransform, QPainter
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSizePolicy, \
    QGridLayout, QDockWidget, QTreeView
import cv2
from jsonrpcclient import request
import requests
from control import Controller
from jsonrpc import RpcClient
from user_config import user_config


class VideoStream(QObject):
    frame_received = pyqtSignal(object)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.running = False

    def start(self):
        self.running = True
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            print("Failed to open RTSP stream")
            self.running = False
            return

        while self.running:
            ret, frame = cap.read()
            if ret:
                self.frame_received.emit(frame)
            cv2.waitKey(30)

        cap.release()

    def stop(self):
        self.running = False


class MainWindow(QWidget):
    def __init__(self, my_user_config, controller, rpc_client):
        super().__init__()
        self.user_config = my_user_config
        self.controller = controller
        self.rpc_client = rpc_client
        self.video_thread = None
        self.last_actions = {}
        self.init_ui()

    def init_ui(self):

        self.setWindowTitle("Joystick & Video Viewer")
        self.setGeometry(100, 100, 800, 600)
        # 获取屏幕分辨率并计算居中坐标
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.geometry()

        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2
        self.setGeometry(x, y, window_geometry.width(), window_geometry.height())

        self.setMinimumSize(400, 300)  # Set a minimum size for the window

        # # 创建一个QDockWidget
        dock_widget = QDockWidget("Floating Grid", self)
        dock_widget.setFloating(True)  # 设置为浮动状态
        dock_widget.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)  # 允许移动
        dock_widget.setGeometry(x+window_geometry.width(), y, 50, 100)

        # Video display label
        self.video_label = QLabel("Video Stream")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: green;")
        self.video_label.setScaledContents(True)  # Allow QLabel to scale its contents
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )  # Allow QLabel to expand and shrink
        self.video_label.setMinimumSize(200, 150)  # Set a minimum size for the video display

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

    # Action buttons
        self.action_buttons = {}
        # 创建一个3x3的网格布局
        grid_layout = QGridLayout()

        # Define action buttons and corresponding icons
        action_icons = {
            "left_rot": "./icons/Adwaita/32x32/actions/object-rotate-left-symbolic.symbolic.png",       # 左旋
            "go": "./icons/Adwaita/32x32/actions/go-up-symbolic.symbolic.png",                          # 前
            "right_rot": "./icons/Adwaita/32x32/actions/object-rotate-right-symbolic.symbolic.png",     # 右旋
            "left": "./icons/Adwaita/32x32/actions/go-next-symbolic-rtl.symbolic.png",                  # 左
            "right": "./icons/Adwaita/32x32/actions/go-next-symbolic.symbolic.png",                     # 右
            "down": "./icons/Adwaita/32x32/actions/go-bottom-symbolic.symbolic.png",                    # 下降
            "back": "./icons/Adwaita/32x32/actions/go-down-symbolic.symbolic.png",                      # 后
            "up": "./icons/Adwaita/32x32/actions/go-top-symbolic.symbolic.png",                         # 上升
            "raise": "./icons/Adwaita/32x32/actions/media-skip-backward-symbolic.symbolic.png",         # 仰头
            "wheel_go": "./icons/Adwaita/32x32/ui/pan-up-symbolic.symbolic.png",                        # 履带-前进
            "prone": "./icons/Adwaita/32x32/actions/media-skip-forward-symbolic.symbolic.png",         # 俯
            "wheel_left": "./icons/Adwaita/32x32/ui/pan-start-symbolic.symbolic.png",                   # 履带-左转
            "wheel_right": "./icons/Adwaita/32x32/ui/pan-end-symbolic.symbolic.png",                    # 履带-右转
            "clear_shift_up": "./icons/Adwaita/32x32/actions/value-increase-symbolic.symbolic.png",     # 清刷盘-升档
            "wheel_back": "./icons/Adwaita/32x32/ui/pan-down-symbolic.symbolic.png",                    # 履带-后退
            "clear_shift_down": "./icons/Adwaita/32x32/actions/value-decrease-symbolic.symbolic.png",   # 清刷盘-降档
        }

        for i, (action, icon_path) in enumerate(action_icons.items()):
            button = QPushButton()
            button.setIcon(QIcon(icon_path))
            button.setIconSize(QSize(16, 16))
            button.setEnabled(False)  # 初始禁用
            self.action_buttons[action] = button

            # 根据按钮的索引放置在网格中的相应位置
            if i == 0:  # 左旋
                grid_layout.addWidget(button, 0, 0)
            elif i == 1:  # 前
                grid_layout.addWidget(button, 0, 1)
            elif i == 2:  # 右旋
                grid_layout.addWidget(button, 0, 2)
            elif i == 3:  # 左
                grid_layout.addWidget(button, 1, 0)
            elif i == 4:  # 右
                grid_layout.addWidget(button, 1, 2)
            elif i == 5:  # 下降
                grid_layout.addWidget(button, 2, 0)
            elif i == 6:  # 后
                grid_layout.addWidget(button, 2, 1)
            elif i == 7:  # 上升
                grid_layout.addWidget(button, 2, 2)
            elif i == 8:  # 俯仰角-仰 pull-up
                grid_layout.addWidget(button, 3, 0)
            elif i == 9:  # 履带-前进
                grid_layout.addWidget(button, 3, 1)
            elif i == 10:  # 俯仰角-俯 pull-down
                grid_layout.addWidget(button, 3, 2)
            elif i == 11:  # 履带-左转
                grid_layout.addWidget(button, 4, 0)
            elif i == 12:  # 履带-右转
                grid_layout.addWidget(button, 4, 2)
            elif i == 13:  # 清刷盘-升档
                grid_layout.addWidget(button, 5, 0)
            elif i == 14:  # 履带-后退
                grid_layout.addWidget(button, 5, 1)
            elif i == 15:  # 清刷盘-降档
                grid_layout.addWidget(button, 5, 2)

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
        info_show_layout.addLayout(grid_layout)
        info_show_layout.addWidget(self.machine_label)
        info_show_layout.addLayout(info_layout)

        # # 创建一个QWidget作为QDockWidget的内容
        dock_widget_content = QWidget()
        dock_widget_content.setLayout(info_show_layout)
        dock_widget.setWidget(dock_widget_content)

        # 默认显示主界面
        visual_layout = QVBoxLayout()
        visual_layout.addLayout(user_top_layout)
        visual_layout.addWidget(self.video_label)

        # Main layout
        main_layout = QHBoxLayout()
        main_layout.addLayout(visual_layout)
        main_layout.addWidget(self.user_config)
        self.user_config.hide()

        self.setLayout(main_layout)

        pass

    def toggle_config_sidebar_view(self, state):
        if state:
            self.user_config.show()
        else:
            self.user_config.hide()

    def toggle_video_stream(self, state):
        if state:
            self.video_thread = VideoStream(self.user_config.video_url)
            self.video_thread.frame_received.connect(self.update_video_frame)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self.video_thread.start)
        else:
            if self.video_thread:
                self.video_thread.stop()

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

    def toggle_jsonrpc_connect(self, state):
        if state:
            self.rpc_client.set_jsonrpc_client_url(self.user_config.rpc_url)
            self.rpc_client.connect_jsonrpc_server(True)
            self.user_config.lock_edit_line_all(True)
        else:
            self.rpc_client.connect_jsonrpc_server(False)
            self.user_config.lock_edit_line_all(False)

    def update_action_buttons(self, actions):
        if self.last_actions != actions:
            self.rpc_client.send_joystick(actions)
            self.last_actions = actions
            for key, value in actions.items():
                print(f"The value of '{key}' is {value}")
            print("******************************\n")
            for action, value in actions.items():
                if isinstance(value, bool):
                    # 如果值是布尔类型
                    if value:
                        print(f"Action '{action}' is locked")
                        # 这里可以添加具体的锁定逻辑，例如：
                        # if action == "depth_locked":
                        #     lock_depth()
                        # elif action == "direction_locked":
                        #     lock_direction()
                    else:
                        print(f"Action '{action}' is unlocked")

                elif isinstance(value, (int, float)):
                    # 如果值是数值类型
                    match action:
                        case "x" :
                            if value > 0.1 :
                                self.action_buttons["right"].setEnabled(True)
                            elif value < -0.1 :
                                self.action_buttons["left"].setEnabled(True)
                            else :
                                self.action_buttons["right"].setEnabled(False)
                                self.action_buttons["left"].setEnabled(False)
                        case "y" :
                            if value > 0.1 :
                                self.action_buttons["back"].setEnabled(True)
                            elif value < -0.1 :
                                self.action_buttons["go"].setEnabled(True)
                            else :
                                self.action_buttons["back"].setEnabled(False)
                                self.action_buttons["go"].setEnabled(False)
                        case "z" :
                            if value > 0.1 :
                                self.action_buttons["down"].setEnabled(True)
                            elif value < -0.1 :
                                self.action_buttons["up"].setEnabled(True)
                            else :
                                self.action_buttons["down"].setEnabled(False)
                                self.action_buttons["up"].setEnabled(False)
                        case "rot" :
                            if value > 0.1 :
                                self.action_buttons["right_rot"].setEnabled(True)
                            elif value < -0.1 :
                                self.action_buttons["left_rot"].setEnabled(True)
                            else :
                                self.action_buttons["right_rot"].setEnabled(False)
                                self.action_buttons["left_rot"].setEnabled(False)
                else:
                    print(f"Unknown type for action '{action}'")
        pass


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
