# run directory

To add a config.json file with YTMdesktop token

Here are the default values :

```json
{
    "token": "see https://ytmdesktop.github.io/developer/companion-server/reference/v1/auth-requestcode.html",
    "baseUrl": "http://localhost:9863/api/v1/",
    "hidePhotos": false,   // if you don't use the "photos" part
    "playerctl_player" : null, // could be "youtube-music-desktop-app" or "chromium.instance4242" if you want to target a specific player
    "host" "0.0.0.0",  // on which IP the server runs
    "port" : 8000,  // and port
    "youtubemusicdesktop_state_cache_delay": 5, // 5 secondes
    "youtubemusicdesktop_playlists_cache_delay": 3600, // 1h
}
```
