"""Apple Music API client for search and playlist management."""

from __future__ import annotations

import logging
import time

import jwt  # PyJWT
import requests

from config import (
    APPLE_MUSIC_API_BASE,
    APPLE_MUSIC_KEY_ID,
    APPLE_MUSIC_PRIVATE_KEY,
    APPLE_MUSIC_TEAM_ID,
    APPLE_MUSIC_USER_TOKEN,
    STOREFRONT,
)

logger = logging.getLogger(__name__)


class AppleMusicClient:
    """Client for Apple Music API operations."""

    def __init__(self):
        self.developer_token = self._generate_developer_token()
        self.user_token = APPLE_MUSIC_USER_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.developer_token}",
            "Content-Type": "application/json",
        })

    def _generate_developer_token(self) -> str:
        """Generate an ES256 JWT developer token from the .p8 private key."""
        if not APPLE_MUSIC_PRIVATE_KEY:
            raise RuntimeError(
                "APPLE_MUSIC_PRIVATE_KEY is not set. "
                "Set it to the contents of your .p8 key file."
            )

        now = int(time.time())
        payload = {
            "iss": APPLE_MUSIC_TEAM_ID,
            "iat": now,
            "exp": now + 3600,  # 1 hour validity
        }
        headers = {
            "alg": "ES256",
            "kid": APPLE_MUSIC_KEY_ID,
        }
        token = jwt.encode(
            payload,
            APPLE_MUSIC_PRIVATE_KEY,
            algorithm="ES256",
            headers=headers,
        )
        logger.info("Generated Apple Music developer token")
        return token

    def search_song(self, title: str, artist: str) -> str | None:
        """
        Search Apple Music catalog for a song by title and artist.

        Returns the catalog ID (e.g., "1234567890") or None if not found.
        Tries artist+title first, then title-only as fallback.
        """
        # First attempt: artist + title
        catalog_id = self._search_catalog(f"{artist} {title}")
        if catalog_id:
            return catalog_id

        # Second attempt: title only (handles artist name differences)
        catalog_id = self._search_catalog(title)
        return catalog_id

    def _search_catalog(self, query: str) -> str | None:
        """Search the Apple Music catalog and return the first match's ID."""
        url = f"{APPLE_MUSIC_API_BASE}/catalog/{STOREFRONT}/search"
        params = {"term": query, "types": "songs", "limit": 5}

        response = self._request_with_retry("GET", url, params=params)
        if response is None:
            return None

        data = response.json()
        songs = data.get("results", {}).get("songs", {}).get("data", [])

        if not songs:
            return None

        return songs[0]["id"]

    def create_playlist(self, name: str, description: str = "") -> str:
        """
        Create a new playlist in the user's Apple Music library.

        Returns the library playlist ID.
        """
        url = f"{APPLE_MUSIC_API_BASE}/me/library/playlists"
        body = {
            "attributes": {
                "name": name,
                "description": description,
            },
        }

        response = self._request_with_retry(
            "POST", url, json=body, use_user_token=True
        )
        if response is None:
            raise RuntimeError("Failed to create playlist")

        data = response.json()
        playlist_id = data["data"][0]["id"]
        logger.info(f"Created playlist: {name} (ID: {playlist_id})")
        return playlist_id

    def add_tracks_to_playlist(
        self, playlist_id: str, catalog_ids: list[str]
    ) -> None:
        """
        Add songs to a playlist by their catalog IDs.

        Sends in batches of 25 to avoid API payload limits.
        """
        url = f"{APPLE_MUSIC_API_BASE}/me/library/playlists/{playlist_id}/tracks"

        batch_size = 25
        for i in range(0, len(catalog_ids), batch_size):
            batch = catalog_ids[i : i + batch_size]
            body = {
                "data": [{"id": cid, "type": "songs"} for cid in batch]
            }

            batch_num = i // batch_size + 1
            response = self._request_with_retry(
                "POST", url, json=body, use_user_token=True
            )
            if response is None:
                logger.error(f"Failed to add tracks (batch {batch_num})")
            else:
                logger.info(f"Added {len(batch)} tracks (batch {batch_num})")

            time.sleep(0.5)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        use_user_token: bool = False,
        **kwargs,
    ) -> requests.Response | None:
        """
        Make an HTTP request with exponential backoff retry.

        Args:
            use_user_token: If True, include Music-User-Token header.
        """
        headers = kwargs.pop("headers", {})
        if use_user_token:
            if not self.user_token:
                raise RuntimeError(
                    "APPLE_MUSIC_USER_TOKEN is not set. "
                    "Run tools/get_music_user_token.html to obtain it."
                )
            headers["Music-User-Token"] = self.user_token

        for attempt in range(max_retries):
            try:
                resp = self.session.request(
                    method, url, headers=headers, timeout=30, **kwargs
                )

                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited (429). Waiting {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code in (401, 403):
                    logger.error(
                        f"Authentication error ({resp.status_code}). "
                        "Music User Token may have expired. "
                        "Re-run tools/get_music_user_token.html to get a new token "
                        "and update the APPLE_MUSIC_USER_TOKEN secret."
                    )
                    raise SystemExit(1)

                resp.raise_for_status()
                return resp

            except SystemExit:
                raise
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Request failed after {max_retries} attempts: {e}"
                    )
                    return None
                wait = 2 ** attempt
                logger.warning(f"Request error, retrying in {wait}s: {e}")
                time.sleep(wait)

        return None
