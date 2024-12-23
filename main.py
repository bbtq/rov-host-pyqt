import sys
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QPushButton, QTextEdit, QWidget, QDialog,QScrollArea,
    QLabel, QSlider, QHBoxLayout, QCheckBox, QGridLayout, QFrame,QInputDialog
)
from PyQt6.QtCore import Qt
from jsonrpcclient import request, parse_json
import requests
import json


class JsonRpcClientDemo(QWidget):
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
        # Button to save the updateparam
        self.save_button = QPushButton("Send 'save_thruster_parameters' Request", self)
        self.save_button.clicked.connect(self.send_saverpc_request)
        # Button to send the request
        self.send_button = QPushButton("Send 'load_thruster_parameters' Request", self)
        self.send_button.clicked.connect(self.send_rpc_request)

        # Layout
        layout.addWidget(self.url_set_button)
        layout.addWidget(self.send_button)
        layout.addWidget(self.result_text)
        layout.addWidget(self.save_button)

        # **************************************

        # **************************************
        self.setLayout(layout)

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

            # 在本窗口显示json回复包
            self.result_text.setText(json.dumps(parsed_response, indent=4))

            # Open new window to display parameters
            self.show_parameter_window(self.propeller_parameters)

        except Exception as e:
            self.result_text.setText(f"An error occurred:\n{str(e)}")

    def show_parameter_window(self,parameters):
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = JsonRpcClientDemo()
    demo.resize(600, 300)
    demo.show()
    sys.exit(app.exec())