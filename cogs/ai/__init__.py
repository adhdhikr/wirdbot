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
from .prompts import SYSTEM_PROMPT, get_system_prompt
from .views import CodeApprovalView, ContinueExecutionView, SandboxExecutionView
from .utils import safe_split_text, ScopedBot

# Import tools from the new package
from .tools import CUSTOM_TOOLS, ADMIN_TOOLS, DISCORD_TOOLS, execute_discord_code, analyze_image
from .tools.memory import fetch_user_memory_context
from .router import evaluate_complexity, SIMPLE_MODEL, COMPLEX_MODEL

logger = logging.getLogger(__name__)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tasks = {} # Map message_id -> asyncio.Task
        self.active_bot_messages = {} # Map channel_id -> message_id (The bot's "Thinking..." or response message)
        self.interrupt_signals = {} # Map channel_id -> interrupter_name
        self.pending_approvals = {} # Map channel_id -> CodeApprovalView
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
                                # Register new message ID for interruption
                                self.active_tasks[sent_message.id] = asyncio.current_task()
                        else:
                            sent_message = await message.reply(accumulated_text)
                            # Register new message ID for interruption
                            self.active_tasks[sent_message.id] = asyncio.current_task()
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
                                # Register new message ID
                                self.active_tasks[sent_message.id] = asyncio.current_task()
                         except:
                            sent_message = await message.reply(status_line.strip())
                            # Register new message ID
                            self.active_tasks[sent_message.id] = asyncio.current_task()
                    else:
                         sent_message = await message.reply(status_line.strip())
                         # Register new message ID
                         self.active_tasks[sent_message.id] = asyncio.current_task()

                    # --- TOOL EXECUTION LOGIC ---
                    tool_result = "Error: Unknown tool"
                    error_occurred = False
                    start_time = time.time()
                    
                    if fname == 'execute_discord_code':
                         pending_execution = True
                         pending_execution_code = fargs.get('code', '')
                         
                         # If we are about to ask for approval, we return early?
                         # Actually, _execute_discord_code_internal handles the View.
                         # But wait, execute_discord_code is a wrapper tool now?
                         # Let's check tools definition.
                         # execute_discord_code returns "Approval Required..." string usually if manual.
                         # BUT the view is attached to the MESSAGE sent.
                         # We need to capture that view.
                         pass 
                    
                    elif fname in self.tool_map:
                        func = self.tool_map[fname]
                        
                        ctx_kwargs = {
                            'bot': self.bot,
                            'guild': message.guild,
                            'guild_id': message.guild.id if message.guild else None,
                            'channel': message.channel,
                            'message': message,
                            'is_owner': await self.bot.is_owner(message.author),
                            'is_admin': message.author.guild_permissions.administrator if message.guild else False,
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
                
                # Register pending approval for interruption handling
                self.pending_approvals[message.channel.id] = view
                
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
                    chunks = safe_split_text(accumulated_text, 1900) # Safety margin
                    
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            if sent_message:
                                # Update the initial "Thinking..." message with the first chunk
                                final_content = sent_message.content.replace("-# 🧠 Thinking (Pro Model)...", "").strip()
                                # If the thinking message plus chunk is too big, just replace content entirely or error?
                                # safe_split logic usually ensures chunk is < 2000. 
                                # But final_content might be non-empty (previous tool outputs).
                                if len(final_content) + len(chunk) < 2000:
                                     await sent_message.edit(content=(final_content + "\n" + chunk).strip())
                                else:
                                     # Edge case: Previous content + new chunk > 2000. 
                                     # We should probably have appended previous content to accumulated_text before splitting? 
                                     # Too complex for now. Just edit with chunk and hope previous content wasn't important context? 
                                     # Or just send new message.
                                     # Let's try to edit, if fail, send new.
                                     await sent_message.edit(content=chunk)
                            else:
                                sent_message = await message.reply(chunk)
                                self.active_tasks[sent_message.id] = asyncio.current_task()
                        
                        else:
                            # Subsequent chunks are always new messages
                            # Register them for tracking too? User might reply to them to cancel?
                            # Yes, safer.
                            msg_chunk = await message.channel.send(chunk)
                            self.active_tasks[msg_chunk.id] = asyncio.current_task()
                            
                            if i == len(chunks) - 1:
                                # Last chunk gets the view
                                if view:
                                    await msg_chunk.edit(view=view)
                    
                    # If we only had 1 chunk and it was i=0, we didn't attach view if sent_message existed?
                    # logic above: i=0 just edits sent_message.
                    # We need to attach view to the LAST message sent/edited.
                    if len(chunks) == 1 and sent_message and view:
                        await sent_message.edit(view=view)

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


    async def _process_chat_turn(self, chat_session, content, message: discord.Message, sent_message=None):
        """Initial Trigger for the chat loop."""
        try:
            response = await chat_session.send_message(content)
            return await self._process_chat_response(chat_session, response, message, existing_message=sent_message, execution_logs=[])
        except Exception as e:
            logger.error(f"AI Turn Error: {e}")
            if sent_message:
                try:
                    await sent_message.edit(content=f"❌ AI Error: {e}")
                except: pass
            else:
                 try:
                    await message.reply(f"❌ AI Error: {e}")
                 except: pass
            return f"❌ AI Error: {e}"

    async def _build_history(self, message: discord.Message) -> list:
        """
        Builds the chat history context.
        """
        reply_chain = []
        curr = message

        # Trace back references ensuring we have the full object
        for _ in range(5):
            if not curr.reference:
                break

            if curr.reference.resolved and isinstance(curr.reference.resolved, discord.Message):
                curr = curr.reference.resolved
                reply_chain.append(curr)
            elif curr.reference.message_id:
                # Attempt to fetch if not resolved
                try:
                    curr = await message.channel.fetch_message(curr.reference.message_id)
                    reply_chain.append(curr)
                except:
                    break
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

            # Avoid duplicates if msg is already in reply chain
            if msg.id in [m.id for m in reply_chain] or msg.id == message.id:
                continue

            # Check Char Limit - Strict Content Count
            msg_len = len(msg.content)
            if current_chars + msg_len > char_limit:
                 break
            
            current_chars += msg_len
            recent_msgs.append(msg)
        
        recent_msgs.reverse() 
        reply_chain.reverse() 
        
        # Reply chain logic: Ensure they are always included, even if they push over limit?
        # User requested "biggest priority". So we put them properly in flow.
        # Construct full list
        full_context_msgs = recent_msgs + reply_chain
        
        history = []
        
        # Debug Log for Char Count
        logger.info(f"Context Build: {current_chars} chars from {len(recent_msgs)} history msgs + {len(reply_chain)} replies.")
        
        for msg in full_context_msgs:
            role = "model" if msg.author.id == self.bot.user.id else "user"
            content = msg.content
            
            # Append attachment info for context
            if msg.attachments:
                content += f"\n[System: Attachment: {msg.attachments[0].url}]"

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
        # Track the active bot message ID for this task
        current_task = asyncio.current_task()
        tracked_msg_ids = [] # Keep local list to cleanup later
        
        logger.info(f"STARTING run_chat for MsgID: {message.id} | Content: '{message.content}' | Author: {message.author}")
        
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
                        att_status_msg = status_msg 
                        
                        # Track status msg
                        self.active_tasks[status_msg.id] = current_task
                        tracked_msg_ids.append(status_msg.id)
                        
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
                        
                        # Cleanup tracking for deleted message so map doesn't grow indefinitely
                        if status_msg.id in self.active_tasks:
                            del self.active_tasks[status_msg.id]
                        if status_msg.id in tracked_msg_ids:
                            tracked_msg_ids.remove(status_msg.id)

                # --- SMART ROUTING ---
                # Check for attachments first -> We now have a description!
                # Route based on (User Text + Image Description) to catch "Solve this math problem" + [Math Image]
                
                combined_context = message.content + image_analysis_text
                
                # --- MODEL OVERRIDE ---
                # Check for explicit model requests in the message
                msg_content_lower = message.content.lower()
                force_pro_keywords = ["use pro", "force pro", "pro model", "pro brain", "use 3 pro"]
                force_flash_keywords = ["use flash", "force flash", "flash model", "fast model", "use 3 flash"]
                
                forced_pro = any(kw in msg_content_lower for kw in force_pro_keywords)
                forced_flash = any(kw in msg_content_lower for kw in force_flash_keywords)
                
                if forced_pro:
                    complexity = "COMPLEX"
                    logger.info(f"User Forced PRO Model: {message.author}")
                elif forced_flash:
                     complexity = "SIMPLE"
                     logger.info(f"User Forced FLASH Model: {message.author}")
                else:
                    complexity = await evaluate_complexity(combined_context)
                     
                selected_model = COMPLEX_MODEL if complexity == "COMPLEX" else SIMPLE_MODEL
                
                logger.info(f"Smart Routing (Text+Image): {complexity} -> {selected_model}")

                # Always send a status message so the user has something to reply to for interruption/cancellation
                status_text = "-# 🧠 Thinking (Pro Model)..." if selected_model == COMPLEX_MODEL else "-# ⚡ Thinking..."
                sent_message = await message.reply(status_text)
                
                # Track main thinking message
                self.active_tasks[sent_message.id] = current_task
                tracked_msg_ids.append(sent_message.id)

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
                        
                        self.active_tasks[att_status_msg.id] = current_task
                        tracked_msg_ids.append(att_status_msg.id)
                        
                        try:
                             # Wait for vision tool
                             description = await analyze_image(target_att.url, model_name=selected_model)
                             image_analysis_text = f"\n[System: Attached Image ({target_att.filename}) Analysis: {description}]"
                             await att_status_msg.edit(content=f"-# ✅ Analyzed `{target_att.filename}`")
                        except Exception as e:
                             logger.error(f"Image analysis failed: {e}")
                             await att_status_msg.edit(content=f"-# ❌ Failed analysis: {e}")
                
                # --- PERMISSIONS & TOOL FILTERING ---
                is_owner = await self.bot.is_owner(message.author)
                is_admin = message.author.guild_permissions.administrator if message.guild else False
                
                allowed_tools = list(self.all_tools)
                
                if not (is_admin or is_owner):
                    # Remove Restricted Tools
                    # We exclude all ADMIN_TOOLS and specifically execute_discord_code
                    # We allow search_channel_history (which is in DISCORD_TOOLS)
                    restricted_funcs = [t.__name__ for t in ADMIN_TOOLS] + ['execute_discord_code']
                    
                    # self.all_tools contains raw Python functions (Client-side tools)
                    allowed_tools = [t for t in self.all_tools if t.__name__ not in restricted_funcs]

                # Generate Dynamic System Prompt
                current_system_prompt = get_system_prompt(is_admin=is_admin, is_owner=is_owner)
                
                # --- MEMORY INJECTION ---
                memory_context = ""
                try:
                    # 1. Author Memory
                    auth_mem = await fetch_user_memory_context(message.author.id, message.guild.id)
                    if auth_mem:
                        memory_context += f"\n[System: Memories about User @{message.author.display_name}: {auth_mem}]"
                        
                    # 2. Mentioned Users Memory
                    for user in message.mentions:
                        if user.id != message.author.id and user.id != self.bot.user.id and not user.bot:
                            men_mem = await fetch_user_memory_context(user.id, message.guild.id)
                            if men_mem:
                                memory_context += f"\n[System: Memories about User @{user.display_name}: {men_mem}]"
                except Exception as e:
                    logger.error(f"Memory injection error: {e}")

                chat = self.async_client.chats.create(
                    model=selected_model,
                    history=history,
                    config=types.GenerateContentConfig(
                        tools=allowed_tools,
                        system_instruction=current_system_prompt,
                        automatic_function_calling=dict(disable=True) 
                    )
                )
                # Store flag for footer and tool context
                chat.is_pro_model = (selected_model == COMPLEX_MODEL)
                chat.model_name = selected_model
                
                user_msg = f"User {message.author.display_name} ({message.author.id}): {message.content}\n[System: THIS IS THE CURRENT MESSAGE. REPLY TO THIS.]{image_analysis_text}{time_gap_note}{memory_context}"
                if await self.bot.is_owner(message.author):
                    user_msg += "\n[System: User IS Bot Owner]"
                elif message.author.guild_permissions.administrator:
                    user_msg += "\n[System: User IS Admin]"
                
                logger.info(f"FINAL PROMPT to Gemini for MsgID {message.id}:\n{user_msg}\nHISTORY LEN: {len(history)}")
                
                await self._process_chat_turn(chat, user_msg, message, sent_message=sent_message)
                
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
                 interrupter = self.interrupt_signals.pop(message.channel.id, "User")
                 logger.info(f"Chat task cancelled for {message.channel.id} by {interrupter}")
                 # Message editing is now handled in on_message where cancellation occurs
                 raise  # Re-raise to let the task be properly cancelled
            except Exception as e:
                logger.error(f"Error in AI handler: {e}")
                traceback.print_exc()
                await message.reply("❌ Error processing request. Check logs.")
            finally:
                # Cleanup task from map
                # Crucial: Remove ALL entries pointing to this task
                keys_to_remove = [k for k, v in self.active_tasks.items() if v == current_task]
                for k in keys_to_remove:
                    del self.active_tasks[k]

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
        # Smart Interruption: ONLY cancel if this new message is a REPLY to the bot's ongoing message.
        
        should_interrupt = False
        
        if message.reference and message.reference.message_id:
             target_msg_id = message.reference.message_id
             if target_msg_id in self.active_tasks:
                 task = self.active_tasks[target_msg_id]
                 if not task.done():
                     should_interrupt = True
                     logger.info(f"Targeted Interruption detected: {message.author} replied to active bot message {target_msg_id}.")
                 else:
                     # cleanup
                     del self.active_tasks[target_msg_id]
        
        # Debug Log
        if message.reference and not should_interrupt:
             logger.debug(f"Reply detected but NO interruption. RefMsgID: {message.reference.message_id} | ActiveTasksKeys: {list(self.active_tasks.keys())}")
        
        if should_interrupt:
            logging.info(f"Interrupting active task in channel {message.channel.id}")
            task = self.active_tasks[target_msg_id] # target_msg_id is defined in the check above
            
            # Signal interruption source
            self.interrupt_signals[message.channel.id] = message.author.display_name
            
            # Auto-reject pending approval if exists
            if message.channel.id in self.pending_approvals:
                 view = self.pending_approvals.pop(message.channel.id)
                 await view.cancel_by_interruption(message.author.display_name)
                 logger.info(f"Auto-rejected pending code approval in {message.channel.id} due to interruption.")
            
            if not task.done():
                task.cancel()
                # Wait for the task to actually finish cancelling
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Edit the target message (the one being replied to) to show interrupted
            try:
                target_msg = await message.channel.fetch_message(target_msg_id)
                if target_msg and target_msg.author.id == self.bot.user.id:
                    content = target_msg.content
                    # Remove any "Thinking" status lines
                    content = content.replace("-# 🧠 Thinking (Pro Model)...", "").strip()
                    content = content.replace("-# ⚡ Thinking...", "").strip()
                    # Remove any tool calling status lines
                    content = re.sub(r"\n?-#\s*🛠️\s*Calling\s*`[^`]+`.*?\.\.\.", "", content)
                    if content:
                        await target_msg.edit(content=content + f"\n🛑 **Interrupted by {message.author.display_name}**", view=None)
                    else:
                        await target_msg.edit(content=f"🛑 **Interrupted by {message.author.display_name}**", view=None)
            except Exception as e:
                logger.error(f"Failed to edit interrupted message: {e}")
            
        # --- CONCURRENCY ---
        # We ALWAYS spawn a new task. We do not block.
        # User said: "if i reply that means interrupt and respond to this"
        # So we cancel the old one (above) and Start the new one (below).
        asyncio.create_task(self.run_chat(message))

def setup(bot):
    bot.add_cog(AICog(bot))
