#!/usr/bin/env python3
# very basic YTMDesktop Companion Server API client
import requests
import json
from datetime import datetime
from pathlib import Path
from config import config  # type: ignore

baseUrl = config.get(  # type: ignore
    "baseUrl",
    "http://localhost:9863/api/v1/",  # standard URL for YTMD API
)
token = config["token"]  # type: ignore

script_dir = Path(__file__).parent

_last_errors: dict[str, str | None] = {}


def _log_error(action: str, error: str | None) -> None:
    # n'affiche une erreur (ou le retour à la normale) que lorsqu'elle change, pour ne pas inonder le log
    if _last_errors.get(action) != error:
        print(f"{datetime.now()} YTMD {action}: {error or 'OK'}")
        _last_errors[action] = error


def ytmdesktop_api_call(  # type: ignore
    mode: str,
    action: str,
    playlistId: str | None = None,  # for changeVideo
    videoId: str | None = None,  # for changeVideo
    data: str | int | dict | None = None,  # repeatMode (int !), queueAdd (dict)...
) -> tuple[bool, dict | None]:  # type: ignore
    # if (mode, action) != ("info", "state"):
    #     print(
    #         f"{datetime.now()} YTMD API call: mode={mode}, action={action}, playlistId={playlistId}, videoId={videoId} data={data}"
    #     )
    global script_dir
    if mode == "info":
        url = f"{baseUrl}{action}"
        try:
            status = requests.get(url, headers={"Authorization": token}, timeout=5)
            state = status.json()
        except Exception as e:
            _log_error(action, f"{type(e).__name__}: {e}")
            return False, None
        if status.status_code == 200:
            _log_error(action, None)
        else:
            # 401 : token invalide (refaire ./ytmd_auth.py) ; 429 : rate limit
            _log_error(action, f"HTTP {status.status_code} {state}")
        # x-rate limit : we may handle that better ;-)
        # I just have a YTMD_CACHE_DELAY consistent with the rate for state (5 sec), and for list of playlists, 5 minutes is way more than their 30 secondes rate
        # for header, value in status.headers.items():
        #    if header.lower().startswith("x-ratelimit-"):
        #        print(f"{action} {header}: {value}")
        # run/<action>.json : dernière réponse en erreur, pour le diagnostic (supprimé quand ça remarche)
        debug_file = script_dir / "run" / f"{action}.json"
        if status.status_code == 200:
            debug_file.unlink(missing_ok=True)
        else:
            with open(debug_file, "w") as f:
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
        try:
            status = requests.post(
                url,
                headers={"Authorization": token},
                json=json_data,
                timeout=5,
            )
        except Exception as e:
            print(f"{datetime.now()} YTMD command {action}: {type(e).__name__}: {e}")
            return False, None
        if status.status_code != 204:
            print(f"{datetime.now()} YTMD command {action}: HTTP {status.status_code} {status.text}")
        return status.status_code == 204, None
    else:
        raise ValueError("Invalid mode")
    return False, None
