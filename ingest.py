import sys
import os
import re
import json
import sqlite3
import subprocess
import textwrap
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8-sig")

from library import ensure

ensure("requests")
ensure("apify-client", "apify_client")
ensure("Pillow", "PIL")

import requests

DB_PATH        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.db")
THUMBNAILS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbnails")
IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".avif"}
VIDEO_EXTS   = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}

PLATFORM_PATTERNS = [
    ("tiktok",    ["tiktok.com"]),
    ("instagram", [r"instagram\.com/(?:[^/?#]+/)?reels?/", r"instagram\.com/(?:[^/?#]+/)?p/"]),
    ("youtube",   ["youtube.com/shorts", "youtu.be", "youtube.com/watch"]),
    ("pinterest", ["pinterest.com", "pin.it"]),
]
VIDEO_PLATFORMS = {"tiktok", "instagram", "youtube"}

VIDEO_CHECKLIST_KEYS = [
    ("outcome_before_how",     "Shows outcome or result before explaining how"),
    ("text_in_first_2s",       "Visible on-screen text in the first 2 seconds"),
    ("audio_suspense",         "Audio starts mid-thought or cuts off to create suspense"),
    ("human_face_or_reaction", "Shows a human face or emotional reaction"),
    ("two_layers_aligned",     "Two or more layers aligned toward the same mechanism"),
    ("pattern_interrupt",      "Pattern interrupt — something visually unexpected — in the first second"),
    ("no_intro_before_value",  "Hook avoids context or intro before the value"),
]

IMAGE_CHECKLIST_KEYS = [
    ("clear_focal_point",       "Clear single focal point the eye goes to first"),
    ("text_readable_at_glance", "Text readable at a glance without zooming"),
    ("contrast_directs",        "Colour palette uses contrast deliberately to direct attention"),
    ("recognisable_aesthetic",  "Layout recognisable as a specific aesthetic or platform style"),
    ("creates_question",        "Creates a question or desire without fully resolving it"),
]

TEXT_CHECKLIST_KEYS = [
    ("claim_without_qualifying", "First sentence makes a claim without qualifying it"),
    ("specific_person",          "Addresses a specific person or situation rather than everyone"),
    ("information_gap",          "Creates an information gap the reader needs to fill"),
    ("under_10_words",           "Opening statement is under 10 words"),
    ("concrete_language",        "Uses concrete language rather than abstract descriptions"),
]

def _safe_int(val):
    try:
        v = int(val)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def build_checklist_summary(checklist_dict):
    if not isinstance(checklist_dict, dict):
        return "0 / 0 passed"
    total  = len(checklist_dict)
    passed = sum(1 for v in checklist_dict.values() if v is True)
    return f"{passed} / {total} passed"


def init_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hooks (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            url                  TEXT NOT NULL,
            platform             TEXT,
            hook_type            TEXT,
            dominant_layer       TEXT,
            dominant_emotion     TEXT,
            checklist_results    TEXT,
            checklist_summary    TEXT,
            visual_explanation   TEXT,
            pacing_explanation   TEXT,
            colour_explanation   TEXT,
            text_explanation     TEXT,
            audio_explanation    TEXT,
            overall_explanation  TEXT,
            weakness             TEXT,
            replication_template TEXT,
            personal_note        TEXT,
            thumbnail_path       TEXT,
            analyzed_at          TEXT
        )
    """)
    for col in ("platform TEXT", "checklist_results TEXT", "checklist_summary TEXT",
                "dominant_emotion TEXT", "pacing_explanation TEXT", "colour_explanation TEXT",
                "weakness TEXT", "replication_template TEXT", "personal_note TEXT",
                "thumbnail_path TEXT", "is_own_content INTEGER DEFAULT 0",
                "target_demographic TEXT", "niche TEXT", "retention_tactics TEXT",
                "views INTEGER", "likes INTEGER", "comments INTEGER", "shares INTEGER",
                "content_title TEXT"):
        try:
            conn.execute(f"ALTER TABLE hooks ADD COLUMN {col}")
        except Exception:
            pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_type        TEXT,
            asset_description TEXT,
            reuse_instruction TEXT,
            source_url        TEXT,
            source_table      TEXT,
            source_id         INTEGER,
            personal_note     TEXT,
            created_at        TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingested_content (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type        TEXT,
            source              TEXT,
            layout_pattern      TEXT,
            colour_palette      TEXT,
            text_style          TEXT,
            emotional_tone      TEXT,
            visual_hook_type    TEXT,
            scroll_stop_reason  TEXT,
            hook_type           TEXT,
            emotional_trigger   TEXT,
            offer_structure     TEXT,
            headline_technique  TEXT,
            strength            TEXT,
            weakness            TEXT,
            rewrite_suggestion  TEXT,
            checklist_results   TEXT,
            checklist_summary   TEXT,
            personal_note       TEXT,
            analyzed_at         TEXT
        )
    """)
    for col in ("checklist_results TEXT", "checklist_summary TEXT",
                "is_own_content INTEGER DEFAULT 0",
                "verbal_technique TEXT", "pacing_note TEXT",
                "audio_transcript TEXT",
                "target_demographic TEXT", "niche TEXT", "retention_tactics TEXT"):
        try:
            conn.execute(f"ALTER TABLE ingested_content ADD COLUMN {col}")
        except Exception:
            pass

    conn.commit()
    return conn


def _str_field(v):
    if v is None:
        return None
    if isinstance(v, list):
        return " ".join(str(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v)
    return str(v)


def save_video_result(conn, url, platform, result, note=None, thumbnail_path=None, is_own=False, kpi=None, title=None):
    checklist = result.get("checklist", {})
    summary   = build_checklist_summary(checklist)
    rt        = result.get("retention_tactics", [])
    kpi       = kpi or {}
    conn.execute("""
        INSERT INTO hooks (
            url, platform, hook_type, dominant_layer, dominant_emotion,
            target_demographic, niche,
            checklist_results, checklist_summary,
            visual_explanation, pacing_explanation, colour_explanation,
            text_explanation, audio_explanation, overall_explanation,
            weakness, replication_template, retention_tactics,
            personal_note, thumbnail_path,
            is_own_content, analyzed_at,
            views, likes, comments, shares, content_title
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        url, platform,
        _str_field(result.get("hook_type")),
        _str_field(result.get("dominant_layer")),
        _str_field(result.get("dominant_emotion")),
        _str_field(result.get("target_demographic")),
        _str_field(result.get("niche")),
        json.dumps(checklist),
        summary,
        _str_field(result.get("visual_explanation")),
        _str_field(result.get("pacing_explanation")),
        _str_field(result.get("colour_explanation")),
        _str_field(result.get("text_explanation")),
        _str_field(result.get("audio_explanation")),
        _str_field(result.get("overall_explanation")),
        _str_field(result.get("weakness")),
        _str_field(result.get("replication_template")),
        json.dumps(rt) if isinstance(rt, list) else (rt or "[]"),
        note or None,
        thumbnail_path or None,
        1 if is_own else 0,
        datetime.utcnow().isoformat(),
        kpi.get("views"), kpi.get("likes"), kpi.get("comments"), kpi.get("shares"),
        (title or "").strip()[:300] or None,
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def save_image_result(conn, source, result, note=None, is_own=False):
    checklist = result.get("checklist", {})
    summary   = build_checklist_summary(checklist)
    palette   = result.get("colour_palette", [])
    if isinstance(palette, list):
        palette = json.dumps(palette)
    conn.execute("""
        INSERT INTO ingested_content (
            content_type, source,
            layout_pattern, colour_palette, text_style,
            emotional_tone, visual_hook_type, scroll_stop_reason,
            target_demographic, niche,
            checklist_results, checklist_summary,
            personal_note, is_own_content, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "image", source,
        result.get("layout_pattern"),
        palette,
        result.get("text_style"),
        result.get("emotional_tone"),
        result.get("visual_hook_type"),
        result.get("scroll_stop_reason"),
        _str_field(result.get("target_demographic")),
        _str_field(result.get("niche")),
        json.dumps(checklist),
        summary,
        note or None,
        1 if is_own else 0,
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def save_text_result(conn, source, result, note=None, is_own=False):
    checklist = result.get("checklist", {})
    summary   = build_checklist_summary(checklist)
    rt        = result.get("retention_tactics", [])
    conn.execute("""
        INSERT INTO ingested_content (
            content_type, source,
            hook_type, emotional_trigger, offer_structure,
            headline_technique, strength, weakness, rewrite_suggestion,
            target_demographic, niche, retention_tactics,
            checklist_results, checklist_summary,
            personal_note, is_own_content, analyzed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "text", str(source)[:500],
        result.get("hook_type"),
        result.get("emotional_trigger"),
        result.get("offer_structure"),
        result.get("headline_technique"),
        result.get("strength"),
        result.get("weakness"),
        result.get("rewrite_suggestion"),
        _str_field(result.get("target_demographic")),
        _str_field(result.get("niche")),
        json.dumps(rt) if isinstance(rt, list) else (rt or "[]"),
        json.dumps(checklist),
        summary,
        note or None,
        1 if is_own else 0,
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def detect_platform(url):
    lower = url.lower()
    for platform, patterns in PLATFORM_PATTERNS:
        for pat in patterns:
            if re.search(pat, lower):
                return platform
    if url.startswith(("http://", "https://")):
        return "web"
    return None


def detect_content_type(source, interactive=True):
    s = source.strip()
    if s.startswith(("http://", "https://")):
        platform = detect_platform(s)
        if platform in VIDEO_PLATFORMS:
            return "video"
        path_only = s.split("?")[0].lower()
        for ext in IMAGE_EXTS:
            if path_only.endswith(ext):
                return "image_url"
        try:
            r = requests.head(s, timeout=5, allow_redirects=True)
            ct = r.headers.get("Content-Type", "")
            if ct.startswith("image/"):
                return "image_url"
        except Exception:
            pass
        if not interactive:
            return "ambiguous"
        print("Could not automatically detect the content type for this URL.")
        while True:
            choice = input("Is this a (v)ideo URL, (i)mage URL, or (t)ext content? ").strip().lower()
            if choice.startswith("v"):
                return "video"
            if choice.startswith("i"):
                return "image_url"
            if choice.startswith("t"):
                return "text"
            print("Please enter v, i, or t.")
    if os.path.isfile(s):
        ext = os.path.splitext(s)[1].lower()
        if ext in VIDEO_EXTS:
            return "local_video"
        return "image_file" if ext in IMAGE_EXTS else "text_file"
    return "text"


def _apify_run(actor_id, run_input):
    from apify_client import ApifyClient
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("Error: APIFY_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    client = ApifyClient(token)
    print(f"  Running Apify: {actor_id} ...", file=sys.stderr)
    run    = client.actor(actor_id).call(run_input=run_input)
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _fetch_tiktok(url):
    items = _apify_run("clockworks/tiktok-scraper", {
        "postURLs": [url],
        "maxItems": 1,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
    })
    if not items:
        return None, "No data retrieved from TikTok.", {}, ""

    item          = items[0]
    thumbnail_url = (
        (item.get("videoMeta") or {}).get("coverUrl") or
        ((item.get("covers") or [None])[0])
    )
    transcript = item.get("text") or item.get("caption") or "No caption available."
    title      = (item.get("text") or item.get("caption") or "").strip()

    kpi = {
        "views":    _safe_int(item.get("playCount")),
        "likes":    _safe_int(item.get("diggCount")),
        "comments": _safe_int(item.get("commentCount")),
        "shares":   _safe_int(item.get("shareCount")),
    }

    try:
        t_items = _apify_run("memo23/tiktok-transcript-extractor-cheerio", {"postUrl": url})
        if t_items:
            spoken = t_items[0].get("transcript") or t_items[0].get("text") or ""
            if spoken:
                transcript = f"Spoken transcript: {spoken}\nPost caption: {transcript}"
    except Exception:
        pass

    return thumbnail_url, transcript, kpi, title


def _fetch_instagram(url):
    items = _apify_run("apify/instagram-scraper", {
        "directUrls": [url],
        "resultsType": "posts",
        "resultsLimit": 1,
    })
    if not items:
        return None, "No data retrieved from Instagram.", {}, ""

    item          = items[0]
    thumbnail_url = (
        item.get("displayUrl") or
        item.get("imageUrl") or
        item.get("thumbnailUrl") or
        item.get("videoUrl")
    )
    transcript = item.get("caption") or item.get("text") or "No caption available."
    title      = (item.get("caption") or item.get("text") or "").strip()
    kpi = {
        "views":    _safe_int(item.get("videoViewCount") or item.get("videoPlayCount")),
        "likes":    _safe_int(item.get("likesCount")),
        "comments": _safe_int(item.get("commentsCount")),
        "shares":   None,
    }
    return thumbnail_url, transcript, kpi, title


def _fetch_youtube(url):
    import re
    shorts_match = re.search(r"youtube\.com/shorts/([A-Za-z0-9_-]+)", url)
    if shorts_match:
        video_id  = shorts_match.group(1)
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        watch_url = url

    items = _apify_run("streamers/youtube-scraper", {
        "startUrls": [{"url": watch_url}],
    })

    if not items:
        print("  Warning: streamers/youtube-scraper returned no data, falling back to rag-web-browser.", file=sys.stderr)
        return _fetch_web(url, "youtube")

    item          = items[0]
    thumbnail_url = item.get("thumbnailUrl") or item.get("thumbnail")

    title     = item.get("title", "")
    desc      = item.get("text") or item.get("description") or ""
    subtitles = item.get("subtitles")

    parts = []
    if title:
        parts.append(f"Title: {title}")

    if subtitles and str(subtitles).lower() != "none":
        if isinstance(subtitles, list):
            lines = []
            for s in subtitles:
                if isinstance(s, dict):
                    lines.append(s.get("text") or s.get("content") or "")
                else:
                    lines.append(str(s))
            spoken = " ".join(l for l in lines if l).strip()
        else:
            spoken = str(subtitles).strip()
        if spoken:
            parts.append(f"Spoken transcript: {spoken[:3000]}")

    if desc:
        parts.append(f"Description/caption: {desc[:1000]}")

    channel = item.get("channelName") or item.get("channelUsername")
    if channel:
        parts.append(f"Channel: {channel}")
    duration = item.get("duration")
    if duration:
        parts.append(f"Duration: {duration}")
    hashtags = item.get("hashtags")
    if hashtags and str(hashtags).lower() not in ("none", "[]"):
        parts.append(f"Hashtags: {hashtags}")

    if not parts:
        parts.append("No transcript or description available.")

    transcript = "\n".join(parts)
    kpi = {
        "views":    _safe_int(item.get("viewCount") or item.get("views")),
        "likes":    _safe_int(item.get("likeCount") or item.get("likes")),
        "comments": _safe_int(item.get("commentCount") or item.get("comments")),
        "shares":   None,
    }
    return thumbnail_url, transcript, kpi, title


def _fetch_web(url, platform):
    items = _apify_run("apify/rag-web-browser", {"query": url, "maxResults": 1})
    if not items:
        return None, "No data retrieved from URL.", {}, ""

    item    = items[0]
    content = item.get("text") or item.get("markdown") or item.get("content") or str(item)
    title   = (item.get("title") or "").strip()
    if len(content) > 3000:
        content = content[:3000] + "...[truncated]"
    return None, content, {}, title


def fetch_apify_content(url, platform):
    print(f"Fetching content via Apify ({platform})...", file=sys.stderr)
    if platform == "tiktok":
        return _fetch_tiktok(url)
    elif platform == "instagram":
        return _fetch_instagram(url)
    elif platform == "youtube":
        return _fetch_youtube(url)
    else:
        return _fetch_web(url, platform)


def _crop_youtube_pillarbox(image_bytes, ext):
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        target_w = int(h * 9 / 16)

        if target_w >= w * 0.95:
            return image_bytes  # already roughly vertical, nothing to crop

        left     = (w - target_w) // 2
        cropped  = img.crop((left, 0, left + target_w, h))
        buf      = io.BytesIO()
        save_fmt = "JPEG" if ext.lower() in ("jpg", "jpeg") else ext.upper()
        cropped.save(buf, format=save_fmt if save_fmt in ("JPEG", "PNG", "WEBP") else "JPEG")
        return buf.getvalue()
    except Exception:
        return image_bytes


def _fetch_and_crop_thumbnail(thumbnail_url, platform=None):
    r = requests.get(thumbnail_url, timeout=15)
    r.raise_for_status()
    mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    ext        = mime.split("/")[1] if "/" in mime else "jpg"
    image_data = r.content
    if platform == "youtube":
        image_data = _crop_youtube_pillarbox(image_data, ext)
    return image_data, mime, ext


def _write_thumbnail(image_data, ext, dedup_key, prefix=""):
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    filename = f"{prefix}{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{abs(hash(dedup_key)) % 10000}.{ext}"
    path     = os.path.join(THUMBNAILS_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_data)
    return path, filename


def _save_thumbnail_to_disk(thumbnail_url, platform=None, prefix=""):
    if not thumbnail_url:
        return None
    try:
        image_data, mime, ext = _fetch_and_crop_thumbnail(thumbnail_url, platform)
        path, filename = _write_thumbnail(image_data, ext, thumbnail_url, prefix)
        print(f"  Thumbnail loaded and saved ({len(image_data) // 1024} KB) -> {filename}", file=sys.stderr)
        return path
    except Exception as e:
        print(f"  Warning: could not fetch thumbnail ({e}).", file=sys.stderr)
        return None


def _extract_frame_ffmpeg(path):
    try:
        os.makedirs(THUMBNAILS_DIR, exist_ok=True)
        filename       = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{abs(hash(path)) % 10000}.jpg"
        thumbnail_path = os.path.join(THUMBNAILS_DIR, filename)
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-ss", "00:00:01", "-vframes", "1", thumbnail_path],
            check=True, capture_output=True,
        )
        print(f"  Frame extracted -> {filename}", file=sys.stderr)
        return thumbnail_path
    except Exception as e:
        print(f"  Warning: could not extract thumbnail ({e})", file=sys.stderr)
        return None


def cmd_fetch_only(source, note=None, forced_type=None):
    content_type = forced_type or detect_content_type(source, interactive=False)
    platform     = detect_platform(source) if content_type == "video" else None
    out = {"content_type": content_type, "source": source, "platform": platform, "note": note}

    if content_type == "ambiguous":
        out["message"] = "Could not automatically detect content type. Ask the user: video, image, or text? Then retry with --type video|image_url|text."
        print(json.dumps(out, ensure_ascii=False))
        return

    if content_type == "video":
        thumbnail_url, transcript, kpi, title = fetch_apify_content(source, platform)
        thumbnail_path = _save_thumbnail_to_disk(thumbnail_url, platform)
        out.update({
            "transcript": transcript, "kpi": kpi, "title": title,
            "thumbnail_path": thumbnail_path,
        })

    elif content_type == "local_video":
        thumbnail_path = _extract_frame_ffmpeg(source)
        out.update({
            "transcript": "", "title": os.path.basename(source),
            "thumbnail_path": thumbnail_path,
        })

    elif content_type == "image_url":
        local_path = _save_thumbnail_to_disk(source, platform=None, prefix="img_")
        out.update({"local_image_path": local_path})

    elif content_type == "image_file":
        out.update({"local_image_path": source})

    elif content_type == "text_file":
        with open(source, "r", encoding="utf-8") as f:
            out.update({"text": f.read()})

    elif content_type == "text":
        out.update({"text": source})

    else:
        out["error"] = f"Unrecognised content_type '{content_type}'. Expected one of: video, local_video, image_url, image_file, text, text_file."

    print(json.dumps(out, ensure_ascii=False))


def cmd_save_result():
    payload      = json.loads(sys.stdin.read())
    content_type = payload.get("content_type")
    source       = payload.get("source")
    if not content_type or not source:
        print("Error: --save-result payload is missing required 'content_type' or 'source'.")
        sys.exit(1)
    note         = payload.get("note")
    is_own       = bool(payload.get("is_own", False))
    result       = payload.get("result", {})
    assets       = payload.get("assets", [])

    conn = init_db()

    if content_type in ("video", "local_video"):
        platform = payload.get("platform") or ("local" if content_type == "local_video" else "web")
        thumbnail_path = payload.get("thumbnail_path")
        kpi   = payload.get("kpi") or {}
        title = payload.get("title")
        entry_id = save_video_result(conn, source, platform, result, note, thumbnail_path, is_own, kpi, title)
        print_video_result(source, platform, result, entry_id, thumbnail_path, kpi)
        table = "hooks"

    elif content_type in ("image_url", "image_file"):
        entry_id = save_image_result(conn, source, result, note, is_own)
        print_image_result(source, result, entry_id)
        table = "ingested_content"

    elif content_type in ("text", "text_file"):
        entry_id = save_text_result(conn, source, result, note, is_own)
        print_text_result(source, result, entry_id)
        table = "ingested_content"

    else:
        print(f"Error: unknown content_type '{content_type}' in --save-result payload.")
        conn.close()
        sys.exit(1)

    print("Saving reusable assets...")
    saved = save_assets(conn, assets, source, table, entry_id, note)
    print_assets(saved)
    print(f"Done. {table} #{entry_id}, {len(saved)} asset(s) saved to hooks.db.")
    conn.close()


def save_assets(conn, assets, source_url, source_table, source_id, personal_note=None):
    saved = []
    for a in assets:
        if not isinstance(a, dict):
            continue
        conn.execute("""
            INSERT INTO assets
                (asset_type, asset_description, reuse_instruction,
                 source_url, source_table, source_id, personal_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(a.get("asset_type", "")).strip(),
            str(a.get("asset_description", "")).strip(),
            str(a.get("reuse_instruction", "")).strip(),
            source_url, source_table, source_id,
            personal_note,
            datetime.utcnow().isoformat(),
        ))
        saved.append(a)
    conn.commit()
    return saved


def _w(text, width=60, indent=18):
    if not text:
        return "n/a"
    return ("\n" + " " * indent).join(textwrap.wrap(str(text), width))


def _print_checklist(checklist, keys):
    summary = build_checklist_summary(checklist)
    print(f"\n  CHECKLIST — {summary}")
    print("  " + "-" * 68)
    for key, label in keys:
        val    = checklist.get(key)
        symbol = "[✓]" if val is True else "[✗]"
        print(f"  {symbol} {label}")


def print_video_result(url, platform, result, entry_id, thumbnail_path=None, kpi=None):
    checklist = result.get("checklist", {})
    bar  = "=" * 72
    thin = "-" * 72

    def g(k):
        return result.get(k, "n/a")

    print(f"\n{bar}")
    print(f"  VIDEO HOOK ANALYSIS  (saved as hooks #{entry_id})")
    print(thin)
    print(f"  URL          : {url}")
    print(f"  Platform     : {platform}")
    if thumbnail_path:
        print(f"  Thumbnail    : {thumbnail_path}")
    if kpi:
        parts = []
        if kpi.get("views"):    parts.append(f"{kpi['views']:,} views")
        if kpi.get("likes"):    parts.append(f"{kpi['likes']:,} likes")
        if kpi.get("comments"): parts.append(f"{kpi['comments']:,} comments")
        if kpi.get("shares"):   parts.append(f"{kpi['shares']:,} shares")
        if parts:
            print(f"  Engagement   : {' · '.join(parts)}")
    print(f"  Hook Type    : {g('hook_type')}")
    print(f"  Dom. Layer   : {g('dominant_layer')}")
    print(f"  Dom. Emotion : {g('dominant_emotion')}")
    print(f"  Demographic  : {g('target_demographic')}")
    print(f"  Niche        : {g('niche')}")
    _print_checklist(checklist, VIDEO_CHECKLIST_KEYS)
    print(thin)
    print(f"  Visual       : {_w(g('visual_explanation'))}")
    print(f"  Pacing       : {_w(g('pacing_explanation'))}")
    print(f"  Colour       : {_w(g('colour_explanation'))}")
    print(f"  Text Overlay : {_w(g('text_explanation'))}")
    print(f"  Audio        : {_w(g('audio_explanation'))}")
    print(thin)
    print(f"  Overall:")
    print(f"  {_w(g('overall_explanation'), width=70, indent=2)}")
    print(thin)
    print(f"  Weakness : {_w(g('weakness'), width=65, indent=13)}")
    print(f"  Template : {_w(g('replication_template'), width=65, indent=13)}")
    rt_raw = result.get("retention_tactics", [])
    if rt_raw:
        rt_list = rt_raw if isinstance(rt_raw, list) else []
        if rt_list:
            print(thin)
            print(f"  RETENTION TACTICS ({len(rt_list)} identified):")
            for i, tactic in enumerate(rt_list, 1):
                print(f"  {i}. {_w(str(tactic), width=65, indent=5)}")
    print(f"{bar}\n")


def print_image_result(source, result, entry_id):
    bar  = "=" * 68
    thin = "-" * 68
    palette = result.get("colour_palette", [])
    palette_str = "  ".join(palette) if isinstance(palette, list) else str(palette)

    print(f"\n{bar}")
    print(f"  IMAGE ANALYSIS  (saved as ingested_content #{entry_id})")
    print(thin)
    src_display = source if len(source) <= 65 else source[:62] + "..."
    print(f"  Source         : {src_display}")
    print(f"  Layout Pattern : {_w(result.get('layout_pattern'))}")
    print(f"  Colour Palette : {palette_str}")
    print(f"  Text Style     : {_w(result.get('text_style'))}")
    print(f"  Emotional Tone : {result.get('emotional_tone', 'n/a')}")
    print(f"  Hook Type      : {result.get('visual_hook_type', 'n/a')}")
    print(f"  Demographic    : {result.get('target_demographic', 'n/a')}")
    print(f"  Niche          : {result.get('niche', 'n/a')}")
    print(thin)
    print(f"  Scroll-Stop    : {_w(result.get('scroll_stop_reason'), width=60)}")
    _print_checklist(result.get("checklist", {}), IMAGE_CHECKLIST_KEYS)
    print(f"{bar}\n")


def print_text_result(source, result, entry_id):
    bar  = "=" * 68
    thin = "-" * 68
    display = source if len(source) <= 65 else source[:62] + "..."

    print(f"\n{bar}")
    print(f"  TEXT / COPY ANALYSIS  (saved as ingested_content #{entry_id})")
    print(thin)
    print(f"  Text           : {display}")
    print(f"  Hook Type      : {result.get('hook_type', 'n/a')}")
    print(f"  Emotion Trigger: {result.get('emotional_trigger', 'n/a')}")
    print(f"  Offer Structure: {_w(result.get('offer_structure'))}")
    print(f"  Technique      : {result.get('headline_technique', 'n/a')}")
    print(f"  Demographic    : {result.get('target_demographic', 'n/a')}")
    print(f"  Niche          : {result.get('niche', 'n/a')}")
    print(thin)
    print(f"  Strength       : {_w(result.get('strength'), width=60)}")
    print(f"  Weakness       : {_w(result.get('weakness'), width=60)}")
    print(f"  Suggestion     : {_w(result.get('rewrite_suggestion'), width=60)}")
    _print_checklist(result.get("checklist", {}), TEXT_CHECKLIST_KEYS)
    rt_raw = result.get("retention_tactics", [])
    if rt_raw:
        rt_list = rt_raw if isinstance(rt_raw, list) else []
        if rt_list:
            print(f"\n  RETENTION TACTICS ({len(rt_list)} identified):")
            for i, tactic in enumerate(rt_list, 1):
                print(f"  {i}. {_w(str(tactic), width=65, indent=5)}")
    print(f"{bar}\n")


def print_assets(assets):
    if not assets:
        print("  No assets extracted.")
        return
    bar = "-" * 68
    type_icons = {
        "layout_pattern":    "[LAYOUT] ",
        "text_style":        "[TEXT]   ",
        "colour_palette":    "[COLOUR] ",
        "hook_template":     "[HOOK]   ",
        "audio_pattern":     "[AUDIO]  ",
        "emotional_trigger": "[TRIGGER]",
    }
    print(f"\n  {len(assets)} reusable asset(s) extracted:")
    for i, a in enumerate(assets, 1):
        atype = str(a.get("asset_type", "unknown"))
        icon  = type_icons.get(atype, "         ")
        print(f"\n  {bar}")
        print(f"  {icon} ASSET {i} — {atype.upper().replace('_', ' ')}")
        print(f"  {bar}")
        desc  = textwrap.fill(str(a.get("asset_description", "n/a")), width=64,
                              initial_indent="  Description : ",
                              subsequent_indent="               ")
        instr = textwrap.fill(str(a.get("reuse_instruction", "n/a")), width=64,
                              initial_indent="  Reuse       : ",
                              subsequent_indent="               ")
        print(desc)
        print(instr)
    print(f"\n  {bar}\n")


CLI_FLAGS = {"--fetch-only", "--save-result", "--type", "--note"}


def _pop_marker(args, flag):
    if flag in args:
        return True, [a for a in args if a != flag]
    return False, args


def _pop_flag(args, flag, greedy=False):
    if flag not in args:
        return None, args
    idx = args.index(flag)
    if greedy:
        end = idx + 1
        while end < len(args) and args[end] not in CLI_FLAGS:
            end += 1
        value = " ".join(args[idx + 1:end]).strip() or None
        return value, args[:idx] + args[end:]
    if idx + 1 < len(args):
        return args[idx + 1], args[:idx] + args[idx + 2:]
    return None, args[:idx]


def main():
    args = sys.argv[1:]

    fetch_only, args = _pop_marker(args, "--fetch-only")
    if fetch_only:
        forced_type, args = _pop_flag(args, "--type")
        note, args        = _pop_flag(args, "--note", greedy=True)
        source = " ".join(args).strip()
        if not source:
            print(json.dumps({"error": "no source provided to --fetch-only"}))
            sys.exit(1)
        cmd_fetch_only(source, note=note, forced_type=forced_type)
        return

    if "--save-result" in args:
        cmd_save_result()
        return

    print('Usage: ingest.py --fetch-only "<source>" [--type video|image_url|text] [--note "..."]')
    print("       ingest.py --save-result   (reads the analysis JSON from stdin)")
    sys.exit(1)


if __name__ == "__main__":
    main()
