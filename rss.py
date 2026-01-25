import feedparser
import requests
import json
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
    for link in entry.get("links", []):
        if link.get("type", "").startswith("audio"):
            return link.get("href")
    return None


def download_file(url, path):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)


def main():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("❌ אין פרקים ב-RSS")
        return

    state = load_state()
    downloaded = set(state["downloaded_ids"])

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    entries = feed.entries[:DOWNLOAD_LAST_N]
    new_downloads = 0

    for entry in reversed(entries):
        episode_id = entry.get("id") or entry.get("guid") or entry.get("link")
        if episode_id in downloaded:
            continue

        title = entry.title
        audio_url = find_audio_url(entry)

        if not audio_url:
            print(f"⚠️ אין אודיו: {title}")
            continue

        filename = sanitize_filename(title) + ".mp3"
        filepath = DOWNLOAD_DIR / filename

        print(f"⬇️ מוריד: {title}")
        download_file(audio_url, filepath)

        downloaded.add(episode_id)
        new_downloads += 1

    state["downloaded_ids"] = list(downloaded)
    save_state(state)

    print(f"✅ סיום. הורדו {new_downloads} פרקים חדשים.")


if __name__ == "__main__":
    main()
