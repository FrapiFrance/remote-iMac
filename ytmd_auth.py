#!/usr/bin/env python3
# Obtenir un (nouveau) token pour l'API Companion Server de YTMDesktop
# et l'écrire dans run/config.json.
#
# Avant de lancer :
#   YTMDesktop > Paramètres > Intégrations :
#     - "Companion server" activé
#     - "Enable companion authorization" activé (se désactive tout seul après quelques minutes)
#
# Usage : ./ytmd_auth.py [base_url]     (défaut : baseUrl de run/config.json)
# Une fenêtre s'ouvre sur l'écran de l'iMac avec le code : vérifier qu'il correspond, cliquer "Allow".
import json
import sys
from pathlib import Path

import requests

APP_ID = "remoteimac"
APP_NAME = "remote iMac"
APP_VERSION = "1.0.0"

config_path = Path(__file__).parent / "run" / "config.json"
config = json.loads(config_path.read_text()) if config_path.exists() else {}
base_url = sys.argv[1] if len(sys.argv) > 1 else config.get("baseUrl", "http://localhost:9863/api/v1/")
if not base_url.endswith("/"):
    base_url += "/"

r = requests.post(
    f"{base_url}auth/requestcode",
    json={"appId": APP_ID, "appName": APP_NAME, "appVersion": APP_VERSION},
    timeout=10,
)
if r.status_code != 200:
    sys.exit(f"requestcode: HTTP {r.status_code} {r.text}\n"
             "-> 'Enable companion authorization' est-il activé dans YTMDesktop ?")
code = r.json()["code"]
print(f"Code : {code}  -> validez-le sur l'écran de l'iMac (bouton Allow)…")

# bloque jusqu'à ce que l'utilisateur valide (ou refuse) dans YTMDesktop
r = requests.post(f"{base_url}auth/request", json={"appId": APP_ID, "code": code}, timeout=180)
if r.status_code != 200:
    sys.exit(f"request: HTTP {r.status_code} {r.text}")
token = r.json()["token"]

config["token"] = token
config_path.write_text(json.dumps(config, indent=4) + "\n")
print(f"Token enregistré dans {config_path}")
