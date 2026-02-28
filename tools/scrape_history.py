"""過去のJ-Wave TOKIO HOT 100データを一括取得するスクリプト。

Usage:
    python tools/scrape_history.py --year 2025
    python tools/scrape_history.py --year 2025 --month 6
    python tools/scrape_history.py --year 2024 --year 2025
"""

import argparse
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from config import JWAVE_CGI_URL, USER_AGENT, SONG_CACHE_PATH


def scrape_week(year: int, month: int, week: int) -> list[dict]:
    """指定された年月週のチャートを取得する。"""
    resp = requests.post(
        JWAVE_CGI_URL,
        data={"YEAR": year, "MONTH": month, "WEEK": week},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    soup = BeautifulSoup(resp.text, "html.parser")
    for s in soup.find_all("script"):
        s.decompose()

    songs = []
    for li in soup.find_all("li"):
        rank_el = li.find(class_="song_rank")
        title_el = li.find(class_="song_title")
        artist_el = li.find(class_="song_artist")
        if not (rank_el and title_el and artist_el):
            continue
        rank_num = int(re.sub(r"[^0-9]", "", rank_el.get_text(strip=True)) or "0")
        title = title_el.get_text(strip=True)
        artist = artist_el.get_text(strip=True)
        if rank_num > 0 and title and artist:
            songs.append({"rank": rank_num, "title": title, "artist": artist})

    songs.sort(key=lambda s: s["rank"])
    return songs


def main():
    parser = argparse.ArgumentParser(description="J-Wave HOT 100 過去データ取得")
    parser.add_argument("--year", type=int, action="append", required=True, help="取得する年（複数指定可）")
    parser.add_argument("--month", type=int, default=None, help="特定の月のみ取得（1-12）")
    args = parser.parse_args()

    # キャッシュ読み込み
    if os.path.exists(SONG_CACHE_PATH):
        with open(SONG_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {"songs": {}, "playlists": {}}

    months = [args.month] if args.month else list(range(1, 13))
    weeks = list(range(1, 6))  # 1〜5週

    total_new = 0
    total_skipped = 0

    for year in sorted(args.year):
        for month in months:
            for week in weeks:
                label = f"{year}/{month:02d} W{week}"
                try:
                    songs = scrape_week(year, month, week)
                except Exception as e:
                    print(f"  {label}: エラー - {e}")
                    continue

                if not songs:
                    # データなし（存在しない週）
                    continue

                new_count = 0
                for s in songs:
                    key = f"{s['artist']}|{s['title']}".lower()
                    if key not in cache["songs"]:
                        cache["songs"][key] = {
                            "catalog_id": None,
                            "rank": s["rank"],
                            "artist": s["artist"],
                            "title": s["title"],
                        }
                        new_count += 1

                skip = len(songs) - new_count
                total_new += new_count
                total_skipped += skip
                print(f"  {label}: {len(songs)}曲取得 (新規: {new_count}, 既存スキップ: {skip})")

                # レート制限: 2秒待機
                time.sleep(2)

    # キャッシュ保存
    with open(SONG_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\n完了: 新規 {total_new}曲追加, {total_skipped}曲スキップ（重複）")
    print(f"キャッシュ合計: {len(cache['songs'])}曲")


if __name__ == "__main__":
    main()
