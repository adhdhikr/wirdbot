import asyncio
import inspect
import logging
import re
import traceback

import nextcord as discord
from google.genai import types

from config import MAX_TOOL_CALLS

from .utils import safe_split_text
from .views import CodeApprovalView, ContinueExecutionView, SandboxExecutionView

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-tool human-readable label builder
# Each entry: (emoji, in_progress_template, done_template[, success_emoji[, error_emoji]])
#   - emoji:            shown while the tool is running (in-progress line)
#   - in_progress_template: text while running, supports {arg} placeholders
#   - done_template:    text after completion, same placeholder support
#   - success_emoji:    (optional) replaces ✅ on success  — default: '✅'
#   - error_emoji:      (optional) replaces ❌ on failure  — default: '❌'
#
#   Placeholder helpers available in templates:
#     {url}           raw URL arg
#     {url_short}     URL truncated to 40 chars
#     {query}         query arg truncated to 40 chars
#     {query_encoded} URL-encoded query
#     {filename}, {search_term}, {page}, {ayah}, {surah}, {setting}, {value}, {status}, {emoji}
# ---------------------------------------------------------------------------
_TOOL_LABELS = {
    # Web
    'search_web':           ('<a:wirdWeb:1474554997583773796>',    'Searching web for **{query}**',            'Searched web for [{query}](<https://duckduckgo.com/?q={query_encoded}>)', '<:wirdWeb_ok:1474555004236071067>', '<:wirdWeb_err:1474555010535657619>'),
    'read_url':             ('<a:wirdWeb:1474554997583773796>',    'Reading `{url}`',                           'Read [{url_short}]({url})', '<:wirdWeb_ok:1474555004236071067>', '<:wirdWeb_err:1474555010535657619>'),
    'search_in_url':        ('<a:wirdWeb:1474554997583773796>',    'Searching `{url}` for **{search_term}**', 'Searched [{url_short}]({url}) for **{search_term}**', '<:wirdWeb_ok:1474555004236071067>', '<:wirdWeb_err:1474555010535657619>'),
    'extract_links':        ('<a:wirdWeb:1474554997583773796>',    'Extracting links from `{url}`',             'Extracted links from [{url_short}]({url})', '<:wirdWeb_ok:1474555004236071067>', '<:wirdWeb_err:1474555010535657619>'),
    'get_page_headings':    ('<a:wirdWeb:1474554997583773796>',    'Getting headings from `{url}`',             'Got headings from [{url_short}]({url})', '<:wirdWeb_ok:1474555004236071067>', '<:wirdWeb_err:1474555010535657619>'),
    # Quran / Lookup
    'lookup_quran_page':    ('<a:wirdLookup:1474555016701415548>', 'Looking up Quran page {page}',       'Looked up Quran page {page}', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'lookup_tafsir':        ('<a:wirdLookup:1474555016701415548>', 'Looking up tafsir for {ayah}',       'Looked up tafsir for {ayah}', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'show_quran_page':      ('<a:wirdLookup:1474555016701415548>', 'Fetching Quran page image',            'Fetched Quran page image', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_ayah_safe':        ('<a:wirdLookup:1474555016701415548>', 'Getting ayah {surah}:{ayah}',      'Got ayah {surah}:{ayah}', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_page_safe':        ('<a:wirdLookup:1474555016701415548>', 'Getting Quran page {page}',          'Got Quran page {page}', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'search_quran_safe':    ('<a:wirdLookup:1474555016701415548>', 'Searching Quran for **{query}**',    'Searched Quran for **{query}**', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    # Admin / DB
    'execute_sql':          ('<a:wirdDatabase:1474555098154664182>',     'Searching database',                   'Searched database', '<:wirdDatabase_ok:1474555104303644837>', '<:wirdDatabase_err:1474555110507020560>'),
    'get_db_schema':        ('<a:wirdDatabase:1474555098154664182>',     'Fetching database schema',             'Fetched database schema', '<:wirdDatabase_ok:1474555104303644837>', '<:wirdDatabase_err:1474555110507020560>'),
    'search_codebase':      ('<a:wirdLookup:1474555016701415548>', 'Searching codebase for **{query}**', 'Searched codebase for **{query}**', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'read_file':            ('<a:wirdFolder:1474555135031115891>', 'Reading `{filename}`',               'Read `{filename}`', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'update_server_config': ('<a:wirdEdit:1474555079947325440>',   'Updating `{setting}` → `{value}`', 'Updated `{setting}` → `{value}`', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    # User
    'get_my_stats':         ('<a:wirdLookup:1474555016701415548>', 'Fetching your stats',                  'Fetched your stats', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'set_my_streak_emoji':  ('<a:wirdEdit:1474555079947325440>',   'Setting streak emoji to {emoji}',    'Set streak emoji to {emoji}', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    # Discord info
    'get_server_info':      ('<a:wirdLookup:1474555016701415548>', 'Fetching server info',                 'Fetched server info', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_member_info':      ('<a:wirdLookup:1474555016701415548>', 'Fetching member info',                 'Fetched member info', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_channel_info':     ('<a:wirdLookup:1474555016701415548>', 'Fetching channel info',                'Fetched channel info', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_role_info':        ('<a:wirdLookup:1474555016701415548>', 'Fetching role info',                   'Fetched role info', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_channels':         ('<a:wirdLookup:1474555016701415548>', 'Listing channels',                     'Listed channels', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'check_permissions':    ('<a:wirdLookup:1474555016701415548>', 'Checking permissions',                 'Checked permissions', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    # Discord actions
    'execute_discord_code': ('<a:wirdEdit:1474555079947325440>',   'Preparing code execution',             'Code execution prepared', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    # User space / files
    'save_to_space':        ('<a:wirdFolder:1474555135031115891>', 'Saving `{filename}` to your space',   'Saved `{filename}` to your space', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'read_from_space':      ('<a:wirdFolder:1474555135031115891>', 'Reading `{filename}` from your space','Read `{filename}` from your space', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'list_space':           ('<a:wirdFolder:1474555135031115891>', 'Listing your space',                    'Listed your space', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'get_space_info':       ('<a:wirdFolder:1474555135031115891>', 'Getting space info',                    'Got space info', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'delete_from_space':    ('<a:wirdFolder:1474555135031115891>', 'Deleting `{filename}` from your space','Deleted `{filename}` from your space', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'zip_files':            ('<a:wirdFolder:1474555135031115891>', 'Zipping files',                         'Zipped files', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'unzip_file':           ('<a:wirdFolder:1474555135031115891>', 'Unzipping `{filename}`',              'Unzipped `{filename}`', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'share_file':           ('<a:wirdFolder:1474555135031115891>', 'Sharing `{filename}`',                'Shared `{filename}`', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'upload_attachment_to_space': ('<a:wirdFolder:1474555135031115891>', 'Uploading attachment to your space', 'Uploaded attachment to your space', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'save_message_attachments':   ('<a:wirdFolder:1474555135031115891>', 'Saving message attachments',         'Saved message attachments', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'extract_pdf_images':   ('<a:wirdImage:1474555116429512785>',    'Extracting PDF images from `{filename}`', 'Extracted PDF images from `{filename}`', '<:wirdImage_ok:1474555122544541801>', '<:wirdImage_err:1474555128999841792>'),
    'analyze_image':        ('<a:wirdImage:1474555116429512785>',    'Analyzing image',                       'Analyzed image', '<:wirdImage_ok:1474555122544541801>', '<:wirdImage_err:1474555128999841792>'),
    # Bot management
    'force_bot_status':     ('<a:wirdEdit:1474555079947325440>',   'Setting bot status to **{status}**',  'Set bot status to **{status}**', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    'add_bot_status_option':('<a:wirdEdit:1474555079947325440>',   'Adding status option',                  'Added status option', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    # Campaign  (announce icons will be added later)
    'create_campaign_tool': ('<a:wirdEdit:1474555079947325440>',   'Creating campaign',                     'Created campaign', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    'send_campaign':        ('<a:wirdEdit:1474555079947325440>',   'Sending campaign',                      'Sent campaign', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    'list_campaigns':       ('<a:wirdLookup:1474555016701415548>', 'Listing campaigns',                     'Listed campaigns', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'get_campaign_responses':('<a:wirdLookup:1474555016701415548>','Fetching campaign responses',            'Fetched campaign responses', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    'add_campaign_button':  ('<a:wirdEdit:1474555079947325440>',   'Adding campaign button',                'Added campaign button', '<:wirdEdit_ok:1474555085915816131>', '<:wirdEdit_err:1474555091934515381>'),
    # CloudConvert
    'convert_file':         ('<a:wirdFolder:1474555135031115891>', 'Converting file',                       'Converted file', '<:wirdFolder_ok:1474555141586813090>', '<:wirdFolder_err:1474555148087857336>'),
    'check_cloudconvert_status': ('<a:wirdLookup:1474555016701415548>', 'Checking conversion status',       'Checked conversion status', '<:wirdLookup_ok:1474555022984347863>', '<:wirdLookup_err:1474555029322072236>'),
    # Memory
    'remember_info':        ('<a:wirdBrain:1474555035982627059>',  'Saving to memory',                      'Saved to memory', '<:wirdBrain_ok:1474555043498823902>', '<:wirdBrain_err:1474555050230812924>'),
    'get_my_memories':      ('<a:wirdBrain:1474555035982627059>',  'Recalling memories',                    'Recalled memories', '<:wirdBrain_ok:1474555043498823902>', '<:wirdBrain_err:1474555050230812924>'),
    'forget_memory':        ('<a:wirdBrain:1474555035982627059>',  'Deleting memory',                       'Deleted memory', '<:wirdBrain_ok:1474555043498823902>', '<:wirdBrain_err:1474555050230812924>'),
    # Sandbox
    'run_python_script':    ('<a:wirdPython:1474555056446771293>', 'Running Python script',                 'Ran Python script', '<:wirdPython_ok:1474555066768687144>', '<:wirdPython_err:1474555073379045466>'),
}


def _get_tool_emojis(fname: str) -> tuple[str, str, str]:
    """
    Return (tool_emoji, success_emoji, error_emoji) for the given tool name.
    Falls back to ('🛠️', '✅', '❌') when the tool is unknown or the entry
    does not declare custom success/error emojis.
    """
    entry = _TOOL_LABELS.get(fname)
    if not entry:
        return ('🛠️', '✅', '❌')
    tool_emoji = entry[0]
    success_emoji = entry[3] if len(entry) > 3 else '✅'
    error_emoji   = entry[4] if len(entry) > 4 else '❌'
    return (tool_emoji, success_emoji, error_emoji)


def _format_tool_label(fname: str, fargs: dict, done: bool = False) -> str:
    """
    Build a human-readable label for a tool call.
    Returns just the label text (no emoji prefix, no leading newline).
    """
    entry = _TOOL_LABELS.get(fname)
    if not entry:
        # Fallback: use a cleaned-up version of the function name
        clean = fname.replace('_', ' ').title()
        return clean if done else f"Running {clean}"

    _tool_emoji, in_progress, done_tpl = entry[0], entry[1], entry[2]
    template = done_tpl if done else in_progress

    # Build substitution dict from fargs with smart truncation helpers
    url    = str(fargs.get('url', ''))
    query  = str(fargs.get('query', ''))
    try:
        import urllib.parse
        query_encoded = urllib.parse.quote_plus(query[:60])
    except Exception:
        query_encoded = query[:60]

    subs = dict(fargs)  # start with raw args
    subs['url']            = url
    subs['url_short']      = url[:40] + ('...' if len(url) > 40 else '')
    subs['query']          = query[:40] + ('...' if len(query) > 40 else '')
    subs['query_encoded']  = query_encoded
    subs.setdefault('filename',    '')
    subs.setdefault('search_term', '')
    subs.setdefault('page',        '')
    subs.setdefault('ayah',        '')
    subs.setdefault('surah',       '')
    subs.setdefault('setting',     '')
    subs.setdefault('value',       '')
    subs.setdefault('status',      '')
    subs.setdefault('emoji',       '')

    try:
        return template.format_map(subs)
    except Exception:
        return f"Called `{fname}`" if done else f"Calling `{fname}`"

def condense_tool_calls(content: str) -> str:
    """
    Collapse consecutive runs of the *exact same* completed tool line.
    e.g. three identical '✅ Searched web for X' lines in a row become
    '✅ Searched web for X ×3'.  Different tools or runs broken by text
    are left untouched.
    """
    lines = content.split('\n')
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Only try to collapse completed tool-status lines (any success/error emoji)
        is_tool_line = stripped.startswith('-#') and (' Error:' in stripped or (
            any(c for c in stripped if c not in ' \t-#' and c != '🛠' and ord(c) > 127)
            and not stripped.startswith('-# <')
            and '...' not in stripped
        ))
        if is_tool_line:
            # Count how many identical lines follow
            count = 1
            while i + count < len(lines) and lines[i + count].strip() == stripped:
                count += 1
            if count > 1:
                output.append(line.rstrip() + f' ×{count}')
            else:
                output.append(line)
            i += count
        else:
            output.append(line)
            i += 1
    return '\n'.join(output)

def strip_status(content: str) -> str:
    lines = content.split('\n')
    cleaned = [line for line in lines if not (
        '🧠 Thinking' in line or 'loading:' in line
    )]
    return '\n'.join(cleaned).strip()

def strip_hallucinated_subtext(text: str) -> str:
    """Remove any -# lines the model hallucinated (tool narration, fake status, etc.)."""
    lines = text.split('\n')
    cleaned = [line for line in lines if not line.strip().startswith('-#')]
    return '\n'.join(cleaned)

def finalize_content(content: str) -> str:
    content = strip_status(content)
    content = condense_tool_calls(content)
    return content.strip()

class ChatHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot

    async def process_chat_response(self, chat_session, response, message: discord.Message, existing_message: discord.Message = None, tool_count: int = 0, execution_logs: list = None, allowed_tool_names: set = None):
         """Process a single response from Gemini (Tool Call vs Text)"""
         if execution_logs is None:
             execution_logs = []
         try:
            if tool_count >= MAX_TOOL_CALLS:
                ctx = await self.bot.get_context(message)
                view = ContinueExecutionView(ctx, self.cog, chat_session, response, message, existing_message)
                msg_txt = "Looks like I've been running for a long time, do you want to keep running?"
                if existing_message:
                     await existing_message.reply(msg_txt, view=view)
                else:
                     await message.reply(msg_txt, view=view)
                return None
            
            if not response.candidates:
                return "⚠️ Error: AI response was empty (No candidates)."

            parts = []
            try:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    parts = candidate.content.parts
            except Exception as e:
                logger.error(f"Error accessing parts: {e}")
                return f"⚠️ Error processing AI response: {e}"

            tool_responses = [] 
            sent_message = existing_message
            accumulated_text = ""
            
            pending_execution = False
            pending_execution_code = ""

            for i, part in enumerate(parts):
                if part.text:
                    accumulated_text += strip_hallucinated_subtext(part.text)
                fn = part.function_call
                
                if fn:
                    if accumulated_text.strip():
                        chunks = safe_split_text(accumulated_text, 1900)
                        for idx, chunk in enumerate(chunks):
                            if idx == 0 and sent_message:
                                formatted_content = sent_message.content + "\n" + chunk
                                if len(formatted_content) < 2000:
                                    sent_message = await sent_message.edit(content=formatted_content)
                                else:
                                    sent_message = await message.reply(chunk)
                                    self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                            else:
                                sent_message = await message.reply(chunk)
                                self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                        accumulated_text = ""

                    fname = fn.name
                    fargs = fn.args
                    if not isinstance(fargs, dict):
                        try:
                            fargs = dict(fargs)
                        except Exception:
                            pass

                    logger.info(f"AI Calling Tool: {fname} args={list(fargs.keys())}")
                    in_progress_label = _format_tool_label(fname, fargs, done=False)
                    tool_emoji, success_emoji, error_emoji = _get_tool_emojis(fname)
                    status_line = f"\n-# {tool_emoji} {in_progress_label}..."
                    
                    if sent_message:
                         try:
                            content = sent_message.content
                            content = content.replace("-# 🧠 Thinking (Pro Model)...", "").strip()
                            content = re.sub(r"-# <a:loading:\d+> Generating\.\.\.", "", content).strip()

                            if len(content) + len(status_line) < 2000:
                                sent_message = await sent_message.edit(content=(content + status_line).strip())
                            else:
                                sent_message = await message.reply(status_line.strip())
                                self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                         except Exception:
                            sent_message = await message.reply(status_line.strip())
                            self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                    else:
                         sent_message = await message.reply(status_line.strip())
                         self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                    
                    tool_result = "Error: Unknown tool"
                    error_occurred = False

                    # Gate: reject any tool not in the per-message allowed set
                    if allowed_tool_names is not None and fname not in allowed_tool_names:
                        tool_result = f"❌ Permission Denied: Tool '{fname}' is not available to you."
                        tool_responses.append(types.Part.from_function_response(
                            name=fname,
                            response={'result': tool_result}
                        ))
                        logger.warning(f"Blocked out-of-scope tool call '{fname}' by {message.author} (not in allowed_tool_names)")
                        continue

                    if fname == 'execute_discord_code':
                         _is_owner = await self.bot.is_owner(message.author)
                         _is_admin = message.author.guild_permissions.administrator if message.guild else False
                         _whitelisted = message.guild.id in self.cog.execute_code_whitelist if message.guild else False
                         
                         if _is_owner or (_is_admin and _whitelisted):
                             pending_execution = True
                             pending_execution_code = fargs.get('code', '')
                         else:
                             # Permission denied — feed error back to model and keep going
                             tool_result = "❌ Permission Denied: execute_discord_code requires Bot Owner, or Server Admin in a whitelisted guild."
                             tool_responses.append(types.Part.from_function_response(
                                 name=fname,
                                 response={'result': tool_result}
                             ))
                             pending_execution = False
                    
                    elif fname in self.cog.tool_map:
                        func = self.cog.tool_map[fname]
                        ctx_kwargs = {
                            'bot': self.bot,
                            'guild': message.guild,
                            'guild_id': message.guild.id if message.guild else None,
                            'channel': message.channel,
                            'message': message,
                            'user_id': message.author.id,
                            'is_owner': await self.bot.is_owner(message.author),
                            'is_admin': message.author.guild_permissions.administrator if message.guild else False,
                            'model_name': getattr(chat_session, 'model_name', 'gemini-3-flash-preview'),
                            'cog': self.cog,
                            'whitelisted_guild': message.guild.id in self.cog.execute_code_whitelist if message.guild else False
                        }
                        
                        try:
                            sig = inspect.signature(func)
                            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                                tool_result = await func(**fargs, **ctx_kwargs)
                            else:
                                tool_result = await func(**fargs)
                                
                            if fname == 'run_python_script':
                                exec_index = len(execution_logs) + 1
                                execution_logs.append({
                                    'index': exec_index,
                                    'code': fargs.get('code', ''),
                                    'output': str(tool_result)
                                })
                                in_progress_label += f" [#{exec_index}]"
                                
                            if fname == 'share_file' and str(tool_result).startswith('__SHARE_FILE__:'):
                                parts_share = str(tool_result).split(':')
                                if len(parts_share) >= 3:
                                    share_filename = parts_share[1]
                                    try:
                                        from .tools.user_space import (
                                            get_file_for_discord,
                                        )
                                        file_data = await get_file_for_discord(share_filename, user_id=message.author.id)
                                        if file_data:
                                            file_buffer, filename = file_data
                                            discord_file = discord.File(file_buffer, filename=filename)
                                            await message.channel.send(f"📎 **{filename}**", file=discord_file)
                                            tool_result = f"✅ File `{filename}` sent successfully."
                                        else:
                                            tool_result = "❌ Failed to prepare file for sending."
                                    except Exception as e:
                                        logger.error(f"File sharing error: {e}")
                                        tool_result = f"❌ Error sending file: {e}"
                        except Exception as e:
                            tool_result = f"Error execution {fname}: {e}"
                            error_occurred = True
                            logger.error(f"Tool Error {fname}: {e}\\n{traceback.format_exc()}")
                    else:
                        tool_result = f"Error: Tool '{fname}' not found."
                        error_occurred = True

                    if not pending_execution:
                        if sent_message:
                             try:
                                current_content = sent_message.content
                                # Match the in-progress line we wrote earlier
                                in_progress_escaped = re.escape(_format_tool_label(fname, fargs, done=False))
                                tool_emoji_escaped = re.escape(tool_emoji)
                                pattern = r"(?:\n)?-#\s*" + tool_emoji_escaped + r"\s*" + in_progress_escaped + r"\.\.\."    
                                done_label = _format_tool_label(fname, fargs, done=True)
                                if re.search(pattern, current_content):
                                    prefix = f'{error_emoji} Error: ' if error_occurred else f'{success_emoji} '
                                    new_marker = f"\n-# {prefix}{done_label}"
                                    new_content = re.sub(pattern, new_marker, current_content, count=1)
                                    match = re.search(pattern, current_content)
                                    if match.start() == 0:
                                        new_content = new_content.lstrip()

                                    view = SandboxExecutionView(execution_logs) if execution_logs else None
                                    sent_message = await sent_message.edit(content=new_content, view=view)
                                else:
                                    view = SandboxExecutionView(execution_logs) if execution_logs else None
                                    sent_message = await sent_message.edit(content=current_content + " " + (error_emoji if error_occurred else success_emoji), view=view)
                             except Exception as e:
                                logger.error(f"Failed to update tool status: {e}")
                        tool_responses.append(types.Part.from_function_response(
                            name=fname,
                            response={'result': str(tool_result)} 
                        ))

            if pending_execution:
                ctx = await self.bot.get_context(message)
                view = CodeApprovalView(ctx, pending_execution_code, self.cog, chat_session, message, other_tool_parts=tool_responses)
                self.cog.pending_approvals[message.channel.id] = view
                
                proposal_text = "🤖 **Code Proposal**\nReview required for server action:"
                if sent_message:
                     await sent_message.edit(content=sent_message.content + "\n" + proposal_text, view=view)
                else:
                     sent_message = await message.reply(proposal_text, view=view)
                return None 


            if tool_responses:
                 if accumulated_text.strip():
                    chunks = safe_split_text(accumulated_text, 1900)
                    for idx, chunk in enumerate(chunks):
                        if idx == 0 and sent_message:
                             content = sent_message.content
                             if len(content) + len(chunk) < 2000:
                                 try:
                                     sent_message = await sent_message.edit(content=content + "\n" + chunk)
                                 except Exception:
                                     sent_message = await message.reply(chunk)
                                     self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                             else:
                                 sent_message = await message.reply(chunk)
                                 self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                        else:
                             sent_message = await message.reply(chunk)
                             self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                    accumulated_text = ""
                 if getattr(chat_session, 'is_pro_model', False):
                     if sent_message:
                         current_content = sent_message.content
                         loading_pattern = r"-# <a:loading:\d+> Generating\.\.\."
                         if re.search(loading_pattern, current_content):
                             new_content = re.sub(loading_pattern, "-# 🧠 Thinking (Pro Model)...", current_content)
                             sent_message = await sent_message.edit(content=new_content)
                         elif "-# 🧠 Thinking (Pro Model)..." not in current_content:
                             sent_message = await sent_message.edit(content=current_content + "\n-# 🧠 Thinking (Pro Model)...")
                     else:
                         sent_message = await message.reply("-# 🧠 Thinking (Pro Model)...")
                 next_response = await chat_session.send_message(tool_responses)
                 return await self.process_chat_response(chat_session, next_response, message, sent_message, tool_count=tool_count+1, execution_logs=execution_logs, allowed_tool_names=allowed_tool_names)
            
            if accumulated_text.strip():
                if getattr(chat_session, 'is_pro_model', False):
                    header = "**Using pro model 🧠**\n\n"
                    if not accumulated_text.startswith(header):
                        accumulated_text = header + accumulated_text
                view = SandboxExecutionView(execution_logs) if execution_logs else None

                if sent_message and len(sent_message.content) + len(accumulated_text) < 2000:
                     final_content = finalize_content(sent_message.content)
                     await sent_message.edit(content=(final_content + "\n" + accumulated_text).strip() if final_content else accumulated_text, view=view)
                else:
                    chunks = safe_split_text(accumulated_text, 1900)
                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            if sent_message:
                                final_content = finalize_content(sent_message.content)
                                combined = (final_content + "\n" + chunk).strip() if final_content else chunk
                                if len(combined) < 2000:
                                    await sent_message.edit(content=combined)
                                else:
                                    await sent_message.edit(content=chunk)
                            else:
                                sent_message = await message.reply(chunk)
                                self.cog.active_tasks[sent_message.id] = asyncio.current_task()
                        else:
                            msg_chunk = await message.channel.send(chunk)
                            self.cog.active_tasks[msg_chunk.id] = asyncio.current_task()
                            if idx == len(chunks) - 1 and view:
                                await msg_chunk.edit(view=view)
                    if len(chunks) == 1 and sent_message and view:
                        await sent_message.edit(view=view)
            return None 

         except asyncio.CancelledError:
             logger.info("AI response generation cancelled.")
             try:
                 if sent_message:
                     await sent_message.edit(content=sent_message.content + " [Interrupted 🛑]")
             except Exception:
                 pass
             raise 
         except Exception as e:
             logger.error(f"Process Response Error: {e}")
             traceback.print_exc()
             return f"❌ Error: {e}"

    async def process_chat_turn(self, chat_session, content, message: discord.Message, sent_message=None, allowed_tool_names: set = None):
        """Initial Trigger for the chat loop."""
        try:
            response = await chat_session.send_message(content)
            return await self.process_chat_response(chat_session, response, message, existing_message=sent_message, execution_logs=[], allowed_tool_names=allowed_tool_names)
        except Exception as e:
            logger.error(f"AI Turn Error: {e}")
            if sent_message:
                try:
                    await sent_message.edit(content=f"❌ AI Error: {e}")
                except Exception:
                    pass
            else:
                 try:
                     await message.reply(f"❌ AI Error: {e}")
                 except Exception:
                     pass
            return f"❌ AI Error: {e}"
