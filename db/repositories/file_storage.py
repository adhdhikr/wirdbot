"""
File Storage Repository
Handles user file storage operations with quota management.
"""
from typing import Optional, List, Dict, Any
from db.connection import DatabaseConnection
import os
import logging

logger = logging.getLogger(__name__)


class FileStorageRepository:
    """Repository for managing user file storage."""
    
    # Storage limits
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB per file
    MAX_USER_STORAGE = 1024 * 1024 * 1024  # 1GB per user
    
    def __init__(self, db: DatabaseConnection):
        self.db = db
    
    async def add_file(
        self,
        user_id: int,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        mime_type: str = None,
        description: str = None
    ) -> Optional[int]:
        """
        Add a file record to the database.
        Returns the file ID on success, None on failure.
        """
        try:
            # Insert file record
            await self.db.execute_write(
                """INSERT INTO user_files 
                   (user_id, filename, original_filename, file_path, file_size, mime_type, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, filename, original_filename, file_path, file_size, mime_type, description)
            )
            
            # Update storage quota
            await self._update_storage_quota(user_id, file_size, 1)
            
            # Get the inserted file ID
            result = await self.db.execute_one(
                "SELECT id FROM user_files WHERE user_id = ? AND filename = ?",
                (user_id, filename)
            )
            return result['id'] if result else None
            
        except Exception as e:
            logger.error(f"Failed to add file record: {e}")
            return None
    
    async def get_file(self, user_id: int, filename: str) -> Optional[Dict[str, Any]]:
        """Get a file record by user and filename."""
        return await self.db.execute_one(
            "SELECT * FROM user_files WHERE user_id = ? AND filename = ?",
            (user_id, filename)
        )
    
    async def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Get a file record by ID."""
        return await self.db.execute_one(
            "SELECT * FROM user_files WHERE id = ?",
            (file_id,)
        )
    
    async def list_files(self, user_id: int) -> List[Dict[str, Any]]:
        """List all files for a user, ordered by creation date."""
        return await self.db.execute_many(
            """SELECT id, filename, original_filename, file_size, mime_type, 
                      description, created_at, updated_at
               FROM user_files 
               WHERE user_id = ? 
               ORDER BY created_at DESC""",
            (user_id,)
        )
    
    async def delete_file(self, user_id: int, filename: str) -> bool:
        """
        Delete a file record from the database.
        Returns True on success.
        Note: This only deletes the DB record, caller must delete actual file.
        """
        try:
            # Get file info first for quota update
            file_info = await self.get_file(user_id, filename)
            if not file_info:
                return False
            
            file_size = file_info['file_size']
            
            # Delete record
            await self.db.execute_write(
                "DELETE FROM user_files WHERE user_id = ? AND filename = ?",
                (user_id, filename)
            )
            
            # Update storage quota (subtract)
            await self._update_storage_quota(user_id, -file_size, -1)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file record: {e}")
            return False
    
    async def update_file_description(self, user_id: int, filename: str, description: str) -> bool:
        """Update a file's description."""
        try:
            await self.db.execute_write(
                """UPDATE user_files 
                   SET description = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND filename = ?""",
                (description, user_id, filename)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update file description: {e}")
            return False
    
    async def rename_file(self, user_id: int, old_filename: str, new_filename: str) -> bool:
        """Rename a file (in database only, caller must rename actual file)."""
        try:
            await self.db.execute_write(
                """UPDATE user_files 
                   SET filename = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND filename = ?""",
                (new_filename, user_id, old_filename)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to rename file: {e}")
            return False
    
    async def get_storage_usage(self, user_id: int) -> Dict[str, Any]:
        """Get storage usage stats for a user."""
        result = await self.db.execute_one(
            "SELECT * FROM user_storage WHERE user_id = ?",
            (user_id,)
        )
        
        if result:
            return {
                'total_bytes_used': result['total_bytes_used'],
                'file_count': result['file_count'],
                'bytes_remaining': self.MAX_USER_STORAGE - result['total_bytes_used'],
                'max_storage': self.MAX_USER_STORAGE,
                'max_file_size': self.MAX_FILE_SIZE,
                'usage_percent': (result['total_bytes_used'] / self.MAX_USER_STORAGE) * 100
            }
        
        # No record means no files yet
        return {
            'total_bytes_used': 0,
            'file_count': 0,
            'bytes_remaining': self.MAX_USER_STORAGE,
            'max_storage': self.MAX_USER_STORAGE,
            'max_file_size': self.MAX_FILE_SIZE,
            'usage_percent': 0.0
        }
    
    async def can_upload(self, user_id: int, file_size: int) -> tuple[bool, str]:
        """
        Check if a user can upload a file of given size.
        Returns (allowed, reason).
        """
        # Check file size limit
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File exceeds maximum size of {self._format_size(self.MAX_FILE_SIZE)}"
        
        # Check storage quota
        usage = await self.get_storage_usage(user_id)
        if usage['total_bytes_used'] + file_size > self.MAX_USER_STORAGE:
            return False, f"Would exceed storage quota. Used: {self._format_size(usage['total_bytes_used'])}/{self._format_size(self.MAX_USER_STORAGE)}"
        
        return True, "OK"
    
    async def _update_storage_quota(self, user_id: int, bytes_delta: int, count_delta: int):
        """Update the user's storage quota tracking."""
        # Try to update existing record
        existing = await self.db.execute_one(
            "SELECT * FROM user_storage WHERE user_id = ?",
            (user_id,)
        )
        
        if existing:
            await self.db.execute_write(
                """UPDATE user_storage 
                   SET total_bytes_used = total_bytes_used + ?,
                       file_count = file_count + ?,
                       last_updated = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (bytes_delta, count_delta, user_id)
            )
        else:
            # Create new record
            await self.db.execute_write(
                """INSERT INTO user_storage (user_id, total_bytes_used, file_count)
                   VALUES (?, ?, ?)""",
                (user_id, max(0, bytes_delta), max(0, count_delta))
            )
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes as human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    # =========================================================================
    # CLEANUP METHODS
    # =========================================================================
    
    # Cleanup settings
    INACTIVE_DAYS = 30  # Delete files after 30 days of no access
    ACTIVE_USER_THRESHOLD_DAYS = 7  # User is "active" if they accessed within 7 days
    
    async def update_last_accessed(self, user_id: int, filename: str):
        """Update the last_accessed timestamp for a file."""
        try:
            await self.db.execute_write(
                """UPDATE user_files 
                   SET last_accessed = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND filename = ?""",
                (user_id, filename)
            )
        except Exception as e:
            logger.error(f"Failed to update last_accessed: {e}")
    
    async def get_stale_files(self, inactive_days: int = None) -> List[Dict[str, Any]]:
        """
        Get files that haven't been accessed for the specified number of days.
        Only returns files from users who are NOT active.
        """
        if inactive_days is None:
            inactive_days = self.INACTIVE_DAYS
        
        # Get files older than threshold from inactive users
        # A user is inactive if they have no files accessed within ACTIVE_USER_THRESHOLD_DAYS
        return await self.db.execute_many(
            """SELECT f.* FROM user_files f
               WHERE datetime(f.last_accessed) < datetime('now', ? || ' days')
               AND f.user_id NOT IN (
                   SELECT DISTINCT user_id FROM user_files 
                   WHERE datetime(last_accessed) > datetime('now', ? || ' days')
               )
               ORDER BY f.last_accessed ASC""",
            (f"-{inactive_days}", f"-{self.ACTIVE_USER_THRESHOLD_DAYS}")
        )
    
    async def get_user_last_activity(self, user_id: int) -> Optional[str]:
        """Get the timestamp of user's most recent file access."""
        result = await self.db.execute_one(
            """SELECT MAX(last_accessed) as last_activity 
               FROM user_files WHERE user_id = ?""",
            (user_id,)
        )
        return result['last_activity'] if result else None
    
    async def cleanup_stale_files(self, inactive_days: int = None) -> Dict[str, Any]:
        """
        Delete files that haven't been accessed for too long (from inactive users).
        Returns cleanup statistics.
        """
        import os
        from pathlib import Path
        
        stale_files = await self.get_stale_files(inactive_days)
        
        deleted_count = 0
        freed_bytes = 0
        errors = []
        
        for file_info in stale_files:
            try:
                user_id = file_info['user_id']
                filename = file_info['filename']
                file_path = Path(file_info['file_path'])
                file_size = file_info['file_size']
                
                # Delete from database
                success = await self.delete_file(user_id, filename)
                if success:
                    # Delete actual file
                    if file_path.exists():
                        os.remove(file_path)
                    
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.info(f"Cleaned up stale file: {filename} (user {user_id})")
                    
            except Exception as e:
                errors.append(f"{file_info['filename']}: {e}")
                logger.error(f"Cleanup error for {file_info['filename']}: {e}")
        
        return {
            'deleted_count': deleted_count,
            'freed_bytes': freed_bytes,
            'freed_formatted': self._format_size(freed_bytes),
            'errors': errors
        }
    
    async def get_cleanup_preview(self, inactive_days: int = None) -> Dict[str, Any]:
        """Preview what would be cleaned up without actually deleting."""
        stale_files = await self.get_stale_files(inactive_days)
        
        total_bytes = sum(f['file_size'] for f in stale_files)
        users_affected = len(set(f['user_id'] for f in stale_files))
        
        return {
            'file_count': len(stale_files),
            'total_bytes': total_bytes,
            'total_formatted': self._format_size(total_bytes),
            'users_affected': users_affected,
            'files': [{'filename': f['filename'], 'user_id': f['user_id'], 
                       'last_accessed': f['last_accessed']} for f in stale_files[:20]]
        }
