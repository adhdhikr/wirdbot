"""
Safe, read-only tools for gathering detailed information about the Discord server, members, and channels.
Use these tools INSTEAD of execute_discord_code for simple information retrieval.
"""
import nextcord as discord
from typing import Optional

async def get_server_info(**kwargs) -> str:
    """
    Get detailed information about the current server (guild).
    Includes member count, verification level, creation date, role count, etc.
    """
    guild = kwargs.get('guild')
    if not guild:
         # Try logic to fetch if not directly in kwargs but usually injected
        return "Error: No server context found."

    owner = guild.owner
    created_at = guild.created_at.strftime("%Y-%m-%d")
    
    info = [
        f"**Server Name:** {guild.name} (ID: {guild.id})",
        f"**Owner:** {owner} (ID: {owner.id})",
        f"**Created:** {created_at}",
        f"**Members:** {guild.member_count}",
        f"**Roles:** {len(guild.roles)}",
        f"**Channels:** {len(guild.channels)} (Text: {len(guild.text_channels)}, Voice: {len(guild.voice_channels)})",
        f"**Verification:** {guild.verification_level}",
        f"**Boosts:** Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)"
    ]
    
    return "\n".join(info)

async def get_member_info(user_id: Optional[str] = None, query: Optional[str] = None, **kwargs) -> str:
    """
    Get detailed info about a server member.
    
    Args:
        user_id: The ID of the user (optional).
        query: Name or mention to search for if ID not provided (optional).
    """
    guild = kwargs.get('guild')
    if not guild: return "Error: No server context."
    
    target = None
    
    # helper to find member
    async def find_member(uid, q):
        if uid:
            try:
                # Stripping non-numeric just in case
                uid = int(str(uid).strip('<@!>'))
                return guild.get_member(uid) or await guild.fetch_member(uid)
            except:
                pass
        if q:
             q = q.lower()
             return next((m for m in guild.members if q in m.name.lower() or q in m.display_name.lower()), None)
        return None

    target = await find_member(user_id, query)
    
    if not target:
        # If no target specified, use the author
        if not user_id and not query:
             target = kwargs.get('message').author if kwargs.get('message') else None
    
    if not target:
        return "Member not found."
        
    roles = [r.name for r in target.roles if r.name != "@everyone"]
    roles.reverse() # High rank first
    role_str = ", ".join(roles[:10])
    if len(roles) > 10: role_str += f" (+{len(roles)-10} more)"
    
    joined = target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown"
    created = target.created_at.strftime("%Y-%m-%d")
    
    status = str(target.status).title()
    activity_str = "None"
    if target.activity:
        if isinstance(target.activity, discord.CustomActivity):
             activity_str = f"Custom: {target.activity.name}"
        else:
             activity_str = f"{target.activity.type.name.title()}: {target.activity.name}"

    info = [
        f"**User:** {target} (ID: {target.id})",
        f"**Display Name:** {target.display_name}",
        f"**Bot:** {'Yes' if target.bot else 'No'}",
        f"**Created:** {created}",
        f"**Joined:** {joined}",
        f"**Status:** {status}",
        f"**Activity:** {activity_str}",
        f"**Top Role:** {target.top_role.name}",
        f"**Roles:** {role_str}",
        f"**Avatar:** {target.display_avatar.url}"
    ]
    
    return "\n".join(info)

async def get_channel_info(channel_id: Optional[str] = None, query: Optional[str] = None, **kwargs) -> str:
    """
    Get info about a channel.
    """
    guild = kwargs.get('guild')
    if not guild: return "Error: No server context."
    
    target = None
    if channel_id:
        try:
             cid = int(str(channel_id).strip('<#>'))
             target = guild.get_channel(cid)
        except: pass
        
    if not target and query:
         target = next((c for c in guild.channels if query.lower() in c.name.lower()), None)
         
    if not target:
        # Use current channel
        target = kwargs.get('channel')
        
    if not target: return "Channel not found."

    info = [
        f"**Channel:** #{target.name} (ID: {target.id})",
        f"**Type:** {str(target.type)}",
        f"**Category:** {target.category.name if target.category else 'None'}",
        f"**Position:** {target.position}",
        f"**Created:** {target.created_at.strftime('%Y-%m-%d')}"
    ]
    
    if hasattr(target, 'topic') and target.topic:
        info.append(f"**Topic:** {target.topic}")
        
    if hasattr(target, 'members'):
         info.append(f"**Visible Members:** {len(target.members)}")
         
    return "\n".join(info)

async def check_permissions(user_id: Optional[str] = None, channel_id: Optional[str] = None, **kwargs) -> str:
    """
    Check permissions for a user (or the bot itself) in a specific channel context.
    
    Args:
        user_id: Target user ID to check. If None, checks the Bot's own permissions.
        channel_id: Target channel ID. If None, uses current channel.
    """
    guild = kwargs.get('guild')
    bot = kwargs.get('bot')
    if not guild: return "Error: No server context."
    
    # Determine target user
    member = None
    if user_id:
        try:
             uid = int(str(user_id).strip('<@!>'))
             member = guild.get_member(uid) or await guild.fetch_member(uid)
        except Exception as e:
            return f"Error finding user: {e}"
    else:
        member = guild.me # Bot itself
        
    if not member: return "Member not found."
    
    # Determine target channel
    channel = None
    if channel_id:
         try:
             cid = int(str(channel_id).strip('<#>'))
             channel = guild.get_channel(cid)
         except: pass
    else:
        channel = kwargs.get('channel')
        
    if not channel: return "Channel context missing."

    # Get permissions
    perms = channel.permissions_for(member)
    
    allowed = [p[0].replace('_', ' ').title() for p in perms if p[1]]
    denied = [p[0].replace('_', ' ').title() for p in perms if not p[1]]
    
    # Clean output - maybe just show important ones or a summary
    # Or return a condensed list
    
    is_admin = perms.administrator
    
    summary = f"**Permissions for {member.display_name} in #{channel.name}:**\n"
    if is_admin:
        summary += "✅ **ADMINISTRATOR** (Has all permissions)\n"
    else:
        # Highlight Key Perms
        key_perms = ['Manage Guild', 'Manage Roles', 'Manage Channels', 'Kick Members', 'Ban Members', 
                     'Send Messages', 'Embed Links', 'Attach Files', 'Manage Messages', 'Mention Everyone', 'Connect']
        
        summary += "**Key Allowed:**\n" + ", ".join([p for p in allowed if p in key_perms]) + "\n"
        
    return summary

DISCORD_INFO_TOOLS = [
    get_server_info,
    get_member_info,
    get_channel_info,
    check_permissions
]
