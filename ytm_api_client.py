#!/usr/bin/env python3
# very basic YTMDesktop Companion Server API client
from datetime import datetime
import requests
import json
import os
from pathlib import Path

BASE_URL = "http://localhost:9863/api/v1/"  # standard URL for YTMD API

script_dir = Path(__file__).parent
config_path = script_dir / "run" / "config.json"

with open(config_path, "r") as f:
    config = json.load(f)
    token = config["token"]
    # see https://ytmdesktop.github.io/developer/companion-server/reference/v1/auth-requestcode.html
    # to get the token
    baseUrl = config.get("baseUrl", BASE_URL)


def ytmdesktop_api_call(  # type: ignore
    mode: str,
    action: str,
    playlistId: str | None = None,  # for changeVideo
    videoId: str | None = None,  # for changeVideo
    data: str | None = None,  # for repeat, or some other commands
) -> tuple[bool, dict | None]:  # type: ignore
    # if (mode, action) != ("info", "state"):
    #     print(
    #         f"{datetime.now()} YTMD API call: mode={mode}, action={action}, playlistId={playlistId}, videoId={videoId} data={data}"
    #     )
    if mode == "info":
        url = f"{baseUrl}{action}"
        status = requests.get(url, headers={"Authorization": token})
        state = json.loads(status.content)
        # x-rate limit : we may handle that better ;-) 
        # I just have a YTMD_CACHE_DELAY consistent with the rate for state (5 sec), and for list of playlists, 5 minutes is way more than their 30 secondes rate
        #for header, value in status.headers.items():
        #    if header.lower().startswith("x-ratelimit-"):
        #        print(f"{action} {header}: {value}")
        with open(script_dir / "run" / f"{action}.json", "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        return status.status_code == 200, state
    elif mode == "command":
        url = f"{baseUrl}command"
        json_data = {
            "command": action,
        }
        if action == "changeVideo":
            # for changeVideo,  data is a dict with playlistId and videoId (those present)
            json_data["data"] = {}
            if playlistId is not None and playlistId != "None":
                json_data["data"]["playlistId"] = playlistId
            if videoId is not None and videoId != "None":
                json_data["data"]["videoId"] = videoId
        elif data is not None and data != "None":
            json_data["data"] = data
        status = requests.post(
            url,
            headers={"Authorization": token},
            json=json_data,
        )
        return status.status_code == 204, None
    else:
        raise ValueError("Invalid mode")
    return False, None
