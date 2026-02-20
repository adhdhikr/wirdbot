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
# Each entry: (emoji, in_progress_template, done_template)
#   Templates support {arg} placeholders drawn from fargs.
#   '~q30' means: the 'query' arg, truncated to 30 chars.
#   '~u40' means: the 'url'   arg, truncated to 40 chars.
#   '~f'   means: the 'filename' arg.
# ---------------------------------------------------------------------------
_TOOL_LABELS = {
    # Web
    'search_web':           ('🛠️', 'Searching web for **{query}**', 'Searched web for [{query}](<https://duckduckgo.com/?q={query_encoded}>)'),
    'read_url':             ('🛠️', 'Reading `{url}`', 'Read [{url_short}]({url})'),
    'search_in_url':        ('🛠️', 'Searching `{url}` for **{search_term}**', 'Searched [{url_short}]({url}) for **{search_term}**'),
    'extract_links':        ('🛠️', 'Extracting links from `{url}`', 'Extracted links from [{url_short}]({url})'),
    'get_page_headings':    ('🛠️', 'Getting headings from `{url}`', 'Got headings from [{url_short}]({url})'),
    # Quran
    'lookup_quran_page':    ('🛠️', 'Looking up Quran page {page}', 'Looked up Quran page {page}'),
    'lookup_tafsir':        ('🛠️', 'Looking up tafsir for {ayah}', 'Looked up tafsir for {ayah}'),
    'show_quran_page':      ('🛠️', 'Fetching Quran page image', 'Fetched Quran page image'),
    'get_ayah_safe':        ('🛠️', 'Getting ayah {surah}:{ayah}', 'Got ayah {surah}:{ayah}'),
    'get_page_safe':        ('🛠️', 'Getting Quran page {page}', 'Got Quran page {page}'),
    'search_quran_safe':    ('🛠️', 'Searching Quran for **{query}**', 'Searched Quran for **{query}**'),
    # Admin / DB
    'execute_sql':          ('🛠️', 'Searching database', 'Searched database'),
    'get_db_schema':        ('🛠️', 'Fetching database schema', 'Fetched database schema'),
    'search_codebase':      ('🛠️', 'Searching codebase for **{query}**', 'Searched codebase for **{query}**'),
    'read_file':            ('🛠️', 'Reading `{filename}`', 'Read `{filename}`'),
    'update_server_config': ('🛠️', 'Updating `{setting}` → `{value}`', 'Updated `{setting}` → `{value}`'),
    # User
    'get_my_stats':         ('🛠️', 'Fetching your stats', 'Fetched your stats'),
    'set_my_streak_emoji':  ('🛠️', 'Setting streak emoji to {emoji}', 'Set streak emoji to {emoji}'),
    # Discord info
    'get_server_info':      ('🛠️', 'Fetching server info', 'Fetched server info'),
    'get_member_info':      ('🛠️', 'Fetching member info', 'Fetched member info'),
    'get_channel_info':     ('🛠️', 'Fetching channel info', 'Fetched channel info'),
    'get_role_info':        ('🛠️', 'Fetching role info', 'Fetched role info'),
    'get_channels':         ('🛠️', 'Listing channels', 'Listed channels'),
    'check_permissions':    ('🛠️', 'Checking permissions', 'Checked permissions'),
    # Discord actions
    'execute_discord_code': ('🛠️', 'Preparing code execution', 'Code execution prepared'),
    # User space / files
    'save_to_space':        ('🛠️', 'Saving `{filename}` to your space', 'Saved `{filename}` to your space'),
    'read_from_space':      ('🛠️', 'Reading `{filename}` from your space', 'Read `{filename}` from your space'),
    'list_space':           ('🛠️', 'Listing your space', 'Listed your space'),
    'get_space_info':       ('🛠️', 'Getting space info', 'Got space info'),
    'delete_from_space':    ('🛠️', 'Deleting `{filename}` from your space', 'Deleted `{filename}` from your space'),
    'zip_files':            ('🛠️', 'Zipping files', 'Zipped files'),
    'unzip_file':           ('🛠️', 'Unzipping `{filename}`', 'Unzipped `{filename}`'),
    'share_file':           ('🛠️', 'Sharing `{filename}`', 'Shared `{filename}`'),
    'upload_attachment_to_space': ('🛠️', 'Uploading attachment to your space', 'Uploaded attachment to your space'),
    'save_message_attachments':   ('🛠️', 'Saving message attachments', 'Saved message attachments'),
    'extract_pdf_images':   ('🛠️', 'Extracting PDF images from `{filename}`', 'Extracted PDF images from `{filename}`'),
    'analyze_image':        ('🛠️', 'Analyzing image', 'Analyzed image'),
    # Vision
    # Bot management
    'force_bot_status':     ('🛠️', 'Setting bot status to **{status}**', 'Set bot status to **{status}**'),
    'add_bot_status_option':('🛠️', 'Adding status option', 'Added status option'),
    # Campaign
    'create_campaign_tool': ('🛠️', 'Creating campaign', 'Created campaign'),
    'send_campaign':        ('🛠️', 'Sending campaign', 'Sent campaign'),
    'list_campaigns':       ('🛠️', 'Listing campaigns', 'Listed campaigns'),
    'get_campaign_responses':('🛠️', 'Fetching campaign responses', 'Fetched campaign responses'),
    'add_campaign_button':  ('🛠️', 'Adding campaign button', 'Added campaign button'),
    # CloudConvert
    'convert_file':         ('🛠️', 'Converting file', 'Converted file'),
    'check_cloudconvert_status': ('🛠️', 'Checking conversion status', 'Checked conversion status'),
    # Memory
}


def _format_tool_label(fname: str, fargs: dict, done: bool = False) -> str:
    """
    Build a human-readable label for a tool call.
    Returns just the label text (no emoji prefix, no leading newline).
    """
    entry = _TOOL_LABELS.get(fname)
    if not entry:
        # Fallback: plain function name as code span
        return f"Called `{fname}`" if done else f"Calling `{fname}`"

    emoji, in_progress, done_tpl = entry
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
        # Only try to collapse completed (✅ / ❌) tool-status lines
        is_tool_line = stripped.startswith('-#') and ('✅ ' in stripped or '❌ Error:' in stripped)
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
                    accumulated_text += part.text
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
                    status_line = f"\n-# 🛠️ {in_progress_label}..."
                    
                    if sent_message:
                         try:
                            content = sent_message.content
                            content = content.replace("-# 🧠 Thinking (Pro Model)...", "").strip()

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
                                arg_str += f" [#{exec_index}]"
                                
                            if fname == 'share_file' and str(tool_result).startswith('__SHARE_FILE__:'):
                                parts_share = str(tool_result).split(':')
                                if len(parts_share) >= 3:
                                    share_filename = parts_share[1]
                                    try:
                                        from .tools.user_space import get_file_for_discord
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
                                pattern = r"(?:\n)?-#\s*🛠️\s*" + in_progress_escaped + r"\.\.\."
                                done_label = _format_tool_label(fname, fargs, done=True)
                                if re.search(pattern, current_content):
                                    prefix = '❌ Error: ' if error_occurred else '✅ '
                                    new_marker = f"\n-# {prefix}{done_label}"
                                    new_content = re.sub(pattern, new_marker, current_content, count=1)
                                    match = re.search(pattern, current_content)
                                    if match.start() == 0:
                                        new_content = new_content.lstrip()

                                    view = SandboxExecutionView(execution_logs) if execution_logs else None
                                    sent_message = await sent_message.edit(content=new_content, view=view)
                                else:
                                    view = SandboxExecutionView(execution_logs) if execution_logs else None
                                    sent_message = await sent_message.edit(content=current_content + " " + ("❌" if error_occurred else "✅"), view=view)
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
