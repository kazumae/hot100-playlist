"""J-Wave TOKIO HOT 100 chart scraper."""

import logging
import math
import re
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

from config import JWAVE_CHART_URL, JWAVE_CGI_URL, USER_AGENT

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def scrape_chart() -> list[dict]:
    """
    Scrape the current J-Wave TOKIO HOT 100 chart.

    Returns a list of dicts with keys: rank (int), title (str), artist (str).
    Tries the static chart page first, falls back to the CGI endpoint.
    """
    try:
        songs = _scrape_chart_page()
        if len(songs) >= 50:
            return songs
        logger.warning(f"Chart page returned only {len(songs)} songs, trying CGI fallback")
    except Exception as e:
        logger.warning(f"Chart page scraping failed: {e}")

    logger.info("Falling back to CGI endpoint...")
    return _scrape_cgi_endpoint()


def _scrape_chart_page() -> list[dict]:
    """
    Parse /chart/main.htm - static page with current week's chart.

    HTML structure per <li>:
        <div class="song_rank">1</div>
        <div class="song_lastrank">...</div>
        <div class="song_title"><a href="...soundinfo.cgi...">TITLE</a></div>
        <div class="song_artist">ARTIST</div>
        <div class="vote_btn">...</div>
    """
    response = requests.get(
        JWAVE_CHART_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove all script tags to avoid noise
    for script in soup.find_all("script"):
        script.decompose()

    songs = []

    for li in soup.find_all("li"):
        rank_el = li.find(class_="song_rank")
        title_el = li.find(class_="song_title")
        artist_el = li.find(class_="song_artist")

        if not (rank_el and title_el and artist_el):
            continue

        rank_text = rank_el.get_text(strip=True)
        rank_num = int(re.sub(r"[^0-9]", "", rank_text) or "0")
        title = title_el.get_text(strip=True)
        artist = artist_el.get_text(strip=True)

        if rank_num > 0 and title and artist:
            songs.append({"rank": rank_num, "title": title, "artist": artist})

    songs.sort(key=lambda s: s["rank"])
    logger.info(f"Scraped {len(songs)} songs from chart page")
    return songs


def _scrape_cgi_endpoint() -> list[dict]:
    """
    Fallback: POST to top100.cgi with calculated week params.

    Week calculation matches the existing Laravel code:
    RankController.php L101: ceil(day / 7)
    """
    now = datetime.now(JST)
    year = now.year
    month = now.month
    week = math.ceil(now.day / 7)

    logger.info(f"CGI fallback: year={year}, month={month}, week={week}")

    response = requests.post(
        JWAVE_CGI_URL,
        data={"YEAR": year, "MONTH": month, "WEEK": week},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove scripts
    for script in soup.find_all("script"):
        script.decompose()

    songs = []

    # Try CSS class-based parsing (from Laravel GetSongFromJwaveCommand.php)
    rank_items = soup.select("ul.chart > li")
    if rank_items:
        for item in rank_items:
            rank_el = item.select_one(".song_rank")
            title_el = item.select_one(".song_title")
            artist_el = item.select_one(".song_artist")
            if rank_el and title_el and artist_el:
                rank_text = rank_el.get_text(strip=True)
                rank_num = int(re.sub(r"[^0-9]", "", rank_text) or "0")
                songs.append({
                    "rank": rank_num,
                    "title": title_el.get_text(strip=True),
                    "artist": artist_el.get_text(strip=True),
                })

    # If CSS class approach fails, try soundinfo.cgi link approach
    if not songs:
        for li in soup.find_all("li"):
            title_link = li.find("a", href=lambda h: h and "soundinfo.cgi" in h)
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            li_text = li.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in li_text.split("\n") if line.strip()]

            rank_num = 0
            if lines:
                match = re.match(r"^(\d+)$", lines[0])
                if match:
                    rank_num = int(match.group(1))

            artist = ""
            for sibling in title_link.next_siblings:
                if hasattr(sibling, "name") and sibling.name == "a":
                    break
                text = sibling.string if hasattr(sibling, "string") else str(sibling)
                if text:
                    text = text.strip()
                    if text and text != "\n":
                        artist = text
                        break

            if rank_num > 0 and title and artist:
                songs.append({"rank": rank_num, "title": title, "artist": artist})

    if len(songs) < 50:
        raise ValueError(
            f"Only parsed {len(songs)} songs from CGI endpoint. "
            "HTML structure may have changed."
        )

    songs.sort(key=lambda s: s["rank"])
    logger.info(f"Scraped {len(songs)} songs from CGI endpoint")
    return songs
