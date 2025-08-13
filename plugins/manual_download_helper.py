
import logging
import asyncio
import requests
import os
from urllib.parse import urlparse
from pyrogram import Client
from config import Config

logging.basicConfig(level=logging.DEBUG)
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

    async def download_from_new_tab_url(self, video_url: str, bot: Client, chat_id: int, user_id: int):
        """Download video when user manually provides the new tab URL"""
        try:
            await bot.send_message(chat_id=chat_id, text="🤖 Starting manual download from new tab URL...")
            
            # Validate URL
            if not video_url.startswith('http'):
                await bot.send_message(chat_id=chat_id, text="❌ Invalid URL format")
                return None
            
            # Check if it's a direct video file
            parsed_url = urlparse(video_url)
            file_ext = os.path.splitext(parsed_url.path)[1].lower()
            
            if file_ext not in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']:
                await bot.send_message(chat_id=chat_id, text="⚠️ URL doesn't appear to be a direct video file")
            
            # Create download directory
            download_dir = f"./DOWNLOADS/{user_id}"
            os.makedirs(download_dir, exist_ok=True)
            
            # Get file info
            status_msg = await bot.send_message(chat_id=chat_id, text="📊 Checking file info...")
            
            try:
                head_response = self.session.head(video_url, timeout=30, allow_redirects=True)
                if head_response.status_code == 200:
                    content_length = int(head_response.headers.get('content-length', 0))
                    content_type = head_response.headers.get('content-type', '')
                    
                    # Determine filename
                    if 'content-disposition' in head_response.headers:
                        filename = head_response.headers['content-disposition'].split('filename=')[-1].strip('"')
                    else:
                        filename = f"manual_download_{int(time.time())}{file_ext or '.mp4'}"
                    
                    filepath = os.path.join(download_dir, filename)
                    
                    await status_msg.edit_text(f"📥 Downloading: {filename}\n📊 Size: {content_length} bytes")
                    
                    # Download with progress
                    with self.session.get(video_url, stream=True, timeout=60) as response:
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    
                                    # Update progress every 2MB
                                    if downloaded % (2*1024*1024) == 0 and total_size > 0:
                                        progress = (downloaded / total_size) * 100
                                        await status_msg.edit_text(
                                            f"📥 Downloading: {filename}\n"
                                            f"📊 Progress: {progress:.1f}% ({downloaded}/{total_size} bytes)"
                                        )
                    
                    await status_msg.edit_text(f"✅ Download completed: {filename}")
                    return filepath
                    
                else:
                    await status_msg.edit_text(f"❌ Failed to access file: HTTP {head_response.status_code}")
                    return None
                    
            except Exception as download_error:
                await status_msg.edit_text(f"❌ Download failed: {str(download_error)}")
                return None
                
        except Exception as e:
            logger.error(f"Manual download error: {e}")
            await bot.send_message(chat_id=chat_id, text=f"❌ Manual download failed: {str(e)}")
            return None

# Initialize helper
manual_helper = ManualDownloadHelper()
