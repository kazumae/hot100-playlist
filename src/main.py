#!/usr/bin/env python3
"""
J-Wave TOKIO HOT 100 -> Apple Music Playlist Automation

Scrapes the weekly J-Wave chart and adds new songs to an annual
Apple Music playlist (e.g., "J-Wave TOKIO HOT 100 2026").
Songs already in this year's playlist are skipped.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

# Ensure src/ is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apple_music import AppleMusicClient
from config import PLAYLIST_NAME_PREFIX, SONG_CACHE_PATH
from jwave_scraper import scrape_chart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def load_cache() -> dict:
    """Load song_cache.json."""
    if os.path.exists(SONG_CACHE_PATH):
        with open(SONG_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"songs": {}, "playlists": {}}


def save_cache(cache: dict) -> None:
    """Save song_cache.json with pretty formatting."""
    os.makedirs(os.path.dirname(SONG_CACHE_PATH), exist_ok=True)
    with open(SONG_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def make_cache_key(artist: str, title: str) -> str:
    """Create a normalized cache key from artist and title."""
    return f"{artist.strip().lower()}|{title.strip().lower()}"


def main():
    now = datetime.now(JST)
    year_str = str(now.year)
    date_str = now.strftime("%Y/%m/%d")

    logger.info(f"=== J-Wave TOKIO HOT 100 Playlist Update ({date_str}) ===")

    # --- Step 1: Scrape the chart ---
    logger.info("Step 1: Scraping J-Wave TOKIO HOT 100...")
    try:
        songs = scrape_chart()
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)

    logger.info(f"Found {len(songs)} songs in the chart")

    # --- Step 2: Match songs to Apple Music catalog ---
    logger.info("Step 2: Searching Apple Music catalog...")
    cache = load_cache()
    if "songs" not in cache:
        cache["songs"] = {}
    if "playlists" not in cache:
        cache["playlists"] = {}

    client = AppleMusicClient()

    matched = []  # list of (rank, catalog_id)
    not_found = []
    cache_hits = 0
    api_searches = 0

    for song in songs:
        key = make_cache_key(song["artist"], song["title"])

        # Check cache
        if key in cache["songs"]:
            catalog_id = cache["songs"][key]
            if catalog_id:
                matched.append((song["rank"], catalog_id))
                cache_hits += 1
            else:
                not_found.append(song)
                cache_hits += 1
            continue

        # Not in cache - search Apple Music
        api_searches += 1
        catalog_id = client.search_song(song["title"], song["artist"])

        if catalog_id:
            cache["songs"][key] = catalog_id
            matched.append((song["rank"], catalog_id))
            logger.info(
                f"  [{song['rank']:>3}] Found: {song['artist']} - {song['title']}"
            )
        else:
            cache["songs"][key] = None  # Cache the miss
            not_found.append(song)
            logger.warning(
                f"  [{song['rank']:>3}] NOT FOUND: {song['artist']} - {song['title']}"
            )

        # Rate limiting
        if api_searches % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.3)

    logger.info(
        f"Search complete: {cache_hits} cache hits, "
        f"{api_searches} API searches, {len(not_found)} not found"
    )

    # --- Step 3: Ensure this year's playlist exists ---
    logger.info(f"Step 3: Checking playlist for {year_str}...")

    playlist_info = cache["playlists"].get(year_str, {})
    playlist_id = playlist_info.get("id")
    added_songs = set(playlist_info.get("added_songs", []))

    if not playlist_id:
        playlist_name = f"{PLAYLIST_NAME_PREFIX} {year_str}"
        logger.info(f"Creating new playlist: {playlist_name}")
        playlist_id = client.create_playlist(
            name=playlist_name,
            description=f"J-Wave TOKIO HOT 100 annual playlist for {year_str}. Auto-generated.",
        )
        cache["playlists"][year_str] = {
            "id": playlist_id,
            "added_songs": [],
        }
        added_songs = set()

    # --- Step 4: Add only new songs to the playlist ---
    logger.info("Step 4: Adding new songs to playlist...")

    # Filter to songs not already in this year's playlist
    new_tracks = []
    skipped = 0
    for rank, catalog_id in sorted(matched, key=lambda x: x[0]):
        if catalog_id in added_songs:
            skipped += 1
        else:
            new_tracks.append(catalog_id)

    if new_tracks:
        logger.info(f"Adding {len(new_tracks)} new songs (skipping {skipped} already in playlist)")
        client.add_tracks_to_playlist(playlist_id, new_tracks)

        # Update the added_songs list in cache
        added_songs.update(new_tracks)
        cache["playlists"][year_str]["added_songs"] = sorted(added_songs)
    else:
        logger.info(f"No new songs to add ({skipped} already in playlist)")

    # --- Step 5: Save cache ---
    logger.info("Step 5: Saving cache...")
    save_cache(cache)

    # --- Summary ---
    logger.info("=" * 60)
    logger.info(f"Chart songs:       {len(songs)}")
    logger.info(f"Matched:           {len(matched)}")
    logger.info(f"Not found:         {len(not_found)}")
    logger.info(f"Newly added:       {len(new_tracks)}")
    logger.info(f"Already in list:   {skipped}")
    logger.info(f"Playlist ID:       {playlist_id}")
    logger.info("=" * 60)

    if not_found:
        logger.info(f"Songs not found on Apple Music ({len(not_found)}):")
        for s in not_found:
            logger.info(f"  [{s['rank']:>3}] {s['artist']} - {s['title']}")

    logger.info("Done!")


if __name__ == "__main__":
    main()
