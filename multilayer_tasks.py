import warnings
warnings.filterwarnings("ignore")
import asyncio
import logging
import math
import os
import time
import traceback
import multilayer_obstacle_traversal_planner
import argparse
import cv2 as cv
import numpy as np
from asyncio.tasks import sleep
from pyapriltags import Detector
import cv2
from ultralytics import YOLO
from simple_pid import PID
# from asyncio.exceptions import CancelledError
from multilayer_auv import AUVTask, FakeAUVServer, Motion
import threading
from main import CleanerTaskWindow  # 假设 CleanerTaskWindow 在 main.py 中定义

first_iden = None

class CVFrameIterator:

    def __init__(self, path, cap=None, **kwargs):
        """
        初始化类实例，打开视频文件，并设置FPS

        :param str path: 视频文件路径
        :param cap: 传入cv2.VideoCapture()函数的其他参数
        """
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频文件: {path}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # float
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))  # float
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))

    def __next__(self):
        global first_iden
        if first_iden:
            assert(threading.current_thread().ident == first_iden)
        else:
            first_iden = threading.current_thread().ident

        ret, frame = self.cap.read()
        # cv2.imshow("frame",frame)
        if ret:
            return frame
        else:
            raise StopIteration
    
    def stop(self):
        print("摄像头资源释放中>>>")
        self.cap.release()
        cv2.destroyAllWindows()

#手柄模拟器
#各通道的值为-1~1
class Motion:
    def __init__(self):
        #前进
        self.y = 0.0
        #上升
        self.z = 0.0
        #右旋转
        self.rot = 0.0

    def clear(self):
        self.y = 0.0
        self.z = -0.8
        self.rot = 0.0

#PID控制器
class PIDController:
    #输入分别为系数P,I,D,最终输出的缩小因子（使得最大值映射到1）,最终输出的限幅
    def __init__(self, Kp, Ki, Kd, proportion , output_limit):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.proportion = proportion
        self.last_error = 0
        self.integral = 0
        self.output_limit = output_limit
    #输入：set_point（期望值），current_value（实际值）
    #输出：控制值
    def calculate(self, set_point,current_value):
        error = set_point - current_value   #计算当前误差
        self.integral += error              #计算积分项
        derivative = error - self.last_error#计算微分项
        output = self.Kp*error + self.Ki*self.integral + self.Kd*derivative #计算控制输出
        self.last_error = error             #更新上一次误差
        output = output*self.proportion
        output = max(min(output,self.output_limit),-self.output_limit)
        return output

#机器人状态类
class Robot_state:
    def __init__(self, path_real):
        #这里节点指的是区域（正方形）的中心
        #当前节点到下一节点的方向（用角度表示，-90,0,90,180）
        #这也就是当前运动的机器人期望方向
        self.area_direction_now = 0
       
        #上一次运动的机器人期望方向
        self.area_direction_last = 0
        #机器人手柄控制器
       
        self.motion=Motion()
        # 平移运动的PID控制器---由于履带问题，移除平移方向上的控制
        # self.PID_controller_motion_translate = PIDController(0.8,0,0.2,0.03,0.5)
        self.PID_controller_motion_rotation_advancing = PIDController(0.8,0,0.2,0.03,0.8)
        
        # 旋转运动的PID控制器
        self.PID_controller_motion_rotation = PIDController(0.8,0,0.2,0.03,0.8)
        
        # 机器人本次导航的运动路径，路径有一系列节点组成
        # self.path,_ = multilayer_obstacle_traversal_planner.return_path()
        self.path = path_real
        
        # 节点id对应着path中的节点
        self.node_id=0
        
        # 第一个节点，起点  注意：这里永远是第一个节点 
        self.area_center_now = self.path[self.node_id]
       
        # 导航任务是否结束标志
        self.navigation_over_flag=False
    
    def calulate_task_progress(self):
        len_path = len(self.path)
        if len_path and self.node_id > 0:
            progress = self.node_id / len_path * 100
        else:
            progress = 0
        return f'{progress}%'

class LoopTask(AUVTask):
    def __init__(self, system):
        """
        初始化

        :param system: 执行此任务的系统
        """
        super().__init__(system)
        self.running = False

    async def run(self):
        """
        启动任务，并在运行任务时检查任务是否已经开始。

        :return: 如果任务已经启动，则抛出异常，否则调用子类的'loop'函数
        """
        if self.running:
            logging.error('任务已经开始')
            raise
        try:
            self.running = True
            start_time = time.time()  # 开始计时
            while self.running:
                await self.loop()
            end_time = time.time()  # 结束计时
            total_time = end_time - start_time  # 计算一次执行总时间
            print('任务结束>>>')
            print('总时间：', total_time)
            return None
        except Exception as e:
            logging.error(f'{self} ERROR: {e}')
            logging.info(traceback.format_exc())
            self.running = False
            return None

    def stop(self):
        """
        停止正在执行的任务
        """
        self.running = False
    
    def judge_task_done(self):
        return not self.running


    async def loop(self):
        """
        执行任务的具体逻辑，由子类实现。
        """
        pass

""""
计算向量AB与向量(1,0)的夹角(-180,180)，画面中逆时针角为正
输入：A是识别主体中心，B是方向点
输出：向量AB与向量(1,0)的夹角，画面中逆时针角为正
公式： cosθ = a·b/|a||b| (向量)
"""
def angle_between_vectors(A, B):
    # 计算向量AB
    AB = [B[0] - A[0], B[1] - A[1]]
    # 计算向量(1,0)
    U = [1, 0]
    # 计算向量AB和向量(1,0)的模长
    mod_AB = math.sqrt(AB[0] ** 2 + AB[1] ** 2)
    mod_U = math.sqrt(U[0] ** 2 + U[1] ** 2)
    # 计算向量AB和向量(1,0)的点乘
    dot_product = AB[0] * U[0] + AB[1] * U[1]
    # 计算夹角的余弦值
    cos_theta = dot_product / (mod_AB * mod_U)
    # 计算夹角的弧度值和角度值
    radian = math.acos(cos_theta)
    degree = math.degrees(radian)
    if AB[0] * U[1] - AB[1] * U[0] < 0:
        degree = -degree
    return degree

"""
计算点C到直线AB的距离，用于-135、-45、45、135度时，motion.x的计算   x为负数机器人左平移，x为正数机器人右平移
输入：A是上一个路径点坐标、B是下一个点路径坐标、C是机器人当前中心坐标，area_direction_now是期望方向
输出：机器人当前中心坐标到直线AB的距离
"""
def calculate_point_to_line_distance(A, B, C,area_direction_now):
    x1, y1 = A
    x2, y2 = B
    x0, y0 = C
    # 计算斜率 m
    m = (y2 - y1) / (x2 - x1)
    # 计算截距 b
    b = y1 - m * x1
    # 计算分子
    numerator = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
    # 计算分母
    denominator = ((y2 - y1) ** 2 + (x2 - x1) ** 2) ** 0.5
    # 计算距离
    distance = numerator / denominator
    #把C点代入直线判断位于直线上方还是下方
    Staight_line = m * x0 + b - y0
    if area_direction_now in [-135, 135]:
        if Staight_line > 0:
            # 位于直线上方
            # print("点C在直线AB上方")
            distance = distance
        else:
            # 位于直线下方
            # print("点C在直线AB下方")
            distance = -distance
    elif area_direction_now in [-45, 45]:
        if Staight_line > 0:
            # 位于直线上方
            # print("点C在直线AB上方")
            distance = -distance
        else:
            # 位于直线下方
            # print("点C在直线AB下方")
            distance = distance
    return distance


# # 示例点
# A = (1, 2)
# B = (3, 4)
# C = (3, 2)
#
# # 计算点 C 到直线 AB 的距离
# distance = calculate_point_to_line_distance(A, B, C)
# print(f"点 C 到直线 AB 的距离为 {distance}")


# 计算两个点之间的距离
def distance_AB(A, B):
    distance = math.sqrt((A[0] - B[0])**2 + (A[1] - B[1])**2)
    return distance

# 投射变换前后四个点的坐标
# 摄像头不在原来位置的话，需重新设置pts1四个点
# 投射变换后获得正对着水池池底的画面
pts1 = np.float32([[340, 132], [1656, 167], [1620, 712], [352, 718]])
# pts1 = np.float32([[193, 40], [1600, 166], [1620, 720], [193, 715]])
pts2 = np.float32([[0, 0], [1920, 0], [1920, 1080], [0, 1080]])
# 计算透视变换矩阵
M = cv.getPerspectiveTransform(pts1, pts2)

# 创建VideoWriter对象，指定输出视频文件的格式、帧率和大小q
# fourcc = cv.VideoWriter_fourcc(*'XVID')
# out = cv.VideoWriter('apriltag_recognition_001.avi', fourcc, 12.0, (1920, 1080))

# 输入:保存参数的文件路径，图像大小
# 输出:保存有摄像机内参和畸变系数的字典
def load_matrix(file_name, frame_size):
    with open(file_name, 'r') as f:
        lines = f.readlines()
        cx = float(lines[0].strip())
        u = float(lines[1].strip())
        cy = float(lines[2].strip())
        v = float(lines[3].strip())
        camera_matrix = np.array(([cx, 0, u], [0, cy, v], [0, 0, 1]), dtype=np.float32)
        k1 = float(lines[4].strip())
        k2 = float(lines[5].strip())
        k3 = float(lines[6].strip())
        p1 = float(lines[7].strip())
        p2 = float(lines[8].strip())
        dist_coeffs = np.array([k1, k2, k3, p1, p2], dtype=np.float32)
    print("load txt 路径规划中>>>")
    mapx, mapy = cv.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, camera_matrix, frame_size, cv.CV_32FC1)
    return {'mapx': mapx, 'mapy': mapy}


#获取摄像机内参矩阵和畸变系数，是一个字典
matrixs = load_matrix("calibrate_front_1080P.txt", (1920,1080))
#摄像机参数矩阵[cx,cy,fx,fy],用于apriltag检测
cameraMatrix = (811.184725, 1011.40783, 811.734172, 488.910479)

# 创建一个 AprilTag 检测器
at_detector = Detector(
    families="tag25h9",
    nthreads=64,
    quad_decimate=1.0,
    quad_sigma=0,
    refine_edges=1,
    decode_sharpening=0.25,
    debug=0
)


imgs = []
current_img = None
# mask上用于提前画好诸如坐标系，网格等不会变化的信息，mask用于和frame叠加在一起
# mask = np.zeros((1080, 1920, 3), np.uint8)

# 获取本次任务导航的路径,以及地图的绘制结果overlay
# path_real, overlay=multilayer_obstacle_traversal_planner.return_path()
# task = path_real

"""
识别画面中的apriltag码，提供位置和姿态信息
输入：当前帧
输出：识别到为[center,yaw],没识别到为[]
"""
def recognition_function(frame, overlay, model):
    # 图像去畸变
    frame = cv.remap(frame, matrixs['mapx'], matrixs['mapy'], cv.INTER_LINEAR)
    # 进行透视变换
    frame = cv.warpPerspective(frame, M, (1920, 1080))
    # 存储图片
    # cv.imwrite('capture.jpg', frame)
    # 转化为灰度图
    gray = cv.cvtColor(frame, cv.COLOR_RGB2GRAY)
    # 识别画面中的apriltag码
    # tagDetection = at_detector.detect(img=gray, estimate_tag_pose=True, camera_params=cameraMatrix, tag_size=0.060325)
    tagDetection = at_detector.detect(img=gray, camera_params=cameraMatrix, tag_size=0.060325)

    # 获得图像中机器人的位置和方向
    if tagDetection == []:
        print("no found")
    else:
        # 获取apriltag码的中心位置
        center = [int(tagDetection[0].center[0]), int(tagDetection[0].center[1])]
        # 打印中心位置坐标
        #print("center:", center)
        # 在frame绘制中心位置，并打上坐标
        cv.circle(frame, (center[0], center[1]), 7, (255, 255, 255), -1)
        cv.putText(frame, '(%d,%d)'%(center[0],center[1]), (center[0] - 20, center[1] - 20), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        # cv.putText(frame, "center", (center[0] - 20, center[1] - 20), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        # 获得方向点，它是apriltag码第一个角点和第二个角点的中心点
        yaw_point = (tagDetection[0].corners[0] + tagDetection[0].corners[1]) / 2
        # print("yaw_point:", yaw_point)
        # 由中心点和方向点获取机器人方向
        yaw = angle_between_vectors(center, yaw_point)
        print("yaw:", yaw)
        yaw_point = [int(yaw_point[0]), int(yaw_point[1])]
        # 绘制方向
        cv.arrowedLine(frame, center, yaw_point, (0, 255, 0), thickness=5, tipLength=0.2)
    
    #识别视频中的污垢并标记出
    results = model(frame, device="cuda:0", conf=0.5, iou=0.5)
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)

            # 获取类别名与置信度
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            conf = float(box.conf[0])
            text = f"{label} {conf:.2f}"

            # 画框与中心点
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

            # 显示标签文字
            cv2.putText(frame, text, (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
    # 将frame和mask图像叠加，并显示叠加结果
    frame = cv.addWeighted(frame, 0.8, overlay, 0.2, 0)
    # 创建一个可调整大小的窗口
    cv.namedWindow('frame', cv.WINDOW_NORMAL)
    # 设置窗口大小
    cv.resizeWindow('frame', 1344, 780)  # 设置窗口宽度为 640，高度为 480
    cv.imshow('frame', frame)
    cv.waitKey(1)

    if tagDetection == []:
        return []
    else:
        return [center,yaw]

""""
运动规划
输入：机器人状态
输出：目标节点、运动方向、导航结束标志
"""
def Movement_planning(robot_state):
    # 更新节点id，刚开始为起点，更新为路径的下一个节点
    robot_state.node_id += 1
    
   
    if robot_state.node_id == len(robot_state.path):
        # 判断是否访问完最后一个节点、终点，是的话navigatiossssssn_over_flag标志为Ture
        robot_state.navigation_over_flag=True   #为True时，表示任务结束
        robot_state.area_center_next = robot_state.area_center_now
    else:
         # 不是的话，更新area_center_next，期望节点
        robot_state.area_center_next = robot_state.path[robot_state.node_id]
    """
    判断机器人的期望方向
    由当前节点和期望节点就可以知道期望方向
    期望方向用航向角表示（-135,-90,-45,0,45,90,135,180）
    cv坐标系：  x轴：从左到右 y轴：从上到下
               0°-> 90°↑ 180°<- -90°↓ 
    """
    if robot_state.area_center_next[0]== robot_state.area_center_now[0]:       #横坐标一致
        if robot_state.area_center_next[1]>robot_state.area_center_now[1]:     #期望节点在当前节点下方 cv坐标系
            robot_state.area_direction_now=-90
        else:
            robot_state.area_direction_now = 90
    elif robot_state.area_center_next[1]== robot_state.area_center_now[1]:     #纵坐标一致
        if robot_state.area_center_next[0]>robot_state.area_center_now[0]:     #期望节点在当前节点右侧
            robot_state.area_direction_now=0
        else:                                                                  #期望节点在当前节点左侧
            robot_state.area_direction_now = 180                            
    elif robot_state.area_center_next[0]>robot_state.area_center_now[0]:       #期望节点在当前节点右上方
        if robot_state.area_center_next[1]<robot_state.area_center_now[1]:
            robot_state.area_direction_now=45
        elif robot_state.area_center_next[1]>robot_state.area_center_now[1]:   #期望节点在当前节点右下方
            robot_state.area_direction_now = -45
    elif robot_state.area_center_next[0]<robot_state.area_center_now[0]:       #期望节点在当前节点左上方
        if robot_state.area_center_next[1]<robot_state.area_center_now[1]:
            robot_state.area_direction_now=135
        elif robot_state.area_center_next[1]>robot_state.area_center_now[1]:   #期望节点在当前节点左下方
            robot_state.area_direction_now = -135

    return robot_state.area_center_next, robot_state.area_direction_now, robot_state.navigation_over_flag

"""
更新手柄模拟器的值，使机器人处于前进状态
输入：机器人状态
输出：机器人状态
"""
def robot_advance(robot_state):
    # 根据在机器人在期望节点前后设置前进还是后退
    # velocit_y= math.sqrt((robot_state.area_center_next[0]-robot_state.path[robot_state.node_id-1][0])**2 +
    #                      (robot_state.area_center_next[1]-robot_state.path[robot_state.node_id-1][1])**2) * 0.001
    
    #机器人前进的速度
    velocit_y = 0.8

    if robot_state.area_direction_now == -90:                   #如果方向为-90°，即向下
        robot_expected_y = robot_state.area_center_next[1]      #期望节点纵坐标
        robot_now_y = robot_state.robot_center[1]               #机器人当前纵坐标
        if robot_now_y <= robot_expected_y:                     #如果机器人当前纵坐标小于期望节点纵坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前纵坐标大于期望节点纵坐标，则后退
            robot_state.motion.y = -velocit_y
    elif robot_state.area_direction_now == 90:                  #如果方向为90°，即向上
        robot_expected_y = robot_state.area_center_next[1]      #期望节点纵坐标  
        robot_now_y = robot_state.robot_center[1]               #机器人当前纵坐标
        if robot_now_y >= robot_expected_y:                     #如果机器人当前纵坐标大于期望节点纵坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前纵坐标小于期望节点纵坐标，则后退
            robot_state.motion.y = -velocit_y
    elif robot_state.area_direction_now == 0:                   #如果方向为0°，即向右
        robot_expected_x = robot_state.area_center_next[0]      #期望节点横坐标
        robot_now_x = robot_state.robot_center[0]               #机器人当前横坐标
        if robot_now_x <= robot_expected_x:                     #如果机器人当前横坐标小于期望节点横坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前横坐标大于期望节点横坐标，则后退
            robot_state.motion.y = -velocit_y
    elif robot_state.area_direction_now == 180:                 #如果方向为180°，即向左
        robot_expected_x = robot_state.area_center_next[0]      #期望节点横坐标
        robot_now_x = robot_state.robot_center[0]               #机器人当前横坐标
        if robot_now_x >= robot_expected_x:                     #如果机器人当前横坐标大于期望节点横坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前横坐标小于期望节点横坐标，则后退
            robot_state.motion.y = -velocit_y
    elif robot_state.area_direction_now == 45:                  #如果方向为45°，即右上
        robot_expected_x = robot_state.area_center_next[0]      #期望节点横坐标
        robot_expected_y = robot_state.area_center_next[1]      #期望节点纵坐标
        robot_now_x = robot_state.robot_center[0]               #机器人当前横坐标
        robot_now_y = robot_state.robot_center[1]               #机器人当前纵坐标
        if robot_now_x <= robot_expected_x and robot_now_y >= robot_expected_y: #如果机器人当前横坐标小于期望节点横坐标且纵坐标大于期望节点纵坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前横坐标大于期望节点横坐标或纵坐标小于期望节点纵坐标，则后退
            robot_state.motion.y = -velocit_y
    elif robot_state.area_direction_now == -45:                 #如果方向为-45°，即左上
        robot_expected_x = robot_state.area_center_next[0]      #期望节点横坐标
        robot_expected_y = robot_state.area_center_next[1]      #期望节点纵坐标
        robot_now_x = robot_state.robot_center[0]               #机器人当前横坐标
        robot_now_y = robot_state.robot_center[1]               #机器人当前纵坐标
        if robot_now_x <= robot_expected_x and robot_now_y <= robot_expected_y: #如果机器人当前横坐标小于期望节点横坐标且纵坐标小于期望节点纵坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前横坐标大于期望节点横坐标或纵坐标小于期望节点纵坐标，则后退
            robot_state.motion.y = -velocit_y

    elif robot_state.area_direction_now == 135:                 #如果方向为135°，即右下
        robot_expected_x = robot_state.area_center_next[0]      #期望节点横坐标
        robot_expected_y = robot_state.area_center_next[1]      #期望节点纵坐标
        robot_now_x = robot_state.robot_center[0]               #机器人当前横坐标
        robot_now_y = robot_state.robot_center[1]               #机器人当前纵坐标
        if robot_now_x >= robot_expected_x and robot_now_y >= robot_expected_y: #如果机器人当前横坐标大于期望节点横坐标且纵坐标大于期望节点纵坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前横坐标小于期望节点横坐标或纵坐标小于期望节点纵坐标，则后退
            robot_state.motion.y = -velocit_y
    elif robot_state.area_direction_now == -135:                #如果方向为-135°，即左下
        robot_expected_x = robot_state.area_center_next[0]      #期望节点横坐标
        robot_expected_y = robot_state.area_center_next[1]      #期望节点纵坐标
        robot_now_x = robot_state.robot_center[0]               #机器人当前横坐标
        robot_now_y = robot_state.robot_center[1]               #机器人当前纵坐标
        if robot_now_x >= robot_expected_x and robot_now_y <= robot_expected_y: #如果机器人当前横坐标大于期望节点横坐标且纵坐标小于期望节点纵坐标，则前进
            robot_state.motion.y = velocit_y
        else:                                                   #如果机器人当前横坐标小于期望节点横坐标或纵坐标小于期望节点纵坐标，则后退
            robot_state.motion.y = -velocit_y

    # 垂推暂时不开
    # robot_state.motion.z = 0

    """
    新机器无平移功能，暂时先注释
    """
    # 控制机器人的平移，使机器人沿着当前节点和期望节点之间的连线运动
    # if robot_state.area_direction_now == 90:
    #     robot_expected_x = robot_state.area_center_next[0]
    #     robot_now_x = robot_state.robot_center[0]
    #     robot_state.motion.x = robot_state.PID_controller_motion_translate.calculate(robot_expected_x,robot_now_x)
    # elif robot_state.area_direction_now == -90:
    #     robot_expected_x = robot_state.area_center_next[0]
    #     robot_now_x = robot_state.robot_center[0]
    #     robot_state.motion.x = -robot_state.PID_controller_motion_translate.calculate(robot_expected_x, robot_now_x)
    # elif robot_state.area_direction_now == 0:
    #     robot_expected_y = robot_state.area_center_next[1]
    #     robot_now_y = robot_state.robot_center[1]
    #     robot_state.motion.x = robot_state.PID_controller_motion_translate.calculate(robot_expected_y, robot_now_y)
    # elif robot_state.area_direction_now == 180:
    #     robot_expected_y = robot_state.area_center_next[1]
    #     robot_now_y = robot_state.robot_center[1]
    #     robot_state.motion.x = -robot_state.PID_controller_motion_translate.calculate(robot_expected_y, robot_now_y)
    # elif robot_state.area_direction_now in [-45, 45, 135, -135]:
    #     A = robot_state.area_center_now
    #     B = robot_state.area_center_next
    #     C = robot_state.robot_center
    #     distance = calculate_point_to_line_distance(A, B, C, robot_state.area_direction_now)          #实现倾斜角度的平移
    #     robot_state.motion.x = robot_state.PID_controller_motion_translate.calculate(0, distance)

    """
    设想用旋转来代替平移量---测试
    """
    if robot_state.area_direction_now == 90:                    #方向为向上，对比横坐标来使用PID控制器
        robot_expected_x = robot_state.area_center_next[0]
        robot_now_x = robot_state.robot_center[0]
        robot_state.motion.rot = robot_state.PID_controller_motion_rotation_advancing.calculate(robot_expected_x,robot_now_x)
        # if abs(robot_expected_x - robot_now_x) > 40:            #如果机器人中心与期望路径距离相差太远，则使用PID控制器进行大调
        #     robot_state.motion.y = 0.5

        # else:
        #     robot_state.motion.rot = robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,robot_state.robot_yaw)
    elif robot_state.area_direction_now == -90:
        robot_expected_x = robot_state.area_center_next[0]
        robot_now_x = robot_state.robot_center[0]
        robot_state.motion.rot = -robot_state.PID_controller_motion_rotation_advancing.calculate(robot_expected_x, robot_now_x)
    elif robot_state.area_direction_now == 0:
        robot_expected_y = robot_state.area_center_next[1]
        robot_now_y = robot_state.robot_center[1]
        robot_state.motion.rot = robot_state.PID_controller_motion_rotation_advancing.calculate(robot_expected_y, robot_now_y)
    elif robot_state.area_direction_now == 180:
        robot_expected_y = robot_state.area_center_next[1]
        robot_now_y = robot_state.robot_center[1]
        robot_state.motion.rot = -robot_state.PID_controller_motion_rotation_advancing.calculate(robot_expected_y, robot_now_y)
        
    elif robot_state.area_direction_now in [-45, 45, 135, -135]:
        A = robot_state.area_center_now
        B = robot_state.area_center_next
        C = robot_state.robot_center
        distance = calculate_point_to_line_distance(A, B, C, robot_state.area_direction_now)          #实现倾斜角度的平移
        robot_state.motion.rot = robot_state.PID_controller_motion_rotation_advancing.calculate(0, distance)

    """
    这里的旋转指的是机器人在执行前进指令时的微调旋转，防止机器人偏离路线
    但是没搞懂PID赋值，这边需要注意！！！
    """
    # 控制机器人的旋转，使机器人沿着当前节点和期望节点之间的连线运动
    # if robot_state.area_direction_now in [0, 90, -90, 180]:
    #     if robot_state.area_direction_now == 180:
    #         if robot_state.robot_yaw < -90:
    #             robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(-robot_state.area_direction_now, robot_state.robot_yaw)
    #         else:
    #             robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now, robot_state.robot_yaw)
    #     else:
    #         robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now, robot_state.robot_yaw)
    # elif robot_state.area_direction_now in [45, -45, 135, -135]:
    #     if robot_state.area_direction_now == -135:
    #         if robot_state.robot_yaw < 45:
    #             robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now, robot_state.robot_yaw)
    #         else:
    #             robot_state.motion.rot = robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,robot_state.robot_yaw)
    #         # robot_state.motion.rot = robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,robot_state.robot_yaw)
    #     else:
    #         robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,robot_state.robot_yaw)
        
        # if robot_state.area_direction_now == 45:
        #     target_yaw = 45
        # elif robot_state.area_direction_now == -45:
        #     target_yaw = -45
        # elif robot_state.area_direction_now == 135:
        #     target_yaw = 135
        # elif robot_state.area_direction_now == -135:
        #     target_yaw = -135
        # robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(target_yaw,
        #                                                                                robot_state.robot_yaw)

    # 控制机器人的旋转，使机器人沿着当前节点和期望节点之间的连线运动
    # if robot_state.area_direction_now == 180:
    #     if robot_state.robot_yaw < -90:
    #         robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(
    #             -robot_state.area_direction_now,
    #             robot_state.robot_yaw)
    #     else:
    #         robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(
    #             robot_state.area_direction_now,
    #             robot_state.robot_yaw)
    # else:
    #     robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(
    #         robot_state.area_direction_now,
    #         robot_state.robot_yaw)

    return robot_state


"""
更新手柄模拟器的值，使机器人处于旋转状态
此处的旋转不同于robot_advance中的旋转，这里的旋转指的是机器人进行节点之前大角度旋转
输入：机器人状态
输出：机器人状态
"""
def robot_revolve(robot_state):
    # 旋转时，关闭直线、旋转、平移功能 --->移除平移、垂推 
    # robot_state.motion.x = 0
    robot_state.motion.y = 0
    # robot_state.motion.z = 0

    # 根据当前方向和期望方向，更新旋转控制值
    if robot_state.area_direction_now == 180:
        if robot_state.robot_yaw < -45:
            robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(-robot_state.area_direction_now,
                                                                                           robot_state.robot_yaw)
        else:
            robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,
                robot_state.robot_yaw)
    elif robot_state.area_direction_now == -90:
        if robot_state.robot_yaw > 135:
            robot_state.motion.rot = robot_state.PID_controller_motion_rotation.calculate(-robot_state.area_direction_now,
                                                                                           robot_state.robot_yaw)
        else:
            robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,
                robot_state.robot_yaw)
    elif robot_state.area_direction_now == 90:
        if robot_state.robot_yaw < -90:
            robot_state.motion.rot = robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,
                                                                                           robot_state.robot_yaw)
        else:
            robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,
                robot_state.robot_yaw)
    elif robot_state.area_direction_now == 0:
        robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,
                                                                                       robot_state.robot_yaw)
    elif robot_state.area_direction_now in [45, -45, 135, -135]:
        if robot_state.area_direction_now == -135:
            if robot_state.robot_yaw < 45:
                robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now, robot_state.robot_yaw)
            else:
                robot_state.motion.rot = robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,robot_state.robot_yaw)
        else:
            robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(robot_state.area_direction_now,robot_state.robot_yaw)

        # if robot_state.area_direction_now == 45:
        #     target_yaw = 45
        # elif robot_state.area_direction_now == -45:
        #     target_yaw = -45
        # elif robot_state.area_direction_now == 135:
        #     target_yaw = 135
        # elif robot_state.area_direction_now == -135:
        #     target_yaw = -135
        # robot_state.motion.rot = -robot_state.PID_controller_motion_rotation.calculate(target_yaw, robot_state.robot_yaw)

    return robot_state


#创建机器人状态器
# robot_state=Robot_state()
#是否第一次进入导航：默认是
navigation_first_start = True
#是否进行导航方向判断：默认否
area_direction_judgement = False

"""
机器人初始化函数，用于使机器人靠近路径的起点。
    
输入：
    robot_state: 当前机器人状态
    threshold: 若机器人中心距起点超过该距离，才会触发初始化（单位：像素）

输出：
    robot_state: 更新后的机器人状态
    init_done: 是否已经靠近起点（True 表示初始化完成）
"""
def robot_initialize(robot_state, threshold=200) :
    distance_to_start = distance_AB(robot_state.robot_center, robot_state.path[0])
    
    # 记录起点
    start_point = robot_state.path[0]

    # 如果机器人已经靠近起点
    if distance_to_start <= threshold:
        print("已靠近起点，不需要初始化")
        return robot_state, True  # 初始化完成

    # 设置当前目标为路径起点（只在初始化中使用，不更新 node_id）
    robot_state.area_center_now = robot_state.robot_center
    robot_state.area_center_next = start_point

    # 计算期望前进方向（朝起点）
    _, robot_state.area_direction_now, _ = Movement_planning(robot_state)

    # 仅进行旋转 + 前后移动，确保能朝起点方向前进
    robot_state = robot_revolve(robot_state)
    
    # 如果朝向已大致对准，开始前进靠近起点
    if abs(abs(robot_state.robot_yaw) - abs(robot_state.area_direction_now)) <= 30:
        robot_state = robot_advance(robot_state)

    return robot_state, False  # 还未到达，继续靠近中

"""
输入当前的位置和姿态，进行导航
输入：机器人的位置、与角度(方向)
输出：手柄模拟器的值，导航是否结束
"""
def navigation_function(robot_state,results):
    # global robot_state
    global navigation_first_start
    global area_direction_judgement
    #获取机器人姿态（位置和方向）
    robot_state.robot_center = results[0]
    robot_state.robot_yaw = results[1]
    #判断是否刚启动，是的话获得初次运动的期望节点，期望方向
    if navigation_first_start == True:
        navigation_first_start = False  #第一次启动后，将navigation_first_start设置为False
        robot_state.area_center_next, robot_state.area_direction_now,robot_state.navigation_over_flag = Movement_planning(robot_state)
    # 当机器人离开当前节点时，将area_direction_judgement设置为False,暂时不需要重新判断期望方向
    # print("离上一个节点距离:",  distance_AB(robot_state.robot_center, robot_state.area_center_now))
    if distance_AB(robot_state.robot_center, robot_state.area_center_now) <= 20:    #离开当前区域节点过近，不需要更新方向
        area_direction_judgement = False
    # print("与当前节点距离:", distance_AB(robot_state.robot_center, robot_state.area_center_now))
    #123123
    # if distance_AB(robot_state.robot_center, robot_state.area_center_next) <= 60 : #靠近期望节点附件，需要启动垂推进行吸污
    #     print("靠近污垢点，启动垂直推进器>>>")
    #     robot_state.motion.z = -0.8  #启动垂直推进器
    #     print(f"motion.z=={robot_state.motion.z}")
    # else:
    #     print("未靠近污垢点，关闭垂直推进器>>>")
    #     robot_state.motion.z = 0.0  #关闭垂推
    #     print(f"motion.z=={robot_state.motion.z}")
    # 当机器人到达期望节点时，将area_direction_judgement设置为Ture,表示需要重新判断期望方向
    # if distance_AB(robot_state.robot_center, robot_state.area_center_next) <= 40 :  #到达期望节点附近，需要重新判断期望方向 40修改到20
    if distance_AB(robot_state.robot_center, robot_state.area_center_next) <= 20 :
        print("到达节点附近，需要更新期望方向>>>")
        area_direction_judgement = True
    # 判断是否需要重新设置期望方向
    # 是的话表示已经走到期望节点了，这时候我们更新当前节点和期望节点，期望方向
    if area_direction_judgement == True:
        #更新区域当前节点
        robot_state.area_center_now = robot_state.area_center_next
        
        #更新上一次区域期望的方向
        robot_state.area_direction_last = robot_state.area_direction_now
        
        #更新区域期望节点、、导航是否结束
        robot_state.area_center_next,robot_state.area_direction_now,robot_state.navigation_over_flag= Movement_planning(robot_state)    
        area_direction_judgement = False
        # print("方向",robot_state.area_direction_now)

    # print("期望方向：", robot_state.area_direction_now)
    # print("上一次期望方向：", robot_state.area_direction_last)
    #运动控制，更新手柄控制值
    
    #如果本次期望方向和上一次期望方向一样，说明机器人不需要旋转，直接前进就行
    if robot_state.area_direction_now == robot_state.area_direction_last:
        robot_state = robot_advance(robot_state)
        # print("前进：", robot_state.motion.y)
        
    #如果本次期望方向和上一次期望方向不一样，说明机器人需要旋转，调用旋转函数
    else:
        robot_state = robot_revolve(robot_state)

        #如果当前期望方向和上一次期望方向的差值小于30度，说明机器人已经旋转到位，更新上一次期望方向
        if abs(abs(robot_state.robot_yaw)-abs(robot_state.area_direction_now)) <= 30:
            robot_state.area_direction_last = robot_state.area_direction_now

    return robot_state.motion,robot_state.navigation_over_flag


class Pool_Navigation_Task(LoopTask):
    def __init__(self, system, frames, label, server=None):
        """
        初始化

        :param system: 执行此任务的系统
        :param frames: 由CVFrameIterator实例提供的帧图像迭代器
        :param server: 机器人服务器实例，默认为系统中的服务器
        """
        super().__init__(system)
        self.label = label
        self.frames = frames
        self.frame = None
        self.server = server if server else system.server
        # self.recognition_function = multilayer_navigation_arithmetics.recognition_function
        # self.navigation_function = multilayer_navigation_arithmetics.navigation_function
        self.recognition_function = recognition_function
        self.navigation_function = navigation_function
        self.detect_first_frame_flag = True
        self.robot_state = None
        self.overlay = None
        self.model = YOLO('best4.21.pt')

    async def loop(self):
        """
        实现自主水下机器人的目标物体识别和导航移动的任务。

        :return: None
        """
        # start_time = time.time()  # 开始计时
        await super().loop()
        self.frame = next(self.frames)
        if self.frame is None:
            logging.info("pool_auv机位无画面!")
            return
        #进行第一帧的机器人画面识别与污垢检测
        if self.detect_first_frame_flag:
            #获取机器人中心点和污垢中心点
            rob_center, dirt_centers = multilayer_obstacle_traversal_planner.detect_first_frame_centers(self.frame, self.model)
            # print(f"rob_center_first_frame：{rob_center}, dirt_centers_first_frame：{dirt_centers}")
            rob_center = []
            dirt_centers = []
            #获取路径和地图的绘制结果
            path_real, self.overlay = multilayer_obstacle_traversal_planner.return_path(rob_center, dirt_centers)
            self.label.setText("工作中")
            #实例化机器人状态
            self.robot_state = Robot_state(path_real)
            #将第一帧处理标志关闭
            self.detect_first_frame_flag = False
        self.robot_state.motion.z = -0.8 # 启动垂直推进器
        # 识别Apriltag码，确认机器人的中心点与方向 [center,yaw]
        results = self.recognition_function(self.frame, self.overlay, self.model)
        """
        注释掉这部分代码，发现在进行吸污的时候水花会扰乱识别，导致识别不到机器人位置从而将手柄值清0
        """
        if results==[]:
            self.motion.clear()
            pass
        else:
        # 从 robot_state 中获取最新导航后的控制值，赋值给 self.motion
            self.motion,navigation_over_flag = self.navigation_function(self.robot_state,results)
            if navigation_over_flag == True:
                self.motion.clear()
                await self.server.move(**self.motion.__dict__)
                await asyncio.sleep(0.1)
                self.running = False
            
        await self.server.move(**self.motion.__dict__)
        await asyncio.sleep(0.001)

        if cv2.waitKey(1) & 0xFF == 27:  # 结束任务-按下ESC键
            self.motion.clear()
            await self.server.move(**self.motion.__dict__)
            await asyncio.sleep(0.1)
            evaluate_level = multilayer_obstacle_traversal_planner.evaluate_pool_frame(self.frame, 'evaluate_model.pth')
            print("evaluate_level:", evaluate_level)
            self.frames.stop()
            self.running = False
            # stop_flag = self.is_task_done() #返回任务是否结束 True
            # print('stop_flag:',stop_flag)
            # print("任务结束")