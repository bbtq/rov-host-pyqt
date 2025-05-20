import asyncio

from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QLabel, QProgressBar, QTreeView

from async_exec import AsyncExecutor
import logging
import jsonrpcclient as rpc
import requests
import time

# AUV服务器，通过向AUV服务器发送指定控制AUV
class AUVServer:
    MAX_RETRIES = 3

    def __init__(self, url):
        self.url = url

    """"
    访问一个实例中不存在的属性或方法时,Python 会自动调用 __getattr__ 方法。
    """
    def __getattr__(self, __name):
        async def function(*args, retry_count=0, **kwargs):
            data = None
            if args:
                data = args
            elif kwargs:
                data = kwargs
            try:
                res = rpc.parse(requests.post(self.url, json=rpc.request(__name, data)).json()).result  #发送RPC请求
                if retry_count > 0:
                    logging.info(f'JSONRPC reqeust succeeded after {retry_count} retries')
                return res
            except Exception as e:
                logging.warning(
                    f'JSONRPC Error [{retry_count + 1}/{self.MAX_RETRIES}]: {e} when sending {__name}({args}{kwargs})')
                if retry_count < self.MAX_RETRIES:
                    # await asyncio.sleep(retry_count + 1.0)
                    await function(*args, retry_count=retry_count + 1, **kwargs)
                else:
                    logging.error('JSONRPC max retry count of request is exceeded. Aborted.')
                return None

        return function

# 返回一个占位符对象，所有属性和方法都为空
class DummyAsync:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        async def function(*args, **kwargs):
            pass
            # print('{}({},{})'.format(name, args, kwargs))

        return function

# 假auv服务器，用于测试
FakeAUVServer = DummyAsync


class AUVSystem(AsyncExecutor):
    '''AUV 系统基类，传入给任务用于处理事件循环，保持 AUV 服务器的对象'''

    def __init__(self, server):
        super().__init__()
        self.server = server

    async def run_linked_task(self, task):
        next_task = await task.run()
        if type(next_task):
            return await self.run_linked_task(next_task)
        else:
            return next_task

    async def main_loop(self):
        pass

    def start(self):
        self.event_loop.run_until_complete(self.main_loop())

# 手柄模拟器（履带控制 无法左右平移————>删除x）
class Motion:
    def __init__(self):
        self.y = 0.0
        self.z = 0.0
        self.rot = 0.0

    def clear(self):
        self.y = 0.0
        self.z = 0.0
        self.rot = -1.0


class AUVTask:
    """AUV 任务基类"""

    def __init__(self, system):
        self.system = system
        self.server = system.server
        self.motion = Motion()
        pass

    async def run(self):
        return None

    def start(self):
        return self.system.event_loop.create_task(self.run())


# multilayer_auv.py
async def async_main(label, progress, model):
    from multilayer_tasks import CVFrameIterator, Pool_Navigation_Task
    class MyAUVSystem(AUVSystem):
        def __init__(self, server):
            super().__init__(server=server)
            iterator_pool = CVFrameIterator(0)
            self.main_task = Pool_Navigation_Task(self, iterator_pool, label, progress, model)
            # self.main_task = motion_test_Task(self, iterator_pool)

        async def lock_deep_and_direction(self):
            await self.server.set_depth_locked(False)
            await self.server.set_direction_locked(False)
            for i in range(3, 0, -1):
                logging.info('深度与方向将在 {} 秒后锁定…….'.format(i))
                await asyncio.sleep(1.0)
            await self.server.set_depth_locked(True)
            await self.server.set_direction_locked(True)
            logging.info('深度与方向已锁定。')

        async def test_control(self):
            test_list = [0.0, 0.0, 0.0]
            test_args = ['y', 'z', 'rot']
            server = self.server
            for i in range(len(test_list)):
                for j in range(2):
                    test_list[i] = 0.5 if j == 0 else -0.5  # 先左后右
                    server.motion_y, server.motion_z, server.motion_rotate = test_list
                    await server.move(**(dict(zip(test_args, test_list))))  # 发送控制指令
                    await asyncio.sleep(10)
                    test_list[i] = 0.0  # 归位 将值修改为0
                    await server.move(**(dict(zip(test_args, test_list))))  # 发送控制指令
                    await asyncio.sleep(1)
        async def main_loop(self):
            logging.info('开始工作')
            result = await self.main_task.start()
            print(result)

    url = 'http://192.168.137.219:8888'
    fake_server = FakeAUVServer()
    system = MyAUVSystem(fake_server)
    # system = MyAUVSystem(AUVServer(url=url))
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    await system.main_loop()


def main():
    # status_label = QLabel("工作状态")
    # progress_bar = QProgressBar()
    # tree_view = QTreeView()
    # infotree_model = QStandardItemModel()
    # infotree_model.setHorizontalHeaderLabels(['水下机器人', ' '])
    # tree_view.setModel(infotree_model)
    #
    # # Sample data
    # root = QStandardItem("清刷情况")
    # root.appendRow([QStandardItem('清刷面积'), QStandardItem('6m²')])
    # root.appendRow([QStandardItem('清刷时间'), QStandardItem('h')])
    # root.appendRow([QStandardItem('清刷效率'), QStandardItem('2m²/h')])
    # infotree_model.appendRow(root)


    asyncio.run(async_main())
    

if __name__ == '__main__':
    main()


# def main():
#     from multilayer_tasks import CVFrameIterator, \
#         Pool_Navigation_Task \
#
#
#     class MyAUVSystem(AUVSystem):
#         def __init__(self, server):
#             super().__init__(server=server)
#             iterator_pool = CVFrameIterator(0)
#             self.main_task = Pool_Navigation_Task(self, iterator_pool)
#             #self.main_task = motion_test_Task(self, iterator_pool)
#
#         async def lock_deep_and_direction(self):
#             await self.server.set_depth_locked(False)
#             await self.server.set_direction_locked(False)
#             for i in range(3, 0, -1):
#                 logging.info('深度与方向将在 {} 秒后锁定…….'.format(i))
#                 await asyncio.sleep(1.0)
#             await self.server.set_depth_locked(True)
#             await self.server.set_direction_locked(True)
#             logging.info('深度与方向已锁定。')
#
#         async def test_control(self):
#             test_list = [0.0, 0.0, 0.0]
#             test_args = ['y', 'z', 'rot']
#             server = self.server
#             for i in range(len(test_list)):
#                 for j in range(2):
#                     test_list[i] = 0.5 if j == 0 else -0.5  #先左后右
#                     server.motion_y, server.motion_z, server.motion_rotate = test_list
#                     await server.move(**(dict(zip(test_args, test_list))))  #发送控制指令
#                     await asyncio.sleep(10)
#                     test_list[i] = 0.0  #归位 将值修改为0
#                     await server.move(**(dict(zip(test_args, test_list))))  #发送控制指令
#                     await asyncio.sleep(1)
#
#         async def main_loop(self):
#             logging.info('开始工作')
#             # await self.lock_deep_and_direction()
#             await self.main_task.start()
#
#             # while True:
#             #     evaluate_level = evaluate_pool_CVFramesIterator_frame(1, "evaluate_model.pth")
#             #     if evaluate_level > 1:
#             #         await self.main_task.start()
#             #     else:
#             #         break #满足评估条件 结束循环
#
#
#     #system = MyAUVSystem(FakeAUVServer())
#     #通信地址
#     url = 'http://192.168.137.219:8888'
#     system = MyAUVSystem(AUVServer(url=url))
#     logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
#     system.start()
