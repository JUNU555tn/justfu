import os
import time
import requests
import logging
import asyncio
import subprocess
from config import Config
from urllib.parse import urljoin, urlparse
from PIL import Image
import shutil

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

    async def send_live_log(self, bot, chat_id: int, message: str):
        """Send live log updates"""
        try:
            await bot.send_message(chat_id=chat_id, text=f"📥 {message}")
            logger.info(f"Manual download log: {message}")
            await asyncio.sleep(0.1)  # Small delay to avoid flooding
        except Exception as e:
            logger.error(f"Failed to send manual download log: {e}")

    async def extract_video_thumbnail(self, video_path: str, download_dir: str, user_id: int):
        """Extract thumbnail from video file using ffmpeg"""
        try:
            # Create thumbnail filename
            thumbnail_path = os.path.join(download_dir, f"video_thumb_{int(time.time())}.jpg")

            # Use ffmpeg to extract frame at 2 seconds
            ffmpeg_command = [
                "ffmpeg", "-i", video_path,
                "-ss", "00:00:02",  # Extract frame at 2 seconds
                "-vframes", "1",    # Extract only 1 frame
                "-q:v", "2",        # High quality
                "-vf", "scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2",  # Resize to standard thumbnail size
                thumbnail_path, "-y"  # Overwrite if exists
            ]

            # Run ffmpeg with timeout
            result = subprocess.run(
                ffmpeg_command,
                capture_output=True,
                timeout=30,
                text=True
            )

            if result.returncode == 0 and os.path.exists(thumbnail_path):
                # Copy thumbnail to user's custom thumbnail location
                user_thumb_path = f"./DOWNLOADS/{user_id}.jpg"

                try:
                    # Open and process the thumbnail
                    img = Image.open(thumbnail_path)

                    # Convert to RGB if needed
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode == 'RGBA':
                            background.paste(img, mask=img.split()[-1])
                        else:
                            background.paste(img)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')

                    # Save as user's custom thumbnail
                    img.save(user_thumb_path, "JPEG", quality=85)
                    logger.info(f"Thumbnail saved to: {user_thumb_path}")

                    # Clean up temporary thumbnail
                    try:
                        os.remove(thumbnail_path)
                    except:
                        pass

                    return user_thumb_path

                except Exception as img_error:
                    logger.error(f"Image processing error: {img_error}")
                    # If PIL processing fails, just copy the file
                    shutil.copy2(thumbnail_path, user_thumb_path)
                    try:
                        os.remove(thumbnail_path)
                    except:
                        pass
                    return user_thumb_path

            else:
                logger.warning(f"ffmpeg failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg thumbnail extraction timed out")
            return None
        except FileNotFoundError:
            logger.warning("ffmpeg not available for thumbnail extraction")
            return None
        except Exception as e:
            logger.error(f"Thumbnail extraction error: {e}")
            return None

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

            final_url = response.url

            if response.status_code == 200:
                content_length = int(response.headers.get('content-length', 0))
                content_type = response.headers.get('content-type', '')

                # Determine file extension
                file_ext = '.mp4'  # default
                if '.mkv' in final_url.lower(): file_ext = '.mkv'
                elif '.webm' in final_url.lower(): file_ext = '.webm'
                elif '.avi' in final_url.lower(): file_ext = '.avi'
                elif '.m4v' in final_url.lower(): file_ext = '.m4v'
                elif '.mp4' in final_url.lower(): file_ext = '.mp4'


                filename = f"manual_video_{int(time.time())}{file_ext}"
                filepath = os.path.join(download_dir, filename)

                await self.send_live_log(bot, chat_id, f"📁 Downloading to: {filename}")

                if content_length > 0:
                    await self.send_live_log(bot, chat_id, f"📊 File size: {self.humanbytes(content_length)}")

                # Download with progress
                with self.session.get(final_url, headers=headers, stream=True, timeout=60) as r:
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

                # Extract thumbnail from downloaded video
                try:
                    await self.send_live_log(bot, chat_id, "📸 Extracting video thumbnail...")
                    thumbnail_path = await self.extract_video_thumbnail(filepath, download_dir, user_id)
                    if thumbnail_path:
                        await self.send_live_log(bot, chat_id, "✅ Thumbnail extracted successfully!")
                    else:
                        await self.send_live_log(bot, chat_id, "⚠️ Could not extract thumbnail")
                except Exception as thumb_error:
                    logger.error(f"Thumbnail extraction error: {thumb_error}")
                    await self.send_live_log(bot, chat_id, "⚠️ Thumbnail extraction failed")

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

# Initialize the manual helper
manual_helper = ManualDownloadHelper()