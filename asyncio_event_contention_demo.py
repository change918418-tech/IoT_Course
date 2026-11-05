"""條列模擬多個 producer 共用狀態與 asyncio.Event 的常見問題。"""

import asyncio


def section(number, title):
    print("\n{}. {}".format(number, title))


async def simulate_overwrite_and_coalescing():
    """兩次寫入只留下最後值，兩次 set 仍只是一個已設定旗標。"""
    section(1, "後寫覆蓋與通知合併")
    state = {"writer": None, "value": None}
    event = asyncio.Event()
    first_write_done = asyncio.Event()

    async def producer_a():
        state.update(writer="A", value=100)
        event.set()
        first_write_done.set()
        print("- A 寫入 100，並呼叫 event.set()")

    async def producer_b():
        await first_write_done.wait()
        state.update(writer="B", value=200)
        event.set()
        print("- B 接著寫入 200，也呼叫 event.set()")

    await asyncio.gather(producer_a(), producer_b())
    await event.wait()
    print("- consumer 只讀到最後值：{} 的 {}".format(
        state["writer"], state["value"]))
    print("- event 只表示 True，不會記錄 set() 被呼叫兩次")


async def simulate_lost_update():
    """兩個 producer 都讀到舊值，再各自寫回，造成一次增量消失。"""
    section(2, "讀取－修改－寫回的爭搶")
    state = {"count": 0}
    both_read = asyncio.Event()
    ready_count = 0

    async def increment(name):
        nonlocal ready_count
        old_value = state["count"]
        print("- {} 讀到 count={}".format(name, old_value))
        ready_count += 1
        if ready_count == 2:
            both_read.set()
        await both_read.wait()
        state["count"] = old_value + 1
        print("- {} 寫回 count={}".format(name, old_value + 1))

    await asyncio.gather(increment("A"), increment("B"))
    print("- 預期結果是 2，實際結果是 {}：遺失一次更新".format(
        state["count"]))


async def simulate_mixed_snapshot():
    """多欄位更新中途 await，使最後狀態混合兩個 producer 的資料。"""
    section(3, "多欄位狀態不一致")
    state = {"writer": None, "value": None}
    a_wrote_name = asyncio.Event()
    b_finished = asyncio.Event()

    async def producer_a():
        state["writer"] = "A"
        print("- A 先寫入 writer=A，接著暫停")
        a_wrote_name.set()
        await b_finished.wait()
        state["value"] = 100
        print("- A 恢復後寫入 value=100")

    async def producer_b():
        await a_wrote_name.wait()
        state.update(writer="B", value=200)
        print("- B 在 A 暫停期間完整寫入 writer=B、value=200")
        b_finished.set()

    await asyncio.gather(producer_a(), producer_b())
    print("- 最後得到混合狀態：writer={}、value={}".format(
        state["writer"], state["value"]))


async def simulate_missing_signal():
    """producer 在 set 前失敗，consumer 若沒有逾時會一直等待。"""
    section(4, "producer 失敗而沒有通知")
    event = asyncio.Event()

    async def producer():
        print("- producer 在 event.set() 前發生錯誤")
        raise RuntimeError("模擬感測器讀取失敗")

    async def consumer():
        try:
            await asyncio.wait_for(event.wait(), timeout=0.1)
        except asyncio.TimeoutError:
            print("- consumer 等待逾時；若沒有 timeout，將持續等待")

    results = await asyncio.gather(producer(), consumer(), return_exceptions=True)
    print("- producer 結果：{}".format(results[0]))


async def main():
    print("多 producer 共用 state 與 Event：條列模擬")
    await simulate_overwrite_and_coalescing()
    await simulate_lost_update()
    await simulate_mixed_snapshot()
    await simulate_missing_signal()
    print("\n建議：")
    print("- 只需要最新狀態：單一 owner 寫入完整 snapshot，再用 Event 通知")
    print("- 每筆資料都要處理：使用 asyncio.Queue")
    print("- 必須共同修改狀態：使用 asyncio.Lock 保護完整操作")
    print("- 外部讀取可能失敗：設定 timeout 與明確錯誤狀態")


if __name__ == "__main__":
    asyncio.run(main())
