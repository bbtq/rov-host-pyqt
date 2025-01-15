import asyncio
import copy

import pygame
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QGridLayout, QPushButton


class Controller:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.actions = {
            "ly": 0.0,
            "lx": 0.0,      # 左摇杆的两个轴
            "ry": 0.0,
            "rx": 0.0,      # 右摇杆的两个轴
            "lt": 0.0,
            "rt": 0.0,      # 两个板机
        }
        self.track = {
            "l": 0.0,   # 履带左轮
            "r": 0.0,   # 履带右轮
        }
        self.hat = {
            "hat": (0.0, 0.0)
        }
        self.brush = {
            "g": 0,
        }
        self.brush_button = {
            "brush_button0": 0,
            "brush_button1": 0,
        }
        self.light = {
            "g": 0
        }
        self.light_button = {
            "light_button0": 0,
            "light_button1": 0,
        }
        self.last_actions = {}
        self.last_track = {}
        self.last_brush = {}
        self.last_brush_button = {}
        self.last_light = {}
        self.last_light_button = {}

        self.joysticks_list = {}
        self.joystick_unlock = False
        self.running = True  # Flag to control polling
        self._initialize_joystick()

    def _initialize_joystick(self):
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            print(f"Joystick connected: {self.joystick.get_name()}")
        else:
            # self.running = False
            print("No joystick connected.")

    async def poll_events(self):
        while self.running:
            if pygame.joystick.get_count() > 0:
                if pygame.joystick.Joystick(0).get_name() != self.joystick.get_name():
                    self.joystick = pygame.joystick.Joystick(0)
                    self.joystick.init()
            else:
                self.joystick = None
                await asyncio.sleep(0.5)
                continue
            # if self.joystick_unlock:
            #     continue
            joystick = self.joystick
            pygame.event.pump()  # Make sure we only call this while running

            for i in range(joystick.get_numaxes()):
                axis = joystick.get_axis(i)
                match i:
                    case 0 :
                        self.actions["lx"] = axis
                    case 1 :
                        self.actions["ly"] = axis
                    case 2 :
                        self.actions["ry"] = axis
                    case 3 :
                        self.actions["rx"] = axis
                    case 4 :
                        self.actions["lt"] = axis
                    case 5 :
                        self.actions["rt"] = axis

            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN or event.type == pygame.JOYBUTTONUP:
                    for i in range(joystick.get_numbuttons()):
                        button = joystick.get_button(i)
                        match i:
                            case 0:
                                self.light_button["light_button1"] = button
                                if button:
                                    if self.light["g"] == 0:
                                        self.light["g"] = 2
                                    else:
                                        self.light["g"] -= 1
                            case 1:
                                self.brush_button["brush_button0"] = button
                                if button:
                                    if self.brush["g"] == 2:
                                        self.brush["g"] = 0
                                    else:
                                        self.brush["g"] += 1
                            case 2:
                                self.brush_button["brush_button1"] = button
                                if button:
                                    if self.brush["g"] == 0:
                                        self.brush["g"] = 2
                                    else:
                                        self.brush["g"] -= 1
                            case 3:
                                self.light_button["light_button0"] = button
                                if button:
                                    if self.light["g"] == 2:
                                        self.light["g"] = 0
                                    else:
                                        self.light["g"] += 1

            for i in range(joystick.get_numhats()):
                hat = joystick.get_hat(i)
                self.hat["hat"] = hat
                match hat:
                    case (0, 0):
                        self.track["l"] = 0.0
                        self.track["r"] = 0.0
                    case (1, 0):
                        self.track["l"] = 1.0
                        self.track["r"] = -1.0
                    case (-1, 0):
                        self.track["l"] = -1.0
                        self.track["r"] = 1.0
                    case (0, 1):
                        self.track["l"] = 1.0
                        self.track["r"] = 1.0
                    case (0, -1):
                        self.track["l"] = -1.0
                        self.track["r"] = -1.0
                    case (1, 1):
                        self.track["l"] = 1.0
                        self.track["r"] = 0.5
                    case (-1, 1):
                        self.track["l"] = 0.5
                        self.track["r"] = 1.0
                    case (1, -1):
                        self.track["l"] = -1.0
                        self.track["r"] = -0.5
                    case (-1, -1):
                        self.track["l"] = -0.5
                        self.track["r"] = -1.0

            await asyncio.sleep(0.01)

    def get_actions(self):
        actions = self.actions.copy()
        return actions

    def get_track(self):
        track = self.track.copy()
        hat = self.hat.copy()
        # actions = []
        return track, hat

    def get_brush(self):
        brush = self.brush.copy()
        brush_button = self.brush_button.copy()
        return brush, brush_button

    def get_light(self):
        light = self.light.copy()
        light_button = self.light_button.copy()
        return light, light_button

    def get_joysticks_list(self):
        joystick_count = pygame.joystick.get_count()
        if joystick_count > 0:
            for i in range(joystick_count):
                joystick = pygame.joystick.Joystick(i)
                joystick.init()
                name = joystick.get_name()
                self.joysticks_list[str(i)] = str(name)
        else:
            print("none joysticks")
        joysticks_list = copy.deepcopy(self.joysticks_list)
        return joysticks_list

    def set_joystick(self, id):
        self.joystick_unlock = True
        self.joystick = pygame.joystick.Joystick(id)
        self.joystick.init()
        self.joystick_unlock = False

    def stop(self):
        """Stop polling and clean up resources."""
        self.running = False
        if pygame.joystick.get_init():
            pygame.joystick.quit()  # Quit joystick system before pygame.quit()
        pygame.quit()  # Quit pygame after quitting joystick system
        print("Controller stopped and resources released.")


class ActionsUi:
    def __init__(self):
        # Action buttons
        self.action_buttons = {}

    def build_actions_gridlayout(self):
        # 创建一个3x3的网格布局
        grid_layout = QGridLayout()

        # Define action buttons and corresponding icons
        action_icons = {
            "left_rot": "./icons/Adwaita/32x32/actions/object-rotate-left-symbolic.symbolic.png",  # 左旋
            "go": "./icons/Adwaita/32x32/actions/go-up-symbolic.symbolic.png",  # 前
            "right_rot": "./icons/Adwaita/32x32/actions/object-rotate-right-symbolic.symbolic.png",  # 右旋
            "left": "./icons/Adwaita/32x32/actions/go-next-symbolic-rtl.symbolic.png",  # 左
            "right": "./icons/Adwaita/32x32/actions/go-next-symbolic.symbolic.png",  # 右
            "down": "./icons/Adwaita/32x32/actions/go-bottom-symbolic.symbolic.png",  # 下降
            "back": "./icons/Adwaita/32x32/actions/go-down-symbolic.symbolic.png",  # 后
            "up": "./icons/Adwaita/32x32/actions/go-top-symbolic.symbolic.png",  # 上升
            "raise": "./icons/Adwaita/32x32/actions/media-skip-backward-symbolic.symbolic.png",  # 仰头
            "wheel_go": "./icons/Adwaita/32x32/ui/pan-up-symbolic.symbolic.png",  # 履带-前进
            "prone": "./icons/Adwaita/32x32/actions/media-skip-forward-symbolic.symbolic.png",  # 俯
            "wheel_left": "./icons/Adwaita/32x32/ui/pan-start-symbolic.symbolic.png",  # 履带-左转
            "wheel_right": "./icons/Adwaita/32x32/ui/pan-end-symbolic.symbolic.png",  # 履带-右转
            "clear_shift_up": "./icons/Adwaita/32x32/actions/value-increase-symbolic.symbolic.png",  # 清刷盘-升档
            "wheel_back": "./icons/Adwaita/32x32/ui/pan-down-symbolic.symbolic.png",  # 履带-后退
            "clear_shift_down": "./icons/Adwaita/32x32/actions/value-decrease-symbolic.symbolic.png",  # 清刷盘-降档
            "light_shift_up": "./icons/Adwaita/32x32/status/daytime-sunrise-symbolic.symbolic.png",  # 灯光-增强
            "light_shift_down": "./icons/Adwaita/32x32/status/daytime-sunset-symbolic.symbolic.png",  # 灯光-减弱


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
            elif i == 16:  # 灯光-增强
                grid_layout.addWidget(button, 6, 0)
            elif i == 17:  # 灯光-减弱
                grid_layout.addWidget(button, 6, 2)

        return grid_layout

    def update_action_buttons(self, actions):
        # for key, value in actions.items():
        #     print(f"The value of '{key}' is {value}")
        # print("******************************\n")
        for key, value in actions.items():
            if isinstance(value, bool):
                # match key:
                #     case "brush_button0":
                #         print("----------------------brush_button 0 --------------------------")
                #         if value:
                #             self.action_buttons["clear_shift_up"].setEnabled(True)
                #         else:
                #             self.action_buttons["clear_shift_up"].setEnabled(False)
                #     case "brush_button1":
                #         if value:
                #             self.action_buttons["clear_shift_down"].setEnabled(True)
                #         else:
                #             self.action_buttons["clear_shift_down"].setEnabled(False)
                #
                #     case "light_button0":
                #         if value:
                #             self.action_buttons["light_shift_up"].setEnabled(True)
                #         else:
                #             self.action_buttons["light_shift_up"].setEnabled(False)
                #
                #     case "light_button1":
                #         if value:
                #             self.action_buttons["light_shift_down"].setEnabled(True)
                #         else:
                #             self.action_buttons["light_shift_down"].setEnabled(False)
                # 如果值是布尔类型
                if value:
                    print(f"Action '{key}' is locked")
                #     # 这里可以添加具体的锁定逻辑，例如：
                #     # if action == "depth_locked":
                #     #     lock_depth()
                #     # elif action == "direction_locked":
                #     #     lock_direction()
                else:
                    print(f"Action '{key}' is unlocked")

            elif isinstance(value, int):
                match key:
                    case "brush_button0":
                        if value:
                            self.action_buttons["clear_shift_up"].setEnabled(True)
                        else:
                            self.action_buttons["clear_shift_up"].setEnabled(False)
                    case "brush_button1":
                        if value:
                            self.action_buttons["clear_shift_down"].setEnabled(True)
                        else:
                            self.action_buttons["clear_shift_down"].setEnabled(False)

                    case "light_button0":
                        if value:
                            self.action_buttons["light_shift_up"].setEnabled(True)
                        else:
                            self.action_buttons["light_shift_up"].setEnabled(False)

                    case "light_button1":
                        if value:
                            self.action_buttons["light_shift_down"].setEnabled(True)
                        else:
                            self.action_buttons["light_shift_down"].setEnabled(False)

            elif isinstance(value, float):
                # 如果值是数值类型
                match key:
                    case "lx":
                        if value > 0.1:
                            self.action_buttons["right"].setEnabled(True)
                        elif value < -0.1:
                            self.action_buttons["left"].setEnabled(True)
                        else:
                            self.action_buttons["right"].setEnabled(False)
                            self.action_buttons["left"].setEnabled(False)
                    case "ly":
                        if value > 0.1:
                            self.action_buttons["back"].setEnabled(True)
                        elif value < -0.1:
                            self.action_buttons["go"].setEnabled(True)
                        else:
                            self.action_buttons["back"].setEnabled(False)
                            self.action_buttons["go"].setEnabled(False)
                    case "rx":
                        if value > 0.1:
                            self.action_buttons["down"].setEnabled(True)
                        elif value < -0.1:
                            self.action_buttons["up"].setEnabled(True)
                        else:
                            self.action_buttons["down"].setEnabled(False)
                            self.action_buttons["up"].setEnabled(False)
                    case "ry":
                        if value > 0.1:
                            self.action_buttons["right_rot"].setEnabled(True)
                        elif value < -0.1:
                            self.action_buttons["left_rot"].setEnabled(True)
                        else:
                            self.action_buttons["right_rot"].setEnabled(False)
                            self.action_buttons["left_rot"].setEnabled(False)
                    case "lt":
                        if value > -1.0:
                            self.action_buttons["prone"].setEnabled(True)
                        else:
                            self.action_buttons["prone"].setEnabled(False)
                    case "rt":
                        if value > -1.0:
                            self.action_buttons["raise"].setEnabled(True)
                        else:
                            self.action_buttons["raise"].setEnabled(False)
            elif isinstance(value, tuple):
                match key:
                    case "hat":
                        # print("0:{}, 1:{}".format(value[0], value[1]))
                        if value[0] > 0:
                            self.action_buttons["wheel_right"].setEnabled(True)
                            self.action_buttons["wheel_left"].setEnabled(False)
                        elif value[0] < 0:
                            self.action_buttons["wheel_right"].setEnabled(False)
                            self.action_buttons["wheel_left"].setEnabled(True)
                        else:
                            self.action_buttons["wheel_right"].setEnabled(False)
                            self.action_buttons["wheel_left"].setEnabled(False)
                        if value[1] > 0:
                            self.action_buttons["wheel_go"].setEnabled(True)
                            self.action_buttons["wheel_back"].setEnabled(False)
                        elif value[1] < 0:
                            self.action_buttons["wheel_go"].setEnabled(False)
                            self.action_buttons["wheel_back"].setEnabled(True)
                        else:
                            self.action_buttons["wheel_go"].setEnabled(False)
                            self.action_buttons["wheel_back"].setEnabled(False)
            else:
                print(f"Unknown type for action '{key}'")
    pass
