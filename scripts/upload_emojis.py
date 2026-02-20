"""
upload_emojis.py
================
Uploads all bot-asset emojis to a Discord guild and prints the resulting
emoji strings so they can be pasted into chat_handler.py.

Usage
-----
    python scripts/upload_emojis.py

Requires:  pip install requests python-dotenv
The DISCORD_TOKEN env-var (or .env file) must contain a valid bot token that
has the Manage Emojis permission in the target guild.
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

BOT_TOKEN   = os.getenv("DISCORD_TOKEN")
GUILD_ID    = "1462925923547484314"
ASSETS_DIR  = Path(__file__).parent.parent / "assets"
OUTPUT_JSON = Path(__file__).parent / "emoji_ids.json"

HEADERS = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

# emoji name → (animated gif, check png, failed png)
ICON_SETS = {
    "Web":      ("Web.gif",      "Web-check.png",      "Web-failed.png"),
    "Lookup":   ("Lookup.gif",   "Lookup-check.png",   "Lookup-failed.png"),
    "Brain":    ("Brain.gif",    "Brain-check.png",    "Brain-failed.png"),
    "Python":   ("Python.gif",   "Python-check.png",   "Python-failed.png"),
    "Edit":     ("Edit.gif",     "Edit-check.png",     "Edit-failed.png"),
    "Database": ("Database.gif", "Database-check.png", "Database-failed.png"),
    "Image":    ("Image.gif",    "Image-check.png",    "Image-failed.png"),
    "Folder":   ("Folder.gif",   "Folder-check.png",   "Folder-failed.png"),
}

# Discord emoji name restrictions: [a-zA-Z0-9_], 2-32 chars
# We'll use names like:  wirdWeb  wirdWeb_ok  wirdWeb_err
PREFIX = "wird"

def name_for(icon: str, variant: str) -> str:
    """variant: 'anim' | 'ok' | 'err'"""
    suffix = {"anim": "", "ok": "_ok", "err": "_err"}[variant]
    return f"{PREFIX}{icon}{suffix}"


def file_to_data_uri(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() == ".gif":
        mime = "image/gif"
    else:
        mime = "image/png"
    b64 = base64.b64encode(raw).decode()
    return f"data:{mime};base64,{b64}"


def list_existing_emojis() -> dict[str, dict]:
    """Return {name: emoji_object} for all emojis already in the guild."""
    r = requests.get(
        f"https://discord.com/api/v10/guilds/{GUILD_ID}/emojis",
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return {e["name"]: e for e in r.json()}


def upload_emoji(name: str, image_path: Path, existing: dict) -> dict:
    """Upload one emoji; skip if already exists. Returns the emoji object."""
    if name in existing:
        print(f"  [skip]   {name}  (already exists, id={existing[name]['id']})")
        return existing[name]

    data_uri = file_to_data_uri(image_path)
    payload = {"name": name, "image": data_uri}
    r = requests.post(
        f"https://discord.com/api/v10/guilds/{GUILD_ID}/emojis",
        headers=HEADERS,
        json=payload,
        timeout=20,
    )
    if r.status_code == 429:
        retry_after = r.json().get("retry_after", 5)
        print(f"  [rate-limit] sleeping {retry_after}s …")
        time.sleep(retry_after + 0.5)
        return upload_emoji(name, image_path, existing)  # retry

    if not r.ok:
        print(f"  [ERROR] {name}: {r.status_code} {r.text}", file=sys.stderr)
        return None

    emoji = r.json()
    print(f"  [uploaded] {name}  id={emoji['id']}")
    time.sleep(1)   # be polite to the rate-limiter
    return emoji


def emoji_str(emoji: dict) -> str:
    """Return the Discord inline emoji string."""
    if emoji is None:
        return "❓"
    animated = emoji.get("animated", False)
    prefix   = "a" if animated else ""
    return f"<{prefix}:{emoji['name']}:{emoji['id']}>"


def main():
    if not BOT_TOKEN:
        sys.exit("ERROR: DISCORD_TOKEN not found in environment / .env")

    print(f"Fetching existing emojis from guild {GUILD_ID} …")
    existing = list_existing_emojis()
    print(f"  Found {len(existing)} existing emojis.\n")

    results: dict[str, dict] = {}   # icon_name → {anim, ok, err}

    for icon, (gif_file, check_file, fail_file) in ICON_SETS.items():
        print(f"── {icon} ──")
        anim_name = name_for(icon, "anim")
        ok_name   = name_for(icon, "ok")
        err_name  = name_for(icon, "err")

        anim = upload_emoji(anim_name, ASSETS_DIR / gif_file,   existing)
        ok   = upload_emoji(ok_name,   ASSETS_DIR / check_file, existing)
        err  = upload_emoji(err_name,  ASSETS_DIR / fail_file,  existing)

        results[icon] = {
            "anim": {"obj": anim, "str": emoji_str(anim)},
            "ok":   {"obj": ok,   "str": emoji_str(ok)},
            "err":  {"obj": err,  "str": emoji_str(err)},
        }

    # -----------------------------------------------------------------------
    # Persist raw IDs so we can regenerate the patch without re-uploading
    # -----------------------------------------------------------------------
    raw = {
        icon: {
            "anim_id":  v["anim"]["obj"]["id"]  if v["anim"]["obj"] else None,
            "ok_id":    v["ok"]["obj"]["id"]    if v["ok"]["obj"]   else None,
            "err_id":   v["err"]["obj"]["id"]   if v["err"]["obj"]  else None,
            "anim_str": v["anim"]["str"],
            "ok_str":   v["ok"]["str"],
            "err_str":  v["err"]["str"],
        }
        for icon, v in results.items()
    }
    OUTPUT_JSON.write_text(json.dumps(raw, indent=2))
    print(f"\nSaved emoji IDs → {OUTPUT_JSON}\n")

    # -----------------------------------------------------------------------
    # Print the _TOOL_LABELS patch
    # -----------------------------------------------------------------------
    R = {icon: v for icon, v in results.items()}
    web    = R["Web"]
    lookup = R["Lookup"]
    brain  = R["Brain"]
    python = R["Python"]
    edit   = R["Edit"]
    db     = R["Database"]
    img    = R["Image"]
    folder = R["Folder"]

    patch = f'''
# ============================================================
# Paste this into chat_handler.py to replace _TOOL_LABELS
# ============================================================
_TOOL_LABELS = {{
    # Web
    'search_web':           ('{web["anim"]["str"]}',    'Searching web for **{{query}}**',            'Searched web for [{{query}}](<https://duckduckgo.com/?q={{query_encoded}}>)', '{web["ok"]["str"]}', '{web["err"]["str"]}'),
    'read_url':             ('{web["anim"]["str"]}',    'Reading `{{url}}`',                           'Read [{{url_short}}]({{url}})', '{web["ok"]["str"]}', '{web["err"]["str"]}'),
    'search_in_url':        ('{web["anim"]["str"]}',    'Searching `{{url}}` for **{{search_term}}**', 'Searched [{{url_short}}]({{url}}) for **{{search_term}}**', '{web["ok"]["str"]}', '{web["err"]["str"]}'),
    'extract_links':        ('{web["anim"]["str"]}',    'Extracting links from `{{url}}`',             'Extracted links from [{{url_short}}]({{url}})', '{web["ok"]["str"]}', '{web["err"]["str"]}'),
    'get_page_headings':    ('{web["anim"]["str"]}',    'Getting headings from `{{url}}`',             'Got headings from [{{url_short}}]({{url}})', '{web["ok"]["str"]}', '{web["err"]["str"]}'),
    # Quran / Lookup
    'lookup_quran_page':    ('{lookup["anim"]["str"]}', 'Looking up Quran page {{page}}',       'Looked up Quran page {{page}}', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'lookup_tafsir':        ('{lookup["anim"]["str"]}', 'Looking up tafsir for {{ayah}}',       'Looked up tafsir for {{ayah}}', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'show_quran_page':      ('{lookup["anim"]["str"]}', 'Fetching Quran page image',            'Fetched Quran page image', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_ayah_safe':        ('{lookup["anim"]["str"]}', 'Getting ayah {{surah}}:{{ayah}}',      'Got ayah {{surah}}:{{ayah}}', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_page_safe':        ('{lookup["anim"]["str"]}', 'Getting Quran page {{page}}',          'Got Quran page {{page}}', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'search_quran_safe':    ('{lookup["anim"]["str"]}', 'Searching Quran for **{{query}}**',    'Searched Quran for **{{query}}**', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    # Admin / DB
    'execute_sql':          ('{db["anim"]["str"]}',     'Searching database',                   'Searched database', '{db["ok"]["str"]}', '{db["err"]["str"]}'),
    'get_db_schema':        ('{db["anim"]["str"]}',     'Fetching database schema',             'Fetched database schema', '{db["ok"]["str"]}', '{db["err"]["str"]}'),
    'search_codebase':      ('{lookup["anim"]["str"]}', 'Searching codebase for **{{query}}**', 'Searched codebase for **{{query}}**', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'read_file':            ('{folder["anim"]["str"]}', 'Reading `{{filename}}`',               'Read `{{filename}}`', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'update_server_config': ('{edit["anim"]["str"]}',   'Updating `{{setting}}` → `{{value}}`', 'Updated `{{setting}}` → `{{value}}`', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    # User
    'get_my_stats':         ('{lookup["anim"]["str"]}', 'Fetching your stats',                  'Fetched your stats', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'set_my_streak_emoji':  ('{edit["anim"]["str"]}',   'Setting streak emoji to {{emoji}}',    'Set streak emoji to {{emoji}}', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    # Discord info
    'get_server_info':      ('{lookup["anim"]["str"]}', 'Fetching server info',                 'Fetched server info', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_member_info':      ('{lookup["anim"]["str"]}', 'Fetching member info',                 'Fetched member info', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_channel_info':     ('{lookup["anim"]["str"]}', 'Fetching channel info',                'Fetched channel info', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_role_info':        ('{lookup["anim"]["str"]}', 'Fetching role info',                   'Fetched role info', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_channels':         ('{lookup["anim"]["str"]}', 'Listing channels',                     'Listed channels', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'check_permissions':    ('{lookup["anim"]["str"]}', 'Checking permissions',                 'Checked permissions', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    # Discord actions
    'execute_discord_code': ('{edit["anim"]["str"]}',   'Preparing code execution',             'Code execution prepared', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    # User space / files
    'save_to_space':        ('{folder["anim"]["str"]}', 'Saving `{{filename}}` to your space',   'Saved `{{filename}}` to your space', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'read_from_space':      ('{folder["anim"]["str"]}', 'Reading `{{filename}}` from your space','Read `{{filename}}` from your space', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'list_space':           ('{folder["anim"]["str"]}', 'Listing your space',                    'Listed your space', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'get_space_info':       ('{folder["anim"]["str"]}', 'Getting space info',                    'Got space info', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'delete_from_space':    ('{folder["anim"]["str"]}', 'Deleting `{{filename}}` from your space','Deleted `{{filename}}` from your space', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'zip_files':            ('{folder["anim"]["str"]}', 'Zipping files',                         'Zipped files', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'unzip_file':           ('{folder["anim"]["str"]}', 'Unzipping `{{filename}}`',              'Unzipped `{{filename}}`', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'share_file':           ('{folder["anim"]["str"]}', 'Sharing `{{filename}}`',                'Shared `{{filename}}`', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'upload_attachment_to_space': ('{folder["anim"]["str"]}', 'Uploading attachment to your space', 'Uploaded attachment to your space', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'save_message_attachments':   ('{folder["anim"]["str"]}', 'Saving message attachments',         'Saved message attachments', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'extract_pdf_images':   ('{img["anim"]["str"]}',    'Extracting PDF images from `{{filename}}`', 'Extracted PDF images from `{{filename}}`', '{img["ok"]["str"]}', '{img["err"]["str"]}'),
    'analyze_image':        ('{img["anim"]["str"]}',    'Analyzing image',                       'Analyzed image', '{img["ok"]["str"]}', '{img["err"]["str"]}'),
    # Bot management
    'force_bot_status':     ('{edit["anim"]["str"]}',   'Setting bot status to **{{status}}**',  'Set bot status to **{{status}}**', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    'add_bot_status_option':('{edit["anim"]["str"]}',   'Adding status option',                  'Added status option', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    # Campaign  (announce icons will be added later)
    'create_campaign_tool': ('{edit["anim"]["str"]}',   'Creating campaign',                     'Created campaign', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    'send_campaign':        ('{edit["anim"]["str"]}',   'Sending campaign',                      'Sent campaign', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    'list_campaigns':       ('{lookup["anim"]["str"]}', 'Listing campaigns',                     'Listed campaigns', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'get_campaign_responses':('{lookup["anim"]["str"]}','Fetching campaign responses',            'Fetched campaign responses', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    'add_campaign_button':  ('{edit["anim"]["str"]}',   'Adding campaign button',                'Added campaign button', '{edit["ok"]["str"]}', '{edit["err"]["str"]}'),
    # CloudConvert
    'convert_file':         ('{folder["anim"]["str"]}', 'Converting file',                       'Converted file', '{folder["ok"]["str"]}', '{folder["err"]["str"]}'),
    'check_cloudconvert_status': ('{lookup["anim"]["str"]}', 'Checking conversion status',       'Checked conversion status', '{lookup["ok"]["str"]}', '{lookup["err"]["str"]}'),
    # Memory
    'remember_info':        ('{brain["anim"]["str"]}',  'Saving to memory',                      'Saved to memory', '{brain["ok"]["str"]}', '{brain["err"]["str"]}'),
    'get_my_memories':      ('{brain["anim"]["str"]}',  'Recalling memories',                    'Recalled memories', '{brain["ok"]["str"]}', '{brain["err"]["str"]}'),
    'forget_memory':        ('{brain["anim"]["str"]}',  'Deleting memory',                       'Deleted memory', '{brain["ok"]["str"]}', '{brain["err"]["str"]}'),
    # Sandbox
    'run_python_script':    ('{python["anim"]["str"]}', 'Running Python script',                 'Ran Python script', '{python["ok"]["str"]}', '{python["err"]["str"]}'),
}}
'''

    print("=" * 70)
    print(patch)
    print("=" * 70)
    print(f"\nDone! Also saved IDs to: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
