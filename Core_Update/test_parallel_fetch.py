import asyncio
import unittest

from .parallel_fetch import run_jobs


class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_overlap_bound_and_order(self):
        active = maximum = 0

        def make_job(i):
            async def job():
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                await asyncio.sleep(0.005)
                active -= 1
                return i

            return job

        result = await run_jobs([make_job(i) for i in range(9)], 3)
        self.assertEqual(result, list(range(9)))
        self.assertEqual(maximum, 3)

    async def test_failure_stops_pending_work(self):
        calls = []

        async def fail():
            calls.append("failed")
            raise RuntimeError("429 simulation")

        async def other():
            calls.append("other")
            await asyncio.sleep(1)

        with self.assertRaises(RuntimeError):
            await run_jobs([fail] + [other] * 20, 3)
        self.assertEqual(calls, ["failed"])

    async def test_empty(self):
        self.assertEqual(await run_jobs([]), [])

    async def test_invalid_bound(self):
        with self.assertRaises(ValueError):
            await run_jobs([], 0)


if __name__ == "__main__":
    unittest.main()
