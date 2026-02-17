"""Campaign views and modals for mass messaging system"""
import nextcord as discord
from nextcord.ui import View, Button, Modal, TextInput, Select
from typing import Optional, Dict, List, Any
import json
import logging
from database import db

logger = logging.getLogger(__name__)


class CampaignFormModal(Modal):
    """Dynamic modal for campaign forms"""
    
    def __init__(self, form_config: Dict[str, Any], campaign_id: int):
        super().__init__(title=form_config.get('modal_title', 'Form'), timeout=None)
        
        self.form_id = form_config['id']
        self.campaign_id = campaign_id
        self.response_channel_id = form_config.get('response_channel_id')
        self.form_fields = form_config.get('form_fields', [])
        
        # Add form fields dynamically (max 5 per modal)
        for field_config in self.form_fields[:5]:
            field = TextInput(
                label=field_config.get('label', 'Input'),
                placeholder=field_config.get('placeholder', ''),
                required=field_config.get('required', True),
                min_length=field_config.get('min_length'),
                max_length=field_config.get('max_length', 1024),
                style=discord.TextInputStyle.paragraph if field_config.get('multiline', False) else discord.TextInputStyle.short
            )
            # Store field name as custom_id for retrieval
            field.custom_id = field_config.get('name', f'field_{len(self.children)}')
            self.add_item(field)
    
    async def callback(self, interaction: discord.Interaction):
        """Handle form submission"""
        logger.info(f"Form submission received from user {interaction.user.id} for campaign {self.campaign_id}")
        
        # Collect responses
        response_data = {}
        for child in self.children:
            if isinstance(child, TextInput):
                response_data[child.custom_id] = child.value
        
        # Check for duplicate submission (per campaign)
        try:
            existing = await db.campaigns.get_responses(
                # form_id=self.form_id, # Check against campaign, not just form
                user_id=interaction.user.id,
                campaign_id=self.campaign_id
            )
            if existing:
                logger.info(f"Duplicate submission blocked for user {interaction.user.id} in campaign {self.campaign_id}")
                await interaction.response.send_message(
                    "⚠️ You have already submitted a response for this campaign.",
                    ephemeral=True
                )
                return
        except Exception as e:
            logger.error(f"Error checking for duplicate response: {e}")
            pass  # Continue if check fails
        
        # Save to database
        try:
            await db.campaigns.save_response(
                form_id=self.form_id,
                campaign_id=self.campaign_id,
                user_id=interaction.user.id,
                guild_id=interaction.guild_id or 0,
                response_data=response_data
            )
            logger.info(f"Response saved for user {interaction.user.id} in campaign {self.campaign_id}")
            
            # Send confirmation to user
            await interaction.response.send_message(
                "✅ Your response has been submitted! Thank you.", 
                ephemeral=True
            )
            
            # Send response to designated channel if configured
            if self.response_channel_id:
                channel = None
                try:
                    # 1. Try to get guild from interaction
                    guild = interaction.guild
                    
                    # 2. If no guild in interaction (e.g. DM), try to find it from campaign data
                    if not guild:
                        try:
                            # We need to fetch the campaign to know which guild it belongs to
                            # This is a bit expensive but necessary for DMs
                            campaign = await db.campaigns.get_campaign(self.campaign_id)
                            if campaign and campaign.get('guild_id'):
                                guild = interaction.client.get_guild(campaign['guild_id'])
                                if not guild:
                                    try:
                                        guild = await interaction.client.fetch_guild(campaign['guild_id'])
                                    except:
                                        pass
                        except Exception as e:
                            logger.error(f"Error fetching campaign guild for response: {e}")

                    # 3. Now try to find the channel using the best available method
                    if guild:
                        channel = guild.get_channel(self.response_channel_id)
                        if not channel:
                            try:
                                channel = await guild.fetch_channel(self.response_channel_id)
                            except:
                                pass
                    
                    # 4. Fallback to global client fetch (works if bot shares server)
                    if not channel:
                        channel = interaction.client.get_channel(self.response_channel_id)
                        if not channel:
                            try:
                                channel = await interaction.client.fetch_channel(self.response_channel_id)
                            except Exception as e:
                                logger.warning(f"Final attempt to fetch channel {self.response_channel_id} failed: {e}")
                    
                    if channel:
                        logger.info(f"Sending notification to channel {channel.id} in guild {channel.guild.name if channel.guild else 'Unknown'}")
                        
                        # Build plain text message
                        msg_content = f"📝 **New Form Response**\n"
                        msg_content += f"**User:** {interaction.user.name} (`{interaction.user.id}`)\n"
                        msg_content += f"**Campaign ID:** {self.campaign_id}\n\n"
                        
                        for field_name, field_value in response_data.items():
                            # Find the label for this field
                            field_label = field_name
                            for field_config in self.form_fields:
                                if field_config.get('name') == field_name:
                                    field_label = field_config.get('label', field_name)
                                    break
                            
                            msg_content += f"**{field_label}:**\n{field_value}\n"
                        
                        msg_content += f"\n*Submitted: {discord.utils.format_dt(discord.utils.utcnow())}*"
                        
                        try:
                            await channel.send(content=msg_content)
                        except Exception as e:
                            logger.error(f"Failed to send notification to channel: {e}")
                    else:
                        logger.error(f"Could not find response channel {self.response_channel_id} (Guild: {guild.id if guild else 'None'})")
                        
                        # Fallback: DM the campaign creator
                        try:
                            # 1. Fetch campaign to get creator ID
                            campaign = await db.campaigns.get_campaign(self.campaign_id)
                            if campaign and campaign.get('created_by'):
                                creator_id = campaign['created_by']
                                creator = interaction.client.get_user(creator_id)
                                if not creator:
                                    try:
                                        creator = await interaction.client.fetch_user(creator_id)
                                    except:
                                        pass
                                
                                if creator:
                                    logger.info(f"Sending fallback notification to campaign creator {creator.id}")
                                    
                                    # Build plain text message with warning
                                    msg_content = f"⚠️ **WARNING: Could not find response channel <#{self.response_channel_id}>**\n"
                                    msg_content += f"Sending response here as fallback.\n\n"
                                    msg_content += f"📝 **New Form Response**\n"
                                    msg_content += f"**User:** {interaction.user.name} (`{interaction.user.id}`)\n"
                                    msg_content += f"**Campaign ID:** {self.campaign_id}\n\n"
                                    
                                    for field_name, field_value in response_data.items():
                                        # Find the label for this field
                                        field_label = field_name
                                        for field_config in self.form_fields:
                                            if field_config.get('name') == field_name:
                                                field_label = field_config.get('label', field_name)
                                                break
                                        
                                        msg_content += f"**{field_label}:**\n{field_value}\n"
                                    
                                    msg_content += f"\n*Submitted: {discord.utils.format_dt(discord.utils.utcnow())}*"
                                    
                                    try:
                                        await creator.send(content=msg_content)
                                    except Exception as e:
                                        logger.error(f"Failed to send fallback notification to creator: {e}")
                                else:
                                    logger.error(f"Campaign creator {creator_id} not found for fallback.")
                        except Exception as e:
                            logger.error(f"Error in response channel fallback: {e}")
                except Exception as e:
                    logger.error(f"Error resolving response channel: {e}")
        
        except Exception as e:
            logger.error(f"Error executing callback: {e}")
            # Only try to respond if we haven't already
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Error submitting response: {str(e)}", 
                    ephemeral=True
                )
            else:
                # Already responded, send followup instead
                try:
                    await interaction.followup.send(
                        f"❌ Error submitting response: {str(e)}",
                        ephemeral=True
                    )
                except:
                    pass


class CampaignMessageView(View):
    """View with buttons for campaign messages"""
    
    def __init__(self, campaign_id: int, buttons_config: List[Dict[str, Any]]):
        super().__init__(timeout=None)
        
        self.campaign_id = campaign_id
        
        # Add buttons dynamically
        for btn_config in buttons_config[:25]:  # Max 25 buttons
            style_map = {
                'primary': discord.ButtonStyle.primary,
                'secondary': discord.ButtonStyle.secondary,
                'success': discord.ButtonStyle.success,
                'danger': discord.ButtonStyle.danger,
                'link': discord.ButtonStyle.link
            }
            
            button = Button(
                label=btn_config['button_label'],
                style=style_map.get(btn_config.get('button_style', 'primary'), discord.ButtonStyle.primary),
                emoji=btn_config.get('button_emoji'),
                custom_id=f"campaign_btn_{btn_config['id']}"
            )
            
            # Store form config in button for callback
            button.form_config = btn_config
            button.callback = self.create_button_callback(btn_config)
            
            self.add_item(button)
    
    def create_button_callback(self, form_config: Dict[str, Any]):
        """Create a callback for a button"""
        async def button_callback(interaction: discord.Interaction):
            logger.info(f"Button '{form_config['button_label']}' pressed by user {interaction.user.id} for campaign {self.campaign_id}")
            
            # Check for duplicate submission (per campaign) - BEFORE doing anything else
            try:
                existing = await db.campaigns.get_responses(
                    # form_id=form_config['id'],
                    user_id=interaction.user.id,
                    campaign_id=self.campaign_id
                )
                if existing:
                    logger.info(f"Duplicate button click blocked for user {interaction.user.id} in campaign {self.campaign_id}")
                    await interaction.response.send_message(
                        "⚠️ You have already responded to this campaign.",
                        ephemeral=True
                    )
                    return
            except Exception as e:
                logger.error(f"Error checking for duplicates: {e}")
                pass

            if form_config.get('has_form'):
                # Show modal
                modal = CampaignFormModal(form_config, self.campaign_id)
                await interaction.response.send_modal(modal)
            else:
                # Save response
                try:
                    await db.campaigns.save_response(
                        form_id=form_config['id'],
                        campaign_id=self.campaign_id,
                        user_id=interaction.user.id,
                        guild_id=interaction.guild_id or 0,
                        response_data={'action': 'clicked', 'label': form_config['button_label']}
                    )
                    logger.info(f"Button click saved for user {interaction.user.id} in campaign {self.campaign_id}")

                    # Just acknowledge the button press
                    await interaction.response.send_message(
                        f"✅ {form_config['button_label']} registered!",
                        ephemeral=True
                    )

                    # Send notification to channel if configured
                    response_channel_id = form_config.get('response_channel_id')
                    # Send notification to channel if configured
                    response_channel_id = form_config.get('response_channel_id')
                    if response_channel_id:
                        channel = None
                        try:
                            # 1. Try to get guild from interaction
                            guild = interaction.guild
                            
                            # 2. If no guild in interaction (e.g. DM), try to find it from campaign data
                            if not guild:
                                try:
                                    # We need to fetch the campaign to know which guild it belongs to
                                    campaign = await db.campaigns.get_campaign(self.campaign_id)
                                    if campaign and campaign.get('guild_id'):
                                        guild = interaction.client.get_guild(campaign['guild_id'])
                                        if not guild:
                                            try:
                                                guild = await interaction.client.fetch_guild(campaign['guild_id'])
                                            except:
                                                pass
                                except Exception as e:
                                    logger.error(f"Error fetching campaign guild for button response: {e}")

                            # 3. Now try to find the channel using the best available method
                            if guild:
                                channel = guild.get_channel(response_channel_id)
                                if not channel:
                                    try:
                                        channel = await guild.fetch_channel(response_channel_id)
                                    except:
                                        pass
                            
                            # 4. Fallback to global client fetch
                            if not channel:
                                channel = interaction.client.get_channel(response_channel_id)
                                if not channel:
                                    try:
                                        channel = await interaction.client.fetch_channel(response_channel_id)
                                    except Exception as e:
                                        logger.warning(f"Final attempt to fetch channel {response_channel_id} failed: {e}")
                            
                            if channel:
                                logger.info(f"Sending button notification to channel {channel.id}")
                                
                                # Plain text notification
                                msg_content = f"👉 **New Button Click**\n"
                                msg_content += f"**User:** {interaction.user.name} (`{interaction.user.id}`)\n"
                                msg_content += f"**Campaign ID:** {self.campaign_id}\n"
                                msg_content += f"**Button:** {form_config['button_label']}\n"
                                msg_content += f"*Time: {discord.utils.format_dt(discord.utils.utcnow())}*"
                                
                                try:
                                    await channel.send(content=msg_content)
                                except Exception as e:
                                    logger.error(f"Failed to send notification: {e}")
                            else:
                                logger.error(f"Could not find response channel {response_channel_id}")
                                
                                # Fallback: DM the campaign creator
                                try:
                                    # 1. Fetch campaign to get creator ID
                                    campaign = await db.campaigns.get_campaign(self.campaign_id)
                                    if campaign and campaign.get('created_by'):
                                        creator_id = campaign['created_by']
                                        creator = interaction.client.get_user(creator_id)
                                        if not creator:
                                            try:
                                                creator = await interaction.client.fetch_user(creator_id)
                                            except:
                                                pass
                                        
                                        if creator:
                                            logger.info(f"Sending button fallback notification to campaign creator {creator.id}")
                                            
                                            # Plain text notification with warning
                                            msg_content = f"⚠️ **WARNING: Could not find response channel <#{response_channel_id}>**\n"
                                            msg_content += f"Sending response here as fallback.\n\n"
                                            msg_content += f"👉 **New Button Click**\n"
                                            msg_content += f"**User:** {interaction.user.name} (`{interaction.user.id}`)\n"
                                            msg_content += f"**Campaign ID:** {self.campaign_id}\n"
                                            msg_content += f"**Button:** {form_config['button_label']}\n"
                                            msg_content += f"*Time: {discord.utils.format_dt(discord.utils.utcnow())}*"
                                            
                                            try:
                                                await creator.send(content=msg_content)
                                            except Exception as e:
                                                logger.error(f"Failed to send fallback notification to creator: {e}")
                                        else:
                                            logger.error(f"Campaign creator {creator_id} not found for fallback.")
                                except Exception as e:
                                    logger.error(f"Error in button response channel fallback: {e}")
                        except Exception as e:
                            logger.error(f"Error handling response channel in button callback: {e}")

                except Exception as e:
                    logger.error(f"Error processing button click: {e}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message(
                            f"❌ Error registering response: {str(e)}",
                            ephemeral=True
                        )
        
        return button_callback


class CampaignCreationModal(Modal):
    """Modal for creating a new campaign"""
    
    def __init__(self, guild_id: int, created_by: int, target_type: str = 'dm'):
        super().__init__(title="Create New Campaign")
        
        self.guild_id = guild_id
        self.created_by = created_by
        self.target_type = target_type
        
        self.name_input = TextInput(
            label="Campaign Name",
            placeholder="e.g., Weekly Announcement",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)
        
        self.message_input = TextInput(
            label="Message Content",
            placeholder="The message to send (optional if using embed)",
            required=False,
            style=discord.TextInputStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.message_input)
        
        self.embed_title_input = TextInput(
            label="Embed Title (Optional)",
            placeholder="Leave empty for no embed",
            required=False,
            max_length=256
        )
        self.add_item(self.embed_title_input)
        
        self.embed_description_input = TextInput(
            label="Embed Description (Optional)",
            placeholder="Embed description text",
            required=False,
            style=discord.TextInputStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.embed_description_input)
    
    async def callback(self, interaction: discord.Interaction):
        """Create the campaign"""
        try:
            campaign_id = await db.campaigns.create_campaign(
                guild_id=self.guild_id,
                name=self.name_input.value,
                created_by=self.created_by,
                message_content=self.message_input.value or None,
                embed_title=self.embed_title_input.value or None,
                embed_description=self.embed_description_input.value or None,
                target_type=self.target_type
            )
            
            msg = (
                f"✅ **Campaign Created!**\n\n"
                f"**Name:** {self.name_input.value}\n"
                f"**Campaign ID:** {campaign_id}\n"
                f"**Target:** {'DMs' if self.target_type == 'dm' else 'Channel'}\n\n"
                f"Use `/admin campaign add_button` to add buttons/forms.\n"
                f"Use `/admin campaign send` to send the campaign."
            )
            
            await interaction.response.send_message(content=msg, ephemeral=True)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error creating campaign: {str(e)}",
                ephemeral=True
            )


class AddButtonModal(Modal):
    """Modal for adding a button/form to a campaign"""
    
    def __init__(self, campaign_id: int):
        super().__init__(title="Add Button to Campaign")
        
        self.campaign_id = campaign_id
        
        self.label_input = TextInput(
            label="Button Label",
            placeholder="e.g., Sign Up",
            required=True,
            max_length=80
        )
        self.add_item(self.label_input)
        
        self.style_input = TextInput(
            label="Button Style",
            placeholder="primary, secondary, success, danger",
            required=False,
            max_length=20,
            default_value="primary"
        )
        self.add_item(self.style_input)
        
        self.emoji_input = TextInput(
            label="Button Emoji (Optional)",
            placeholder="e.g., ✅",
            required=False,
            max_length=50
        )
        self.add_item(self.emoji_input)
    
    async def callback(self, interaction: discord.Interaction):
        """Add the button"""
        try:
            form_id = await db.campaigns.add_form(
                campaign_id=self.campaign_id,
                button_label=self.label_input.value,
                button_style=self.style_input.value or 'primary',
                button_emoji=self.emoji_input.value or None,
                has_form=False
            )
            
            msg = (
                f"✅ **Button Added!**\n\n"
                f"**Label:** {self.label_input.value}\n"
                f"**Form ID:** {form_id}\n\n"
                f"Use `/admin campaign add_form` to add form fields to this button."
            )
            
            await interaction.response.send_message(content=msg, ephemeral=True)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error adding button: {str(e)}",
                ephemeral=True
            )
