"""
apply_emojis.py
===============
Reads scripts/emoji_ids.json (produced by upload_emojis.py) and rewrites
the _TOOL_LABELS dict in cogs/ai/chat_handler.py in-place.

Usage (after running upload_emojis.py first):
    python scripts/apply_emojis.py
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT    = Path(__file__).parent.parent
JSON_PATH    = Path(__file__).parent / "emoji_ids.json"
HANDLER_PATH = REPO_ROOT / "cogs" / "ai" / "chat_handler.py"


def load_ids() -> dict:
    if not JSON_PATH.exists():
        sys.exit(f"ERROR: {JSON_PATH} not found – run upload_emojis.py first.")
    with JSON_PATH.open() as f:
        return json.load(f)


def build_labels(R: dict) -> str:
    """Return the full _TOOL_LABELS block as a string."""
    web    = R["Web"]
    lookup = R["Lookup"]
    brain  = R["Brain"]
    python = R["Python"]
    edit   = R["Edit"]
    db     = R["Database"]
    img    = R["Image"]
    folder = R["Folder"]

    def e(icon, key):
        return R[icon][key + "_str"]

    lines = [
        "_TOOL_LABELS = {",
        "    # Web",
        f"    'search_web':           ('{e('Web','anim')}', 'Searching web for **{{query}}**',            'Searched web for [{{query}}](<https://duckduckgo.com/?q={{query_encoded}}>)', '{e('Web','ok')}', '{e('Web','err')}'),",
        f"    'read_url':             ('{e('Web','anim')}', 'Reading `{{url}}`',                           'Read [{{url_short}}]({{url}})', '{e('Web','ok')}', '{e('Web','err')}'),",
        f"    'search_in_url':        ('{e('Web','anim')}', 'Searching `{{url}}` for **{{search_term}}**', 'Searched [{{url_short}}]({{url}}) for **{{search_term}}**', '{e('Web','ok')}', '{e('Web','err')}'),",
        f"    'extract_links':        ('{e('Web','anim')}', 'Extracting links from `{{url}}`',             'Extracted links from [{{url_short}}]({{url}})', '{e('Web','ok')}', '{e('Web','err')}'),",
        f"    'get_page_headings':    ('{e('Web','anim')}', 'Getting headings from `{{url}}`',             'Got headings from [{{url_short}}]({{url}})', '{e('Web','ok')}', '{e('Web','err')}'),",
        "    # Quran / Lookup",
        f"    'lookup_quran_page':    ('{e('Lookup','anim')}', 'Looking up Quran page {{page}}',       'Looked up Quran page {{page}}', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'lookup_tafsir':        ('{e('Lookup','anim')}', 'Looking up tafsir for {{ayah}}',       'Looked up tafsir for {{ayah}}', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'show_quran_page':      ('{e('Lookup','anim')}', 'Fetching Quran page image',            'Fetched Quran page image', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_ayah_safe':        ('{e('Lookup','anim')}', 'Getting ayah {{surah}}:{{ayah}}',      'Got ayah {{surah}}:{{ayah}}', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_page_safe':        ('{e('Lookup','anim')}', 'Getting Quran page {{page}}',          'Got Quran page {{page}}', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'search_quran_safe':    ('{e('Lookup','anim')}', 'Searching Quran for **{{query}}**',    'Searched Quran for **{{query}}**', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        "    # Admin / DB",
        f"    'execute_sql':          ('{e('Database','anim')}', 'Searching database',                   'Searched database', '{e('Database','ok')}', '{e('Database','err')}'),",
        f"    'get_db_schema':        ('{e('Database','anim')}', 'Fetching database schema',             'Fetched database schema', '{e('Database','ok')}', '{e('Database','err')}'),",
        f"    'search_codebase':      ('{e('Lookup','anim')}',   'Searching codebase for **{{query}}**', 'Searched codebase for **{{query}}**', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'read_file':            ('{e('Folder','anim')}',   'Reading `{{filename}}`',               'Read `{{filename}}`', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'update_server_config': ('{e('Edit','anim')}',     'Updating `{{setting}}` \u2192 `{{value}}`', 'Updated `{{setting}}` \u2192 `{{value}}`', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        "    # User",
        f"    'get_my_stats':         ('{e('Lookup','anim')}', 'Fetching your stats',                  'Fetched your stats', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'set_my_streak_emoji':  ('{e('Edit','anim')}',   'Setting streak emoji to {{emoji}}',    'Set streak emoji to {{emoji}}', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        "    # Discord info",
        f"    'get_server_info':      ('{e('Lookup','anim')}', 'Fetching server info',                 'Fetched server info', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_member_info':      ('{e('Lookup','anim')}', 'Fetching member info',                 'Fetched member info', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_channel_info':     ('{e('Lookup','anim')}', 'Fetching channel info',                'Fetched channel info', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_role_info':        ('{e('Lookup','anim')}', 'Fetching role info',                   'Fetched role info', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_channels':         ('{e('Lookup','anim')}', 'Listing channels',                     'Listed channels', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'check_permissions':    ('{e('Lookup','anim')}', 'Checking permissions',                 'Checked permissions', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        "    # Discord actions",
        f"    'execute_discord_code': ('{e('Edit','anim')}', 'Preparing code execution',               'Code execution prepared', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        "    # User space / files",
        f"    'save_to_space':        ('{e('Folder','anim')}', 'Saving `{{filename}}` to your space',   'Saved `{{filename}}` to your space', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'read_from_space':      ('{e('Folder','anim')}', 'Reading `{{filename}}` from your space','Read `{{filename}}` from your space', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'list_space':           ('{e('Folder','anim')}', 'Listing your space',                    'Listed your space', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'get_space_info':       ('{e('Folder','anim')}', 'Getting space info',                    'Got space info', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'delete_from_space':    ('{e('Folder','anim')}', 'Deleting `{{filename}}` from your space','Deleted `{{filename}}` from your space', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'zip_files':            ('{e('Folder','anim')}', 'Zipping files',                         'Zipped files', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'unzip_file':           ('{e('Folder','anim')}', 'Unzipping `{{filename}}`',              'Unzipped `{{filename}}`', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'share_file':           ('{e('Folder','anim')}', 'Sharing `{{filename}}`',                'Shared `{{filename}}`', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'upload_attachment_to_space': ('{e('Folder','anim')}', 'Uploading attachment to your space', 'Uploaded attachment to your space', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'save_message_attachments':   ('{e('Folder','anim')}', 'Saving message attachments',         'Saved message attachments', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'extract_pdf_images':   ('{e('Image','anim')}', 'Extracting PDF images from `{{filename}}`', 'Extracted PDF images from `{{filename}}`', '{e('Image','ok')}', '{e('Image','err')}'),",
        f"    'analyze_image':        ('{e('Image','anim')}', 'Analyzing image',                        'Analyzed image', '{e('Image','ok')}', '{e('Image','err')}'),",
        "    # Bot management",
        f"    'force_bot_status':     ('{e('Edit','anim')}', 'Setting bot status to **{{status}}**',   'Set bot status to **{{status}}**', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        f"    'add_bot_status_option':('{e('Edit','anim')}', 'Adding status option',                   'Added status option', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        "    # Campaign",
        f"    'create_campaign_tool': ('{e('Edit','anim')}',   'Creating campaign',                    'Created campaign', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        f"    'send_campaign':        ('{e('Edit','anim')}',   'Sending campaign',                     'Sent campaign', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        f"    'list_campaigns':       ('{e('Lookup','anim')}', 'Listing campaigns',                    'Listed campaigns', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'get_campaign_responses':('{e('Lookup','anim')}','Fetching campaign responses',           'Fetched campaign responses', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        f"    'add_campaign_button':  ('{e('Edit','anim')}',   'Adding campaign button',               'Added campaign button', '{e('Edit','ok')}', '{e('Edit','err')}'),",
        "    # CloudConvert",
        f"    'convert_file':         ('{e('Folder','anim')}', 'Converting file',                      'Converted file', '{e('Folder','ok')}', '{e('Folder','err')}'),",
        f"    'check_cloudconvert_status': ('{e('Lookup','anim')}', 'Checking conversion status',      'Checked conversion status', '{e('Lookup','ok')}', '{e('Lookup','err')}'),",
        "    # Memory",
        f"    'remember_info':        ('{e('Brain','anim')}', 'Saving to memory',                      'Saved to memory', '{e('Brain','ok')}', '{e('Brain','err')}'),",
        f"    'get_my_memories':      ('{e('Brain','anim')}', 'Recalling memories',                    'Recalled memories', '{e('Brain','ok')}', '{e('Brain','err')}'),",
        f"    'forget_memory':        ('{e('Brain','anim')}', 'Deleting memory',                       'Deleted memory', '{e('Brain','ok')}', '{e('Brain','err')}'),",
        "    # Sandbox",
        f"    'run_python_script':    ('{e('Python','anim')}', 'Running Python script',                'Ran Python script', '{e('Python','ok')}', '{e('Python','err')}'),",
        "}",
    ]
    return "\n".join(lines)


def patch_handler(new_block: str) -> None:
    src = HANDLER_PATH.read_text(encoding="utf-8")

    # Match from _TOOL_LABELS = { up to the closing }
    pattern = re.compile(
        r"_TOOL_LABELS\s*=\s*\{.*?^\}",
        re.DOTALL | re.MULTILINE,
    )
    if not pattern.search(src):
        sys.exit("ERROR: Could not locate _TOOL_LABELS block in chat_handler.py")

    new_src = pattern.sub(new_block, src, count=1)
    HANDLER_PATH.write_text(new_src, encoding="utf-8")
    print(f"Patched: {HANDLER_PATH}")


def main():
    print(f"Loading emoji IDs from {JSON_PATH} …")
    R = load_ids()
    new_block = build_labels(R)
    patch_handler(new_block)
    print("Done! Restart your bot to pick up the new emojis.")


if __name__ == "__main__":
    main()
