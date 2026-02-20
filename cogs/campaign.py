"""Campaign management cog for mass messaging"""
import json
from typing import Optional

import nextcord as discord
from nextcord import SlashOption
from nextcord.ext import commands

from cogs.campaign_views import (
    AddButtonModal,
    CampaignCreationModal,
    CampaignMessageView,
)
from database import db


def admin_or_specific_user():
    """Check if user has manage_channels permission or is the specific user ID"""
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.manage_channels:
            return True
        if interaction.user.id == 1030575337869955102:
            return True
        return False
    return commands.check(predicate)


class CampaignCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="campaign", description="Mass messaging and form management")
    async def campaign(self, interaction: discord.Interaction):
        pass

    @campaign.subcommand(name="create", description="Create a new campaign")
    @admin_or_specific_user()
    async def create_campaign(
        self,
        interaction: discord.Interaction,
        target: str = SlashOption(
            name="target",
            description="Where to send: dm (all), channel, roles, or users",
            choices=["dm", "channel", "roles", "users"],
            required=True
        )
    ):
        """Create a new mass messaging campaign"""
        modal = CampaignCreationModal(
            guild_id=interaction.guild_id,
            created_by=interaction.user.id,
            target_type=target
        )
        await interaction.response.send_modal(modal)

    @campaign.subcommand(name="list", description="List all campaigns")
    @admin_or_specific_user()
    async def list_campaigns(
        self,
        interaction: discord.Interaction,
        status: Optional[str] = SlashOption(
            name="status",
            description="Filter by status",
            choices=["draft", "sent", "archived"],
            required=False
        )
    ):
        """List all campaigns in the server"""
        await interaction.response.defer(ephemeral=True)
        
        campaigns = await db.campaigns.get_campaigns(interaction.guild_id, status)
        
        if not campaigns:
            await interaction.followup.send("No campaigns found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📢 Campaigns",
            description=f"Found {len(campaigns)} campaign(s)",
            color=discord.Color.blue()
        )
        
        for campaign in campaigns[:10]:  # Show max 10
            response_count = await db.campaigns.get_response_count(campaign['id'])
            embed.add_field(
                name=f"{campaign['name']} (ID: {campaign['id']})",
                value=f"**Status:** {campaign['status']}\n"
                      f"**Target:** {campaign['target_type']}\n"
                      f"**Responses:** {response_count}\n"
                      f"**Created:** <t:{int(discord.utils.parse_time(campaign['created_at']).timestamp())}:R>",
                inline=False
            )
        
        if len(campaigns) > 10:
            embed.set_footer(text=f"Showing 10 of {len(campaigns)} campaigns")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @campaign.subcommand(name="set_targets", description="Set target roles or users for a campaign")
    @admin_or_specific_user()
    async def set_targets(
        self,
        interaction: discord.Interaction,
        campaign_id: int = SlashOption(
            name="campaign_id",
            description="The ID of the campaign",
            required=True
        ),
        roles: str = SlashOption(
            name="roles",
            description="Role mentions or IDs (comma-separated, e.g., @Role1,@Role2)",
            required=False
        ),
        users: str = SlashOption(
            name="users",
            description="User mentions or IDs (comma-separated, e.g., @User1,@User2)",
            required=False
        )
    ):
        """Set target roles or users for a campaign"""
        await interaction.response.defer(ephemeral=True)
        
        campaign = await db.campaigns.get_campaign(campaign_id, interaction.guild_id)
        if not campaign:
            await interaction.followup.send("❌ Campaign not found.", ephemeral=True)
            return
        
        role_ids = []
        user_ids = []
        if roles:
            import re
            role_matches = re.findall(r'<@&(\d+)>|(\d+)', roles)
            for match in role_matches:
                role_id = int(match[0] or match[1])
                role = interaction.guild.get_role(role_id)
                if role:
                    role_ids.append(role_id)
        if users:
            import re
            user_matches = re.findall(r'<@!?(\d+)>|(\d+)', users)
            for match in user_matches:
                user_id = int(match[0] or match[1])
                user_ids.append(user_id)
        role_ids_json = json.dumps(role_ids) if role_ids else None
        user_ids_json = json.dumps(user_ids) if user_ids else None
        
        query = "UPDATE campaigns SET target_role_ids = ?, target_user_ids = ? WHERE id = ?"
        await db.connection.execute_write(query, (role_ids_json, user_ids_json, campaign_id))
        
        embed = discord.Embed(
            title="✅ Targets Updated",
            description="Campaign targets have been set.",
            color=discord.Color.green()
        )
        
        if role_ids:
            roles_text = ", ".join([f"<@&{rid}>" for rid in role_ids])
            embed.add_field(name="Target Roles", value=roles_text, inline=False)
        
        if user_ids:
            users_text = ", ".join([f"<@{uid}>" for uid in user_ids])
            embed.add_field(name="Target Users", value=users_text[:1024], inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @campaign.subcommand(name="add_button", description="Add a button to a campaign")
    @admin_or_specific_user()
    async def add_button(
        self,
        interaction: discord.Interaction,
        campaign_id: int = SlashOption(
            name="campaign_id",
            description="The ID of the campaign",
            required=True
        )
    ):
        """Add a button to a campaign"""
        campaign = await db.campaigns.get_campaign(campaign_id, interaction.guild_id)
        if not campaign:
            await interaction.response.send_message(
                "❌ Campaign not found or doesn't belong to this server.",
                ephemeral=True
            )
            return
        
        modal = AddButtonModal(campaign_id)
        await interaction.response.send_modal(modal)

    @campaign.subcommand(name="add_form", description="Add form fields to a button")
    @admin_or_specific_user()
    async def add_form(
        self,
        interaction: discord.Interaction,
        form_id: int = SlashOption(
            name="form_id",
            description="The button/form ID to add fields to",
            required=True
        ),
        modal_title: str = SlashOption(
            name="modal_title",
            description="Title for the form modal",
            required=True
        ),
        field1_name: str = SlashOption(
            name="field1_name",
            description="Field 1 internal name (e.g., 'name')",
            required=True
        ),
        field1_label: str = SlashOption(
            name="field1_label",
            description="Field 1 display label",
            required=True
        ),
        field2_name: Optional[str] = SlashOption(
            name="field2_name",
            description="Field 2 internal name",
            required=False
        ),
        field2_label: Optional[str] = SlashOption(
            name="field2_label",
            description="Field 2 display label",
            required=False
        ),
        field3_name: Optional[str] = SlashOption(
            name="field3_name",
            description="Field 3 internal name",
            required=False
        ),
        field3_label: Optional[str] = SlashOption(
            name="field3_label",
            description="Field 3 display label",
            required=False
        ),
        response_channel: Optional[discord.TextChannel] = SlashOption(
            name="response_channel",
            description="Channel to send responses to",
            required=False
        )
    ):
        """Add form fields to a button"""
        await interaction.response.defer(ephemeral=True)
        form = await db.campaigns.get_form(form_id)
        if not form:
            await interaction.followup.send("❌ Button/Form not found.", ephemeral=True)
            return
        form_fields = []
        
        if field1_name and field1_label:
            form_fields.append({
                'name': field1_name,
                'label': field1_label,
                'required': True,
                'multiline': False
            })
        
        if field2_name and field2_label:
            form_fields.append({
                'name': field2_name,
                'label': field2_label,
                'required': True,
                'multiline': False
            })
        
        if field3_name and field3_label:
            form_fields.append({
                'name': field3_name,
                'label': field3_label,
                'required': True,
                'multiline': False
            })
        form_fields_json = json.dumps(form_fields)
        query = """
            UPDATE campaign_forms 
            SET has_form = 1, modal_title = ?, form_fields = ?, response_channel_id = ?
            WHERE id = ?
        """
        await db.connection.execute_write(
            query,
            (modal_title,
            form_fields_json,
            response_channel.id if response_channel else None,
            form_id)
        )
        
        embed = discord.Embed(
            title="✅ Form Fields Added",
            description=f"Added {len(form_fields)} field(s) to button.",
            color=discord.Color.green()
        )
        embed.add_field(name="Modal Title", value=modal_title, inline=False)
        
        for i, field in enumerate(form_fields, 1):
            embed.add_field(
                name=f"Field {i}",
                value=f"**Name:** `{field['name']}`\n**Label:** {field['label']}",
                inline=True
            )
        
        if response_channel:
            embed.add_field(
                name="Response Channel",
                value=response_channel.mention,
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @campaign.subcommand(name="preview", description="Preview a campaign message")
    @admin_or_specific_user()
    async def preview_campaign(
        self,
        interaction: discord.Interaction,
        campaign_id: int = SlashOption(
            name="campaign_id",
            description="The ID of the campaign to preview",
            required=True
        )
    ):
        """Preview what the campaign will look like"""
        await interaction.response.defer(ephemeral=True)
        
        campaign = await db.campaigns.get_campaign(campaign_id, interaction.guild_id)
        if not campaign:
            await interaction.followup.send("❌ Campaign not found.", ephemeral=True)
            return
        buttons = await db.campaigns.get_campaign_forms(campaign_id)
        content = campaign.get('message_content')
        embed = None
        
        if campaign.get('embed_title') or campaign.get('embed_description'):
            embed = discord.Embed(
                title=campaign.get('embed_title'),
                description=campaign.get('embed_description'),
                color=campaign.get('embed_color') or discord.Color.blue()
            )
            if campaign.get('embed_image_url'):
                embed.set_image(url=campaign['embed_image_url'])
            if campaign.get('embed_thumbnail_url'):
                embed.set_thumbnail(url=campaign['embed_thumbnail_url'])
        view = None
        if buttons:
            view = CampaignMessageView(campaign_id, buttons)
        
        await interaction.followup.send(
            content=f"**Preview of Campaign: {campaign['name']}**\n\n" + (content or ""),
            embed=embed,
            view=view,
            ephemeral=True
        )

    @campaign.subcommand(name="send", description="Send a campaign")
    @admin_or_specific_user()
    async def send_campaign(
        self,
        interaction: discord.Interaction,
        campaign_id: int = SlashOption(
            name="campaign_id",
            description="The ID of the campaign to send",
            required=True
        ),
        channel: Optional[discord.TextChannel] = SlashOption(
            name="channel",
            description="Channel to send to (required if target is 'channel')",
            required=False
        )
    ):
        """Send a campaign to DMs or a channel"""
        await interaction.response.defer(ephemeral=True)
        
        campaign = await db.campaigns.get_campaign(campaign_id, interaction.guild_id)
        if not campaign:
            await interaction.followup.send("❌ Campaign not found.", ephemeral=True)
            return
        buttons = await db.campaigns.get_campaign_forms(campaign_id)
        content = campaign.get('message_content')
        embed = None
        
        if campaign.get('embed_title') or campaign.get('embed_description'):
            embed = discord.Embed(
                title=campaign.get('embed_title'),
                description=campaign.get('embed_description'),
                color=campaign.get('embed_color') or discord.Color.blue()
            )
            if campaign.get('embed_image_url'):
                embed.set_image(url=campaign['embed_image_url'])
            if campaign.get('embed_thumbnail_url'):
                embed.set_thumbnail(url=campaign['embed_thumbnail_url'])
        view = None
        if buttons:
            view = CampaignMessageView(campaign_id, buttons)
        
        success_count = 0
        fail_count = 0
        recipients = []
        
        if campaign['target_type'] == 'dm':
            recipients = [m for m in interaction.guild.members if not m.bot]
            
        elif campaign['target_type'] == 'roles':
            if campaign.get('target_role_ids'):
                role_ids = campaign['target_role_ids']  # Already parsed by repository
                for member in interaction.guild.members:
                    if member.bot:
                        continue
                    if any(role.id in role_ids for role in member.roles):
                        recipients.append(member)
            else:
                await interaction.followup.send(
                    "❌ No target roles set. Use `/campaign set_targets` first.",
                    ephemeral=True
                )
                return
                
        elif campaign['target_type'] == 'users':
            if campaign.get('target_user_ids'):
                user_ids = campaign['target_user_ids']  # Already parsed by repository
                for user_id in user_ids:
                    member = interaction.guild.get_member(user_id)
                    if member and not member.bot:
                        recipients.append(member)
            else:
                await interaction.followup.send(
                    "❌ No target users set. Use `/campaign set_targets` first.",
                    ephemeral=True
                )
                return
        
        if campaign['target_type'] in ['dm', 'roles', 'users']:
            
            status_msg = await interaction.followup.send(
                f"📤 Sending DMs... (0/{len(recipients)})",
                ephemeral=True
            )
            
            for i, member in enumerate(recipients):
                try:
                    await member.send(content=content, embed=embed, view=view)
                    success_count += 1
                except Exception:
                    fail_count += 1
                if (i + 1) % 10 == 0:
                    try:
                        await status_msg.edit(
                            content=f"📤 Sending DMs... ({i + 1}/{len(recipients)})\n"
                                   f"✅ Sent: {success_count} | ❌ Failed: {fail_count}"
                        )
                    except Exception:
                        pass
            await status_msg.edit(
                content=f"✅ Campaign sent!\n"
                       f"**Successful:** {success_count}\n"
                       f"**Failed:** {fail_count}"
            )
            
        elif campaign['target_type'] == 'channel':
            if not channel:
                await interaction.followup.send(
                    "❌ Please specify a channel for channel-type campaigns.",
                    ephemeral=True
                )
                return
            
            try:
                await channel.send(content=content, embed=embed, view=view)
                await interaction.followup.send(
                    f"✅ Campaign sent to {channel.mention}!",
                    ephemeral=True
                )
                success_count = 1
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Failed to send campaign: {str(e)}",
                    ephemeral=True
                )
                fail_count = 1
        if success_count > 0:
            await db.campaigns.update_campaign_status(campaign_id, 'sent')

    @campaign.subcommand(name="delete", description="Delete a campaign")
    @admin_or_specific_user()
    async def delete_campaign(
        self,
        interaction: discord.Interaction,
        campaign_id: int = SlashOption(
            name="campaign_id",
            description="The ID of the campaign to delete",
            required=True
        )
    ):
        """Delete a campaign"""
        campaign = await db.campaigns.get_campaign(campaign_id, interaction.guild_id)
        if not campaign:
            await interaction.response.send_message(
                "❌ Campaign not found.",
                ephemeral=True
            )
            return
        
        await db.campaigns.delete_campaign(campaign_id, interaction.guild_id)
        
        await interaction.response.send_message(
            f"✅ Campaign **{campaign['name']}** has been deleted.",
            ephemeral=True
        )

    @campaign.subcommand(name="responses", description="View responses for a campaign")
    @admin_or_specific_user()
    async def view_responses(
        self,
        interaction: discord.Interaction,
        campaign_id: int = SlashOption(
            name="campaign_id",
            description="The ID of the campaign",
            required=True
        )
    ):
        """View form responses for a campaign"""
        await interaction.response.defer(ephemeral=True)
        
        responses = await db.campaigns.get_responses(campaign_id=campaign_id)
        
        if not responses:
            await interaction.followup.send("No responses found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 Campaign Responses",
            description=f"Total responses: {len(responses)}",
            color=discord.Color.blue()
        )
        
        for response in responses[:10]:  # Show max 10
            user = interaction.guild.get_member(response['user_id'])
            user_name = user.name if user else f"User {response['user_id']}"
            
            response_data = response.get('response_data', {})
            response_text = "\n".join([f"**{k}:** {v}" for k, v in response_data.items()])
            
            embed.add_field(
                name=f"{user_name}",
                value=response_text[:1024] if response_text else "No data",
                inline=False
            )
        
        if len(responses) > 10:
            embed.set_footer(text=f"Showing 10 of {len(responses)} responses")
        
        await interaction.followup.send(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(CampaignCog(bot))
