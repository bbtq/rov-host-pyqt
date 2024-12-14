import sys
from PyQt6.QtWidgets import (QApplication, QVBoxLayout, QPushButton, QTextEdit, QWidget,
                             QSlider, QLCDNumber, QLabel, QHBoxLayout, QCheckBox, QFrame, QGridLayout, QDialog)
from PyQt6.QtCore import Qt
from jsonrpcclient import request, parse_json
import requests
import json


class JsonRpcClientDemo(QWidget):
    def __init__(self):
        super().__init__()

        # Initialize UI
        self.init_ui()

        # Store parameters
        self.propeller_parameters = {}

    def init_ui(self):
        self.setWindowTitle("JSON-RPC 2.0 Client Demo")
        main_layout = QVBoxLayout()

        # Display area for JSON-RPC response
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)

        # Button to send the JSON-RPC request
        self.send_button = QPushButton("Send 'load_parameters' Request", self)
        self.send_button.clicked.connect(self.send_rpc_request)

        # Main layout components
        main_layout.addWidget(self.send_button)
        main_layout.addWidget(self.result_text)

        # Layout to show parameters in a new window
        self.param_layout = QVBoxLayout()
        main_layout.addLayout(self.param_layout)

        self.setLayout(main_layout)

    def send_rpc_request(self):
        rpc_server_url = "http://192.168.137.219:8888"  # Replace with actual server URL

        try:
            # Create JSON-RPC request
            rpc_request = request("load_parameters")
            json_request = json.dumps(rpc_request)

            # Send HTTP POST request
            response = requests.post(rpc_server_url, data=json_request, headers={"Content-Type": "application/json"})
            parsed_response = parse_json(response.text)

            # Extract parameters
            self.propeller_parameters = parsed_response[0].get("propeller_parameters", {})
            control_loop_parameters = parsed_response[0].get("control_loop_parameters", {})

            # Display raw JSON response
            self.result_text.setText(json.dumps(parsed_response, indent=4))

            # Show parameters in a new window
            self.show_parameter_window(self.propeller_parameters)
        except Exception as e:
            self.result_text.setText(f"An error occurred:\n{str(e)}")

    def show_parameter_window(self, parameters):
        """
        Show a new window displaying parameters in a 2x4 grid layout.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Propeller Parameters")
        layout = QVBoxLayout()
        grid_layout = QGridLayout()

        row, col = 0, 0  # Initialize grid positions

        for propeller, values in parameters.items():
            for key, value in values.items():
                # Label for parameter
                label = QLabel(f"{propeller} - {key}:")
                grid_layout.addWidget(label, row, col)

                if isinstance(value, (int, float)):
                    # Slider and display for numeric values
                    slider = QSlider(Qt.Orientation.Horizontal)
                    slider.setRange(0, 100)
                    slider.setValue(int(value))
                    lcd = QLCDNumber()
                    lcd.display(value)
                    slider.valueChanged.connect(
                        lambda val, prop=propeller, k=key, lcd=lcd: self.update_slider_value(prop, k, val, lcd))

                    grid_layout.addWidget(slider, row, col + 1)
                    grid_layout.addWidget(lcd, row, col + 2)
                elif isinstance(value, bool):
                    # Checkbox for boolean values
                    checkbox = QCheckBox()
                    checkbox.setChecked(value)
                    checkbox.stateChanged.connect(
                        lambda state, prop=propeller, k=key: self.update_checkbox_value(prop, k, state))
                    grid_layout.addWidget(checkbox, row, col + 1)

                # Update row and column positions
                col += 3
                if col >= 8:
                    col = 0
                    row += 1

        layout.addLayout(grid_layout)
        confirm_button = QPushButton("Confirm")
        confirm_button.clicked.connect(dialog.accept)
        layout.addWidget(confirm_button)

        dialog.setLayout(layout)
        dialog.resize(600, 400)
        dialog.exec()

    def update_slider_value(self, propeller, key, value, lcd):
        """
        Update slider value and display it.
        """
        self.propeller_parameters[propeller][key] = value
        lcd.display(value)

    def update_checkbox_value(self, propeller, key, state):
        """
        Update checkbox value.
        """
        self.propeller_parameters[propeller][key] = state == Qt.CheckState.Checked.value


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = JsonRpcClientDemo()
    demo.resize(800, 600)
    demo.show()
    sys.exit(app.exec())
