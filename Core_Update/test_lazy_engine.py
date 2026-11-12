import asyncio
import unittest

from .lazy_engine import try_candidates
from .resolver import LinkError, RateLimitedError


class Tests(unittest.IsolatedAsyncioTestCase):
    async def scenario(self, api, downloads, stop=None):
        calls, attempts = [], []

        async def resolve(candidate):
            calls.append(candidate)
            value = api[candidate]
            if isinstance(value, Exception):
                raise value
            return value

        async def download(url, candidate):
            attempts.append((candidate, url))
            return downloads[candidate]

        result = await try_candidates(
            range(len(api)),
            resolve,
            download,
            recoverable=(LinkError,),
            stopped=stop or (lambda: False),
        )
        return result, calls, attempts

    async def test_first_success_one_api(self):
        result, calls, attempts = await self.scenario(
            ["https://a", "https://b"], [True, True]
        )
        self.assertTrue(result)
        self.assertEqual(calls, [0])
        self.assertEqual(len(attempts), 1)

    async def test_api_error_fallback(self):
        result, calls, attempts = await self.scenario(
            [LinkError("absent"), "https://b"], [False, True]
        )
        self.assertTrue(result)
        self.assertEqual(calls, [0, 1])
        self.assertEqual(attempts, [(1, "https://b")])

    async def test_download_error_fallback(self):
        result, calls, attempts = await self.scenario(
            ["https://a", "https://b"], [False, True]
        )
        self.assertTrue(result)
        self.assertEqual(calls, [0, 1])
        self.assertEqual(len(attempts), 2)

    async def test_both_failures_then_success(self):
        result, calls, attempts = await self.scenario(
            [LinkError("bad"), "https://b", "https://c"], [False, False, True]
        )
        self.assertTrue(result)
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(len(attempts), 2)

    async def test_all_fail(self):
        result, _, _ = await self.scenario(["https://a", "https://b"], [False, False])
        self.assertFalse(result)

    async def test_429_never_falls_back(self):
        calls = []

        async def resolve(c):
            calls.append(c)
            raise RateLimitedError("429")

        async def download(*args):
            self.fail("download should not run")

        with self.assertRaises(RateLimitedError):
            await try_candidates(
                [0, 1],
                resolve,
                download,
                recoverable=(LinkError,),
                stopped=lambda: False,
            )
        self.assertEqual(calls, [0])

    async def test_duplicates_not_downloaded_twice(self):
        result, _calls, attempts = await self.scenario(
            ["https://a", "https://a", "https://b"], [False, False, True]
        )
        self.assertTrue(result)
        self.assertEqual(len(attempts), 2)

    async def test_stopped_zero_requests(self):
        result, calls, _ = await self.scenario(["https://a"], [True], stop=lambda: True)
        self.assertFalse(result)
        self.assertEqual(calls, [])

    async def test_no_next_request_while_downloading(self):
        events = []

        async def resolve(c):
            events.append(("api", c))
            return "https://a"

        async def download(url, c):
            events.append(("start", c))
            await asyncio.sleep(0)
            self.assertEqual(events, [("api", 0), ("start", 0)])
            return True

        self.assertTrue(
            await try_candidates(
                [0, 1],
                resolve,
                download,
                recoverable=(LinkError,),
                stopped=lambda: False,
            )
        )

    async def test_unexpected_error_propagates(self):
        async def resolve(c):
            raise TypeError("bug")

        async def download(*args):
            return True

        with self.assertRaises(TypeError):
            await try_candidates(
                [0], resolve, download, recoverable=(LinkError,), stopped=lambda: False
            )


if __name__ == "__main__":
    unittest.main()
