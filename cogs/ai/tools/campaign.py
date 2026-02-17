"""
Campaign management tools for the AI cog.
Allows AI to create mass messaging campaigns and forms.
These require admin permissions.
"""
import logging
import json
import nextcord as discord
from database import db
from cogs.campaign_views import CampaignMessageView

logger = logging.getLogger(__name__)


async def create_campaign_tool(
    name: str,
    message_content: str = None,
    embed_title: str = None,
    embed_description: str = None,
    target_type: str = 'dm',
    target_role_ids: str = None,
    target_user_ids: str = None,
    **kwargs
):
    """
    Create a new mass messaging campaign.
    
    Args:
        name: Campaign name/title
        message_content: The message text to send (optional if using embed)
        embed_title: Title for an embed (optional)
        embed_description: Description for an embed (optional)
        target_type: 'dm' for all members, 'channel' for channel, 'roles' for specific roles, 'users' for specific users
        target_role_ids: JSON array of role IDs for 'roles' type. Example: '[123456789, 987654321]'
        target_user_ids: JSON array of user IDs for 'users' type. Example: '[111111111, 222222222]'
        target_channel_id: Channel ID to send to (if target_type='channel'). Pass as string. IF USER SAYS "HERE", use the current channel ID. IF USER LINKS A CHANNEL (e.g. #general), extract the ID. DO NOT HALLUCINATE IDs.
    
    Returns:
        Campaign ID and success message
    """
    guild_id = kwargs.get('guild_id')
    user_id = kwargs.get('user_id')
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)

    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to create campaigns."
    
    if not guild_id:
        return "❌ Error: This tool can only be used in a server."
    
    if target_type not in ['dm', 'channel', 'roles', 'users']:
        return "❌ Error: target_type must be 'dm', 'channel', 'roles', or 'users'."
    
    # Parse role/user IDs if provided
    role_ids = None
    user_ids = None
    
    if target_type == 'roles' and target_role_ids:
        try:
            role_ids = json.loads(target_role_ids)
        except:
            return "❌ Error: target_role_ids must be valid JSON array of role IDs."
    
    if target_type == 'users' and target_user_ids:
        try:
            user_ids = json.loads(target_user_ids)
        except:
            return "❌ Error: target_user_ids must be valid JSON array of user IDs."
    
    target_channel_id_int = None
    if kwargs.get('target_channel_id'):
        try:
            target_channel_id_int = int(str(kwargs.get('target_channel_id')).strip())
        except:
            pass

    try:
        campaign_id = await db.campaigns.create_campaign(
            guild_id=guild_id,
            name=name,
            created_by=user_id,
            message_content=message_content,
            embed_title=embed_title,
            embed_description=embed_description,
            target_type=target_type,
            target_channel_id=target_channel_id_int,
            target_role_ids=role_ids,
            target_user_ids=user_ids
        )
        
        return (
            f"✅ Campaign created successfully!\n\n"
            f"**Campaign ID:** {campaign_id}\n"
            f"**Name:** {name}\n"
            f"**Target:** {target_type}\n\n"
            f"Use `add_campaign_button` to add interactive buttons and forms to this campaign."
        )
    
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        return f"❌ Error creating campaign: {str(e)}"



async def add_campaign_button(
    campaign_id: int,
    button_label: str,
    button_style: str = 'primary',
    button_emoji: str = None,
    has_form: bool = False,
    modal_title: str = None,
    form_fields_json: str = None,
    response_channel_id: str = None,
    **kwargs
):
    """
    Add a button (with optional form) to a campaign.
    
    Args:
        campaign_id: The ID of the campaign to add the button to
        button_label: Text to display on the button
        button_style: Button color - 'primary' (blue), 'secondary' (gray), 'success' (green), 'danger' (red)
        button_emoji: Optional emoji for the button (e.g., '✅', '📝')
        has_form: Whether this button should show a form modal
        modal_title: Title for the form modal (required if has_form is True)
        form_fields_json: JSON string of form fields array. Each field needs 'name' and 'label'. 
                         Example: '[{"name": "email", "label": "Your Email"}, {"name": "phone", "label": "Phone Number"}]'
        response_channel_id: Channel ID where responses should be logged. YOU MUST ASK THE USER "Where should responses be sent?" before calling this tool. Pass as string. IF USER SAYS "HERE", use the current channel ID. IF USER LINKS A CHANNEL (e.g. #general), extract the ID. DO NOT HALLUCINATE IDs.
    
    Returns:
        Success message with form ID
    """
    guild_id = kwargs.get('guild_id')
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)

    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to modify campaigns."
    
    if not guild_id:
        return "❌ Error: This tool can only be used in a server."
    
    # Verify campaign exists and belongs to this guild
    campaign = await db.campaigns.get_campaign(campaign_id, guild_id)
    if not campaign:
        return "❌ Error: Campaign not found or doesn't belong to this server."
    
    if button_style not in ['primary', 'secondary', 'success', 'danger']:
        return "❌ Error: button_style must be 'primary', 'secondary', 'success', or 'danger'."
    
    if has_form and not modal_title:
        return "❌ Error: modal_title is required when has_form is True."
    
    # Parse and validate form_fields if provided
    form_fields = None
    if has_form and form_fields_json:
        try:
            form_fields = json.loads(form_fields_json)
        except json.JSONDecodeError:
            return "❌ Error: form_fields_json must be valid JSON."
        
        if not isinstance(form_fields, list):
            return "❌ Error: form_fields must be a JSON array of field objects."
        
        for field in form_fields:
            if not isinstance(field, dict) or 'name' not in field or 'label' not in field:
                return "❌ Error: Each form field must have 'name' and 'label' keys."

    response_channel_id_int = None
    if response_channel_id:
        try:
            response_channel_id_int = int(str(response_channel_id).strip())
        except ValueError:
            return "❌ Error: response_channel_id must be a valid ID."
    
    try:
        form_id = await db.campaigns.add_form(
            campaign_id=campaign_id,
            button_label=button_label,
            button_style=button_style,
            button_emoji=button_emoji,
            has_form=has_form,
            modal_title=modal_title,
            form_fields=form_fields if has_form else None,
            response_channel_id=response_channel_id_int
        )
        
        result = (
            f"✅ Button added successfully!\n\n"
            f"**Form ID:** {form_id}\n"
            f"**Label:** {button_label}\n"
            f"**Style:** {button_style}\n"
        )
        
        if has_form:
            result += f"**Form:** Yes ({len(form_fields or [])} field(s))\n"
            if response_channel_id_int:
                result += f"**Response Channel:** <#{response_channel_id_int}>\n"
        
        return result
    
    except Exception as e:
        logger.error(f"Error adding button: {e}")
        return f"❌ Error adding button: {str(e)}"


async def send_campaign(
    campaign_id: int,
    channel_id: str = None,
    **kwargs
):
    """
    Send a campaign to users (DM) or a channel.
    
    Args:
        campaign_id: The ID of the campaign to send
        channel_id: Required if the campaign target is 'channel' - the channel to send to. Pass as string. IF USER SAYS "HERE", use the current channel ID. IF USER LINKS A CHANNEL, extract the ID.
    
    Returns:
        Success message with send statistics
    """
    guild_id = kwargs.get('guild_id')
    guild = kwargs.get('guild')
    bot = kwargs.get('bot')
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)

    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to send campaigns."
    
    if not guild_id or not guild:
        return "❌ Error: This tool can only be used in a server."
    
    # Verify campaign exists
    campaign = await db.campaigns.get_campaign(campaign_id, guild_id)
    if not campaign:
        return "❌ Error: Campaign not found or doesn't belong to this server."
    
    # Get buttons
    buttons = await db.campaigns.get_campaign_forms(campaign_id)
    
    # Build message
    # Build message - Flattened (No Embeds) as requested
    content = campaign.get('message_content') or ""
    
    # Prepend title if exists
    if campaign.get('embed_title'):
        content = f"**{campaign.get('embed_title')}**\n{content}"
        
    # Append description if exists
    if campaign.get('embed_description'):
        content += f"\n\n{campaign.get('embed_description')}"
    
    # Append images as links (Discord will unfurl them usually, or user sees link)
    if campaign.get('embed_image_url'):
        content += f"\n{campaign['embed_image_url']}"
        
    if campaign.get('embed_thumbnail_url'):
         content += f"\n{campaign['embed_thumbnail_url']}"

    # Force no embed object
    embed = None
    
    # Create view with buttons
    view = None
    if buttons:
        view = CampaignMessageView(campaign_id, buttons)
    
    success_count = 0
    fail_count = 0
    
    # Determine recipients based on target type
    recipients = []
    
    if campaign['target_type'] == 'dm':
        # Send to all members
        recipients = [m for m in guild.members if not m.bot]
        
    elif campaign['target_type'] == 'roles':
        # Send to members with specific roles
        if campaign.get('target_role_ids'):
            role_ids = campaign['target_role_ids']  # Already parsed by repository
            for member in guild.members:
                if member.bot:
                    continue
                if any(role.id in role_ids for role in member.roles):
                    recipients.append(member)
        else:
            return "❌ Error: No target roles set for this campaign."
            
    elif campaign['target_type'] == 'users':
        # Send to specific users
        if campaign.get('target_user_ids'):
            user_ids = campaign['target_user_ids']  # Already parsed by repository
            for user_id in user_ids:
                member = guild.get_member(user_id)
                if member and not member.bot:
                    recipients.append(member)
        else:
            return "❌ Error: No target users set for this campaign."
    
    try:
        if campaign['target_type'] in ['dm', 'roles', 'users']:
            # Send DMs to recipients
            for member in recipients:
                try:
                    await member.send(content=content, embed=embed, view=view)
                    success_count += 1
                except:
                    fail_count += 1
            
            result = (
                f"✅ Campaign sent via DM!\n\n"
                f"**Successful:** {success_count}\n"
                f"**Failed:** {fail_count}\n"
                f"**Total:** {success_count + fail_count}"
            )
            
        elif campaign['target_type'] == 'channel':
            if not channel_id:
                return "❌ Error: channel_id is required for channel-type campaigns."
            
            try:
                channel_id_int = int(str(channel_id).strip())
                channel = guild.get_channel(channel_id_int)
                if not channel:
                    return f"❌ Error: Channel {channel_id} not found."
                
                await channel.send(content=content, embed=embed, view=view)
                result = f"✅ Campaign sent to <#{channel_id_int}>!"
                success_count = 1
            except ValueError:
                return "❌ Error: channel_id must be a valid ID."
        
        # Update campaign status
        if success_count > 0:
            await db.campaigns.update_campaign_status(campaign_id, 'sent')
        
        return result
    
    except Exception as e:
        logger.error(f"Error sending campaign: {e}")
        return f"❌ Error sending campaign: {str(e)}"


async def list_campaigns(**kwargs):
    """
    List all campaigns in the current server.
    
    Returns:
        List of campaigns with their details
    """
    guild_id = kwargs.get('guild_id')
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)

    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to view campaigns."
    
    if not guild_id:
        return "❌ Error: This tool can only be used in a server."
    
    try:
        campaigns = await db.campaigns.get_campaigns(guild_id)
        
        if not campaigns:
            return "No campaigns found in this server."
        
        result = f"**Campaigns in this server:**\n\n"
        
        for campaign in campaigns:
            response_count = await db.campaigns.get_response_count(campaign['id'])
            result += (
                f"**{campaign['name']}** (ID: {campaign['id']})\n"
                f"├ Status: {campaign['status']}\n"
                f"├ Target: {campaign['target_type']}\n"
                f"├ Responses: {response_count}\n"
                f"└ Created: {campaign['created_at']}\n\n"
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        return f"❌ Error listing campaigns: {str(e)}"


async def get_campaign_responses(campaign_id: int, **kwargs):
    """
    Get form responses for a campaign.
    
    Args:
        campaign_id: The ID of the campaign
    
    Returns:
        List of responses with user info and form data
    """
    guild_id = kwargs.get('guild_id')
    guild = kwargs.get('guild')
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)

    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to view responses."
    
    if not guild_id:
        return "❌ Error: This tool can only be used in a server."
    
    try:
        responses = await db.campaigns.get_responses(campaign_id=campaign_id, guild_id=guild_id)
        
        if not responses:
            return "No responses found for this campaign."
        
        result = f"**Campaign Responses ({len(responses)} total):**\n\n"
        
        for i, response in enumerate(responses[:20], 1):  # Limit to 20
            user = guild.get_member(response['user_id']) if guild else None
            user_name = user.name if user else f"User {response['user_id']}"
            
            response_data = response.get('response_data', {})
            response_text = "\n".join([f"  • {k}: {v}" for k, v in response_data.items()])
            
            result += f"{i}. **{user_name}**\n{response_text}\n\n"
        
        if len(responses) > 20:
            result += f"... and {len(responses) - 20} more responses"
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting responses: {e}")
        return f"❌ Error getting responses: {str(e)}"


# Tool declarations for Gemini
CAMPAIGN_TOOLS = [
    create_campaign_tool,
    add_campaign_button,
    send_campaign,
    list_campaigns,
    get_campaign_responses,
]
