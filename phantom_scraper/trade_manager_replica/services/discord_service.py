"""
Discord Service for Just.Trades
Handles Discord OAuth and DM notifications
"""

import aiohttp
import logging
import os

logger = logging.getLogger(__name__)

class DiscordService:
    """Service for Discord integration"""
    
    DISCORD_API_BASE = "https://discord.com/api/v10"
    DISCORD_OAUTH_BASE = "https://discord.com/api/oauth2"
    
    @staticmethod
    def get_oauth_url(client_id: str, redirect_uri: str, state: str = None) -> str:
        """Generate Discord OAuth URL"""
        scopes = "identify guilds"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes
        }
        if state:
            params["state"] = state
        
        from urllib.parse import urlencode
        return f"{DiscordService.DISCORD_OAUTH_BASE}/authorize?{urlencode(params)}"
    
    @staticmethod
    async def exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
        """Exchange OAuth code for access token"""
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DiscordService.DISCORD_OAUTH_BASE}/token",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    logger.error(f"Discord token exchange failed: {error}")
                    return {"error": error}
    
    @staticmethod
    async def get_user_info(access_token: str) -> dict:
        """Get Discord user information"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DiscordService.DISCORD_API_BASE}/users/@me",
                headers=headers
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    logger.error(f"Discord user info failed: {error}")
                    return {"error": error}
    
    @staticmethod
    async def send_dm(discord_user_id: str, message: str, bot_token: str) -> dict:
        """Send a DM to a Discord user via bot"""
        # First, create a DM channel
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            # Create DM channel
            async with session.post(
                f"{DiscordService.DISCORD_API_BASE}/users/@me/channels",
                headers=headers,
                json={"recipient_id": discord_user_id}
            ) as channel_response:
                if channel_response.status != 200:
                    return {"success": False, "error": "Failed to create DM channel"}
                
                channel_data = await channel_response.json()
                channel_id = channel_data.get("id")
            
            # Send message
            async with session.post(
                f"{DiscordService.DISCORD_API_BASE}/channels/{channel_id}/messages",
                headers=headers,
                json={"content": message}
            ) as message_response:
                if message_response.status == 200:
                    return {"success": True, "message": "DM sent successfully"}
                else:
                    error = await message_response.text()
                    return {"success": False, "error": error}
    
    @staticmethod
    def run_async(coro):
        """Run async function in sync context"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


