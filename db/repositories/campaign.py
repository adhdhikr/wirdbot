"""Campaign repository for mass messaging and form management"""
import json
from typing import Any, Dict, List, Optional


class CampaignRepository:
    def __init__(self, connection):
        self.connection = connection

    async def create_campaign(
        self,
        guild_id: int,
        name: str,
        created_by: int,
        message_content: Optional[str] = None,
        embed_title: Optional[str] = None,
        embed_description: Optional[str] = None,
        embed_color: Optional[int] = None,
        embed_image_url: Optional[str] = None,
        embed_thumbnail_url: Optional[str] = None,
        target_type: str = 'dm',
        target_channel_id: Optional[int] = None,
        target_role_ids: Optional[List[int]] = None,
        target_user_ids: Optional[List[int]] = None
    ) -> int:
        """Create a new campaign and return its ID"""
        role_ids_json = json.dumps(target_role_ids) if target_role_ids else None
        user_ids_json = json.dumps(target_user_ids) if target_user_ids else None
        
        query = """
            INSERT INTO campaigns (
                guild_id, name, message_content, embed_title, embed_description,
                embed_color, embed_image_url, embed_thumbnail_url,
                target_type, target_channel_id, target_role_ids, target_user_ids, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute_write(
            query, (guild_id, name, message_content, embed_title, embed_description,
            embed_color, embed_image_url, embed_thumbnail_url,
            target_type, target_channel_id, role_ids_json, user_ids_json, created_by)
        )
        row = await self.connection.execute_one(
            "SELECT id FROM campaigns WHERE guild_id = ? ORDER BY id DESC LIMIT 1",
            (guild_id,)
        )
        return row['id'] if row else None

    async def get_campaign(self, campaign_id: int, guild_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get a campaign by ID"""
        if guild_id:
            query = "SELECT * FROM campaigns WHERE id = ? AND guild_id = ?"
            result = await self.connection.execute_one(query, (campaign_id, guild_id))
        else:
            query = "SELECT * FROM campaigns WHERE id = ?"
            result = await self.connection.execute_one(query, (campaign_id,))
        if result:
            if result.get('target_role_ids'):
                try:
                    result['target_role_ids'] = json.loads(result['target_role_ids'])
                except Exception:
                    result['target_role_ids'] = []
            else:
                result['target_role_ids'] = []
            
            if result.get('target_user_ids'):
                try:
                    result['target_user_ids'] = json.loads(result['target_user_ids'])
                except Exception:
                    result['target_user_ids'] = []
            else:
                result['target_user_ids'] = []
        
        return result

    async def get_campaigns(self, guild_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all campaigns for a guild, optionally filtered by status"""
        if status:
            query = "SELECT * FROM campaigns WHERE guild_id = ? AND status = ? ORDER BY created_at DESC"
            return await self.connection.execute_many(query, (guild_id, status))
        else:
            query = "SELECT * FROM campaigns WHERE guild_id = ? ORDER BY created_at DESC"
            return await self.connection.execute_many(query, (guild_id,))

    async def update_campaign_status(self, campaign_id: int, status: str) -> None:
        """Update campaign status"""
        query = "UPDATE campaigns SET status = ? WHERE id = ?"
        await self.connection.execute_write(query, (status, campaign_id))

    async def delete_campaign(self, campaign_id: int, guild_id: int) -> None:
        """Delete a campaign"""
        query = "DELETE FROM campaigns WHERE id = ? AND guild_id = ?"
        await self.connection.execute_write(query, (campaign_id, guild_id))

    async def add_form(
        self,
        campaign_id: int,
        button_label: str,
        button_style: str = 'primary',
        button_emoji: Optional[str] = None,
        button_order: int = 0,
        has_form: bool = False,
        modal_title: Optional[str] = None,
        form_fields: Optional[List[Dict[str, Any]]] = None,
        response_channel_id: Optional[int] = None
    ) -> int:
        """Add a button/form to a campaign"""
        form_fields_json = json.dumps(form_fields) if form_fields else None
        
        query = """
            INSERT INTO campaign_forms (
                campaign_id, button_label, button_style, button_emoji,
                button_order, has_form, modal_title, form_fields, response_channel_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.connection.execute_write(
            query, (campaign_id, button_label, button_style, button_emoji,
            button_order, int(has_form), modal_title, form_fields_json, response_channel_id)
        )
        row = await self.connection.execute_one(
            "SELECT id FROM campaign_forms WHERE campaign_id = ? ORDER BY id DESC LIMIT 1",
            (campaign_id,)
        )
        return row['id'] if row else None

    async def get_campaign_forms(self, campaign_id: int) -> List[Dict[str, Any]]:
        """Get all forms/buttons for a campaign"""
        query = "SELECT * FROM campaign_forms WHERE campaign_id = ? ORDER BY button_order"
        results = await self.connection.execute_many(query, (campaign_id,))
        for result in results:
            if result.get('form_fields'):
                try:
                    result['form_fields'] = json.loads(result['form_fields'])
                except Exception:
                    result['form_fields'] = []
            else:
                result['form_fields'] = []
        
        return results

    async def get_form(self, form_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific form by ID"""
        query = "SELECT * FROM campaign_forms WHERE id = ?"
        result = await self.connection.execute_one(query, (form_id,))
        
        if result and result.get('form_fields'):
            try:
                result['form_fields'] = json.loads(result['form_fields'])
            except Exception:
                result['form_fields'] = []
        
        return result

    async def delete_form(self, form_id: int) -> None:
        """Delete a form/button"""
        query = "DELETE FROM campaign_forms WHERE id = ?"
        await self.connection.execute_write(query, (form_id,))

    async def save_response(
        self,
        form_id: int,
        campaign_id: int,
        user_id: int,
        guild_id: int,
        response_data: Dict[str, str]
    ) -> int:
        """Save a user's form response"""
        response_json = json.dumps(response_data)
        
        query = """
            INSERT INTO campaign_responses (
                form_id, campaign_id, user_id, guild_id, response_data
            ) VALUES (?, ?, ?, ?, ?)
        """
        await self.connection.execute_write(
            query, (form_id, campaign_id, user_id, guild_id, response_json)
        )
        row = await self.connection.execute_one(
            "SELECT id FROM campaign_responses WHERE user_id = ? AND guild_id = ? ORDER BY id DESC LIMIT 1",
            (user_id, guild_id)
        )
        return row['id'] if row else None

    async def get_responses(
        self,
        campaign_id: Optional[int] = None,
        form_id: Optional[int] = None,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get responses with optional filters"""
        conditions = []
        params = []
        
        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if form_id:
            conditions.append("form_id = ?")
            params.append(form_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if guild_id:
            conditions.append("guild_id = ?")
            params.append(guild_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM campaign_responses WHERE {where_clause} ORDER BY submitted_at DESC"
        
        results = await self.connection.execute_many(query, tuple(params))
        for result in results:
            if result.get('response_data'):
                try:
                    result['response_data'] = json.loads(result['response_data'])
                except Exception:
                    result['response_data'] = {}
        
        return results

    async def get_response_count(self, campaign_id: int) -> int:
        """Get total number of responses for a campaign"""
        query = "SELECT COUNT(*) as count FROM campaign_responses WHERE campaign_id = ?"
        result = await self.connection.execute_one(query, (campaign_id,))
        return result['count'] if result else 0
