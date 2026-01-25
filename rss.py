import argparse
import logging
import feedparser
import requests
import json
import os
import time
from pathlib import Path

RSS_URL = "https://www.osimhistoria.com/feed/podcast/osim-psychology"

DOWNLOAD_LAST_N = 3   # 👈 שנה ל־1 / 5 / 10 לפי הצורך
DOWNLOAD_DIR = Path("downloads")
STATE_FILE = Path("state.json")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"downloaded_ids": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in " _-").strip()


def find_audio_url(entry):
    # check standard links
    for link in entry.get("links", []):
        if link.get("type", "").startswith("audio"):
            return link.get("href")

    # check enclosures
    for enc in entry.get("enclosures", []):
        href = enc.get("href") or enc.get("url")
        if not href:
            continue
        if enc.get("type", "").startswith("audio") or True:
            return href

    # feedparser sometimes provides media_content
    for m in entry.get("media_content", []) if entry.get("media_content") else []:
        href = m.get("url") or m.get("href")
        if href and m.get("type", "").startswith("audio"):
            return href

    return None


def download_file(url, path, retries=3):
    tmp = path.with_name(path.name + ".part")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
            os.replace(tmp, path)
            return
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise


def main():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        logging.error("אין פרקים ב-RSS")
        return

    state = load_state()
    downloaded = set(state.get("downloaded_ids", []))

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    entries = feed.entries[:DOWNLOAD_LAST_N]
    new_downloads = 0

    for entry in reversed(entries):
        episode_id = entry.get("id") or entry.get("guid") or entry.get("link") or entry.get("title")

        title = entry.get("title", "untitled")
        audio_url = find_audio_url(entry)

        filename = sanitize_filename(title) + ".mp3"
        filepath = DOWNLOAD_DIR / filename

        if episode_id in downloaded:
            logging.info("כבר הורד: %s", title)
            continue

        if filepath.exists():
            logging.info("קובץ קיים — מדלג: %s", filename)
            downloaded.add(episode_id)
            continue

        if not audio_url:
            logging.warning("אין אודיו: %s", title)
            continue

        logging.info("מוריד: %s", title)
        try:
            download_file(audio_url, filepath)
        except Exception as e:
            logging.error("כשל בהורדה: %s — %s", title, e)
            continue

        downloaded.add(episode_id)
        new_downloads += 1

    state["downloaded_ids"] = list(downloaded)
    save_state(state)

    logging.info("סיום. הורדו %d פרקים חדשים.", new_downloads)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSS downloader")
    parser.add_argument("--url", "-u", default=RSS_URL, help="RSS feed URL")
    parser.add_argument("--n", "-n", type=int, default=DOWNLOAD_LAST_N, help="Number of recent entries to check")
    parser.add_argument("--dir", "-d", default=str(DOWNLOAD_DIR), help="Download directory")
    parser.add_argument("--state", "-s", default=str(STATE_FILE), help="State file path")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    args = parser.parse_args()

    RSS_URL = args.url
    DOWNLOAD_LAST_N = args.n
    DOWNLOAD_DIR = Path(args.dir)
    STATE_FILE = Path(args.state)

    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format='%(levelname)s: %(message)s')

    main()
