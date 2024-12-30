import sys
import asyncio
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSizePolicy
import cv2
from control import Controller


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
    def __init__(self, controller, rtsp_url):
        super().__init__()
        self.controller = controller
        self.rtsp_url = rtsp_url
        self.init_ui()
        self.setup_video_stream()

    def init_ui(self):
        self.setWindowTitle("Joystick & Video Viewer")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(400, 300)  # Set a minimum size for the window

        # Video display label
        self.video_label = QLabel("Video Stream")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setScaledContents(True)  # Allow QLabel to scale its contents
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )  # Allow QLabel to expand and shrink
        self.video_label.setMinimumSize(200, 150)  # Set a minimum size for the video display

        # Action buttons
        self.action_buttons = {}
        actions_layout = QHBoxLayout()

        # Define action buttons and corresponding icons
        action_icons = {
            "Button 0": "icon0.ico",
            "Button 1": "icon1.ico",
            "Button 2": "icon2.ico",
            "Button 3": "icon3.ico",
        }

        for action, icon_path in action_icons.items():
            button = QPushButton()
            button.setIcon(QIcon(icon_path))
            button.setIconSize(button.size())
            button.setEnabled(False)  # Disabled initially
            self.action_buttons[action] = button
            actions_layout.addWidget(button)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.video_label)
        main_layout.addLayout(actions_layout)

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
        for action, button in self.action_buttons.items():
            if action in actions:
                button.setEnabled(True)
            else:
                button.setEnabled(False)
        pass


async def update_ui(main_window):
    while True:
        actions = main_window.controller.get_actions()
        main_window.update_action_buttons(actions)
        await asyncio.sleep(0.1)  # Update interval


async def main():
    app = QApplication(sys.argv)

    rtsp_url = "rtsp://rov:rov@192.168.137.132:554/"
    controller = Controller()
    main_window = MainWindow(controller, rtsp_url)

    # Show the window
    main_window.show()

    # Async tasks
    tasks = [
        asyncio.create_task(controller.poll_events()),
        asyncio.create_task(update_ui(main_window)),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        app.quit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application terminated.")
