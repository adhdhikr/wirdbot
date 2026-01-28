from database import db
import logging

logger = logging.getLogger(__name__)

async def remember_info(content: str, **kwargs) -> str:
    """
    Stores a piece of information in the user's long-term memory.
    
    Args:
        content: The fact or information to remember.
        **kwargs: Injected context (user_id, guild_id).
    """
    user_id = kwargs.get('user_id')
    guild_id = kwargs.get('guild_id')
    
    if not user_id or not guild_id:
        return "Error: Missing user or guild context."
        
    try:
        await db.add_user_memory(user_id, guild_id, content)
        return f"✅ I've remembered: '{content}'"
    except Exception as e:
        logger.error(f"Failed to remember: {e}")
        return f"Error saving memory: {e}"

async def get_my_memories(search_query: str = None, **kwargs) -> str:
    """
    Retrieves the user's memories.
    
    Args:
        search_query: Optional keywords to filter memories.
        **kwargs: Injected context.
    """
    user_id = kwargs.get('user_id')
    guild_id = kwargs.get('guild_id')
    
    if not user_id or not guild_id:
        return "Error: Context missing."
        
    try:
        if search_query:
            memories = await db.search_user_memories(user_id, guild_id, search_query)
        else:
            memories = await db.get_user_memories(user_id, guild_id, limit=10)
            
        if not memories:
            return "You have no saved memories."
            
        result = "**Your Memories:**\n"
        for mem in memories:
            result += f"- [ID: {mem['id']}] {mem['content']} ({mem['created_at']})\n"
            
        return result
    except Exception as e:
        return f"Error retrieving memories: {e}"

async def forget_memory(memory_id: int, **kwargs) -> str:
    """
    Deletes a specific memory by its ID.
    
    Args:
        memory_id: The ID of the memory to delete (found via get_my_memories).
        **kwargs: Injected context.
    """
    user_id = kwargs.get('user_id')
    
    try:
        await db.delete_user_memory(memory_id, user_id)
        return f"✅ Memory {memory_id} deleted."
    except Exception as e:
        return f"Error deleting memory: {e}"

MEMORY_TOOLS = [
    remember_info,
    get_my_memories,
    forget_memory
]
