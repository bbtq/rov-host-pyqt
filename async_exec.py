import asyncio
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures.process import ProcessPoolExecutor
from enum import Enum


class ConcurrentMethod(Enum):
    Coroutine = 0
    Thread = 1


class AsyncExecutor:
    def __init__(self):
        self.thread_pool_executor = ThreadPoolExecutor(4)
        self.process_pool_executor = ProcessPoolExecutor(4)
        self.event_loop = asyncio.get_event_loop()

    #让一个协程函数在单独线程中运行
    def run_in_thread(self, function, *args, **kwargs):
        def run(async_function, *args, **kwargs):
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(async_function(*args, **kwargs))
            except Exception as e:
                print(e)
                raise e
            finally:
                loop.close()

        return self.event_loop.run_in_executor(self.thread_pool_executor, run, function, *args, **kwargs)
    
    #把普通函数放进进程池异步运行
    def run_in_process(self, function, *args, **kwargs):
        return self.event_loop.run_in_executor(self.process_pool_executor, function, *args, **kwargs)
    
    #直接调度一个异步函数为协程任务（常用于 main loop 或任务列表中）
    def run_in_coroutine(self, function, *args, **kwargs):
        return self.event_loop.create_task(function(*args, **kwargs))

    #根据传入的并发方式类型（枚举）创建协程锁或线程锁封装类
    def create_lock(self, concurrent_method=ConcurrentMethod.Coroutine):
        if concurrent_method == ConcurrentMethod.Coroutine:
            return CoroutineLock(asyncio.Lock())
        elif concurrent_method == ConcurrentMethod.Thread:
            return ThreadLock(threading.Lock(), self.thread_pool_executor)


class AsyncTask(AsyncExecutor):
    async def run(self):
        pass

    def start(self):
        self.event_loop.run_until_complete(self.run())


class AsyncLock():
    """
    线程锁、协程锁的代理
    """

    def __init__(self, lock):
        self.lock = lock

    async def acquire(self):
        pass

    def release(self):
        pass


class ThreadLock(AsyncLock):
    def __init__(self, lock, executor):
        super().__init__(lock)
        self.executor = executor

    async def acquire(self):
        def run():
            self.lock.acquire()

        await asyncio.get_event_loop().run_in_executor(self.executor, run)

    def release(self):
        self.lock.release()


class CoroutineLock(AsyncLock):
    async def acquire(self):
        await self.lock.acquire()

    def release(self):
        self.lock.release()
