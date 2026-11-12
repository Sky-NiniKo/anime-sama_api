"""Bounded workers: no unbounded gather and no artificial per-call delay."""

import asyncio


async def run_jobs(jobs, concurrency=3):
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    results = [None] * len(jobs)
    next_index = 0
    failed = False

    async def worker():
        nonlocal next_index, failed
        while not failed and next_index < len(jobs):
            index = next_index
            next_index += 1
            try:
                results[index] = await jobs[index]()
            except BaseException:
                failed = True
                raise

    workers = [
        asyncio.create_task(worker()) for _ in range(min(concurrency, len(jobs)))
    ]
    try:
        await asyncio.gather(*workers)
    except BaseException:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        raise
    return results
