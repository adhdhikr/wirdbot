
from db.connection import DatabaseConnection
from db.repositories.guild import GuildRepository
from db.repositories.schedule import ScheduleRepository
from db.repositories.user import UserRepository
from db.repositories.completion import CompletionRepository
from db.repositories.session import SessionRepository
from db.repositories.cache import CacheRepository
import os




class Database:
    _instance = None
    _initialized = False

    def __new__(cls, db_path: str = "data/wird.db"):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = "data/wird.db"):
        if self.__class__._initialized:
            return
        # Ensure the data directory exists
        data_dir = os.path.dirname(db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        self.connection = DatabaseConnection(db_path)
        self.guilds = GuildRepository(self.connection)
        self.schedules = ScheduleRepository(self.connection)
        self.users = UserRepository(self.connection)
        self.completions = CompletionRepository(self.connection)
        self.sessions = SessionRepository(self.connection)
        self.cache = CacheRepository(self.connection)
        self.__class__._initialized = True

    async def connect(self):
        await self.connection.connect()

    async def close(self):
        await self.connection.close()
    
    async def get_guild_config(self, guild_id: int):
        return await self.guilds.get(guild_id)
    
    async def create_or_update_guild(self, guild_id: int, **kwargs):
        await self.guilds.create_or_update(guild_id, **kwargs)
    
    async def add_scheduled_time(self, guild_id: int, time_type: str, time_value=None):
        await self.schedules.add(guild_id, time_type, time_value)
    
    async def get_scheduled_times(self, guild_id: int):
        return await self.schedules.get_all(guild_id)
    
    async def remove_scheduled_time(self, time_id: int):
        await self.schedules.remove(time_id)
    
    async def clear_scheduled_times(self, guild_id: int):
        await self.schedules.clear_all(guild_id)
    
    async def register_user(self, user_id: int, guild_id: int):
        await self.users.register(user_id, guild_id)
    
    async def unregister_user(self, user_id: int, guild_id: int):
        await self.users.unregister(user_id, guild_id)
    
    async def get_user(self, user_id: int, guild_id: int):
        return await self.users.get(user_id, guild_id)
    
    async def get_registered_users(self, guild_id: int):
        return await self.users.get_all_registered(guild_id)
    
    async def update_streak(self, user_id: int, guild_id: int, new_streak: int, last_completion: str):
        await self.users.update_streak(user_id, guild_id, new_streak, last_completion)
    
    async def mark_page_complete(self, user_id: int, guild_id: int, page_number: int, date: str, session_id: int = None, is_late: bool = False):
        await self.completions.mark_complete(user_id, guild_id, page_number, date, session_id, is_late)

    
    async def get_user_completions_for_date(self, user_id: int, guild_id: int, date: str):
        return await self.completions.get_user_completions_for_date(user_id, guild_id, date)
    
    async def get_all_completions_for_date(self, guild_id: int, date: str):
        return await self.completions.get_all_completions_for_date(guild_id, date)
    
    async def create_daily_session(self, guild_id: int, session_date: str, start_page: int, end_page: int, message_ids: str):
        await self.sessions.create(guild_id, session_date, start_page, end_page, message_ids)
    
    async def get_today_session(self, guild_id: int, session_date: str):
        return await self.sessions.get_today(guild_id, session_date)
    
    async def get_current_active_session(self, guild_id: int):
        return await self.sessions.get_current_active_session(guild_id)
    
    async def get_session_for_page(self, guild_id: int, page_number: int):
        return await self.sessions.get_session_for_page(guild_id, page_number)
    
    async def mark_session_completed(self, session_id: int):
        await self.sessions.mark_session_completed(session_id)
    
    async def get_completed_sessions_for_guild(self, guild_id: int):
        return await self.sessions.get_completed_sessions_for_guild(guild_id)
    
    async def get_all_sessions_for_guild(self, guild_id: int):
        return await self.sessions.get_all_sessions_for_guild(guild_id)
    
    async def get_user_completions_for_session(self, user_id: int, session_id: int):
        return await self.completions.get_user_completions_for_session(user_id, session_id)
    
    async def get_late_completions_for_date(self, guild_id: int, date: str):
        return await self.completions.get_late_completions_for_date(guild_id, date)
    
    async def get_late_completions_for_session(self, session_id: int):
        return await self.completions.get_late_completions_for_session(session_id)
    
    async def get_session_by_id(self, session_id: int):
        return await self.sessions.get_session_by_id(session_id)

    
    async def update_session_streak(self, user_id: int, guild_id: int, new_streak: int):
        await self.users.update_session_streak(user_id, guild_id, new_streak)
    
    async def set_session_streak(self, user_id: int, guild_id: int, streak: int):
        await self.users.set_session_streak(user_id, guild_id, streak)
    
    async def get_user_session_completions(self, user_id: int, guild_id: int):
        return await self.users.get_user_session_completions(user_id, guild_id)
    
    async def get_all_configured_guilds(self):
        return await self.guilds.get_all_configured()
    
    async def update_session_message_ids(self, guild_id: int, session_date: str, message_ids: str):
        await self.sessions.update_message_ids(guild_id, session_date, message_ids)
    
    async def update_session_summary_message_id(self, session_id: int, message_id: int):
        await self.sessions.update_summary_message_id(session_id, message_id)



    async def get_previous_session(self, guild_id: int, current_session_id: int):
        return await self.sessions.get_previous_session(guild_id, current_session_id)
        
    async def get_session_completion_status(self, user_id: int, session_id: int):
        return await self.completions.get_session_completion_status(user_id, session_id)

    async def reset_guild_data(self, guild_id: int):
        """Reset all data for a guild (admin command)"""
        # Delete in reverse order of dependencies
        await self.completions.clear_all(guild_id)
        await self.sessions.clear_all(guild_id)
        await self.users.clear_all(guild_id)
        await self.schedules.clear_all(guild_id)
        await self.guilds.delete(guild_id)

    async def get_user_language_preference(self, user_id: int, guild_id: int) -> str:
        return await self.users.get_language_preference(user_id, guild_id)

    async def set_user_language_preference(self, user_id: int, guild_id: int, language: str):
        await self.users.set_language_preference(user_id, guild_id, language)

    async def get_user_tafsir_preference(self, user_id: int, guild_id: int) -> str:
        return await self.users.get_tafsir_preference(user_id, guild_id)

    async def set_user_tafsir_preference(self, user_id: int, guild_id: int, tafsir: str):
        await self.users.set_tafsir_preference(user_id, guild_id, tafsir)

    # Cache methods
    async def get_translation_cache(self, page_number: int, language: str):
        return await self.cache.get_translation_cache(page_number, language)

    async def set_translation_cache(self, page_number: int, language: str, data):
        await self.cache.set_translation_cache(page_number, language, data)

    async def get_tafsir_cache(self, page_number: int, edition: str):
        return await self.cache.get_tafsir_cache(page_number, edition)

    async def set_tafsir_cache(self, page_number: int, edition: str, data):
        await self.cache.set_tafsir_cache(page_number, edition, data)

    async def get_cache_stats(self):
        return await self.cache.get_cache_stats()


# Global singleton instance
db = Database()
