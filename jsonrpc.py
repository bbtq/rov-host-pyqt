from jsonrpcclient import request
import requests


class RpcClient:
    def __init__(self, rpc_server_url):
        self.rpc_server_url = rpc_server_url
        self.unconnected = True

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