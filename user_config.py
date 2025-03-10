import os
import re
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (QPixmap, QStandardItemModel, QStandardItem, QFont)
from PyQt6.QtWidgets import (QLineEdit, QHBoxLayout, QVBoxLayout, QPushButton, QTextEdit, QWidget, QDialog,
                             QScrollArea, QLabel, QSlider, QCheckBox, QGridLayout, QFrame, QInputDialog, QFileDialog,
                             QMessageBox)
from PyQt6.QtCore import Qt
from jsonrpcclient import request, parse_json
import requests
import json
import sys


class UserConfig(QWidget):
    def __init__(self):
        super().__init__()
        self.rpc_url = "http://192.168.137.219:8888/"
        self.video_url = "rtsp://rov:rov@192.168.137.132:554/"
        self.rpc_url_edit_line = QLineEdit()
        self.video_url_edit_line = QLineEdit()
        self.init_ui()

    def init_ui(self):
        import_config_file_button = QPushButton('导入')
        import_config_file_button.setFixedWidth(40)
        import_config_file_button.clicked.connect(self.open_and_read_file)

        export_config_file_button = QPushButton('导出')
        export_config_file_button.setFixedWidth(40)
        export_config_file_button.clicked.connect(self.create_and_open_file)

        in_out_config_layout = QHBoxLayout()
        in_out_config_layout.addWidget(import_config_file_button)
        in_out_config_layout.addWidget(export_config_file_button)


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
        main_layout.addLayout(in_out_config_layout)
        main_layout.addWidget(rpc_url_edit_line)
        main_layout.addWidget(rpc_save_button)
        main_layout.addWidget(video_url_edit_line)
        main_layout.addWidget(video_save_button)

        self.setFixedWidth(300)
        self.setFixedHeight(220)

        self.setLayout(main_layout)

    def open_and_read_file(self):
        # 打开文件对话框，让用户选择配置文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "文本文件 (*.txt);;所有文件 (*)")

        if file_path:
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                # 使用正则表达式解析 rpc_url 和 video_url
                rpc_match = re.search(r"rpc_url:\s*(\S+)", content)
                video_match = re.search(r"video_url:\s*(\S+)", content)

                if rpc_match and video_match:
                    rpc_url = rpc_match.group(1)
                    video_url = video_match.group(1)
                    self.rpc_url = rpc_url
                    self.video_url = video_url
                    # QMessageBox.information(self, "解析成功", f"RPC URL: {rpc_url}\nVideo URL: {video_url}")
                else:
                    QMessageBox.warning(self, "解析失败", "未找到有效的 格式")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"文件读取失败: {e}")

    def create_and_open_file(self):
        # 打开文件对话框，获取用户选择的文件路径
        file_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "文本文件 (*.txt);;所有文件 (*)")

        if file_path:  # 确保用户没有取消
            try:
                # 创建文件并写入默认内容
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write("rpc_url:\n{}\n".format(self.rpc_url))
                    file.write("video_url:\n{}\n".format(self.video_url))

            except Exception as e:
                print(f"应用配置导出失败: {e}")

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


class ParametersSetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.propeller_parameters = {}  # To store the modified parameters
        self.rpc_server_url = "http://192.168.31.247:8888"

    def init_ui(self):
        self.setWindowTitle("JSON-RPC 2.0 Client Demo")
        layout = QVBoxLayout()

        # Text area to display the results
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)

        # Button to set url
        self.url_set_button = QPushButton('http://192.168.31.247:8888', self)
        self.url_set_button.clicked.connect(self.showUrlSetWindow)
        # import parameters
        self.import_config_button = QPushButton('导入配置', self)
        self.import_config_button.clicked.connect(self.open_and_read_file)
        # export parameters
        self.export_config_button = QPushButton('导出配置', self)
        self.export_config_button.clicked.connect(self.create_and_open_file)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.url_set_button)
        h_layout.addWidget(self.import_config_button)
        h_layout.addWidget(self.export_config_button)

        # Button to send the request
        self.send_button = QPushButton("Send 'load_thruster_parameters' Request", self)
        self.send_button.clicked.connect(self.send_rpc_request)
        # Button to save the updateparam
        self.save_button = QPushButton("Send 'save_thruster_parameters' Request", self)
        self.save_button.clicked.connect(self.send_saverpc_request)

        # Layout
        layout.addLayout(h_layout)
        layout.addWidget(self.send_button)
        layout.addWidget(self.result_text)
        layout.addWidget(self.save_button)

        # **************************************

        # **************************************
        self.setLayout(layout)

    def open_and_read_file(self):
        # 打开文件对话框，让用户选择配置文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "文本文件 (*.txt);;所有文件 (*)")

        if file_path:
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                    # 解析 JSON 确保 self.propeller_parameters 类型与 send_rpc_request 中一致
                    self.propeller_parameters = json.loads(content)
                    # Open new window to display parameters
                    self.show_parameter_window(self.propeller_parameters)


            except json.JSONDecodeError:
                QMessageBox.critical(self, "错误", "文件内容不是有效的 JSON 格式")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"文件读取失败: {e}")

    def create_and_open_file(self):
        # 打开文件对话框，获取用户选择的文件路径
        file_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "文本文件 (*.txt);;所有文件 (*)")

        if file_path:  # 确保用户没有取消
            try:
                # 创建文件并写入默认内容
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write("{}".format(self.propeller_parameters))

            except Exception as e:
                print(f"应用配置导出失败: {e}")

    def showUrlSetWindow(self):

        text, ok = QInputDialog.getText(self, 'Input New URL',
                                        'Enter your url:')

        if ok:
            self.rpc_server_url = (str(text))
            self.url_set_button.setText('now url : ' + self.rpc_server_url)

            # self.rpc_server_url.setText(str(text))

    def send_saverpc_request(self):
        rpc_server_url = self.rpc_server_url  # Replace with your RPC server address

        try:
            rpc_request = request("save_thruster_config")
            json_request = json.dumps(rpc_request)

            response = requests.post(rpc_server_url, data=json_request, headers={"Content-Type": "application/json"})
        except Exception as e:
            self.result_text.setText(f"An error occurred:\n{str(e)}")

    def send_rpc_request(self):
        rpc_server_url = self.rpc_server_url  # Replace with your RPC server address

        try:
            rpc_request = request("get_thruster_config")
            json_request = json.dumps(rpc_request)

            response = requests.post(rpc_server_url, data=json_request, headers={"Content-Type": "application/json"})
            parsed_response = parse_json(response.text)
            print(f"{parsed_response}")

            # Extract parameters
            self.propeller_parameters = parsed_response[0]
            print(f"{parsed_response[0]}")

            # 在本窗口显示json回复包
            self.result_text.setText(json.dumps(parsed_response, indent=4))

            # Open new window to display parameters
            self.show_parameter_window(self.propeller_parameters)

        except Exception as e:
            self.result_text.setText(f"An error occurred:\n{str(e)}")

    def show_parameter_window(self, parameters):
        """
        Show a window with sliders and checkboxes to adjust propeller parameters.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Adjust Propeller Parameters")

        # Main layout
        main_layout = QGridLayout()

        # Create a scroll area to allow scrolling when the window is resized
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_area.setWidgetResizable(True)  # Ensure the widget resizes with the window
        scroll_area.setWidget(scroll_widget)

        # Create a layout for the scroll area
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)

        # Store updated values
        self.updated_values = {}

        # Loop through each propeller and its parameters
        for thruster, values in parameters.items():
            # Create a new grid layout for each propeller's parameters
            grid_layout = QGridLayout()

            # Add header (propeller name)
            header = QLabel(f"{thruster}")
            header.setStyleSheet("font-weight: bold; margin-top: 10px;")
            grid_layout.addWidget(header, 0, 0, 1, 2)  # Span across 2 columns

            # Add horizontal line under header
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            grid_layout.addWidget(line, 1, 0, 1, 2)  # Span across 2 columns

            row = 2  # Start adding parameters after header and line

            # Add parameters (sliders and checkboxes)
            for key, value in values.items():
                name_label = QLabel(key)

                if isinstance(value, bool):
                    # Checkbox for boolean values
                    checkbox = self.create_checkbox(key, value, thruster)
                    grid_layout.addWidget(name_label, row, 0)  # Place in the first column
                    grid_layout.addWidget(checkbox, row, 1)  # Place in the second column
                elif isinstance(value, (int, float)):
                    # Slider for numeric values
                    slider, value_label = self.create_slider(key, value, thruster)
                    grid_layout.addWidget(name_label, row, 0)  # Place in the first column
                    grid_layout.addWidget(slider, row, 1)  # Place in the second column
                    grid_layout.addWidget(value_label, row, 2)  # Place value label next to the slider

                row += 1  # Move to the next row after each parameter

            # Add grid_layout for this propeller to the scroll_layout
            scroll_layout.addLayout(grid_layout)

        # Add scroll area to the main layout
        main_layout.addWidget(scroll_area)

        # Confirm button
        confirm_button = QPushButton("confirm Changes !")
        confirm_button.clicked.connect(lambda: self.confirm_changes(dialog))
        main_layout.addWidget(confirm_button)

        dialog.setLayout(main_layout)
        dialog.resize(800, 400)
        dialog.exec()

    def add_freq_grid_layout(self, value):
        # layout show pwm_freq
        grid_layout = QGridLayout()
        # Add header (propeller name)
        key = "propeller_pwm_freq_calibration"
        name_label = QLabel(key)
        name_label.setStyleSheet("font-weight: bold; margin-top: 10px;")

        slider: QSlider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-100, 100)  # Scale float to -100 ~ 100
        slider.setValue(int(value * 100))  # Scale initial value
        value_label = QLabel(f"{value:.2f}")
        slider.valueChanged.connect(
            lambda val, k=key, lbl=value_label: self.update_pwmslider_value(val / 100, k, lbl)
        )

        grid_layout.addWidget(name_label, 0, 0)  # Place in the first column
        grid_layout.addWidget(slider, 0, 1)  # Place in the second column
        grid_layout.addWidget(value_label, 0, 2)  # Place value label next to the slider

        # Add horizontal line under header
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        grid_layout.addWidget(line, 1, 0, 1, 2)  # Span across 2 columns

        return grid_layout

    def create_slider(self, key, value, propeller):
        """
        Create a slider and associated value label for numeric parameters.
        - For integers: range is -128 to 127.
        - For floats: range is -1.0 to 1.0, scaled to -100 to 100 internally.
        """
        slider: QSlider = QSlider(Qt.Orientation.Horizontal)

        # Determine slider range and scaling factor based on type
        if isinstance(value, int):
            slider.setRange(0, 7)
            slider.setValue(value)
            value_label = QLabel(f"{value}")
            slider.valueChanged.connect(
                lambda val, k=key, p=propeller, lbl=value_label: self.update_slider_value(val, k, p, lbl)
            )
        elif isinstance(value, float):
            slider.setRange(0, 100)  # Scale float to -100 ~ 100
            slider.setValue(int(value * 100))  # Scale initial value
            value_label = QLabel(f"{value:.2f}")
            slider.valueChanged.connect(
                lambda val, k=key, p=propeller, lbl=value_label: self.update_slider_value(val / 100, k, p, lbl)
            )

        return slider, value_label

    def create_checkbox(self, key, value, propeller):
        """
        Create a checkbox for boolean parameters.
        """
        checkbox = QCheckBox()
        checkbox.setChecked(value)
        checkbox.stateChanged.connect(
            lambda state, k=key, p=propeller: self.update_checkbox_value(state, k, p)
        )
        return checkbox

    def update_slider_value(self, value, key, propeller, label):
        """
        Update the value of a slider and store it.
        """
        label.setText(f"{value} *")
        self.propeller_parameters[propeller][key] = value

    def update_pwmslider_value(self, value, key, label):
        """
        Update the value of a slider and store it.
        """
        label.setText(f"{value} *")
        self.propeller_parameters[key] = value

    def update_checkbox_value(self, state, key, propeller):
        """
        Update the value of a checkbox and store it.
        """
        self.propeller_parameters[propeller][key] = True if state == Qt.CheckState.Checked.value else False

    def confirm_changes(self, dialog):
        """
        Display the updated parameters in the main text area and close the dialog.
        """
        updated_text = json.dumps(self.propeller_parameters, indent=4)
        self.result_text.setText(f"Updated Propeller Parameters:\n{updated_text}")
        rpc_request = {
            "jsonrpc": "2.0",
            "method": "set_thruster_config",
            "params": self.propeller_parameters,
            "id": 1
        }
        json_request = json.dumps(rpc_request)
        print(f"{json_request}")
        response = requests.post(self.rpc_server_url, data=json_request, headers={"Content-Type": "application/json"})
        dialog.accept()

#
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     demo = JsonRpcClientDemo()
#     demo.resize(600, 300)
#     demo.show()
#     sys.exit(app.exec())