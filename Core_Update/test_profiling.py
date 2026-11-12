import asyncio
import types
import unittest
from unittest.mock import patch

from . import profiling as p


class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        p._records.clear()

    def test_sync(self):
        obj = types.SimpleNamespace(f=lambda: 42)
        with patch.object(p, "perf_counter", side_effect=[1, 1.25]):
            p.wrap(obj, "f", "sync")
            self.assertEqual(obj.f(), 42)
        self.assertEqual(p._records, [("sync", 0.25, True)])

    async def test_async(self):
        async def f():
            return 12

        obj = types.SimpleNamespace(f=f)
        p.wrap(obj, "f", "async")
        self.assertEqual(await obj.f(), 12)
        self.assertEqual(p._records[0][0], "async")
        self.assertTrue(p._records[0][2])

    def test_failure_propagates(self):
        def fail():
            raise ValueError("secret")

        obj = types.SimpleNamespace(f=fail)
        p.wrap(obj, "f", "failure")
        with self.assertRaises(ValueError):
            obj.f()
        self.assertFalse(p._records[0][2])

    def test_no_double_wrapping(self):
        obj = types.SimpleNamespace(f=lambda: None)
        p.wrap(obj, "f", "test")
        p.wrap(obj, "f", "test")
        obj.f()
        self.assertEqual(len(p._records), 1)

    def test_http_label_has_no_token(self):
        request = types.SimpleNamespace(
            url="https://example.test/api/lien.php?j=SECRET&l=42", method="GET"
        )
        self.assertEqual(p.http_label(None, request), "HTTP GET /api/lien.php")

    async def test_cancellation_recorded(self):
        async def cancelled():
            raise asyncio.CancelledError()

        obj = types.SimpleNamespace(f=cancelled)
        p.wrap(obj, "f", "cancel")
        with self.assertRaises(asyncio.CancelledError):
            await obj.f()
        self.assertFalse(p._records[0][2])


if __name__ == "__main__":
    unittest.main()
