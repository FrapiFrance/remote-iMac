#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:9863/api/v1/"

with open("./run/config.json", "r") as f:
    config = json.load(f)
    token = config["token"]
    # see https://ytmdesktop.github.io/developer/companion-server/reference/v1/auth-requestcode.html
    # to get the token

mode = "info"
info = "playlists"
info = "state"

mode = "command"
command = "playPause"
command = "next"


if mode == "info":
    url = f"{BASE_URL}{info}"
    status = requests.get(url, headers={"Authorization": token})
    state = json.loads(status.content)
    if info == "state":
        # to reduce output size
        state["player"]["queue"] = None
        state["video"]["thumbnails"] = None
    print(json.dumps(state, indent=2, ensure_ascii=False))
else:
    url = f"{BASE_URL}command"
    status = requests.post(
        url,
        headers={"Authorization": token},
        json={
            "command": command,
        },
    )
    if status.status_code == 204:
        print("Command executed successfully.")
    else:
        state = json.loads(status.content)
        print(json.dumps(state, indent=2, ensure_ascii=False))
