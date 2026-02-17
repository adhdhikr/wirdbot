# Mass Messaging & Forms Feature

A comprehensive system for creating mass DM/channel messages with interactive forms and buttons.

## Features

- **Mass Messaging**: Send messages to all server members, specific roles, or specific users via DM or to a channel
- **Role Targeting**: Send campaigns only to members with specific roles
- **User Targeting**: Send campaigns only to specific users
- **Interactive Buttons**: Add up to 25 buttons to any campaign message
- **Dynamic Forms**: Create forms that pop up as modals when users click buttons
- **Response Tracking**: Automatically collect and route form responses to designated channels
- **AI Integration**: The AI can create and manage campaigns for you (admin-only)

## Usage

### Method 1: Slash Commands (Manual)

#### 1. Create a Campaign
```
/campaign create target:dm
```
or
```
/campaign create target:channel
```
or
```
/campaign create target:roles
```
or
```
/campaign create ta
```
/campaign add_button campaign_id:1
```

This opens a modal where you specify:
- Button label
- Button style (primary, secondary, success, danger)
- Button emoji (optional)

#### 3. Add Form Fields to a Buttonrget:users
```

This opens a modal where you fill in:
- Campaign name
- Message content
- Embed title and description (optional)

#### 2. Set Targets (for roles or users campaigns)
```
/campaign set_targets campaign_id:1 roles:@Members,@VIP users:@John,@Jane
```

You can use role/user mentions or IDs (comma-separated).

#### 2. Add Buttons
```
/campaign add_button campaign_id:1
```

This opens a modal where you specify:
- Button label
- Button style (primary, secondary, success, danger)
- Button emoji (optional)

#### 3. Add Form Fields to a Button
```
/campaign add_form form_id:1 modal_title:"Signup Form" field1_name:email field1_label:"Your Email" response_channel:#responses
```

You can add up to 3 fields per command. Each field requires:
- Internal name (for database storage)
- Display label (shown to users)

Optional:
- `response_channel`: Where form submissions will be sent

#### 4. Preview the Campaign
```
/campaign preview campaign_id:1
```

Shows you exactly what the campaign will look like.

#### 5. Send the Campaign
```
/campaign send campaign_id:1
```

For channel campaigns:
```
/campaign send campaign_id:1 channel:#announcements
```

#### 6. View Responses
```
/campaign responses campaign_id:1
```

#### 7. Manage Campaigns
```
/campaign list
/campaign list status:draft
/campaign delete campaign_id:1
```

### Method 2: AI Assistant (Recommended)

The AI can create entire campaigns for you. Simply ask:

> "Create a campaign that only sends to members with the @VIP role"

> "Send a message to @User1, @User2, and @User3 asking for their availability"

The AI has access to these tools:
- `create_campaign_tool` - Creates a new campaign (supports dm, channel, roles, users)
> "Create a weekly announcement campaign that DMs all members with a signup button"

> "Make a campaign with a feedback form that has fields for name, email, and feedback"

> "Create a server-wide announcement in #general with buttons for Yes, No, and Maybe"

> "Create a participation campaign with a Oui button that asks for phone number and a No button with no form"

The AI has access to these tools:
- `create_campaign_tool` - Creates a new campaign
- `add_campaign_button` - Adds buttons and forms (uses JSON for form fields)
- `send_campaign` - Sends the campaign
- `list_campaigns` - Lists all campaigns
- `get_campaign_responses` - Views responses

## Campaign Structure


3. **Role Campaigns** (`target_type: roles`)
   - Sends DMs only to members with specific roles
   - Use `/campaign set_targets` to specify which roles
   - Members with any of the specified roles will receive it

4. **User Campaigns** (`target_type: users`)
   - Sends DMs only to specific users
   - Use `/campaign set_targets` to specify which users
   - Only listed users will receive the campaign
### Campaign Types

1. **DM Campaigns** (`target_type: dm`)
   - Sends the message to all server members via direct message
   - Shows success/failure statistics
   - Skips bots automatically

2. **Channel Campaigns** (`target_type: channel`)
   - Sends the message to a specific channel
   - Requires channel selection on send

### Button Types

1. **Simple Button** (`has_form: false`)
   - Just acknowledges when clicked
   - No form shown

2. **Form Button** (`has_form: true`)
   - Shows a modal with form fields
   - Collects user input
   - Saves responses to database
   - Optionally sends to a response channel

### Form Fields

Each form can have up to 5 fields with:
- `name`: Internal identifier (e.g., "email")
- `label`: Display text (e.g., "Your Email Address")
- `required`: Whether the field is mandatory (default: true)
- `multiline`: Short vs. paragraph style (default: false)
- `min_length`/`max_length`: Character limits
- `placeholder`: Hint text

## Database Schema

### Tables

1. **campaigns** - Stores campaign configurations
2. **campaign_forms** - Stores button/form definitions
3. **campaign_responses** - Stores user submissions

### Campaign Status

- `draft`: Not yet sent
- `sent`: Successfully sent
- `archived`: Archived for historical purposes

## Examples

### Example 1: Simple Announcement

```python
# AI can do this:
# "Create a simple announcement campaign"

campaign_id = create_campaign_tool(
    name="Weekly Update",
    message_content="Check out this week's updates!",
    embed_title="📢 Weekly Announcement",
    embed_description="We have exciting news to share!",
    target_type="channel"
)

send_campaign(campaign_id, channel_id=123456789)
```

### Example 2: Event RSVP

```python
# AI can do this:
# "Create an RSVP form for the community event"

campaign_id = create_campaign_tool(
    name="Event RSVP",
    embed_title="🎉 Community Event",
    embed_description="Join us for our monthly meetup!",
    target_type="dm"
)

add_campaign_button(
    campaign_id,
    button_label="RSVP Now",
    button_style="success",
    button_emoji="✅",
    has_form=True,
    modal_title="Event Registration",
    form_fields_json='[{"name": "name", "label": "Full Name"}, {"name": "dietary", "label": "Dietary Restrictions"}]',
    response_channel_id=987654321
)

send_campaign(campaign_id)
```

### Example 3: Multi-Button Poll

```python
# AI can do this:
# "Create a poll asking which game to play"

campaign_id = create_campaign_tool(
    name="Game Poll",
    message_content="Vote for what game we should play this weekend!",
    target_type="channel"
)

add_campaign_button(campaign_id, button_label="Minecraft", button_style="success", button_emoji="⛏️")
add_campaign_button(campaign_id, button_label="Valorant", button_style="danger", button_emoji="🎯")
add_campaign_button(campaign_id, button_label="League", button_style="primary", button_emoji="⚔️")

send_campaign(campaign_id, channel_id=123456789)
```

## Permissions

All campaign commands require:
- **Admin permissions** (`manage_channels`)
- Or be the bot owner (ID: 1030575337869955102)

## Response Handling

When a user submits a form:
1. Response is saved to `campaign_responses` table
2. User receives a confirmation message (ephemeral)
3. If configured, an embed is sent to the response channel with:
   - User information
   - All form field responses
   - Timestamp

## Best Practices

1. **Test First**: Always use `/campaign preview` before sending
2. **Clear Labels**: Use descriptive button and form field labels
3. **Response Channels**: Set up dedicated channels for form responses
4. **Embed Design**: Use embeds for better visual appeal
5. **Field Limits**: Keep forms short (max 5 fields) for better user experience

## Limitations

- Maximum 25 buttons per campaign
- Maximum 5 form fields per button
- Form fields have Discord's text input limits (max 1024 characters)
- DM campaigns may fail for users with DMs disabled (counted in statistics)

## Troubleshooting

**Campaign not sending?**
- Check bot permissions in target channel
- Verify campaign ID is correct
- For DMs, some failures are normal (users with DMs disabled)

**Forms not showing?**
- Ensure `has_form` is set to `true`
- Verify form fields are properly formatted
- Check that modal_title is set

**Responses not appearing in channel?**
- Verify bot has send permissions in response channel
- Check that response_channel_id is correct
- Ensure channel still exists

## Migration

The feature requires the migration file:
- `014_create_mass_campaigns.sql`

This is automatically applied when the bot starts.
