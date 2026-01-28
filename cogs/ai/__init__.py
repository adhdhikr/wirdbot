import nextcord as discord
from nextcord.ext import commands

from google import genai
from google.genai import types
import logging
import asyncio
import io
import time
import inspect
import traceback
import re
from config import GEMINI_API_KEY, API_BASE_URL, MAX_TOOL_CALLS, TOOL_LOG_CHANNEL_ID
from database import db
from .prompts import SYSTEM_PROMPT
from .views import CodeApprovalView, ContinueExecutionView, SandboxExecutionView
from .utils import safe_split_text, ScopedBot

# Import tools from the new package
from .tools import CUSTOM_TOOLS, execute_discord_code, analyze_image
from .router import evaluate_complexity, SIMPLE_MODEL, COMPLEX_MODEL

logger = logging.getLogger(__name__)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tasks = {} # Map channel_id -> asyncio.Task
        self.chat_histories = {} # Map channel_id -> list[types.Content]
        self.context_pruning_markers = {} # Map channel_id -> message_id (ignore msgs before this)
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            self.has_key = True
            
            # Map tool names to functions for easy dispatch
            self.tool_map = {func.__name__: func for func in CUSTOM_TOOLS}
            
            # Prepare Tools configuration
            # Mix Python functions (Client-side) and Gemini Capabilities (Server-side)
            self.all_tools = list(CUSTOM_TOOLS)
            
            # Mix Python functions (Client-side) and Gemini Capabilities (Server-side)
            self.all_tools = list(CUSTOM_TOOLS)
            
            # NOTE: Gemini 3 Flash Preview DOES NOT support mixing Custom Tools with Google Search/Code Execution.
            # We disable built-in skills to ensure Custom Tools (Discord Actions) work.
            # self.all_tools.append(types.Tool(
            #     google_search=types.GoogleSearch(),
            #     code_execution=types.ToolCodeExecution()
            # ))

        else:
            self.has_key = False
            logger.warning("GEMINI_API_KEY not found. AI features disabled.")

    async def _process_chat_response(self, chat_session, response, message: discord.Message, existing_message: discord.Message = None, tool_count: int = 0, execution_logs: list = None):
         """Process a single response from Gemini (Tool Call vs Text)"""
         if execution_logs is None:
             execution_logs = []
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

            # New SDK Response Structure
            has_candidates = False
            if response.candidates:
                has_candidates = True
            
            if not has_candidates:
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
                # 1. Handle Text
                if part.text:
                    accumulated_text += part.text

                # 2. Handle Built-in Code Execution (Executable Code)
                if part.executable_code:
                    logger.info("Received executable_code from Gemini (Built-in).")
                
                # 3. Handle Code Execution Result (Output from Built-in Sandbox)
                if part.code_execution_result:
                    pass

                # 4. Handle Function Calls (Client-side Custom Tools)
                fn = part.function_call
                
                if fn:
                    # Flush accumulated text before running tool
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
                    fargs = fn.args
                    if not isinstance(fargs, dict):
                         try:
                             fargs = dict(fargs)
                         except:
                             pass

                    # Format args for display
                    arg_str = ""
                    if 'query' in fargs: arg_str = f" \"{fargs['query'][:30]}{'...' if len(fargs['query'])>30 else ''}\""
                    elif 'url' in fargs: arg_str = f" ({fargs['url'][:40]}{'...' if len(fargs['url'])>40 else ''})"
                    elif 'code' in fargs: arg_str = " (code)"
                    
                    logger.info(f"AI Calling Tool: {fname}{arg_str}")
                    status_line = f"\n-# 🛠️ Calling `{fname}`{arg_str}..."
                    
                    if sent_message:
                         try:
                            # Clear "Thinking" status if present
                            content = sent_message.content
                            content = content.replace("-# 🧠 Thinking (Pro Model)...", "").strip()

                            if len(content) + len(status_line) < 2000:
                                sent_message = await sent_message.edit(content=(content + status_line).strip())
                            else:
                                sent_message = await message.reply(status_line.strip())
                         except:
                            sent_message = await message.reply(status_line.strip())
                    else:
                         sent_message = await message.reply(status_line.strip())

                    # --- TOOL EXECUTION LOGIC ---
                    tool_result = "Error: Unknown tool"
                    error_occurred = False
                    start_time = time.time()
                    
                    if fname == 'execute_discord_code':
                         pending_execution = True
                         pending_execution_code = fargs.get('code', '')
                         pass 
                    
                    elif fname in self.tool_map:
                        func = self.tool_map[fname]
                        
                        ctx_kwargs = {
                            'bot': self.bot,
                            'guild_id': message.guild.id if message.guild else None,
                            'user_id': message.author.id,
                            'channel': message.channel,
                            'message': message,
                            'user_id': message.author.id,
                            'channel': message.channel,
                            'message': message,
                            'is_owner': await self.bot.is_owner(message.author),
                            'model_name': getattr(chat_session, 'model_name', 'gemini-3-flash-preview'),
                            'cog': self 
                        }
                        
                        try:
                            sig = inspect.signature(func)
                            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                                tool_result = await func(**fargs, **ctx_kwargs)
                            else:
                                tool_result = await func(**fargs)
                                
                            # --- LOG SANDBOX EXECUTION ---
                            if fname == 'run_python_script':
                                exec_index = len(execution_logs) + 1
                                execution_logs.append({
                                    'index': exec_index,
                                    'code': fargs.get('code', ''),
                                    'output': str(tool_result)
                                })
                                arg_str += f" [#{exec_index}]"
                                
                        except Exception as e:
                            tool_result = f"Error execution {fname}: {e}"
                            error_occurred = True
                            logger.error(f"Tool Error {fname}: {e}\n{traceback.format_exc()}")
                    else:
                        tool_result = f"Error: Tool '{fname}' not found."
                        error_occurred = True

                    if not pending_execution:
                        duration = time.time() - start_time
                        if sent_message:
                             try:
                                current_content = sent_message.content
                                # Use Regex for robust replacement of the status line
                                # Pattern matches: optional newline + -# + space + hammer + Calling + `fname` + anything + ...
                                pattern = r"(?:\n)?-#\s*🛠️\s*Calling\s*`" + re.escape(fname) + r"`.*?\.\.\."
                                
                                # Check if present
                                if re.search(pattern, current_content):
                                    # We keep the arg string in the final output too? Or simplify?
                                    # User wants info, so let's keep it.
                                    # But we need to capture what was matched or regenerate arg_str?
                                    # arg_str is available here.
                                    new_marker = f"\n-# {'❌ Error' if error_occurred else '✅ Called'} `{fname}`{arg_str}"
                                    # If it was the first line (no newline originally), strip the newline from replacement if needed
                                    # But usually keeping the newline is safer for formatting. 
                                    # Let's just sub.
                                    new_content = re.sub(pattern, new_marker, current_content, count=1)
                                    # If the original didn't have a newline and we added one, it might look weird?
                                    # If the match started at index 0, we probably want to strip the leading newline of new_marker.
                                    match = re.search(pattern, current_content)
                                    if match.start() == 0:
                                        new_content = new_content.lstrip()
                                        
                                    view = SandboxExecutionView(execution_logs) if execution_logs else None
                                    sent_message = await sent_message.edit(content=new_content, view=view)
                                else:
                                    # Fallback
                                    view = SandboxExecutionView(execution_logs) if execution_logs else None
                                    sent_message = await sent_message.edit(content=current_content + " " + ("❌" if error_occurred else "✅"), view=view)
                             except Exception as e:
                                logger.error(f"Failed to update tool status: {e}")

                        # Append result to response list
                        tool_responses.append(types.Part.from_function_response(
                            name=fname,
                            response={'result': str(tool_result)} 
                        ))
            
            # End of parts loop

            if pending_execution:
                ctx = await self.bot.get_context(message)
                view = CodeApprovalView(ctx, pending_execution_code, self, chat_session, message, other_tool_parts=tool_responses)
                
                proposal_text = f"🤖 **Code Proposal**\nReview required for server action:"
                if sent_message:
                     await sent_message.edit(content=sent_message.content + "\n" + proposal_text, view=view)
                else:
                     sent_message = await message.reply(proposal_text, view=view)
                return None 


            if tool_responses:
                 # Show Thinking status again before sending tool results if it's the Pro model
                 if getattr(chat_session, 'is_pro_model', False):
                     status_text = "\n-# 🧠 Thinking (Pro Model)..."
                     if sent_message:
                         if "-# 🧠 Thinking (Pro Model)..." not in sent_message.content:
                             sent_message = await sent_message.edit(content=sent_message.content + status_text)
                     else:
                         sent_message = await message.reply(status_text)

                 # Send tool outputs back to model
                 next_response = await chat_session.send_message(
                     tool_responses 
                 )
                 return await self._process_chat_response(chat_session, next_response, message, sent_message, tool_count=tool_count, execution_logs=execution_logs)
            
            if accumulated_text.strip():
                # Prep Pro Model Header if applicable
                if getattr(chat_session, 'is_pro_model', False):
                    # Check if we need to prepend or if it's already there
                    header = "**Using pro model 🧠**\n\n"
                    if not accumulated_text.startswith(header):
                        accumulated_text = header + accumulated_text

                # --- ATTACH SANDBOX UI ---
                view = SandboxExecutionView(execution_logs) if execution_logs else None

                if sent_message and len(sent_message.content) + len(accumulated_text) < 2000:
                     # Clear "Thinking" status if present
                     final_content = sent_message.content.replace("-# 🧠 Thinking (Pro Model)...", "").strip()
                     await sent_message.edit(content=(final_content + "\n" + accumulated_text).strip(), view=view)
                else:
                    chunks = safe_split_text(accumulated_text, 2000)
                    for i, chunk in enumerate(chunks):
                        if i == 0 and not sent_message:
                             sent_message = await message.reply(chunk, view=view)
                        elif i == len(chunks) - 1:
                             # Attach view to last chunk? Or first? User usually expects it at the end of the text that referenced it.
                             # But if we have multiple chunks, putting it on the first one (reply) is better for threading.
                             # Actually the user prompt said "to that message", and we edit the tool-call message.
                             # So putting it on sent_message (which contains tool calls) is correct.
                             if sent_message:
                                  await sent_message.edit(view=view)
                             else:
                                  sent_message = await message.reply(chunk, view=view)
                        else:
                             await message.channel.send(chunk)

            return None 


         except asyncio.CancelledError:
             logger.info("AI response generation cancelled.")
             try:
                 if sent_message:
                     await sent_message.edit(content=sent_message.content + " [Interrupted 🛑]")
             except: pass
             raise # Re-raise to let the task be cancelled properly
         except Exception as e:
             logger.error(f"Process Response Error: {e}")
             traceback.print_exc()
             return f"❌ Error: {e}"


    async def _process_chat_turn(self, chat_session, content, message: discord.Message):
        """Initial Trigger for the chat loop."""
        try:
            response = await chat_session.send_message(content)
            return await self._process_chat_response(chat_session, response, message, execution_logs=[])
        except Exception as e:
            logger.error(f"AI Turn Error: {e}")
            return f"❌ AI Error: {e}"

    async def _build_history(self, message: discord.Message) -> list:
        """
        Builds the chat history context.
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
        
        
        
        # --- Time-Based and Char-Based Loading ---
        
        # 1. Config
        is_dm = isinstance(message.channel, discord.DMChannel)
        char_limit = 14000 if is_dm else 6000
        time_prune_threshold = 6 * 3600 # 6 hours in seconds
        
        current_chars = 0
        last_msg_time = None
        recent_msgs = []
        
        # 2. Iterate history (checking limits and time gap)
        # We increase message limit to be safe, but stop early if chars hit
        search_limit = 300 if is_dm else 100 
        
        async for msg in message.channel.history(limit=search_limit, before=message):
            # Check pruning marker (Manual Clear)
            if message.channel.id in self.context_pruning_markers:
                if msg.id <= self.context_pruning_markers[message.channel.id]:
                    continue 

            # REMOVED AUTO-PRUNE LOOP AS REQUESTED
            # We will handle time-gaps via prompt injection in run_chat instead

            if msg not in reply_chain and msg.id != message.id:
                 # Check Char Limit
                 if current_chars + len(msg.content) > char_limit:
                      break
                 
                 current_chars += len(msg.content)
                 recent_msgs.append(msg)
        
        recent_msgs.reverse() 
        reply_chain.reverse() 
        full_context_msgs = recent_msgs + reply_chain
        
        history = []
        limit = 100000 
        
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
                
            history.append(types.Content(role=role, parts=[types.Part(text=text)]))
            
        return history

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

        is_dm = isinstance(message.channel, discord.DMChannel)
        if not (is_mention or is_reply or is_dm): return

        logger.info(f"AI Triggered by {message.author.display_name}")

    async def run_chat(self, message: discord.Message):
        """
        Runs the full chat session. Designed to be a cancellable task.
        """
        async with message.channel.typing():
            try:
                # 1. Retrieve or Build History
                # We prioritize in-memory history to preserve Tool Call context (which is not in Discord messages)
                if message.channel.id in self.chat_histories:
                     history = self.chat_histories[message.channel.id]
                     # Check if history is too old? For now, infinite context (Gemini 3 Flash).
                else:
                     history = await self._build_history(message)
                
                if not hasattr(self, 'async_client'):
                    self.async_client = self.client.aio

                # --- IMAGE ANALYSIS (PRE-ROUTING) ---
                image_analysis_text = ""
                att_status_msg = None
                sent_message = None
                
                if message.attachments:
                    valid_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                    target_att = next((a for a in message.attachments if a.filename.split('.')[-1].lower() in valid_exts), None)
                    
                    if target_att:
                        status_msg = await message.reply(f"🔍 Analyzing image for routing...", mention_author=False)
                        att_status_msg = status_msg # Track to delete later if needed
                        
                        try:
                            # Use Vision Tool Logic directly or via helper? 
                            # We'll use the tool function but imported or accessed. 
                            # Since it's a tool, we might need to import it or duplicate logic slightly for pre-processing.
                            # Better: Import the tool function.
                            from .tools.vision import analyze_image
                            
                            # Always use Gemini 3 Flash for Image Analysis
                            description = await analyze_image(target_att.url, question="Describe this image in extreme detail for context.", model_name=SIMPLE_MODEL)
                            
                            image_analysis_text = f"\n[System: User uploaded an Image. Description: {description}]"
                            
                        except Exception as e:
                            logger.error(f"Pre-routing image analysis failed: {e}")
                            image_analysis_text = "\n[System: Image upload failed analysis.]"
                            
                        # Cleanup status
                        try: await status_msg.delete() 
                        except: pass

                # --- SMART ROUTING ---
                # Check for attachments first -> We now have a description!
                # Route based on (User Text + Image Description) to catch "Solve this math problem" + [Math Image]
                
                combined_context = message.content + image_analysis_text
                
                # --- OWNER OVERRIDE ---
                is_owner = await self.bot.is_owner(message.author)
                force_pro_keywords = ["use pro", "force pro", "pro model", "pro brain", "use 3 pro", "use pro model"]
                owner_forced_pro = is_owner and any(kw in message.content.lower() for kw in force_pro_keywords)
                
                if owner_forced_pro:
                    complexity = "COMPLEX"
                    logger.info(f"Owner Forced PRO Model: {message.author}")
                else:
                    complexity = await evaluate_complexity(combined_context)
                     
                selected_model = COMPLEX_MODEL if complexity == "COMPLEX" else SIMPLE_MODEL
                
                logger.info(f"Smart Routing (Text+Image): {complexity} -> {selected_model}")

                if selected_model == COMPLEX_MODEL:
                    status_text = "-# 🧠 Thinking (Pro Model)..."
                    if sent_message:
                        sent_message = await sent_message.edit(content=sent_message.content + "\n" + status_text)
                    else:
                        sent_message = await message.reply(status_text)

                time_gap_note = ""
                
                # Time Gap Check (> 6 Hours)
                # Check the most recent message before this one to see if there was a long break
                last_msg_chk = [m async for m in message.channel.history(limit=1, before=message)]
                if last_msg_chk:
                     delta = (message.created_at - last_msg_chk[0].created_at).total_seconds()
                     if delta > 6 * 3600:
                          time_gap_note = "\n[System: Significant time gap (>6h) detected since last message. If the user's topic has changed, AGGRESSIVELY suggest cleaning context.]"

                if message.attachments:
                    valid_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                    target_att = next((a for a in message.attachments if a.filename.split('.')[-1].lower() in valid_exts), None)
                    
                    if target_att:
                        att_status_msg = await message.reply(f"-# 👀 Analyzing `{target_att.filename}` with `{selected_model}`...")
                        try:
                             # Wait for vision tool
                             description = await analyze_image(target_att.url, model_name=selected_model)
                             image_analysis_text = f"\n[System: Attached Image ({target_att.filename}) Analysis: {description}]"
                             await att_status_msg.edit(content=f"-# ✅ Analyzed `{target_att.filename}`")
                        except Exception as e:
                             logger.error(f"Image analysis failed: {e}")
                             await att_status_msg.edit(content=f"-# ❌ Failed analysis: {e}")
                
                chat = self.async_client.chats.create(
                    model=selected_model,
                    history=history,
                    config=types.GenerateContentConfig(
                        tools=self.all_tools,
                        system_instruction=SYSTEM_PROMPT,
                        automatic_function_calling=dict(disable=True) 
                    )
                )
                # Store flag for footer and tool context
                chat.is_pro_model = (selected_model == COMPLEX_MODEL)
                chat.model_name = selected_model
                
                user_msg = f"User {message.author.display_name} ({message.author.id}): {message.content}\n[System: THIS IS THE CURRENT MESSAGE. REPLY TO THIS.]{image_analysis_text}{time_gap_note}"
                if await self.bot.is_owner(message.author):
                    user_msg += "\n[System: User IS Bot Owner]"
                elif message.author.guild_permissions.administrator:
                    user_msg += "\n[System: User IS Admin]"
                
                await self._process_chat_turn(chat, user_msg, message)
                
                # 2. Update History
                # 2. Update History
                # 'google-genai' AsyncChat uses _curated_history
                if hasattr(chat, '_curated_history'):
                    self.chat_histories[message.channel.id] = chat._curated_history
                else: 
                     # Fallback mechanisms
                     if hasattr(chat, 'history'):
                         self.chat_histories[message.channel.id] = chat.history
                     else:
                         logger.warning("Could not persist history: neither '_curated_history' nor 'history' found.")
            
            except asyncio.CancelledError:
                 logger.info(f"Chat task cancelled for {message.author.display_name}")
                 # Optional: React to show cancellation? 
                 # await message.add_reaction("🛑") 
                 pass
            except Exception as e:
                logger.error(f"Error in AI handler: {e}")
                traceback.print_exc()
                await message.reply("❌ Error processing request. Check logs.")
            finally:
                # Cleanup task from map
                if message.channel.id in self.active_tasks:
                    del self.active_tasks[message.channel.id]

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

        logger.info(f"AI Triggered by {message.author.display_name}")
        
        # --- TASK INTERRUPTION LOGIC ---
        # If there is an active generation in this channel, CANCEL IT.
        if message.channel.id in self.active_tasks:
            logging.info(f"Interrupting active task in channel {message.channel.id}")
            task = self.active_tasks[message.channel.id]
            if not task.done():
                task.cancel()
            # Wait a tiny bit? No, proceed immediately.
            
        # Create new task
        task = asyncio.create_task(self.run_chat(message))
        self.active_tasks[message.channel.id] = task

def setup(bot):
    bot.add_cog(AICog(bot))
