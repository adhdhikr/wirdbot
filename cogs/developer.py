import nextcord as discord
from nextcord.ext import commands
import google.generativeai as genai
from config import GEMINI_API_KEY
import logging

logger = logging.getLogger(__name__)


AVAILABLE_MODELS = [
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

class DeveloperCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.has_key = True
        else:
            self.has_key = False
            logger.warning("GEMINI_API_KEY not found. Gemini commands will be disabled.")

    @commands.group(name="dev", invoke_without_command=True)
    async def dev(self, ctx):
        """Developer commands group. Usage: !dev ai [prompt]"""
        await ctx.send_help(ctx.command)

    @dev.command(name="ai", aliases=["gemini", "gen"])
    @commands.is_owner()
    async def ai(self, ctx, *, args: str):
        """
        Generates code using Gemini.
        Usage: !dev ai [model] <prompt>
        Example: !dev ai gemini-3-flash-preview send "hello"
        """
        if not self.has_key:
            await ctx.send("❌ Gemini API key is not configured.")
            return

        # Simple parsing to check if first word is a model
        parts = args.split(' ', 1)
        model = "gemini-3-pro-preview"
        prompt = args
        
        if len(parts) > 1 and parts[0] in AVAILABLE_MODELS:
            model = parts[0]
            prompt = parts[1]
        
        await ctx.message.add_reaction("⏳")

        # Gather context data
        guild_info = f"Guild: {ctx.guild.name} (ID: {ctx.guild.id})" if ctx.guild else "Guild: None (DM)"
        channel_info = f"Channel: {ctx.channel.name} (ID: {ctx.channel.id})" if ctx.channel and hasattr(ctx.channel, 'name') else "Channel: Unknown"
        author_info = f"Author: {ctx.author.name} (ID: {ctx.author.id})"

        system_instruction = (
            "You are an expert Python assistant for a Discord bot using the 'nextcord' library. "
            "You are generating code snippets to be run inside the 'Onami' REPL/eval command. "
            "The content of the code block will be executed directly.\n\n"
            "If the user requests a regular chat AI assistant, you will act as one. So infer if they want Onami help or not."
            "**Available Context Variables:**\n"
            "- `_ctx`: The Context that invoked the command.\n"
            "- `_bot`: The running Bot instance.\n"
            "- `_author`: Shortcut for `_ctx.author`.\n"
            "- `_channel`: Shortcut for `_ctx.channel`.\n"
            "- `_guild`: Shortcut for `_ctx.guild`.\n"
            "- `_message` / `_msg`: Shortcuts for `_ctx.message`.\n"
            "- `_find`: Shortcut for `nextcord.utils.find`.\n"
            "- `_get`: Shortcut for `nextcord.utils.get`.\n\n"
            "**Current Runtime Context:**\n"
            f"- {guild_info}\n"
            f"- {channel_info}\n"
            f"- {author_info}\n\n"
            "**Instructions:**\n"
            "1. Output ONLY a valid Python code block (inside ```python ... ```) if deemed Onami help. In this format in total: !onami py [code block]\n"
            "2. Use the underscored variables (e.g. `_channel`, `_guild`) provided above.\n"
            "3. Do not assume other variables exist unless you define them.\n"
            "4. Keep the code concise and robust.\n"
            "5. If importing modules, do it inside the code block (e.g. `import asyncio`).\n\n"
            "**Example Output:**\n"
            "```python\n"
            "await _channel.send('Hello world')\n"
            "```"
        )

        try:
            generative_model = genai.GenerativeModel(model)
            full_prompt = f"{system_instruction}\n\nUser Request: {prompt}"
            response = generative_model.generate_content(full_prompt)
            content = response.text
            
            await ctx.reply(content)
            await ctx.message.remove_reaction("⏳", self.bot.user)
            await ctx.message.add_reaction("✅")

        except Exception as e:
            logger.error(f"Error generating gemini content with model {model}: {e}")
            await ctx.reply(f"❌ Error generating code with `{model}`: {e}")
            await ctx.message.remove_reaction("⏳", self.bot.user)
            await ctx.message.add_reaction("❌")

def setup(bot):
    bot.add_cog(DeveloperCog(bot))
