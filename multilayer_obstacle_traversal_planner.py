import warnings

warnings.filterwarnings("ignore")
import heapq
import numpy as np
import cv2
import torch
from pyapriltags import Detector
from ultralytics import YOLO
from PIL import Image
from torchvision import transforms
from torchvision.models import resnet18, ResNet18_Weights


# from multilayer_detect_return_results import detect_first_frame_centers_CVFrameIterator
# 定义节点类，用于A*算法中的节点
class Node:
    def __init__(self, parent=None, position=None):
        self.parent = parent  # 父节点
        self.position = position  # 节点在网格中的位置

        self.g = 0  # 从起点到当前节点的代价
        self.h = 0  # 从当前节点到终点的预估代价（启发式函数）
        self.f = 0  # 总代价 f = g + h

    # 重载等于运算符，用于比较两个节点是否相同
    def __eq__(self, other):
        return self.position == other.position

    # 重载小于运算符，用于优先队列中节点的排序
    def __lt__(self, other):
        return self.f < other.f

    # 重载哈希运算符，使节点可以被添加到集合中
    def __hash__(self):
        return hash(self.position)


def distance_to_obstacle(grid, position):
    """计算节点与障碍物的最小距离"""
    min_distance = float('inf')
    for i in range(len(grid)):
        for j in range(len(grid[0])):
            if grid[i][j] != 0:  # 如果是障碍物
                distance = abs(position[0] - i) + abs(position[1] - j)  # 曼哈顿距离
                min_distance = min(min_distance, distance)
    return min_distance


# # A*算法的实现
# def astar_search(grid, start, end, mode=0):
#     start_node = Node(None, start)  # 创建起始节点
#     end_node = Node(None, end)  # 创建终止节点

#     open_list = []  # 创建开放列表（待处理节点）
#     heapq.heappush(open_list, start_node)  # 将起始节点添加到开放列表中
#     closed_list = set()  # 创建闭合列表（已处理节点）

#     # 开始搜索
#     while open_list:
#         current_node = heapq.heappop(open_list)  # 从开放列表中取出代价最小的节点
#         closed_list.add(current_node)  # 将当前节点添加到闭合列表中

#         # 如果找到终点，返回路径
#         if current_node == end_node:
#             path = []
#             while current_node:
#                 path.append(current_node.position)
#                 current_node = current_node.parent
#             return path[::-1]  # 反转路径

#         neighbors = []
#         # 获取当前节点的所有邻居节点
#         for new_position in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)] if mode ==1 else [(0, -1), (0, 1), (-1, 0), (1, 0)]:
#             # mode == 1 取八个方向(对于小网格)，mode == 0 取四个方向(对于大网格)
#             node_position = (current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])
#             # 检查邻居节点是否在网格范围内
#             if node_position[0] < 0 or node_position[0] >= len(grid) or node_position[1] < 0 or node_position[1] >= len(grid[0]):
#                 continue
#             # 检查邻居节点是否为障碍物
#             if grid[node_position[0]][node_position[1]] != 0:
#                 continue
#             new_node = Node(current_node, node_position)  # 创建邻居节点
#             neighbors.append(new_node)

#         # 处理所有邻居节点
#         for neighbor in neighbors:
#             if neighbor in closed_list:
#                 continue
#             neighbor.g = current_node.g + 1 # 否则，g值自加1
#             neighbor.h = abs(neighbor.position[0] - end_node.position[0]) + abs(neighbor.position[1] - end_node.position[1])  # 使用曼哈顿距离作为启发式函数
#             neighbor.f = neighbor.g + neighbor.h

#             # 如果邻居节点已经在开放列表中，且新的g值更大，则跳过
#             if any(neighbor == open_node and neighbor.g > open_node.g for open_node in open_list):
#                 continue
#             heapq.heappush(open_list, neighbor)  # 将邻居节点添加到开放列表中

#     return None  # 如果没有找到路径，返回None

# 加入转弯惩罚项
def astar_search(grid, start, end):
    start_node = Node(None, start)
    end_node = Node(None, end)

    open_list = []
    heapq.heappush(open_list, start_node)
    closed_list = set()

    while open_list:
        current_node = heapq.heappop(open_list)
        closed_list.add(current_node)

        if current_node == end_node:
            path = []
            while current_node:
                path.append(current_node.position)
                current_node = current_node.parent
            return path[::-1]

        neighbors = []
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0),
                      (-1, -1), (-1, 1), (1, -1), (1, 1)]
        for new_position in directions:
            node_position = (current_node.position[0] + new_position[0],
                             current_node.position[1] + new_position[1])

            if node_position[0] < 0 or node_position[0] >= len(grid) or node_position[1] < 0 or node_position[1] >= len(
                    grid[0]):
                continue
            if grid[node_position[0]][node_position[1]] != 0:
                continue

            new_node = Node(current_node, node_position)
            neighbors.append((new_node, new_position))

        for neighbor, direction in neighbors:
            if neighbor in closed_list:
                continue

            # 转向惩罚项：与上一步方向不一致就惩罚
            turn_penalty = 0
            if current_node.parent:
                prev_dir = (current_node.position[0] - current_node.parent.position[0],
                            current_node.position[1] - current_node.parent.position[1])
                if prev_dir != direction:
                    turn_penalty = 1.5  # 可以调节

            base_cost = 1.4 if abs(direction[0]) + abs(direction[1]) == 2 else 1
            neighbor.g = current_node.g + base_cost + turn_penalty

            neighbor.h = abs(neighbor.position[0] - end_node.position[0]) + abs(
                neighbor.position[1] - end_node.position[1])
            neighbor.f = neighbor.g + neighbor.h

            if any(neighbor == open_node and neighbor.g > open_node.g for open_node in open_list):
                continue
            heapq.heappush(open_list, neighbor)

    return None


def compute_distance_matrix(points, grid, cell_size):
    """基于A*路径长度构建距离矩阵，points为像素坐标列表"""
    coords = [(p[1] // cell_size, p[0] // cell_size) for p in points]
    n = len(coords)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            path = astar_search(grid, coords[i], coords[j])
            d = len(path) if path else 1e9
            dist[i][j] = dist[j][i] = d
    return dist


def nearest_neighbor_path(dist_matrix):
    """最近邻初始路径"""
    n = len(dist_matrix)
    visited = [False] * n
    path = [0]  # 从起点出发
    visited[0] = True
    for _ in range(n - 1):
        last = path[-1]
        next_node = np.argmin([dist_matrix[last][j] if not visited[j] else 1e9 for j in range(n)])
        path.append(next_node)
        visited[next_node] = True
    return path


def two_opt(path, dist_matrix):
    """2-opt 路径局部优化"""
    improved = True
    while improved:
        improved = False
        for i in range(1, len(path) - 2):
            for j in range(i + 1, len(path)):
                if j - i == 1:
                    continue
                a, b = path[i - 1], path[i]
                c, d = path[j - 1], path[j % len(path)]
                if dist_matrix[a][b] + dist_matrix[c][d] > dist_matrix[a][c] + dist_matrix[b][d]:
                    path[i:j] = reversed(path[i:j])
                    improved = True
    return path


def nearest_neighbor_with_angle(start_idx, dist_matrix, coords):
    n = len(dist_matrix)
    visited = [False] * n
    path = [start_idx]
    visited[start_idx] = True
    current = start_idx
    last_direction = None

    for _ in range(n - 1):
        best_cost = float('inf')
        next_node = None

        for j in range(n):
            if visited[j]:
                continue
            # 方向代价计算
            direction = np.array(coords[j]) - np.array(coords[current])
            if last_direction is not None:
                cosine = np.dot(direction, last_direction) / (
                        np.linalg.norm(direction) * np.linalg.norm(last_direction) + 1e-6)
                angle_penalty = (1 - cosine) * 10  # 可调节，cos越小惩罚越大
            else:
                angle_penalty = 0

            cost = dist_matrix[current][j] + angle_penalty
            if cost < best_cost:
                best_cost = cost
                next_node = j
                best_dir = direction

        path.append(next_node)
        visited[next_node] = True
        last_direction = best_dir
        current = next_node

    return path


# 加载相机内参矩阵和畸变系数
def load_matrix_K_dist(file_name):
    """
    加载txt文件，txt文件内容为相机内参矩阵和畸变系数
    输入：文件名
    输出：相机内参矩阵和畸变系数
    """
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
    # print("load txt... 进行第一帧的检测")
    # print(camera_matrix)
    # print(dist_coeffs)
    return (camera_matrix, dist_coeffs)


# 对视频帧进行预处理（去畸变、透视变换、高亮区域检测、修复）
def videos_preprocessing_detect(frame):
    """
    对视频帧进行预处理（去畸变、透视变换、高亮区域检测、修复）
    输入：视频帧
    输出：预处理后的视频帧
    """

    K, distortion_coeffs = load_matrix_K_dist('calibrate_front_1080P.txt')

    # 透视变换参数
    # 确保 src_pts 和 dst_pts 形状正确
    src_pts = np.array([[193, 40], [1600, 166], [1620, 720], [193, 715]], dtype=np.float32)
    dst_pts = np.array([[0, 0], [1920, 0], [1920, 1080], [0, 1080]], dtype=np.float32)

    # print("src_pts shape:", src_pts.shape)  # 应该输出 (4, 2)
    # print("dst_pts shape:", dst_pts.shape)  # 应该输出 (4, 2)

    # 计算透视变换矩阵
    if src_pts.shape == (4, 2) and dst_pts.shape == (4, 2):
        M_perspective = cv2.getPerspectiveTransform(src_pts, dst_pts)
        # print("M_perspective 矩阵计算成功:", M_perspective)
    else:
        print("Error: src_pts 或 dst_pts 形状错误")

    # brightness_threshold = 200

    # 1️⃣ **去畸变**
    undistorted_frame = cv2.undistort(frame, K, distortion_coeffs)

    # 2️⃣ **透视变换**
    warped_frame = cv2.warpPerspective(undistorted_frame, M_perspective, (1920, 1080))

    repaired_frame = warped_frame
    # 3️⃣ **高亮区域检测**
    # gray = cv2.cvtColor(warped_frame, cv2.COLOR_BGR2GRAY)
    # _, bright_spots = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)

    # 4️⃣ **形态学操作（去噪）**
    # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    # smooth_mask = cv2.morphologyEx(bright_spots, cv2.MORPH_CLOSE, kernel)

    # 5️⃣ **修复高亮区域**
    # repaired_frame = cv2.inpaint(warped_frame, smooth_mask, 5, cv2.INPAINT_TELEA)

    return repaired_frame


# 对视频帧进行预处理（去畸变、透视变换、高亮区域检测、修复）
def videos_preprocessing_evaluate(frame):
    """
    对视频帧进行预处理（去畸变、透视变换、高亮区域检测、修复）
    输入：视频帧
    输出：预处理后的视频帧
    """
    K, distortion_coeffs = load_matrix_K_dist('calibrate_front_1080P.txt')

    # 透视变换参数
    # 确保 src_pts 和 dst_pts 形状正确
    src_pts = np.array([[193, 40], [1600, 166], [1620, 720], [193, 715]], dtype=np.float32)
    dst_pts = np.array([[0, 0], [1920, 0], [1920, 1080], [0, 1080]], dtype=np.float32)

    # 计算透视变换矩阵
    if src_pts.shape == (4, 2) and dst_pts.shape == (4, 2):
        M_perspective = cv2.getPerspectiveTransform(src_pts, dst_pts)
        # print("M_perspective 矩阵计算成功:", M_perspective)
    else:
        print("Error: src_pts 或 dst_pts 形状错误")

    brightness_threshold = 200

    # 1️⃣ **去畸变**
    undistorted_frame = cv2.undistort(frame, K, distortion_coeffs)

    # 2️⃣ **透视变换**
    warped_frame = cv2.warpPerspective(undistorted_frame, M_perspective, (1920, 1080))

    # 3️⃣ **高亮区域检测**
    gray = cv2.cvtColor(warped_frame, cv2.COLOR_BGR2GRAY)
    _, bright_spots = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)

    # 4️⃣ **形态学操作（去噪）**
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    smooth_mask = cv2.morphologyEx(bright_spots, cv2.MORPH_CLOSE, kernel)

    # 5️⃣ **修复高亮区域**
    repaired_frame = cv2.inpaint(warped_frame, smooth_mask, 5, cv2.INPAINT_TELEA)

    return repaired_frame


# 检测第一帧机器人和污垢的位置：
def detect_first_frame_centers(frame, model):
    """
    处理视频的第一帧，并返回目标的中心点坐标列表。

    参数：
    - frame: 视频帧
    - model_path: str, YOLOv8 模型路径

    返回：
    - center_points: list of tuples, [(x1, y1), (x2, y2), ...] 目标框的中心点坐标
    """
    # 创建一个ApriTag检测器
    at_detector = Detector(
        families="tag25h9",
        nthreads=64,
        quad_decimate=1.0,
        quad_sigma=0,
        refine_edges=1,
        decode_sharpening=0.25,
        debug=0
    )
    # 相机内参矩阵 为AprilTag检测提供
    cameraMatrix = (811.184725, 1011.40783, 811.734172, 488.910479)

    # 加载模型
    # model = YOLO(model_path)

    repaired_frame = videos_preprocessing_detect(frame)

    # 检测机器人的初始位置
    repaired_frame_gray = cv2.cvtColor(repaired_frame, cv2.COLOR_BGR2GRAY)
    tagDetection = at_detector.detect(img=repaired_frame_gray, estimate_tag_pose=True, camera_params=cameraMatrix,
                                      tag_size=0.060325)
    # 获得图像中机器人的位置,为路径规划提供起点
    if tagDetection == []:
        print("no found Robot")
        Robot_center = []
    else:
        # 获取apriltag码的中心位置
        Robot_center = [(int(tagDetection[0].center[0]), int(tagDetection[0].center[1]))]
    #  **目标检测**
    # results = model(repaired_frame, device="cuda:0", conf=0.5, iou=0.7, verbose=False)

    #  **解析检测结果，获取中心点坐标**
    dirt_center_points = []
    # for result in results:
    #     for box in result.boxes:
    #         x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()  # 获取检测框坐标
    #         center_x = int((x1 + x2) / 2)  # 计算中心点 x 坐标
    #         center_y = int((y1 + y2) / 2)  # 计算中心点 y 坐标
    #         dirt_center_points.append((center_x, center_y))
    #         #可视化
    #         # 绘制边界框（绿色）
    #         cv2.rectangle(repaired_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
    #         # 绘制中心点（红色）
    #         cv2.circle(repaired_frame, (center_x, center_y), 5, (0, 0, 255), -1)

    # cv2.namedWindow('第一帧-检测机器人中心与污垢中心', cv2.WINDOW_NORMAL)
    # cv2.resizeWindow('第一帧-检测机器人中心与污垢中心', 800, 600)
    # cv2.imshow('第一帧-检测机器人中心与污垢中心', repaired_frame)
    # cv2.waitKey(1)

    return Robot_center, dirt_center_points  # 返回中心点列表


def evaluate_pool_frame(frame, model_path):
    """
    评估视频帧的分类结果
    输入：
        source: 可以是视频路径(str)或摄像头索引(int)
        model_path: 模型路径
    输出：分类结果（字符串形式的等级，1-5）
    """

    label_map = {0: "Level 1", 1: "Level 2", 2: "Level 3", 3: "Level 4", 4: "Level 5"}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # cap = None
    # try:
    # 定义和加载模型
    weights = ResNet18_Weights.IMAGENET1K_V1
    model = resnet18(weights=weights)
    model.fc = torch.nn.Linear(model.fc.in_features, 5)
    model.load_state_dict(torch.load(model_path))
    model.to(device)
    model.eval()
    print("加载评估模型！")

    # 定义图像预处理
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])
    ])

    # try:
    #     frame = cv2.imread(frame)

    # except StopIteration as e:
    #     print("无法读取帧")

    repaired_frame = videos_preprocessing_evaluate(frame)
    image = Image.fromarray(cv2.cvtColor(repaired_frame, cv2.COLOR_BGR2RGB))
    image = transform(image).unsqueeze(0).to(device)

    # 预测
    with torch.no_grad():
        outputs = model(image)
        _, predicted = torch.max(outputs, 1)
        predicted_class = predicted.item()

    # 处理预测结果
    predicted_label = label_map.get(predicted_class, "Unknown")
    # if predicted_label == "Unknown":
    #     return 5

    # try:
    result = predicted_label.split()[1]
    # except IndexError:
    #     return 5

    # 显示结果
    cv2.putText(repaired_frame, f"Predicted: {predicted_label}",
                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("evaluate_level:", repaired_frame)
    cv2.waitKey(0)

    return result


# 地图网格构建
def create_map(start, ends, grid, grid_small, cell_size, small_cell_size, path_real):
    # 创建叠加图层
    overlay = np.zeros((1080, 1920, 3), np.uint8)

    # 绘制起点、终点、障碍物
    ends_small = ends
    start = (start[0][1] // cell_size, start[0][0] // cell_size)  # 转换起点坐标
    ends = [(end[1] // cell_size, end[0] // cell_size) for end in ends]  # 转换终点坐标
    ends_small = [(end[1] // small_cell_size, end[0] // small_cell_size) for end in ends_small]  # 转换终点坐标
    for x in range(grid.shape[0]):
        for y in range(grid.shape[1]):
            # 绘制障碍物和空白区域
            color = (0, 0, 255) if grid[x][y] == 1 else (255, 255, 255)
            cv2.rectangle(overlay, (y * cell_size, x * cell_size), ((y + 1) * cell_size, (x + 1) * cell_size),
                          color, -1)  # 绘制障碍物区域和可行区域
            cv2.rectangle(overlay, (y * cell_size, x * cell_size), ((y + 1) * cell_size, (x + 1) * cell_size),
                          (255, 0, 0), 8)  # 绘制大网格线  蓝色
    # 绘制小网格
    for x in range(grid_small.shape[0]):
        for y in range(grid_small.shape[1]):
            cv2.rectangle(overlay, (y * small_cell_size, x * small_cell_size),
                          ((y + 1) * small_cell_size, (x + 1) * small_cell_size),
                          (88, 87, 86), 3)  # 绘制小网格线  灰色

    # 绘制起点和终点---大网格——红色
    for point in [start] + ends:
        cv2.circle(overlay, (point[1] * cell_size + cell_size // 2, point[0] * cell_size + cell_size // 2), 10,
                   (0, 0, 255), 8)
    # 绘制起点和终点---小网格——绿色
    for point_small in ends_small:
        cv2.circle(overlay, (point_small[1] * small_cell_size + small_cell_size // 2,
                             point_small[0] * small_cell_size + small_cell_size // 2), 10, (0, 255, 0), 3)
    # 绘制路径
    for id in range(len(path_real) - 1):
        cv2.circle(overlay, path_real[id], 7, (255, 255, 255), -1)
        cv2.arrowedLine(overlay, path_real[id], path_real[id + 1], (255, 0, 0), thickness=10)
    return overlay


def get_path(start, ends_pixel, cell_size, small_cell_size, grid, grid_small):
    big_path = []
    small_path = []
    final_path = []
    final_path_real = []

    start_copy = start.copy()
    start_pixel = start[0]

    all_points = [start_pixel] + ends_pixel
    dist_matrix = compute_distance_matrix(all_points, grid, cell_size)
    coords = [(p[1] // cell_size, p[0] // cell_size) for p in all_points]
    optimal_path = nearest_neighbor_with_angle(0, dist_matrix, coords)

    ordered_ends_pixel = [all_points[i] for i in optimal_path[1:]]

    start = (start_pixel[1] // cell_size, start_pixel[0] // cell_size)
    ends_all = [
        (
            pixel,
            (pixel[1] // cell_size, pixel[0] // cell_size),
            (pixel[1] // small_cell_size, pixel[0] // small_cell_size)
        )
        for pixel in ordered_ends_pixel
    ]

    flag_first = True
    current_position = start

    while ends_all:
        if not flag_first:
            current_position = current_path[-1]

        closest_idx = 0
        pixel_end, big_end, small_end = ends_all.pop(closest_idx)
        current_path = astar_search(grid, current_position, big_end)
        if current_path:
            current_position = big_end

        if len(current_path) > 1:
            if len(current_path) > 2:
                if flag_first:
                    big_path.extend(current_path[:-1])
                    final_path.extend(current_path[:-1])
                    final_path_real.extend(
                        (p[0] * cell_size + cell_size // 2, p[1] * cell_size + cell_size // 2) for p in
                        current_path[:-1])
                else:
                    big_path.extend(current_path[1:-1])
                    final_path.extend(current_path[1:-1])
                    final_path_real.extend(
                        (p[0] * cell_size + cell_size // 2, p[1] * cell_size + cell_size // 2) for p in
                        current_path[1:-1])

                Turning_point = current_path[-2]
                Turning_point = (
                Turning_point[1] * cell_size + cell_size // 2, Turning_point[0] * cell_size + cell_size // 2)
                Turning_point = (Turning_point[1] // small_cell_size, Turning_point[0] // small_cell_size)
                path_small = []
                current_small_position = Turning_point
            else:
                if flag_first:
                    Turning_point = current_path[-2]
                    Turning_point = (
                    Turning_point[1] * cell_size + cell_size // 2, Turning_point[0] * cell_size + cell_size // 2)
                    Turning_point = (Turning_point[1] // small_cell_size, Turning_point[0] // small_cell_size)
                    path_small = [Turning_point]
                    current_small_position = Turning_point
                else:
                    path_small = [current_small_path[-1]]
                    current_small_position = current_small_path[-1]
        else:
            if flag_first:
                Turning_point = (start_copy[0][1] // small_cell_size, start_copy[0][0] // small_cell_size)
                current_small_position = Turning_point
            else:
                Turning_point = small_end
                current_small_position = small_end
            path_small = [Turning_point]

        current_small_path = astar_search(grid_small, current_small_position, small_end)
        if current_small_path:
            path_small.extend(current_small_path[1:])
            current_small_position = small_end

        if flag_first:
            small_path.extend(path_small)
            final_path.extend(path_small)
            final_path_real.extend(
                (p[0] * small_cell_size + small_cell_size // 2, p[1] * small_cell_size + small_cell_size // 2) for p in
                current_small_path)
        else:
            small_path.extend(current_small_path[1:])
            final_path.extend(current_small_path[1:])
            final_path_real.extend(
                (p[0] * small_cell_size + small_cell_size // 2, p[1] * small_cell_size + small_cell_size // 2) for p in
                current_small_path[1:])

        flag_first = False

    final_path_real = [(y, x) for x, y in final_path_real]
    return final_path, final_path_real


def return_path(rob_center, dirt_centers):
    video_path = "WIN_20240410_14_24_21_Pro.mp4"
    # video_path = 1
    model_path = "best.pt"
    # start, ends = detect_first_frame_centers(video_path, model_path)
    start, ends = rob_center, dirt_centers
    if start == []:
        start = [(150, 220)]

    if ends == []:
        """实测的点位
        # ends = [(450,150), (750,150), (1050,150), (1350,150), (450,450), (750,450), (1050,450), (1350, 450)]
        # ends = [(450,150), (750,150), (1050, 150), (450,450), (750,450),(150, 450), (1050,450)]
        """
        # 大网格300 小网格100
        # ends = [(450,150), (750,150), (1050,150), (1350,150), (450,450), (750,450), (1050,450), (1350, 450)]

        # 大网格240 小网格80
        ends = [(350, 150), (590, 150), (830, 150), (1070, 150), (1310, 150), (1310, 390), (1310, 630), (1310, 850)]
        # (350,350), (590,350), (830,350), (1070, 350), (1310,350)]

        # ends = [(765, 225), (1306, 286), (413, 220), (1019, 776), (1534, 778), (1255, 747),  (696, 345), (1677, 506), (1079, 315),(479, 786),(710, 676)]
    obstacles = []
    height, width = 1080, 1920  # h*w = 1080*1920
    # cell_size = 300  # 大网格尺寸
    # small_cell_size = 100  # 小网格尺寸
    cell_size = 240  # 大网格尺寸
    small_cell_size = 80  # 小网格尺寸
    grid = np.zeros((int(np.ceil(height / cell_size)), int(np.ceil(width / cell_size))), dtype=int)
    grid_small = np.zeros((int(np.ceil(height / small_cell_size)), int(np.ceil(width / small_cell_size))), dtype=int)
    for obstacle in obstacles:
        x, y = obstacle
        grid[y // cell_size, x // cell_size] = 1
    # 将大网格中的障碍物映射到小网格中
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if grid[i, j] == 1:
                # 计算对应的小网格区域
                small_start_y = i * (cell_size // small_cell_size)
                small_start_x = j * (cell_size // small_cell_size)
                small_end_y = small_start_y + (cell_size // small_cell_size)
                small_end_x = small_start_x + (cell_size // small_cell_size)
                grid_small[small_start_y:small_end_y, small_start_x:small_end_x] = 1
    # for end in ends:
    #     if grid[end[1]//cell_size,end[0]//cell_size] == 1 or grid_small[end[1]//small_cell_size,end[0]//small_cell_size] == 1:
    #         ends.remove(end)
    ends = [end for end in ends if not (grid[end[1] // cell_size, end[0] // cell_size] == 1 or grid_small[
        end[1] // small_cell_size, end[0] // small_cell_size] == 1)]

    # print(f"ends: {ends}")

    final_path, final_path_real = get_path(start, ends, cell_size, small_cell_size, grid, grid_small)
    # print(grid)
    # print(grid_small)
    overlay = create_map(start, ends, grid, grid_small, cell_size, small_cell_size, final_path_real)
    return final_path_real, overlay


def overlay():
    a, overlay = return_path([], [])
    return overlay


# 主程序入口
if __name__ == '__main__':
    a, overlay = return_path([], [])
    # print(overlay.shape)
    frame = cv2.imread('capture.jpg')
    frame = videos_preprocessing_detect(frame)
    overlay = cv2.addWeighted(frame, 0.8, overlay, 0.2, 0)
    cv2.imwrite("overlay.jpg", overlay)
    cv2.imshow("overlay", overlay)
    cv2.waitKey(0)
    # cv2.destroyAllWindows()
    print(f"path_real: {a}")