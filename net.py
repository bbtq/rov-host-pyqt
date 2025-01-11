
import cv2
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QTransform, QStandardItemModel, QStandardItem
from jsonrpcclient import request
import requests
import asyncio
from PyQt6.QtWidgets import QLabel, QTreeView, QVBoxLayout


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


class RpcClient:
    def __init__(self, rpc_server_url):
        self.running = True
        self.rpc_server_url = rpc_server_url
        self.unconnected = True
        self.get_info_time = 0.1

        self.machine_info = {}

    def set_jsonrpc_client_url(self, rpc_server_url):
        self.rpc_server_url = rpc_server_url

    def connect_jsonrpc_server(self, state: bool):
        self.unconnected = not state

    def send_joystick(self, actions):
        if self.unconnected:
            return
        # Prepare JSON-RPC requests using params dictionary
        requests_list = [
            request("move", params={"rot": actions["rot"], "x": actions["x"], "y": actions["y"], "z": actions["z"]}),
            request("set_depth_locked", params=[actions["depth_locked"]]),
            request("set_direction_locked", params=[actions["direction_locked"]]),
            request("catch", params=[actions["catch"]])
        ]

        # Send the requests to the server
        response = requests.post(self.rpc_server_url, json=requests_list)
        # Print the response from the server
        print(response.json())

    async def send_get_info(self, pic_widget: QLabel, info_tree: QTreeView):
        # 加载原始图片
        self.original_pixmap = QPixmap("./icons/machine/test_machine.png")
        angle = 0
        while self.running:
            if self.unconnected:
                await asyncio.sleep(1.0)
                continue
            json_request = request("get_info")
            response = requests.post(self.rpc_server_url, json=json_request)
            result = response.json()
            self.machine_info = result['result']

            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(['Name', 'Value'])
            root_item = QStandardItem('ROV_Info')
            # 遍历所有信息，更新
            for key, value in self.machine_info.items():
                child = QStandardItem(key)
                child_value = QStandardItem(value)
                root_item.appendRow([child, child_value])
                if key == 'Yaw':
                    angle = float(value)
                else:
                    angle = 0
            # 将根节点添加到模型
            model.appendRow(root_item)
            # 设置模型到树状视图
            info_tree.setModel(model)
            # 展开所有节点
            info_tree.expandAll()

            # 创建一个QTransform对象并设置旋转角度
            transform = QTransform().rotate(angle)  # 旋转角度
            # 应用旋转变换到原始图片
            rotated_pixmap = self.original_pixmap.transformed(transform)
            pic_widget.setPixmap(rotated_pixmap)

            print(self.machine_info)
            await asyncio.sleep(self.get_info_time)

    def rpc_server_stop(self):
        self.running = False

