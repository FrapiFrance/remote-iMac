#!/usr/bin/env python3
import json
from pathlib import Path


def load_config() -> dict:  # type: ignore
    script_dir = Path(__file__).parent
    config_path = script_dir / "run" / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["host"] = config.get("host", "0.0.0.0")
    config["port"] = config.get("port", 8000)
    config["token"] = config.get("token", "")
    config["baseUrl"] = config.get("baseUrl", "http://localhost:9863/api/v1/")
    config["hidePhotos"] = config.get("hidePhotos", False)
    config["playerctl_player"] = config.get("playerctl_player", None)
    config["youtubemusicdesktop_state_cache_delay"] = config.get(
        "youtubemusicdesktop_state_cache_delay", 5
    )
    config["youtubemusicdesktop_playlists_cache_delay"] = config.get(
        "youtubemusicdesktop_playlists_cache_delay", 3600
    )
    config["photoFile"] = config.get(
        "photoFile", "~/magicmirror/mounts/config/imagePath.txt"
    )
    config["photoMagicMirrorRoot"] = config.get(
        "photoMagicMirrorRoot", "modules/MMM-BackgroundSlideshow/google_photos/"
    )
    config["photoRoot"] = config.get("photoRoot", "~/GooglePhotos/")
    return config


config = load_config()
