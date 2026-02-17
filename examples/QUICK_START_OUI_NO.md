"""
Quick Start: Oui/No Campaign with Phone Number Form

Just ask the AI:
"Create a participation campaign. Add a green 'Oui' button that asks for phone number, 
and a red 'No' button with no form. Send responses to #registrations."

The AI will execute these steps automatically:
"""

# Step 1: Create the campaign
campaign_id = await create_campaign_tool(
    name="Participation Request",
    embed_title="🎉 Join Our Event",
    embed_description="Would you like to participate? Click below!",
    target_type="dm"
)
# Returns: campaign_id = 1

# Step 2: Add "Oui" button with phone number form
await add_campaign_button(
    campaign_id=1,
    button_label="Oui",
    button_style="success",
    button_emoji="✅",
    has_form=True,
    modal_title="Contact Information",
    form_fields_json='[{"name": "phone", "label": "Phone Number"}]',
    response_channel_id=1234567890  # Your #registrations channel ID
)

# Step 3: Add "No" button (no form)
await add_campaign_button(
    campaign_id=1,
    button_label="No",
    button_style="danger",
    button_emoji="❌",
    has_form=False
)

# Step 4: Send to all members
await send_campaign(campaign_id=1)

# What users will see:
"""
┌─────────────────────────────┐
│  🎉 Join Our Event          │
│                             │
│  Would you like to          │
│  participate? Click below!  │
│                             │
│  [✅ Oui]    [❌ No]        │
└─────────────────────────────┘

When clicking "Oui":
┌─────────────────────────────┐
│  Contact Information        │
├─────────────────────────────┤
│  Phone Number *             │
│  ┌─────────────────────┐   │
│  │                     │   │
│  └─────────────────────┘   │
│                             │
│       [Cancel] [Submit]     │
└─────────────────────────────┘

When clicking "No":
✅ No registered! (ephemeral message)
"""
