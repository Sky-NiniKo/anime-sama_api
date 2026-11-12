import unittest
from urllib.parse import urlsplit

from .lang_fix import iter_unique_candidates


class FakePlayers(list):
    def sort_and_filter(self, prefers, bans):
        urls = [u for u in self if urlsplit(u).hostname not in bans]

        def rank(u):
            host = urlsplit(u).hostname
            return prefers.index(host) if host in prefers else len(prefers)

        return sorted(urls, key=rank)


class Tests(unittest.TestCase):
    def result(self, available, langs=("VOSTFR",), prefers=(), bans=()):
        return list(iter_unique_candidates(available, langs, list(prefers), list(bans)))

    def test_preferred_language_first(self):
        data = {
            "VF": [FakePlayers(["https://vf.test/a"])],
            "VOSTFR": [FakePlayers(["https://vo.test/a"])],
        }
        self.assertEqual(self.result(data), ["https://vo.test/a", "https://vf.test/a"])

    def test_duplicate_urls_across_aliases(self):
        data = {
            "VOSTFR": [FakePlayers(["https://vo.test/a"])],
            "VJSTFR": [FakePlayers(["https://vo.test/a"])],
        }
        self.assertEqual(self.result(data), ["https://vo.test/a"])

    def test_repeated_preferences(self):
        data = {"VOSTFR": [FakePlayers(["https://vo.test/a", "https://vo.test/a"])]}
        self.assertEqual(self.result(data, ("VOSTFR", "VOSTFR")), ["https://vo.test/a"])

    def test_banned_host(self):
        data = {"VOSTFR": [FakePlayers(["https://bad.test/a", "https://ok.test/a"])]}
        self.assertEqual(self.result(data, bans=("bad.test",)), ["https://ok.test/a"])

    def test_host_preference(self):
        data = {"VOSTFR": [FakePlayers(["https://a.test/x", "https://b.test/x"])]}
        self.assertEqual(
            self.result(data, prefers=("b.test",)),
            ["https://b.test/x", "https://a.test/x"],
        )

    def test_fallback_if_preferred_banned(self):
        data = {
            "VOSTFR": [FakePlayers(["https://bad.test/a"])],
            "VF": [FakePlayers(["https://vf.test/a"])],
        }
        self.assertEqual(self.result(data, bans=("bad.test",)), ["https://vf.test/a"])

    def test_no_false_warning_during_enumeration(self):
        import logging

        records = []

        class Recorder(logging.Handler):
            def emit(self, record):
                records.append(record)

        root = logging.getLogger()
        handler = Recorder()
        root.addHandler(handler)
        try:
            self.result({"VF": [FakePlayers(["https://vf.test/a"])]})
        finally:
            root.removeHandler(handler)
        self.assertEqual(records, [])

    def test_metadata_unchanged(self):
        data = {
            "VOSTFR": [FakePlayers(["https://vo.test/a"])],
            "VJSTFR": [FakePlayers(["https://vo.test/a"])],
        }
        self.result(data)
        self.assertEqual(list(data), ["VOSTFR", "VJSTFR"])


if __name__ == "__main__":
    unittest.main()
