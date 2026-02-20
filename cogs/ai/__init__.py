import asyncio
import logging
import traceback

import nextcord as discord
from google import genai
from google.genai import types
from nextcord.ext import commands

from config import GEMINI_API_KEY

from .prompts import get_system_prompt
from .router import COMPLEX_MODEL, SIMPLE_MODEL, evaluate_complexity
from .tools import ADMIN_TOOLS, BOT_MANAGEMENT_TOOLS, CUSTOM_TOOLS
from .tools.memory import fetch_user_memory_context
from .history import build_chat_history
from .chat_handler import ChatHandler
from db.repositories.ai_whitelist import add_to_whitelist, load_whitelist, remove_from_whitelist

logger = logging.getLogger(__name__)

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tasks = {} # Map message_id -> asyncio.Task
        self.active_bot_messages = {} # Map channel_id -> message_id
        self.interrupt_signals = {} # Map channel_id -> interrupter_name
        self.pending_approvals = {} # Map channel_id -> View
        self.chat_histories = {} # Map channel_id -> list[types.Content]
        self.context_pruning_markers = {} # Map channel_id -> message_id
        self.execute_code_whitelist = set()
        
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            self.async_client = self.client.aio
            self.has_key = True
            self.tool_map = {func.__name__: func for func in CUSTOM_TOOLS}
            self.all_tools = list(CUSTOM_TOOLS)
            self.chat_handler = ChatHandler(self)
        else:
            self.has_key = False
            logger.warning("GEMINI_API_KEY not found. AI features disabled.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Load the persistent whitelist from DB once the bot is ready."""
        try:
            self.execute_code_whitelist = await load_whitelist()
            logger.info(f"AI whitelist loaded: {self.execute_code_whitelist}")
        except Exception as e:
            logger.error(f"Failed to load AI whitelist: {e}")

    async def run_chat(self, message: discord.Message):
        """
        Runs the full chat session. Designed to be a cancellable task.
        """
        current_task = asyncio.current_task()
        tracked_msg_ids = []
        
        logger.info(f"STARTING run_chat for MsgID: {message.id} | Author: {message.author}")
        
        async with message.channel.typing():
            try:
                # 1. Build or fetch history
                if message.channel.id in self.chat_histories:
                     history = self.chat_histories[message.channel.id]
                else:
                     history = await build_chat_history(self.bot, message, self.context_pruning_markers)
                
                # 2. Image Analysis (Pre-routing)
                image_analysis_text = ""
                if message.attachments:
                    valid_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                    target_att = next((a for a in message.attachments if a.filename.split('.')[-1].lower() in valid_exts), None)
                    
                    if target_att:
                        status_msg = await message.reply("🔍 Analyzing image for routing...", mention_author=False)
                        self.active_tasks[status_msg.id] = current_task
                        tracked_msg_ids.append(status_msg.id)
                        
                        try:
                            from .tools.vision import analyze_image
                            description = await analyze_image(target_att.url, question="Describe this image in extreme detail for context.", model_name=SIMPLE_MODEL)
                            image_analysis_text = f"\n[System: User uploaded an Image. Description: {description}]"
                        except Exception as e:
                            logger.error(f"Pre-routing image analysis failed: {e}")
                            image_analysis_text = "\n[System: Image upload failed analysis.]"
                            
                        try:
                            await status_msg.delete()
                        except Exception:
                            pass
                        self.active_tasks.pop(status_msg.id, None)

                # 3. Model Complexity Routing
                combined_context = message.content + image_analysis_text
                msg_content_lower = message.content.lower()
                
                force_pro = any(kw in msg_content_lower for kw in ["use pro", "force pro", "pro model", "pro brain", "use 3 pro"])
                force_flash = any(kw in msg_content_lower for kw in ["use flash", "force flash", "flash model", "fast model", "use 3 flash"])
                
                if force_pro:
                    complexity = "COMPLEX"
                elif force_flash:
                    complexity = "SIMPLE"
                elif len(message.content) < 100 and not image_analysis_text:
                    complexity = "SIMPLE"
                else:
                    complexity = await evaluate_complexity(combined_context)
                     
                selected_model = COMPLEX_MODEL if complexity == "COMPLEX" else SIMPLE_MODEL
                logger.info(f"Smart Routing: {complexity} -> {selected_model}")
                
                status_text = "-# 🧠 Thinking (Pro Model)..." if selected_model == COMPLEX_MODEL else "-# <a:loading:1466182602317889576> Generating..."
                sent_message = await message.reply(status_text)
                self.active_tasks[sent_message.id] = current_task
                tracked_msg_ids.append(sent_message.id)

                # 4. Context Enhancements (Time gap, permissions, memories)
                time_gap_note = ""
                last_msg_chk = [m async for m in message.channel.history(limit=1, before=message)]
                if last_msg_chk and (message.created_at - last_msg_chk[0].created_at).total_seconds() > 6 * 3600:
                    time_gap_note = "\n[System: Significant time gap (>6h) detected. Suggest cleaning context if topic changed.]"

                is_owner = await self.bot.is_owner(message.author)
                is_admin = message.author.guild_permissions.administrator if message.guild else False
                whitelisted_guild = message.guild.id in self.execute_code_whitelist if message.guild else False
                
                # 5. Tool Filtering
                allowed_tools = list(self.all_tools)
                if not (is_admin or is_owner):
                    restricted = [t.__name__ for t in ADMIN_TOOLS] + [t.__name__ for t in BOT_MANAGEMENT_TOOLS] + ['execute_discord_code']
                    allowed_tools = [t for t in self.all_tools if t.__name__ not in restricted]
                    bot_mgmt_names = [t.__name__ for t in BOT_MANAGEMENT_TOOLS]
                    if not whitelisted_guild:
                        bot_mgmt_names.append('execute_discord_code')
                    allowed_tools = [t for t in self.all_tools if t.__name__ not in bot_mgmt_names]

                # 6. Memory Injection
                memory_context = ""
                try:
                    auth_mem = await fetch_user_memory_context(message.author.id, message.guild.id if message.guild else None)
                    if auth_mem:
                        memory_context += f"\n[System: Memories about User @{message.author.display_name}: {auth_mem}]"
                    for user in message.mentions:
                        if user.id != message.author.id and user.id != self.bot.user.id and not user.bot:
                            men_mem = await fetch_user_memory_context(user.id, message.guild.id if message.guild else None)
                            if men_mem:
                                memory_context += f"\n[System: Memories about User @{user.display_name}: {men_mem}]"
                except Exception as e:
                    logger.error(f"Memory injection error: {e}")

                # 7. Start Chat Session
                chat = self.async_client.chats.create(
                    model=selected_model,
                    history=history,
                    config=types.GenerateContentConfig(
                        tools=allowed_tools,
                        system_instruction=get_system_prompt(is_admin=is_admin, is_owner=is_owner, whitelisted_guild=whitelisted_guild),
                        automatic_function_calling=dict(disable=True) 
                    )
                )
                chat.is_pro_model = (selected_model == COMPLEX_MODEL)
                chat.model_name = selected_model
                
                guild_ctx_str = f", Guild ID: {message.guild.id}" if message.guild else ", Guild: None (DM)"
                user_msg = (
                    f"User {message.author.display_name} ({message.author.id}): {message.content}\n"
                    f"[System: THIS IS THE CURRENT MESSAGE. REPLY TO THIS.]\n"
                    f"[System Context: Current Channel ID: {message.channel.id}{guild_ctx_str}]\n"
                    f"{image_analysis_text}{time_gap_note}{memory_context}"
                )
                
                # 8. Delegation to Handler
                allowed_tool_names = {t.__name__ for t in allowed_tools}
                await self.chat_handler.process_chat_turn(chat, user_msg, message, sent_message=sent_message, allowed_tool_names=allowed_tool_names)
                
                if message.channel.id not in self.context_pruning_markers:
                    self.chat_histories[message.channel.id] = getattr(chat, '_curated_history', getattr(chat, 'history', []))
            
            except asyncio.CancelledError:
                 interrupter = self.interrupt_signals.pop(message.channel.id, "User")
                 logger.info(f"Chat task cancelled for {message.channel.id} by {interrupter}")
                 raise 
            except Exception as e:
                logger.error(f"Error in AI handler: {e}\n{traceback.format_exc()}")
                await message.reply("❌ Error processing request. Check logs.")
            finally:
                keys_to_remove = [k for k, v in self.active_tasks.items() if v == current_task]
                for k in keys_to_remove:
                    self.active_tasks.pop(k, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.has_key or not self.bot.user or message.author.bot:
            return
        if message.author.id == self.bot.user.id:
            return

        # Check for triggers (Mention, Reply to Bot, or DM)
        is_mention = self.bot.user in message.mentions
        is_reply = False
        if message.reference:
             resolved = message.reference.resolved
             if resolved and isinstance(resolved, discord.Message):
                 is_reply = resolved.author.id == self.bot.user.id
             else:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    is_reply = ref_msg.author.id == self.bot.user.id
                except Exception:
                    pass
        is_dm = isinstance(message.channel, discord.DMChannel)
        
        if not (is_mention or is_reply or is_dm):
            return

        logger.info(f"AI Triggered by {message.author.display_name}")
        
        # Handle Interruption
        target_msg_id = message.reference.message_id if message.reference else None
        if target_msg_id and target_msg_id in self.active_tasks:
            task = self.active_tasks[target_msg_id]
            if not task.done():
                logger.info(f"Interrupting active task in {message.channel.id}")
                self.interrupt_signals[message.channel.id] = message.author.display_name
                
                if message.channel.id in self.pending_approvals:
                     view = self.pending_approvals.pop(message.channel.id)
                     await view.cancel_by_interruption(message.author.display_name)
                
                try:
                    target_msg = await message.channel.fetch_message(target_msg_id)
                    if target_msg and target_msg.author.id == self.bot.user.id:
                        content = target_msg.content
                        # Clean status lines
                        content = '\n'.join([line for line in content.split('\n') if '🧠 Thinking' not in line and 'loading:' not in line]).strip()
                        await target_msg.edit(content=(content + f"\n🛑 **Interrupted by {message.author.display_name}**" if content else f"🛑 **Interrupted by {message.author.display_name}**"), view=None)
                except Exception as e:
                    logger.error(f"Interruption edit failed: {e}")
                task.cancel()
        
        asyncio.create_task(self.run_chat(message))

    @commands.command(name='whitelist_code')
    @commands.is_owner()
    async def whitelist_code_execution(self, ctx, guild_id: int = None):
        """[Owner Only] Whitelist a guild for execute_discord_code tool."""
        gid = guild_id or (ctx.guild.id if ctx.guild else None)
        if not gid:
            return await ctx.send("❌ Provide a guild ID.")
        if gid in self.execute_code_whitelist:
            return await ctx.send(f"⚠️ `{gid}` already whitelisted.")
        self.execute_code_whitelist.add(gid)
        await add_to_whitelist(gid)
        await ctx.send(f"✅ Whitelisted `{gid}`.")

    @commands.command(name='unwhitelist_code')
    @commands.is_owner()
    async def unwhitelist_code_execution(self, ctx, guild_id: int = None):
        """[Owner Only] Remove a guild from whitelist."""
        gid = guild_id or (ctx.guild.id if ctx.guild else None)
        if not gid or gid not in self.execute_code_whitelist:
            return await ctx.send("❌ Not whitelisted.")
        self.execute_code_whitelist.remove(gid)
        await remove_from_whitelist(gid)
        await ctx.send(f"✅ Removed `{gid}`.")

    @commands.command(name='list_whitelisted')
    @commands.is_owner()
    async def list_whitelisted_guilds(self, ctx):
        """[Owner Only] List whitelisted guilds."""
        if not self.execute_code_whitelist:
            return await ctx.send("📋 No whitelisted guilds.")
        lst = [f"• `{gid}` - {getattr(self.bot.get_guild(gid), 'name', 'Unknown')}" for gid in self.execute_code_whitelist]
        await ctx.send("📋 **Whitelisted Guilds:**\n" + "\n".join(lst))

def setup(bot):
    bot.add_cog(AICog(bot))
