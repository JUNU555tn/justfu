
import os
import time
import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

class ManualDownloadHelper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'video/mp4,video/*,*/*;q=0.9',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive'
        })

    async def send_live_log(self, bot, chat_id, message):
        """Send live log updates"""
        try:
            await bot.send_message(chat_id=chat_id, text=f"📥 {message}")
            logger.info(f"Manual download log: {message}")
        except Exception as e:
            logger.error(f"Failed to send live log: {e}")

    async def download_from_new_tab_url(self, manual_url, bot, chat_id, user_id):
        """Download file from manually provided URL (from new tab)"""
        try:
            await self.send_live_log(bot, chat_id, f"📋 Processing manual URL: {manual_url[:60]}...")
            
            # Create download directory
            download_dir = f"./DOWNLOADS/{user_id}"
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
            # Get file info with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'video/mp4,video/*,*/*;q=0.9',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Referer': manual_url
            }
            
            response = self.session.head(manual_url, headers=headers, timeout=30, allow_redirects=True)
            
            if response.status_code == 200:
                content_length = int(response.headers.get('content-length', 0))
                content_type = response.headers.get('content-type', '')
                
                # Determine file extension
                file_ext = '.mp4'  # default
                if '.mkv' in manual_url.lower(): file_ext = '.mkv'
                elif '.webm' in manual_url.lower(): file_ext = '.webm'
                elif '.avi' in manual_url.lower(): file_ext = '.avi'
                elif '.m4v' in manual_url.lower(): file_ext = '.m4v'
                
                filename = f"manual_video_{int(time.time())}{file_ext}"
                filepath = os.path.join(download_dir, filename)
                
                await self.send_live_log(bot, chat_id, f"📁 Downloading to: {filename}")
                
                if content_length > 0:
                    await self.send_live_log(bot, chat_id, f"📊 File size: {self.humanbytes(content_length)}")
                
                # Download with progress
                with self.session.get(manual_url, headers=headers, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(filepath, 'wb') as f:
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Update progress every 1MB
                                if downloaded % (1024*1024) == 0 and content_length > 0:
                                    progress = (downloaded / content_length * 100)
                                    await self.send_live_log(bot, chat_id, f"📥 Downloaded: {progress:.1f}% ({self.humanbytes(downloaded)})")
                
                await self.send_live_log(bot, chat_id, f"✅ Manual download completed: {filepath}")
                return filepath
            else:
                await self.send_live_log(bot, chat_id, f"❌ Manual download failed: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            await self.send_live_log(bot, chat_id, f"❌ Manual download error: {str(e)}")
            logger.error(f"Manual download error: {e}")
            return None

    def humanbytes(self, size):
        """Convert bytes to human readable format"""
        if not size:
            return "0 B"
        
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        
        while size > power:
            size /= power
            n += 1
            
        return f"{size:.1f} {power_labels[n]}B"

# Initialize the helper
manual_helper = ManualDownloadHelper()
