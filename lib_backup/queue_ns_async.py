import uasyncio as asyncio

class SimpleQueue:
    def __init__(self):
        self._data = []
        self._get_event = asyncio.Event()
    def qsize(self):
        return len(self._data)
    def empty(self):
        return not self._data
    async def put(self, item):
        self._data.append(item)
        self._get_event.set()
    async def get(self):
        while not self._data:
            self._get_event.clear()
            await self._get_event.wait()
        return self._data.pop(0)
    def task_done(self):
        pass
    
class AsyncQueue:
    def __init__(self, initial_capacity=512):
        # 初始容量（自動擴增）
        self._size = initial_capacity
        self._queue = [None] * self._size
        self._item_added_event = asyncio.Event()
        self._write_pointer = 0
        self._read_pointer = 0
        self.discard_count = 0

    def qsize(self):
        # 計算目前佇列有多少資料
        if self._write_pointer >= self._read_pointer:
            return self._write_pointer - self._read_pointer
        else:
            return self._size - self._read_pointer + self._write_pointer

    def empty(self):
        return self._write_pointer == self._read_pointer

    def _move_write_pointer(self):
        self._write_pointer = (self._write_pointer + 1) % self._size

    def _move_read_pointer(self):
        self._read_pointer = (self._read_pointer + 1) % self._size

    def _is_full(self):
        # "空一格"策略，write pointer 下一位是 read pointer 代表滿
        next_ptr = (self._write_pointer + 1) % self._size
        return next_ptr == self._read_pointer

    def _expand(self):
        # 容量倍增策略，並保持原資料順序
        old_size = self._size
        new_size = old_size * 2
        new_queue = [None] * new_size
        n = self.qsize()
        # 拷貝現有資料到新 queue
        for i in range(n):
            idx = (self._read_pointer + i) % old_size
            new_queue[i] = self._queue[idx]
        self._queue = new_queue
        self._size = new_size
        self._read_pointer = 0
        self._write_pointer = n
        # print(f"AsyncQueue擴充: {old_size} -> {new_size}")

    async def put(self, value):
        if self._is_full():
            self._expand()
        self._queue[self._write_pointer] = value
        self._item_added_event.set()
        self._move_write_pointer()

    async def get(self):
        while self.empty():
            self._item_added_event.clear()
            await self._item_added_event.wait()
        value = self._queue[self._read_pointer]
        self._move_read_pointer()
        return value

    # 支援 async for 迭代消費
    def __aiter__(self):
        return self
    async def __anext__(self):
        return await self.get()

    def discard(self):
        # 直接丟掉最舊一筆（適用需要搶救空間時）
        if not self.empty():
            self._move_read_pointer()
            self.discard_count += 1

    def clear(self):
        # 清空佇列
        self._read_pointer = self._write_pointer = 0
        self.discard_count = 0

    def capacity(self):
        return self._size    