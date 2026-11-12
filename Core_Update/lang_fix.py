"""Language candidate ordering without misleading warnings or duplicate URLs."""


def iter_unique_candidates(available, prefer_languages, prefer_players, ban_players):
    # Retain preference order, then the original fallback order.
    from_order = ("VOSTFR", "VASTFR", "VCN", "VF", "VJSTFR", "VKR", "VQC")
    ordered = list(dict.fromkeys([*prefer_languages, *from_order, *available]))
    seen = set()
    for language in ordered:
        for players in available.get(language, []):
            for url in players.sort_and_filter(prefer_players, ban_players):
                if url and url not in seen:
                    seen.add(url)
                    yield url


def make_resolved_languages(mapping):
    """Return a Languages-compatible object, preserving language metadata.

    Candidate enumeration cannot prove a download fallback occurred, so it must
    not emit a warning merely because a fallback URL is enumerated.
    """
    from anime_sama_api.episode import Languages

    class ResolvedLanguages(Languages):
        def consume_player(self, prefer_languages, prefer_players, ban_players):
            yield from iter_unique_candidates(
                self.availables, prefer_languages, prefer_players, ban_players
            )

    if not mapping:
        raise ValueError("Cannot build resolved languages without URLs")
    return ResolvedLanguages(mapping)
