from anime_sama_api.episode import Episode


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
