"""
Example: Creating a campaign with Yes/No buttons
- "Oui" button with phone number form
- "No" button without form
"""

# This is how you would ask the AI to create this campaign:

# Example 1: Using natural language (recommended)
"""
Create a campaign asking users if they want to participate.
Add a "Oui" button (green, success style) that shows a form asking only for their phone number.
Add a "No" button (red, danger style) with no form.
Send responses to #registrations channel.
"""

# Example 2: Using slash commands manually
"""
Step 1: Create the campaign
/campaign create target:dm

Fill in modal:
- Name: Participation Request
- Message: Do you want to participate in our event?
- Embed Title: 🎉 Event Participation
- Embed Description: Click below to let us know!

Step 2: Add "Oui" button with form
/campaign add_button campaign_id:1

Fill in modal:
- Button Label: Oui
- Button Style: success
- Button Emoji: ✅

This creates form ID 1. Then run:

/campaign add_form form_id:1 modal_title:"Contact Information" 
                 field1_name:phone field1_label:"Phone Number" 
                 response_channel:#registrations

Step 3: Add "No" button without form
/campaign add_button campaign_id:1

Fill in modal:
- Button Label: No
- Button Style: danger
- Button Emoji: ❌

Step 4: Preview
/campaign preview campaign_id:1

Step 5: Send
/campaign send campaign_id:1
"""

# Example 3: Using AI tools directly (what AI does behind the scenes)
"""
from cogs.ai.tools.campaign import create_campaign_tool, add_campaign_button, send_campaign

# Create campaign
campaign_id = await create_campaign_tool(
    name="Participation Request",
    message_content="Do you want to participate in our event?",
    embed_title="🎉 Event Participation", 
    embed_description="Click below to let us know!",
    target_type="dm",
    guild_id=YOUR_GUILD_ID,
    user_id=YOUR_USER_ID,
    is_admin=True
)

# Add "Oui" button with phone form
await add_campaign_button(
    campaign_id=1,
    button_label="Oui",
    button_style="success",
    button_emoji="✅",
    has_form=True,
    modal_title="Contact Information",
    form_fields_json='[{"name": "phone", "label": "Phone Number"}]',
    response_channel_id=CHANNEL_ID,
    guild_id=YOUR_GUILD_ID,
    is_admin=True
)

# Add "No" button without form
await add_campaign_button(
    campaign_id=1,
    button_label="No",
    button_style="danger",
    button_emoji="❌",
    has_form=False,
    guild_id=YOUR_GUILD_ID,
    is_admin=True
)

# Send the campaign
await send_campaign(
    campaign_id=1,
    guild_id=YOUR_GUILD_ID,
    guild=YOUR_GUILD,
    bot=YOUR_BOT,
    is_admin=True
)
"""
