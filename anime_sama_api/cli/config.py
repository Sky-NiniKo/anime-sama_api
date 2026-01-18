# TODO: Allway hard to read but I can't find a better way to do it
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

# import platformdirs for config_dir and download_dir
from platformdirs import user_config_dir, user_downloads_dir

from anime_sama_api.langs import Lang, lang2ids

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayersConfig:
    prefers: list[str] = field(default_factory=list)
    bans: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    prefer_languages: list[Lang]
    download_path: Path
    episode_path: str
    download: bool
    show_players: bool
    max_retry_time: int
    format: str
    format_sort: str
    internal_player_command: list[str]
    url: str
    provider_url: str
    players_config: PlayersConfig
    concurrent_downloads: dict[str, int]


def load_config() -> Config:
    # 1. Load default config from the package
    default_config_file = Path(__file__).parent / "config.toml"
    if not default_config_file.exists():
        raise FileNotFoundError(
            f"The default config.toml could not be found at {default_config_file}"
        )

    with open(default_config_file, "rb") as f:
        config_dict = tomllib.load(f)

    # 2. Determine user config path
    # Order of priority:
    # - current directory (./config.toml)
    # - system config directory (e.g. ~/AppData/Local/anime-sama_api/config.toml)
    local_config = Path("config.toml")
    system_config_dir = Path(user_config_dir("anime-sama_api", appauthor=False))
    system_config_file = system_config_dir / "config.toml"

    user_config_data = {}
    if local_config.exists():
        with open(local_config, "rb") as f:
            user_config_data = tomllib.load(f)
    elif system_config_file.exists():
        with open(system_config_file, "rb") as f:
            user_config_data = tomllib.load(f)
    else:
        # Recreate default config if not found anywhere
        from shutil import copy

        system_config_dir.mkdir(parents=True, exist_ok=True)
        copy(default_config_file, system_config_file)
        logger.info("Default config created at %s", system_config_file)

    # 3. Merge configs (user values override defaults)
    config_dict.update(user_config_data)

    # 4. Backward compatibility and data cleaning
    # Languages conversion
    new_langs: list[Lang] = []
    for lang in config_dict.get("prefer_languages", []):
        if lang == "VO":
            lang = "VOSTFR"
        if lang in lang2ids:
            new_langs.append(lang)
        else:
            logger.warning("'%s' is not a valid language, ignoring it.", lang)
    config_dict["prefer_languages"] = new_langs

    # Path detection and expansion
    raw_path = config_dict.get("download_path")
    if not raw_path:
        # Default to system Downloads / Anime-Sama if not specified
        config_dict["download_path"] = Path(user_downloads_dir()) / "Anime-Sama"
    else:
        config_dict["download_path"] = Path(raw_path).expanduser()

    # Internal player command string to list
    player_cmd = config_dict.get("internal_player_command")
    if isinstance(player_cmd, str):
        config_dict["internal_player_command"] = player_cmd.split()
    elif player_cmd is None:
        config_dict["internal_player_command"] = []

    # Players config mapping
    players_data = config_dict.pop("players_hostname", {})
    if "players" in config_dict:  # Old key removal
        del config_dict["players"]
    config_dict["players_config"] = PlayersConfig(**players_data)

    # Ensure all required keys are present for Config dataclass
    # (Checking against keys in Config.__annotations__ if necessary)
    return Config(**config_dict)


# Exported config instance
config = load_config()
