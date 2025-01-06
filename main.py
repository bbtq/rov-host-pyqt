import sys
import asyncio
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSizePolicy, \
    QGridLayout, QDockWidget
import cv2
from jsonrpcclient import request
import requests
from control import Controller
from jsonrpc import RpcClient


class VideoStream(QObject):
    frame_received = pyqtSignal(object)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.running = True

    def start(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            print("Failed to open RTSP stream")
            self.running = False
            return

        while self.running:
            ret, frame = cap.read()
            if ret:
                self.frame_received.emit(frame)
            cv2.waitKey(30)  # Simulate frame delay

        cap.release()

    def stop(self):
        self.running = False


class MainWindow(QWidget):
    def __init__(self, controller, rtsp_url, rpc_server_url):
        super().__init__()
        self.controller = controller
        self.rtsp_url = rtsp_url
        self.rpc_client = RpcClient(rpc_server_url)
        self.init_ui()
        self.setup_video_stream()
        self.last_actions = {}

    def init_ui(self):
        self.setWindowTitle("Joystick & Video Viewer")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(400, 300)  # Set a minimum size for the window

        # # 创建一个QDockWidget
        dock_widget = QDockWidget("Floating Grid", self)
        dock_widget.setFloating(True)  # 设置为浮动状态
        dock_widget.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)  # 允许移动


        # Video display label
        self.video_label = QLabel("Video Stream")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: green;")
        self.video_label.setScaledContents(True)  # Allow QLabel to scale its contents
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )  # Allow QLabel to expand and shrink
        self.video_label.setMinimumSize(200, 150)  # Set a minimum size for the video display

        # Action buttons
        self.action_buttons = {}
        # 创建一个3x3的网格布局
        grid_layout = QGridLayout()

        # Define action buttons and corresponding icons
        action_icons = {
            "left_rot": "./icons/Adwaita/32x32/actions/object-rotate-left-symbolic.symbolic.png",
            "go": "./icons/Adwaita/32x32/ui/pan-up-symbolic.symbolic.png",
            "right_rot": "./icons/Adwaita/32x32/actions/object-rotate-right-symbolic.symbolic.png",
            "left": "./icons/Adwaita/32x32/ui/pan-start-symbolic.symbolic.png",
            "right": "./icons/Adwaita/32x32/ui/pan-end-symbolic.symbolic.png",
            "down": "./icons/Adwaita/32x32/actions/go-bottom-symbolic.symbolic.png",
            "back": "./icons/Adwaita/32x32/ui/pan-down-symbolic.symbolic.png",
            "up": "./icons/Adwaita/32x32/actions/go-top-symbolic.symbolic.png"
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

        # # 创建一个QWidget作为QDockWidget的内容
        dock_widget_content = QWidget()
        dock_widget_content.setLayout(grid_layout)
        dock_widget.setWidget(dock_widget_content)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.video_label)

        self.setLayout(main_layout)

        pass

    def setup_video_stream(self):
        self.video_thread = VideoStream(self.rtsp_url)
        self.video_thread.frame_received.connect(self.update_video_frame)
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self.video_thread.start)

    def closeEvent(self, event):
        # Stop video stream
        self.video_thread.stop()

        # Stop controller tasks
        self.controller.stop()

        # Exit application
        QApplication.instance().quit()
        event.accept()

    def update_video_frame(self, frame):
        # Resize the frame to fit QLabel dynamically
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        resized_frame = cv2.resize(frame, (label_width, label_height))
        height, width, channel = resized_frame.shape
        bytes_per_line = 3 * width
        qt_image = QImage(resized_frame.data, width, height, bytes_per_line, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap)
        pass

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
        actions = main_window.controller.get_actions()
        main_window.update_action_buttons(actions)
        await asyncio.sleep(0.01)  # Update interval


async def main():
    app = QApplication(sys.argv)

    rtsp_url = "rtsp://rov:rov@192.168.137.132:554/"
    rpc_server_url = "http://192.168.137.219:8888/"
    controller = Controller()
    main_window = MainWindow(controller, rtsp_url, rpc_server_url)

    # Show the window
    main_window.show()

    # Async tasks
    tasks = [
        asyncio.create_task(controller.poll_events()),
        asyncio.create_task(update_ui(main_window)),
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
