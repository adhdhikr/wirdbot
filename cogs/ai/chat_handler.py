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

def condense_tool_calls(content: str) -> str:
    """Condense multiple tool call lines into a summary."""
    lines = content.split('\n')
    tool_lines = []
    other_lines = []
    
    for line in lines:
        if line.strip().startswith('-#') and ('✅ Called' in line or '❌ Error' in line):
            tool_lines.append(line)
        else:
            other_lines.append(line)
    
    if len(tool_lines) <= 2:
        return content
        
    from collections import Counter
    tool_counts = Counter()
    errors = []
    
    for line in tool_lines:
        match = re.search(r'`([^`]+)`', line)
        if match:
            tool_name = match.group(1)
            if '❌ Error' in line:
                errors.append(tool_name)
            else:
                tool_counts[tool_name] += 1
                
    parts = []
    for tool, count in tool_counts.items():
        if count > 1:
            parts.append(f"`{tool}` ×{count}")
        else:
            parts.append(f"`{tool}`")
    for err_tool in errors:
        parts.append(f"❌`{err_tool}`")
    
    if parts:
        condensed = "-# 🛠️ " + ", ".join(parts)
        return '\n'.join(other_lines + [condensed])
    
    return '\n'.join(other_lines)

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

                    arg_str = ""
                    if 'query' in fargs:
                        arg_str = f" \"{fargs['query'][:30]}{'...' if len(fargs['query'])>30 else ''}\""
                    elif 'url' in fargs:
                        arg_str = f" ({fargs['url'][:40]}{'...' if len(fargs['url'])>40 else ''})"
                    elif 'code' in fargs:
                        arg_str = " (code)"
                    
                    logger.info(f"AI Calling Tool: {fname}{arg_str}")
                    status_line = f"\n-# 🛠️ Calling `{fname}`{arg_str}..."
                    
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
                                pattern = r"(?:\n)?-#\s*🛠️\s*Calling\s*`" + re.escape(fname) + r"`.*?\.\.\."
                                if re.search(pattern, current_content):
                                    new_marker = f"\n-# {'❌ Error' if error_occurred else '✅ Called'} `{fname}`{arg_str}"
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
