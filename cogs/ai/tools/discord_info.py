"""
Safe, read-only tools for gathering detailed information about the Discord server, members, and channels.
Use these tools INSTEAD of execute_discord_code for simple information retrieval.
"""
from typing import Optional

import nextcord as discord


async def get_server_info(**kwargs) -> str:
    """
    Get detailed information about the current server (guild).
    Includes member count, verification level, creation date, role count, etc.
    """
    guild = kwargs.get('guild')
    if not guild:
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
    if not guild:
        return "Error: No server context."
    
    target = None
    async def find_member(uid, q):
        if uid:
            try:
                uid = int(str(uid).strip('<@!>'))
                return guild.get_member(uid) or await guild.fetch_member(uid)
            except Exception:
                pass
        if q:
             q = q.lower()
             return next((m for m in guild.members if q in m.name.lower() or q in m.display_name.lower()), None)
        return None

    target = await find_member(user_id, query)
    
    if not target:
        if not user_id and not query:
             target = kwargs.get('message').author if kwargs.get('message') else None
    
    if not target:
        return "Member not found."
        
    roles = [r.name for r in target.roles if r.name != "@everyone"]
    roles.reverse() # High rank first
    role_str = ", ".join(roles[:10])
    if len(roles) > 10:
        role_str += f" (+{len(roles)-10} more)"
    
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
    if not guild:
        return "Error: No server context."
    
    target = None
    if channel_id:
        try:
             cid = int(str(channel_id).strip('<#>'))
             target = guild.get_channel(cid)
        except Exception:
            pass
        
    if not target and query:
         target = next((c for c in guild.channels if query.lower() in c.name.lower()), None)
         
    if not target:
        target = kwargs.get('channel')
        
    if not target:
        return "Channel not found."

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
    kwargs.get('bot')
    if not guild:
        return "Error: No server context."
    member = None
    if user_id:
        try:
             uid = int(str(user_id).strip('<@!>'))
             member = guild.get_member(uid) or await guild.fetch_member(uid)
        except Exception as e:
            return f"Error finding user: {e}"
    else:
        member = guild.me # Bot itself
        
    if not member:
        return "Member not found."
    channel = None
    if channel_id:
         try:
             cid = int(str(channel_id).strip('<#>'))
             channel = guild.get_channel(cid)
         except Exception:
             pass
    else:
        channel = kwargs.get('channel')
        
    if not channel:
        return "Channel context missing."
    perms = channel.permissions_for(member)
    
    allowed = [p[0].replace('_', ' ').title() for p in perms if p[1]]
    [p[0].replace('_', ' ').title() for p in perms if not p[1]]
    
    is_admin = perms.administrator
    
    summary = f"**Permissions for {member.display_name} in #{channel.name}:**\n"
    if is_admin:
        summary += "✅ **ADMINISTRATOR** (Has all permissions)\n"
    else:
        key_perms = ['Manage Guild', 'Manage Roles', 'Manage Channels', 'Kick Members', 'Ban Members', 
                     'Send Messages', 'Embed Links', 'Attach Files', 'Manage Messages', 'Mention Everyone', 'Connect']
        
        summary += "**Key Allowed:**\n" + ", ".join([p for p in allowed if p in key_perms]) + "\n"
        
    return summary
    return summary

async def get_role_info(role_id: Optional[str] = None, query: Optional[str] = None, **kwargs) -> str:
    """
    Get detailed info about a role.
    """
    guild = kwargs.get('guild')
    if not guild:
        return "Error: No server context."
    
    target = None
    if role_id:
        try:
             rid = int(str(role_id).strip('<@&>'))
             target = guild.get_role(rid)
        except Exception:
            pass
        
    if not target and query:
         target = next((r for r in guild.roles if query.lower() in r.name.lower()), None)
         
    if not target:
        return "Role not found."

    perms = [p[0].replace('_', ' ').title() for p in target.permissions if p[1]]
    perm_summary = "All" if target.permissions.administrator else ", ".join(perms[:10])
    if len(perms) > 10 and not target.permissions.administrator:
        perm_summary += f" (+{len(perms)-10} more)"

    info = [
        f"**Role:** {target.name} (ID: {target.id})",
        f"**Color:** {target.color}",
        f"**Position:** {target.position}",
        f"**Hoisted:** {'Yes' if target.hoist else 'No'}",
        f"**Mentionable:** {'Yes' if target.mentionable else 'No'}",
        f"**Members:** {len(target.members)}",
        f"**Created:** {target.created_at.strftime('%Y-%m-%d')}",
        f"**Permissions:** {perm_summary}"
    ]
    return "\n".join(info)

async def get_channels(mode: str = "text", category_id: Optional[str] = None, **kwargs) -> str:
    """
    List channels in the server that the caller has permission to view.
    
    Args:
        mode: 'text', 'voice', 'category', or 'all'.
        category_id: Filter by category ID (optional).
    """
    guild = kwargs.get('guild')
    message = kwargs.get('message')
    if not guild or not message:
        return "Error: No server/user context."
    
    author = message.author
    
    channels = guild.channels
    target_channels = []
    if category_id:
         try:
             cid = int(str(category_id))
             channels = [c for c in channels if c.category_id == cid]
         except Exception:
             pass
    channels = [c for c in channels if c.permissions_for(author).view_channel]

    if mode == 'text':
        target_channels = [c for c in channels if isinstance(c, discord.TextChannel)]
    elif mode == 'voice':
        target_channels = [c for c in channels if isinstance(c, discord.VoiceChannel)]
    elif mode == 'category':
        target_channels = [c for c in channels if isinstance(c, discord.CategoryChannel)]
    else:
        target_channels = channels
    target_channels.sort(key=lambda c: c.position)
    
    if not target_channels:
        return "No accessible channels found matching criteria."
    lines = [f"**Channels ({mode}) visible to {author.display_name}:**"]
    for c in target_channels[:30]: # Limit to avoid huge messages
        lines.append(f"- {c.name} (ID: {c.id})")
        
    if len(target_channels) > 30:
        lines.append(f"... and {len(target_channels)-30} more.")
        
    return "\n".join(lines)

DISCORD_INFO_TOOLS = [
    get_server_info,
    get_member_info,
    get_channel_info,
    check_permissions,
    get_role_info,
    get_channels
]
