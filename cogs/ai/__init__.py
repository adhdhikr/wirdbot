import nextcord as discord
from nextcord.ext import commands
import google.generativeai as genai
import logging
import asyncio
import io
import time
import aiohttp
import traceback
from config import GEMINI_API_KEY, API_BASE_URL, MAX_TOOL_CALLS, TOOL_LOG_CHANNEL_ID
from database import db
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS, _execute_python_internal
from .views import CodeApprovalView, ContinueExecutionView
from .utils import safe_split_text, ScopedBot

logger = logging.getLogger(__name__)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            

            self.tools = ALL_TOOLS
            
            self.model = genai.GenerativeModel(
                model_name='gemini-3-flash-preview',
                tools=self.tools,
                system_instruction=SYSTEM_PROMPT
            )
            self.has_key = True
        else:
            self.has_key = False
            logger.warning("GEMINI_API_KEY not found. AI features disabled.")










    async def _execute_python_internal(self, code: str, ctx_data: dict) -> str:

        return await _execute_python_internal(self.bot, code, ctx_data)

    async def _send_image_to_channel(self, channel, page_number: int, mushaf_type: str = 'madani'):
        """Fetches image from internal API and sends as file."""
        url = f"{API_BASE_URL}/mushaf/{mushaf_type}/page/{int(page_number)}"
        logger.info(f"Fetching image from: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = io.BytesIO(await resp.read())
                        file = discord.File(data, filename=f"page_{page_number}.png")
                        await channel.send(content=f"**Page {page_number}** ({mushaf_type})", file=file)
                        return True
                    else:
                        logger.error(f"Failed to fetch image {url}: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Error sending image: {e}")
            return False

    async def _process_chat_response(self, chat_session, response, message: discord.Message, existing_message: discord.Message = None, tool_count: int = 0):
         """Process a single response from Gemini (Tool Call vs Text)"""
         try:

            if tool_count >= MAX_TOOL_CALLS:

                ctx = await self.bot.get_context(message)
                view = ContinueExecutionView(ctx, self, chat_session, response, message, existing_message)
                msg_txt = "Looks like I've been running for a long time, do you want to keep running?"
                
                if existing_message:
                     await existing_message.reply(msg_txt, view=view)
                else:
                     await message.reply(msg_txt, view=view)
                return None


            has_candidates = False
            try:
                if hasattr(response, 'candidates'):
                    has_candidates = len(response.candidates) > 0
            except Exception as e:
                logger.warning(f"Failed to inspect response candidates: {e}")

            if not has_candidates:
                if hasattr(response, 'prompt_feedback'):
                      logger.warning(f"Prompt Feedback: {response.prompt_feedback}")
                return "⚠️ Error: AI response was empty (No candidates)."


            parts = []
            try:
                candidate = response.candidates[0]
                if hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts
                else:
                    logger.warning("Candidate has no content.parts")
            except Exception as e:
                logger.error(f"Error accessing parts: {e}")
                return f"⚠️ Error processing AI response: {e}"

            tool_responses = [] 
            sent_message = existing_message
            accumulated_text = ""
            

            pending_execution = False
            pending_execution_code = ""
            

            for i, part in enumerate(parts):
                try:
                    text_val = part.text
                    if text_val:
                        accumulated_text += text_val
                except Exception:
                    pass # Maybe no text

                try:
                    fn = part.function_call
                except Exception:
                    fn = None
                
                if fn:

                    if accumulated_text.strip():
                        if sent_message:
                            formatted_content = sent_message.content + "\n" + accumulated_text
                            if len(formatted_content) < 2000:
                                sent_message = await sent_message.edit(content=formatted_content)
                            else:
                                    sent_message = await message.reply(accumulated_text)
                        else:
                            sent_message = await message.reply(accumulated_text)
                        accumulated_text = ""

                    fname = fn.name
                    fargs = dict(fn.args)


                    context_str = ""
                    if fname == 'read_file':
                        f = fargs.get('filename')
                        if f: context_str = f" (`{f}`)"
                    elif fname == 'search_codebase':
                        q = fargs.get('query')
                        if q: context_str = f" (`{q}`)"
                    elif fname == 'execute_python':
                        context_str = " (Code Execution)"
                    elif fname == 'lookup_quran_page':
                        p = fargs.get('page_number')
                        if p: context_str = f" (Page {p})"
                    elif fname == 'get_ayah':
                        s = fargs.get('surah')
                        a = fargs.get('ayah')
                        if s and a: context_str = f" ({s}:{a})"
                    elif fname == 'search_quran':
                        q = fargs.get('query')
                        if q: context_str = f" (`{q}`)"
                    elif fname == 'execute_sql':
                        q = fargs.get('query')
                        if q: context_str = " (SQL)"

                    logger.info(f"AI Calling Tool: {fname}{context_str}")
                    

                    status_line = f"\n-# 🛠️ Calling `{fname}`{context_str}..."
                    if sent_message:
                         try:
                            if len(sent_message.content) + len(status_line) < 2000:
                                sent_message = await sent_message.edit(content=sent_message.content + status_line)
                            else:
                                sent_message = await message.reply(status_line.strip())
                         except:
                            sent_message = await message.reply(status_line.strip())
                    else:
                         sent_message = await message.reply(status_line.strip())


                    tool_result = "Error: Unknown tool"
                    error_occurred = False
                    
                    start_time = time.time()
                    

                    if fname == 'execute_python':
                        is_owner = await self.bot.is_owner(message.author)
                        is_admin = message.author.guild_permissions.administrator if message.guild else False
                        
                        if is_owner or is_admin:
                             pending_execution = True
                             pending_execution_code = fargs.get('code', '')
                             continue # SKIP adding to tool_responses
                        else:
                             tool_result = "Only the Bot Owner or Admins can execute Python code."
                    



                    try:



                        
                        if fname == 'get_my_stats':
                            user_data = await db.get_user(message.author.id, message.guild.id)
                            if user_data:
                                 if user_data.get('registered'):
                                     tool_result = f"Stats for {message.author.display_name}:\n- Streak: {user_data.get('session_streak', 0)} 🔥\n- Longest: {user_data.get('longest_session_streak', 0)}\n- Emoji: {user_data.get('streak_emoji', '🔥')}"
                                 else:
                                     tool_result = "You are not registered! Tell them to use /register."
                            else:
                                 tool_result = "User not found in DB."

                        elif fname == 'set_my_streak_emoji':
                            emoji = fargs.get('emoji')
                            user_data = await db.get_user(message.author.id, message.guild.id)
                            if user_data and user_data.get('registered'):
                                await db.set_user_streak_emoji(message.author.id, message.guild.id, emoji)
                                tool_result = f"Updated streak emoji to {emoji}"
                            else:
                                tool_result = "User not registered."

                        elif fname == 'show_quran_page':

                            page_num = fargs.get('page_number')
                            mushaf = 'madani'
                            if message.guild:
                                    config = await db.get_guild_config(message.guild.id)
                                    if config and 'mushaf_type' in config:
                                        mushaf = config['mushaf_type']
                            success = await self._send_image_to_channel(message.channel, page_num, float(mushaf) if str(mushaf).isdigit() else str(mushaf))
                            if success:
                                tool_result = f"Successfully uploaded image of page {page_num}."
                            else:
                                tool_result = "Failed to fetch/upload image."
                                
                        elif fname == 'update_server_config':

                            if not message.guild:
                                tool_result = "This command must be used in a server."
                            elif not message.author.guild_permissions.administrator:
                                 tool_result = "Error: You need Administrator permissions."
                            else:


                                setting = fargs.get('setting')
                                value = fargs.get('value')
                                safe_map = {
                                    'mushaf_type': 'mushaf_type',
                                    'pages_per_day': 'pages_per_day',
                                    'channel_id': 'channel_id',
                                    'mosque_id': 'mosque_id', 
                                    'followup_on_completion': 'followup_on_completion',
                                    'wird_role_id': 'wird_role_id'
                                }
                                if setting not in safe_map:
                                    tool_result = f"Error: Setting '{setting}' is not allowed."
                                else:
                                    db_key = safe_map[setting]
                                    final_value = value
                                    try:
                                        if setting == 'pages_per_day':
                                            final_value = int(value)
                                            if not (1 <= final_value <= 20): raise ValueError("Pages must be 1-20")
                                        elif setting == 'channel_id' or setting == 'wird_role_id':
                                            import re
                                            if match := re.search(r'(\d+)', str(value)):
                                                final_value = int(match.group(1))
                                            else: raise ValueError("Invalid ID format")
                                        elif setting == 'followup_on_completion':
                                            final_value = 1 if str(value).lower() in ['true', '1', 'yes'] else 0
                                            
                                        kwargs = {db_key: final_value}
                                        await db.create_or_update_guild(message.guild.id, **kwargs)
                                        tool_result = f"✅ Successfully updated `{setting}` to `{final_value}`."
                                    except Exception as e:
                                        tool_result = f"Error updating config: {e}"

                        elif fname == 'execute_sql':

                            query = fargs.get('query', '').strip()
                            is_owner = await self.bot.is_owner(message.author)
                            is_admin = message.author.guild_permissions.administrator if message.guild else False
                            
                            if not (is_owner or is_admin):
                                tool_result = "❌ Error: Only Admins or Bot Owner can run SQL."
                            elif not query.upper().startswith("SELECT"):
                                tool_result = "❌ Error: Only SELECT queries are allowed."
                            elif ";" in query:
                                 tool_result = "❌ Error: Multiple statements (;) are not allowed."
                            elif is_admin and not is_owner:
                                if not message.guild:
                                    tool_result = "❌ Error: Admins must run this in a server."
                                elif str(message.guild.id) not in query:
                                    tool_result = f"❌ Error: Admin Safety Check Failed. Include `WHERE guild_id = {message.guild.id}`."
                                else:
                                    try:
                                        rows = await db.connection.execute_many(query)
                                        if not rows: tool_result = "No results found."
                                        else:

                                            if len(rows) > 20: rows = rows[:20]; footer = "\n... (Truncated)"
                                            else: footer = ""
                                            headers = rows[0].keys() if rows else []
                                            if headers:
                                                header_row = " | ".join(headers)
                                                sep_row = " | ".join(["---"] * len(headers))
                                                body = "\n".join([" | ".join(str(r[k]) for k in headers) for r in rows])
                                                tool_result = f"### SQL Result\n\n{header_row}\n{sep_row}\n{body}{footer}"
                                            else: tool_result = "Query executed. No rows returned."
                                    except Exception as e: tool_result = f"SQL Error: {e}"
                            else: # Owner
                                try:
                                    rows = await db.connection.execute_many(query)
                                    if not rows: tool_result = "No results found."
                                    else:
                                        res_str = ""
                                        for r in rows[:15]: res_str += str(dict(r)) + "\n"
                                        if len(rows) > 15: res_str += "... (Truncated)"
                                        tool_result = f"```\n{res_str}\n```"
                                except Exception as e: tool_result = f"SQL Error: {e}"

                        elif fname == 'read_file':

                            is_owner = await self.bot.is_owner(message.author)
                            is_admin = message.author.guild_permissions.administrator if message.guild else False
                            if not (is_owner or is_admin):
                                 tool_result = "❌ Error: You do not have permission to read files."
                            else:
                                from .tools import read_file # Import locally to avoid circular issues if any
                                tool_result = await read_file(**fargs)

                        elif fname == 'search_codebase':
                             is_owner = await self.bot.is_owner(message.author)
                             is_admin = message.author.guild_permissions.administrator if message.guild else False
                             if not (is_owner or is_admin):
                                  tool_result = "❌ Error: You do not have permission to search."
                             else:
                                  from .tools import search_codebase
                                  tool_result = await search_codebase(**fargs)

                        elif fname == 'get_db_schema':
                             is_owner = await self.bot.is_owner(message.author)
                             is_admin = message.author.guild_permissions.administrator if message.guild else False
                             if not (is_owner or is_admin):
                                  tool_result = "❌ Error: You do not have permission."
                             else:
                                  from .tools import get_db_schema
                                  tool_result = await get_db_schema()

                        else:

                            found_tool = False
                            for t in self.tools:
                                if t.__name__ == fname:
                                    found_tool = True
                                    tool_result = await t(**fargs)
                                    break
                            if not found_tool:
                                logger.warning(f"Tool {fname} not found in logic dispatch.")
                                tool_result = "Error: Tool not implemented in dispatcher."

                    except Exception as e:
                        tool_result = f"Error executing {fname}: {e}"
                        logger.error(f"Tool Execution Error ({fname}): {e}\n{traceback.format_exc()}")
                        error_occurred = True

                    logger.info(f"Tool {fname} executed. Result length: {len(str(tool_result))}")
                    duration = time.time() - start_time
                    

                    if sent_message:
                         try:
                            current_content = sent_message.content
                            call_marker = f"\n-# 🛠️ Calling `{fname}`{context_str}..."
                            if error_occurred: new_marker = f"\n-# ❌ Error Calling `{fname}`{context_str}"
                            else: new_marker = f"\n-# ✅ Called `{fname}`{context_str}"
                            
                            if call_marker in current_content:
                                new_content = current_content.replace(call_marker, new_marker)
                                sent_message = await sent_message.edit(content=new_content)
                            elif call_marker.strip() in current_content:
                                new_content = current_content.replace(call_marker.strip(), new_marker.strip())
                                sent_message = await sent_message.edit(content=new_content)
                            else:
                                sent_message = await sent_message.edit(content=current_content + " " + ("❌" if error_occurred else "✅"))
                         except Exception as e:
                            logger.error(f"Failed to update tool status: {e}")


                    
                    tool_responses.append(genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fname,
                            response={'result': str(tool_result)} 
                        )
                    ))
                    
                    tool_count += 1


            

            if accumulated_text.strip():
                if sent_message and len(sent_message.content) + len(accumulated_text) < 2000:

                     await sent_message.edit(content=sent_message.content + "\n" + accumulated_text)
                else:

                    chunks = safe_split_text(accumulated_text, 2000)
                    for i, chunk in enumerate(chunks):
                        if i == 0 and not sent_message: # First chunk is reply if no message sent yet
                             sent_message = await message.reply(chunk)
                        else:

                             sent_message = await message.channel.send(chunk)


            if pending_execution:
                ctx = await self.bot.get_context(message)
                view = CodeApprovalView(ctx, pending_execution_code, self, chat_session, message, other_tool_parts=tool_responses)
                
                proposal_text = f"🤖 **Code Proposal**\nReview required:"
                if sent_message:
                     await sent_message.edit(content=sent_message.content + "\n" + proposal_text, view=view)
                else:
                     sent_message = await message.reply(proposal_text, view=view)
                return None 


            if tool_responses:
                next_response = await chat_session.send_message_async(
                    genai.protos.Content(parts=tool_responses)
                )
                return await self._process_chat_response(chat_session, next_response, message, sent_message, tool_count=tool_count)

            return None 

         except Exception as e:
             logger.error(f"Process Response Error: {e}")
             return f"❌ Error: {e}"


    async def _process_chat_turn(self, chat_session, content, message: discord.Message):
        """Initial Trigger for the chat loop."""
        try:
            response = await chat_session.send_message_async(content)
            return await self._process_chat_response(chat_session, response, message)
        except Exception as e:
            logger.error(f"AI Turn Error: {e}")
            return f"❌ AI Error: {e}"

    async def _build_history(self, message: discord.Message) -> list:
        """
        Builds the chat history context with priority:
        1. Current Reply Chain (Limit 5)
        2. Recent Channel Messages (Limit ~50 to fill 4k chars)
        """
        
        reply_chain = []
        curr = message

        for _ in range(5):
            if not curr.reference or not curr.reference.resolved:
                break
            if isinstance(curr.reference.resolved, discord.Message):
                curr = curr.reference.resolved
                reply_chain.append(curr)
            else:
                break
        

        recent_msgs = []
        async for msg in message.channel.history(limit=50, before=message):
            if msg not in reply_chain and msg.id != message.id:
                recent_msgs.append(msg)
        
        recent_msgs.reverse() 
        reply_chain.reverse() 
        
        full_context_msgs = recent_msgs + reply_chain
        

        temp_history_parts = []
        limit = 4000
        
        for msg in full_context_msgs:
            role = "model" if msg.author.id == self.bot.user.id else "user"
            content = msg.content
            
            if msg.reference:
                try:
                    if msg.reference.resolved and isinstance(msg.reference.resolved, discord.Message):
                        ref_author = msg.reference.resolved.author.display_name
                        content = f"[Replying to {ref_author}] {content}"
                except: pass

            if role == "user":
                text = f"User {msg.author.display_name} ({msg.author.id}): {content}"
            else:
                text = content
                
            temp_history_parts.append({"role": role, "text": text})
        

        final_history = []
        current_chars = 0
        
        for part in reversed(temp_history_parts):
            slen = len(part['text'])
            if current_chars + slen > limit:
                break
            current_chars += slen
            final_history.append({"role": part['role'], "parts": [part['text']]})
            
        final_history.reverse() 
        return final_history

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.has_key or message.author.bot: return
        if not self.bot.user: return

        is_mention = self.bot.user in message.mentions
        is_reply = False
        if message.reference:
            if message.reference.resolved:
                if message.reference.resolved.author.id == self.bot.user.id:
                    is_reply = True
            else:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    if ref_msg.author.id == self.bot.user.id:
                        is_reply = True
                except: pass

        if not (is_mention or is_reply): return

        logger.info(f"AI Triggered by {message.author.display_name}: Mention={is_mention}, Reply={is_reply}")

        async with message.channel.typing():
            try:
                history = await self._build_history(message)
                chat = self.model.start_chat(history=history)
                
                user_msg = f"User {message.author.display_name} ({message.author.id}): {message.content}\n[System: THIS IS THE CURRENT MESSAGE. REPLY TO THIS.]"
                if await self.bot.is_owner(message.author):
                    user_msg += "\n[System: User IS Bot Owner]"
                elif message.author.guild_permissions.administrator:
                    user_msg += "\n[System: User IS Admin]"
                
                response_text = await self._process_chat_turn(chat, user_msg, message)
                



                
                if response_text:
                    chunks = safe_split_text(response_text, 2000)
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)
                            
            except Exception as e:
                logger.error(f"Error in AI handler: {e}")
                await message.reply("❌ Error processing request. Check logs.")

def setup(bot):
    bot.add_cog(AICog(bot))
