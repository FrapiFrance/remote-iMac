#!/usr/bin/env python3
import json
from pathlib import Path


def load_config() -> (
    dict
):  # TODO : should not be insid this API, but globally loaded by main, and used here and in ytremote
    script_dir = Path(__file__).parent
    config_path = script_dir / "run" / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    return config


config = load_config()
