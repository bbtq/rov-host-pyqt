import asyncio
import copy

import pygame


class Controller:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.actions = {
            "x": 0.0,  # 左右平移
            "y": 0.0,  # 前进后退
            "z": 0.0,  # 上浮下沉
            "rot": 0.0,  # 左右旋转
            "catch": 0.0,  # 机械臂
            "depth_locked": False,  # 深度锁定
            "direction_locked": True  # 方向锁定
        }
        self.running = True  # Flag to control polling
        self._initialize_joystick()

    def _initialize_joystick(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Joystick connected: {self.joystick.get_name()}")
        else:
            self.running = False
            print("No joystick connected.")

    async def poll_events(self):
        joystick = self.joystick
        while self.running:
            pygame.event.pump()  # Make sure we only call this while running

            for i in range(joystick.get_numaxes()):
                axis = joystick.get_axis(i)
                match i:
                    case 0 :
                        self.actions["x"] = axis
                    case 1 :
                        self.actions["y"] = axis
                    case 2 :
                        self.actions["rot"] = axis
                    case 3 :
                        self.actions["z"] = axis
                    case 5 :
                        if axis > -0.8:
                            self.actions["catch"] = -1.0

            for i in range(joystick.get_numbuttons()):
                button = joystick.get_button(i)
                match i:
                    case 5:
                        self.actions["catch"] = float(button)
                    case 8:
                        self.actions["depth_locked"] = bool(button)
                    case 9:
                        self.actions["direction_locked"] = bool(button)

            for i in range(joystick.get_numhats()):
                hat = joystick.get_hat(i)
                # self.actions["x"] = hat[0] * 0.5
                # self.actions["y"] = hat[1] * -0.5

            # 遍历字典并打印每个键对应的值
            # for key, value in self.actions.items():
            #     print(f"The value of '{key}' is {value}")
            # print("******************************\n")
            await asyncio.sleep(0.01)  # Avoid busy-waiting

    def get_actions(self):
        actions = copy.deepcopy(self.actions)
        # actions = []
        return actions

    def stop(self):
        """Stop polling and clean up resources."""
        self.running = False
        pygame.joystick.quit()  # Quit joystick system before pygame.quit()
        pygame.quit()  # Quit pygame after quitting joystick system
        print("Controller stopped and resources released.")
