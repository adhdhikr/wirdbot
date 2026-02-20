import io
import logging

import nextcord as discord
from google.genai import types

from .tools import _execute_discord_code_internal

logger = logging.getLogger(__name__)

class CodeApprovalView(discord.ui.View):
    def __init__(self, ctx, code: str, cog, chat_session, message: discord.Message, other_tool_parts: list = None):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.code = code
        self.cog = cog
        self.chat_session = chat_session
        self.message = message
        self.other_tool_parts = other_tool_parts or []
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        if await self.cog.bot.is_owner(interaction.user):
            return True
            
        await interaction.response.send_message("❌ Only the command author or Bot Owner can use this.", ephemeral=True)
        return False

    @discord.ui.button(label="Show Code", style=discord.ButtonStyle.secondary, emoji="👀")
    async def show_code(self, button: discord.ui.Button, interaction: discord.Interaction):
        if len(self.code) > 1900:
            file = discord.File(io.StringIO(self.code), filename="proposed_code.py")
            await interaction.response.send_message("📄 **Code is too long to display inline.** See attached file.", file=file, ephemeral=True)
        else:
            await interaction.response.send_message(f"```python\n{self.code}\n```", ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        for child in self.children:
            child.disabled = True
        updated_message = await interaction.response.edit_message(view=self)
        if not updated_message:
             updated_message = interaction.message
        try:
            result = await _execute_discord_code_internal(self.cog.bot, self.code, {
                'ctx': self.ctx,
                'channel': self.ctx.channel,
                'author': self.ctx.author,
                'guild': self.ctx.guild,
                'message': self.ctx.message,
                '_ctx': self.ctx,
                '_bot': self.cog.bot, 
                '_author': self.ctx.author,
                '_channel': self.ctx.channel,
                '_guild': self.ctx.guild,
                '_message': self.ctx.message,
                '_msg': self.ctx.message,
                '_find': discord.utils.find,
                '_get': discord.utils.get
            })
        except Exception as e:
            result = f"Error: {e.__class__.__name__}: {e}"
            logger.error(f"Execution Startup Error: {e}")


        try:
            try:
                if len(result) > 1900:
                    file = discord.File(io.StringIO(result), filename="execution_output.txt")
                    if len(updated_message.content) + 100 < 2000:
                         updated_message = await updated_message.edit(content=updated_message.content + "\n\n✅ **Executed.** Output attached.")
                         await interaction.message.channel.send(content=f"📄 **Output for {updated_message.jump_url}**", file=file)
                    else:
                         await interaction.message.channel.send(content="✅ **Executed.** Output attached.", file=file)
                else:
                    content = updated_message.content + f"\n\n**Output:**\n```\n{result}\n```"
                    if len(content) > 2000:
                       await interaction.message.channel.send(f"**Output:**\n```\n{result}\n```")
                    else:
                       updated_message = await updated_message.edit(content=content)
            except Exception as e:
                logger.error(f"Error displaying output: {e}")
                pass
            exec_part = types.Part(
                function_response=types.FunctionResponse(
                    name='execute_discord_code',
                    response={'result': str(result)}
                )
            )
            all_parts = self.other_tool_parts + [exec_part]
            response = await self.chat_session.send_message(all_parts)
            response_text = await self.cog.chat_handler.process_chat_response(self.chat_session, response, self.message, existing_message=updated_message)
            if response_text:
                await self.message.reply(response_text)
                
        except Exception as e:
             logger.error(f"Error resuming chat after code exec: {e}")


    @discord.ui.button(label="Refuse", style=discord.ButtonStyle.danger, emoji="⛔")
    async def refuse(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        for child in self.children:
            child.disabled = True
        current_content = interaction.message.content if interaction.message else "Proposed Code:"
        lines = current_content.split('\n')
        cleaned = [line for line in lines if not ('🧠 Thinking' in line or 'loading:' in line)]
        current_content = '\n'.join(cleaned).strip()
        
        new_content = current_content + "\n\n❌ **Execution Cancelled by User**"
        
        if interaction:
             await interaction.response.edit_message(content=new_content, view=self)
        if self.message.channel.id in self.cog.pending_approvals:
            del self.cog.pending_approvals[self.message.channel.id]

    async def cancel_by_interruption(self, interrupter_name: str):
        """Called programmatically when a new message interrupts the approval wait."""
        self.value = False
        for child in self.children:
            child.disabled = True
        current_content = self.message.content
        lines = current_content.split('\n')
        cleaned = [line for line in lines if not ('🧠 Thinking' in line or 'loading:' in line)]
        current_content = '\n'.join(cleaned).strip()
        
        new_content = current_content + f"\n\n🛑 **Auto-Rejected: Interrupted by {interrupter_name}**"
        
        try:
            await self.message.edit(content=new_content, view=self)
        except Exception as e:
            logger.error(f"Failed to edit message for auto-rejection: {e}")
        if self.message.channel.id in self.cog.pending_approvals:
            del self.cog.pending_approvals[self.message.channel.id]


class ContinueExecutionView(discord.ui.View):
    def __init__(self, ctx, cog, chat_session, response, message, existing_message):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.cog = cog
        self.chat_session = chat_session
        self.response = response
        self.message = message
        self.existing_message = existing_message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        if await self.cog.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message("❌ You cannot control this.", ephemeral=True)
        return False

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.success, emoji="▶️")
    async def continue_running(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🔄 **Continuing execution...**", view=None)
        await self.cog.chat_handler.process_chat_response(
            self.chat_session, 
            self.response, 
            self.message, 
            existing_message=interaction.message, 
            tool_count=0
        )

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="🛑")
    async def stop_running(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content="🛑 **Execution Stopped (User Request).**", view=None)
        self.stop()

class SandboxExecutionView(discord.ui.View):
    def __init__(self, execution_logs: list):
        super().__init__(timeout=None) 
        self.logs = execution_logs
        
        for i, log in enumerate(execution_logs):
            if i >= 25:
                break
            btn = discord.ui.Button(
                label=f">_[{log['index']}]",
                style=discord.ButtonStyle.secondary,
                custom_id=f"sandbox_exec_{i}"
            )
            btn.callback = self.create_callback(log)
            self.add_item(btn)

    def create_callback(self, log):
        async def callback(interaction: discord.Interaction):
            code = log['code']
            output = log['output']
            msg = f"### 🚀 Execution #{log['index']}\n\n"
            msg += f"**Code:**\n```python\n{code}\n```\n"
            
            if output:
                msg += output
            else:
                msg += "✅ *Script ran with no output.*"
            
            if len(msg) > 2000:
                f = discord.File(io.StringIO(msg), filename=f"execution_{log['index']}.txt")
                await interaction.response.send_message("📄 **Full log is too long, attached below.**", file=f, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        return callback
