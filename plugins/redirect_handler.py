
import asyncio
import requests
import re
import logging
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class RedirectHandler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    async def handle_desitales2_redirect(self, url, bot, chat_id):
        """Handle desitales2.com get_file redirects to CDN URLs"""
        try:
            if 'get_file' not in url or 'desitales2.com' not in url:
                return None
                
            await self.send_live_log(bot, chat_id, f"🎯 Handling desitales2 redirect: {url[:60]}...")
            
            # Follow the redirect chain
            response = self.session.get(url, allow_redirects=True, timeout=30)
            
            final_url = response.url
            
            # Check if we got a CDN URL
            if 'cdn.' in final_url and '.mp4' in final_url:
                await self.send_live_log(bot, chat_id, f"✅ Found CDN URL: {final_url}")
                return final_url
            
            # If still on get_file page, parse for redirect URLs
            if 'get_file' in final_url:
                content = response.text
                
                # Look for JavaScript redirects
                js_redirect_patterns = [
                    r'window\.location\s*=\s*["\']([^"\']+)["\']',
                    r'location\.href\s*=\s*["\']([^"\']+)["\']',
                    r'location\.replace\s*\(\s*["\']([^"\']+)["\']\s*\)',
                    r'document\.location\s*=\s*["\']([^"\']+)["\']'
                ]
                
                for pattern in js_redirect_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if 'cdn.' in match and '.mp4' in match:
                            await self.send_live_log(bot, chat_id, f"✅ Found JS redirect: {match}")
                            return match
                
                # Look for meta refresh redirects
                meta_pattern = r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\'][^;]*;\s*url=([^"\']+)["\']'
                meta_matches = re.findall(meta_pattern, content, re.IGNORECASE)
                for match in meta_matches:
                    if 'cdn.' in match and '.mp4' in match:
                        await self.send_live_log(bot, chat_id, f"✅ Found meta redirect: {match}")
                        return match
                
                # Look for direct CDN URLs in content
                cdn_patterns = [
                    r'https?://cdn\.[^"\'<>\s]+\.mp4[^"\'<>\s]*',
                    r'"(https?://[^"]*cdn[^"]*\.mp4[^"]*)"',
                    r'src\s*=\s*["\']([^"\']*cdn[^"\']*\.mp4[^"\']*)["\']'
                ]
                
                for pattern in cdn_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        if match.startswith('http') and 'cdn.' in match and '.mp4' in match:
                            await self.send_live_log(bot, chat_id, f"✅ Found CDN URL in content: {match}")
                            return match
            
            return None
            
        except Exception as e:
            logger.error(f"desitales2 redirect error: {e}")
            return None

    async def follow_redirect_chain(self, url, bot, chat_id, max_redirects=10):
        """Follow a chain of redirects to find the final download URL"""
        try:
            await self.send_live_log(bot, chat_id, f"🔄 Following redirect chain: {url[:60]}...")
            
            current_url = url
            redirect_count = 0
            
            while redirect_count < max_redirects:
                response = self.session.get(current_url, allow_redirects=False, timeout=30)
                
                # If we got a direct video file
                if any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                    await self.send_live_log(bot, chat_id, f"✅ Found video URL: {current_url}")
                    return current_url
                
                # Check for redirect headers
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('Location')
                    if location:
                        if not location.startswith('http'):
                            location = urljoin(current_url, location)
                        
                        await self.send_live_log(bot, chat_id, f"🔄 Redirect {redirect_count + 1}: {location[:60]}...")
                        current_url = location
                        redirect_count += 1
                        continue
                
                # No more redirects, check if final URL is a video
                if any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                    return current_url
                
                break
            
            return None
            
        except Exception as e:
            logger.error(f"Redirect chain error: {e}")
            return None

    async def detect_and_handle_redirects(self, url, bot, chat_id):
        """Main method to detect and handle various redirect patterns"""
        try:
            # Handle desitales2.com specifically
            if 'desitales2.com' in url and 'get_file' in url:
                result = await self.handle_desitales2_redirect(url, bot, chat_id)
                if result:
                    return result
            
            # Handle other redirect patterns
            result = await self.follow_redirect_chain(url, bot, chat_id)
            if result:
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Redirect detection error: {e}")
            return None

    async def send_live_log(self, bot, chat_id, message):
        """Send live log updates to user"""
        try:
            await bot.send_message(chat_id=chat_id, text=f"🔄 {message}")
            logger.info(f"Live log: {message}")
        except Exception as e:
            logger.error(f"Failed to send live log: {e}")

# Initialize redirect handler
redirect_handler = RedirectHandler()
