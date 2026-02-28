import os

# Apple Music API credentials
APPLE_MUSIC_TEAM_ID = os.environ.get("APPLE_MUSIC_TEAM_ID", "")
APPLE_MUSIC_KEY_ID = os.environ.get("APPLE_MUSIC_KEY_ID", "")
APPLE_MUSIC_PRIVATE_KEY = os.environ.get("APPLE_MUSIC_PRIVATE_KEY", "")
APPLE_MUSIC_USER_TOKEN = os.environ.get("APPLE_MUSIC_USER_TOKEN", "")

# J-Wave URLs
JWAVE_CHART_URL = "https://www.j-wave.co.jp/original/tokiohot100/chart/main.htm"
JWAVE_CGI_URL = "https://www.j-wave.co.jp/original/tokiohot100/cgi-bin/top100.cgi"

# Apple Music API
APPLE_MUSIC_API_BASE = "https://api.music.apple.com/v1"
STOREFRONT = "jp"

# Playlist
PLAYLIST_NAME_PREFIX = "J-Wave TOKIO HOT 100"

# Paths
SONG_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "song_cache.json",
)

# HTTP
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
