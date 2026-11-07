import asyncio

from app.core.translation.queue import TranslationQueue


async def test_runs_by_priority_then_fifo() -> None:
    order: list[str] = []

    async def handler(job_id: str, payload: str) -> None:
        order.append(job_id)

    q: TranslationQueue[str] = TranslationQueue(handler, concurrency=1)
    q.pause(True)
    q.start()
    q.submit("bulk", 4, "x")
    q.submit("visible", 2, "x")
    q.submit("edit", 1, "x")
    q.submit("visible2", 2, "x")
    q.pause(False)
    await asyncio.wait_for(q.join(), 2)
    assert order == ["edit", "visible", "visible2", "bulk"]
    await q.stop()


async def test_resubmitting_a_queued_job_replaces_it() -> None:
    seen: list[str] = []

    async def handler(job_id: str, payload: str) -> None:
        seen.append(payload)

    q: TranslationQueue[str] = TranslationQueue(handler, concurrency=1)
    q.pause(True)
    q.start()
    q.submit("a", 3, "old")
    q.submit("a", 3, "new")
    q.pause(False)
    await asyncio.wait_for(q.join(), 2)
    assert seen == ["new"]
    await q.stop()


async def test_superseded_running_job_is_cancelled() -> None:
    started: list[str] = []
    finished: list[str] = []

    async def handler(job_id: str, payload: str) -> None:
        started.append(payload)
        await asyncio.sleep(0.3 if payload == "old" else 0)
        finished.append(payload)

    q: TranslationQueue[str] = TranslationQueue(handler, concurrency=2)
    q.start()
    q.submit("a", 1, "old")
    await asyncio.sleep(0.05)
    q.submit("a", 1, "new")
    await asyncio.wait_for(q.join(), 2)
    assert started == ["old", "new"]
    assert finished == ["new"]
    await q.stop()


async def test_failing_job_does_not_stop_the_worker() -> None:
    done: list[str] = []

    async def handler(job_id: str, payload: str) -> None:
        if job_id == "bad":
            raise RuntimeError("boom")
        done.append(job_id)

    q: TranslationQueue[str] = TranslationQueue(handler, concurrency=1)
    q.start()
    q.submit("bad", 1, "")
    q.submit("good", 1, "")
    await asyncio.wait_for(q.join(), 2)
    assert done == ["good"]
    await q.stop()


async def test_cancel_prefix_drops_queued_jobs() -> None:
    done: list[str] = []

    async def handler(job_id: str, payload: str) -> None:
        done.append(job_id)

    q: TranslationQueue[str] = TranslationQueue(handler, concurrency=1)
    q.pause(True)
    q.start()
    q.submit("p1:a", 1, "")
    q.submit("p2:a", 1, "")
    q.cancel_prefix("p1:")
    q.pause(False)
    await asyncio.wait_for(q.join(), 2)
    assert done == ["p2:a"]
    await q.stop()


async def test_endpoints_run_in_threads_so_the_queue_must_accept_calls_from_one() -> None:
    import threading

    done: list[str] = []

    async def handler(job_id: str, payload: str) -> None:
        done.append(job_id)

    q: TranslationQueue[str] = TranslationQueue(handler, concurrency=1)
    q.start()
    await asyncio.sleep(0.05)  # the worker is idle, waiting to be woken
    thread = threading.Thread(target=q.submit, args=("from-thread", 1, ""))
    thread.start()
    thread.join()
    await asyncio.sleep(0.05)  # the call is handed to the loop, not run in the thread
    await asyncio.wait_for(q.join(), 2)
    assert done == ["from-thread"]
    await q.stop()
