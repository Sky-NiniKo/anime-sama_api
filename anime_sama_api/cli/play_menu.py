import asyncio

from anime_sama_api.episode import Episode, iter_resolved_players

from .config import config


class EpisodesManager:
    def __init__(self, episodes: list[Episode], current_index: int = 0) -> None:
        self.episodes = episodes
        self.current_index = current_index

    def __next__(self) -> Episode:
        if self.current_index < len(self.episodes) - 1:
            self.current_index += 1
            return self.episodes[self.current_index]

        raise StopIteration

    def previous(self) -> Episode:
        if self.current_index > 0:
            self.current_index -= 1
            return self.episodes[self.current_index]

        raise StopIteration

    @property
    def current(self) -> Episode:
        return self.episodes[self.current_index]


class PlayMenu:
    def print_menu(self) -> None:
        pass


async def play_episode(episode):
    from . import internal_player

    async for url in iter_resolved_players(
        episode, config.prefer_languages, config.players_config.bans
    ):

        class PlayerEpisode:
            def __getattr__(self, name):
                return getattr(episode, name)

            def best(self, prefer_languages, url=url):
                return url

            def consume_player(self, *args, url=url, **kwargs):
                yield url

        command = internal_player.play_episode(PlayerEpisode(), config.prefer_languages)
        if command is not None and await asyncio.to_thread(command.wait) == 0:
            return True
    return False


async def async_main(episodes: list[Episode]):
    return await play_episode(episodes[0])
