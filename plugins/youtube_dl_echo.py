#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K

import logging
import os
import asyncio
import time
import math
from datetime import datetime

# the secret configuration specific things
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

# the Strings used for this "thing"
from translation import Translation

import pyrogram
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import re

from plugins.auto_download_detector import EnhancedDownloadDetector, AutoDownloadDetector
from plugins.manual_download_helper import manual_helper

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress urllib3 and selenium debug logs
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('pyrogram').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Global progress tracking
progress_messages = {}

def is_youtube_url(url):
    """Check if URL is from YouTube or other yt-dlp supported platforms"""
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)',
        r'(?:https?://)?(?:www\.)?(?:m\.youtube\.com)',
        r'(?:https?://)?(?:music\.youtube\.com)',
        r'(?:https?://)?(?:www\.)?(?:vimeo\.com)',
        r'(?:https?://)?(?:www\.)?(?:dailymotion\.com)',
        r'(?:https?://)?(?:www\.)?(?:twitch\.tv)',
        r'(?:https?://)?(?:www\.)?(?:instagram\.com)',
        r'(?:https?://)?(?:www\.)?(?:facebook\.com)',
        r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)',
        r'(?:https?://)?(?:www\.)?(?:tiktok\.com)',
        r'(?:https?://)?(?:www\.)?(?:streamable\.com)',
        r'(?:https?://)?(?:www\.)?(?:reddit\.com)',
        r'(?:https?://)?(?:www\.)?(?:soundcloud\.com)',
        r'(?:https?://)?(?:www\.)?(?:bandcamp\.com)'
    ]

    for pattern in youtube_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False

def is_direct_video_url(url):
    """Check if URL is a direct video file"""
    video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.m4v', '.mov', '.flv', '.wmv']
    return any(ext in url.lower() for ext in video_extensions)

async def try_ytdlp_first(url, bot, update):
    """Try yt-dlp first for all URLs to get better quality and metadata"""
    try:
        from helper_funcs.help_uploadbot import get_formats_from_link
        
        # Show initial status
        status_msg = await bot.send_message(
            chat_id=update.chat.id,
            text="🔍 Trying yt-dlp for best quality download...",
            reply_to_message_id=update.id
        )

        # Try yt-dlp extraction
        response_json = await get_formats_from_link(url, bot, update)

        if response_json:
            await status_msg.edit_text("✅ Found formats with yt-dlp! Choose quality below:")
            return True
        else:
            await status_msg.edit_text("⚠️ yt-dlp failed, trying enhanced detection...")
            return False

    except Exception as e:
        logger.error(f"yt-dlp attempt failed: {e}")
        return False

class UnifiedProgressDisplay:
    def __init__(self):
        self.current_method = ""
        self.download_progress = 0
        self.upload_progress = 0
        self.download_speed = "0 B/s"
        self.upload_speed = "0 B/s"
        self.filename = ""
        self.status = "Detecting"
        self.total_size = ""
        self.downloaded_size = ""

    def format_progress_bar(self, percentage):
        """Create visual progress bar"""
        filled = int(percentage / 5)
        empty = 20 - filled
        return f"[{'█' * filled}{'░' * empty}]"

    def get_unified_message(self, user_id, cancel_id=None):
        """Generate unified progress message like your example"""
        progress_bar = self.format_progress_bar(self.download_progress)

        message = f"🎥 {self.filename}\n"
        message += f"┃ {progress_bar} {self.download_progress:.1f}%\n"
        message += f"┠ Processed: {self.downloaded_size} of {self.total_size}\n"
        message += f"┠ Status: {self.status} | ETA: -\n"
        message += f"┠ Speed: {self.download_speed} | Elapsed: {self.get_elapsed_time()}\n"
        message += f"┠ Engine: PyroMulti v2.3.45\n"
        message += f"┠ Mode: #{self.current_method} | #Aria2\n"
        message += f"┠ User: Jack | ID: {user_id}\n"

        if cancel_id:
            message += f"┖ /cancel_{cancel_id}"
        else:
            message += f"┖ Processing..."

        return message

    def get_elapsed_time(self):
        """Get elapsed time in readable format"""
        if hasattr(self, 'start_time'):
            elapsed = int(time.time() - self.start_time)
            return f"{elapsed}s"
        return "0s"

unified_display = UnifiedProgressDisplay()

@pyrogram.Client.on_message(pyrogram.filters.command(["start"]))
async def echo(bot, update):
    await bot.send_message(
        chat_id=update.chat.id,
        text=Translation.START_TEXT.format(update.from_user.first_name),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton('📺 Join Updates Channel', url='https://telegram.me/LazyDeveloper')
        ]])
    )

@pyrogram.Client.on_message(pyrogram.filters.command(["help"]))
async def help_user(bot, update):
    await bot.send_message(
        chat_id=update.chat.id,
        text=Translation.HELP_USER,
        parse_mode=pyrogram.enums.ParseMode.HTML,
        disable_web_page_preview=True,
        reply_to_message_id=update.id
    )

@pyrogram.Client.on_message(pyrogram.filters.regex(pattern=".*http.*"))
async def echo(bot, update):
    if update.from_user.id not in Config.AUTH_USERS:
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.NOT_AUTH_USER_TEXT,
            reply_to_message_id=update.id
        )
        return

    url = update.text.strip()

    # First check if it's a YouTube or yt-dlp supported URL
    if is_youtube_url(url):
        # YouTube/supported platform - use yt-dlp
        await handle_youtube_download(bot, update, url)
        return

    # Check if it's a direct video URL
    if is_direct_video_url(url):
        # Direct video URL - download immediately
        await handle_direct_video_download(bot, update, url, is_direct=True)
        return

    # For other URLs, try yt-dlp first, then fallback to enhanced detection
    ytdlp_success = await try_ytdlp_first(url, bot, update)
    
    if not ytdlp_success:
        # Show auto-detection option for unsupported URLs
        from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Encode URL to avoid callback data being too large
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        
        # Store URL mapping temporarily (in a real app, use a database)
        if not hasattr(echo, '_url_cache'):
            echo._url_cache = {}
        echo._url_cache[url_hash] = url
        
        buttons = [
            [InlineKeyboardButton("🔍 Auto Detect Video", callback_data=f"auto_detect|{url_hash}")],
            [InlineKeyboardButton("⬇️ Try Direct Download", callback_data=f"direct_download|{url_hash}")],
            [InlineKeyboardButton("🌐 Enhanced Detection", callback_data=f"enhanced_detect|{url_hash}")]
        ]
        
        await bot.send_message(
            chat_id=update.chat.id,
            text="🤖 **URL not recognized as a supported platform**\n\nChoose detection method:",
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=update.id
        )

async def handle_youtube_download(bot, update, url):
    """Handle YouTube and yt-dlp supported URLs"""
    # Import here to avoid circular imports
    from helper_funcs.help_uploadbot import get_formats_from_link

    try:
        # Show initial status
        status_msg = await bot.send_message(
            chat_id=update.chat.id,
            text="🔍 Analyzing YouTube URL with yt-dlp...",
            reply_to_message_id=update.id
        )

        # Get available formats using yt-dlp
        response_json = await get_formats_from_link(url, bot, update)

        if response_json:
            await status_msg.edit_text("✅ Found available formats! Please choose quality from the buttons below:")
        else:
            await status_msg.edit_text("❌ Failed to get video formats from this YouTube URL.")

    except Exception as e:
        logger.error(f"YouTube download error: {e}")
        await bot.send_message(
            chat_id=update.chat.id,
            text=f"❌ YouTube download failed: {str(e)}",
            reply_to_message_id=update.id
        )

async def handle_direct_video_download(bot, update, url, is_direct=False):
    """Handle direct video URLs with enhanced detection"""
    # Initialize unified progress display
    global unified_display
    unified_display = UnifiedProgressDisplay()
    unified_display.start_time = time.time()
    unified_display.filename = f"video_{int(time.time())}.mp4"

    # Send initial progress message
    progress_msg = await bot.send_message(
        chat_id=update.chat.id,
        text=unified_display.get_unified_message(update.from_user.id),
        reply_to_message_id=update.id
    )

    # Store progress message for updates
    progress_messages[update.from_user.id] = progress_msg

    try:
        enhanced_detector = EnhancedDownloadDetector()
        
        # Check if URL is already a direct video link
        if is_direct or is_direct_video_url(url):
            # Direct video URL - download immediately
            unified_display.current_method = "Direct"
            unified_display.status = "Downloading"
            await update_progress_message_safe(bot, update.from_user.id, "⬇️ Direct video URL detected, downloading...")

            filepath = await enhanced_detector.human_download_file(url, bot, update.chat.id, update.from_user.id)

            if filepath and os.path.exists(filepath):
                unified_display.status = "Uploading"
                await update_progress_message_safe(bot, update.from_user.id, "📤 Uploading to Telegram...")

                # Get video thumbnail
                thumb_path = await extract_video_thumbnail(filepath, update.from_user.id)

                # Upload to Telegram with thumbnail
                await bot.send_video(
                    chat_id=update.chat.id,
                    video=filepath,
                    thumb=thumb_path,
                    caption="✅ **Direct Video Download Complete!**\n\nDownloaded from direct video URL",
                    reply_to_message_id=update.id
                )

                # Clean up
                try:
                    os.remove(filepath)
                    if thumb_path and os.path.exists(thumb_path):
                        os.remove(thumb_path)
                except:
                    pass

                await progress_msg.edit_text("✅ Video downloaded and uploaded successfully!")
                return
            else:
                await progress_msg.edit_text("❌ Failed to download from direct video URL")
                return

        # Update status to detection
        unified_display.current_method = "Enhanced"
        unified_display.status = "Detecting"
        await update_progress_message_safe(bot, update.from_user.id, "🔍 Starting enhanced detection...")

        # Try enhanced detection for non-direct URLs
        enhanced_detector = EnhancedDownloadDetector()

        # Use comprehensive detection method
        await update_progress_message_safe(bot, update.from_user.id, "🔍 Running comprehensive video detection...")
        video_urls, downloaded_files = await enhanced_detector.comprehensive_video_detection(url, bot, update.chat.id)

        if video_urls and len(video_urls) > 0:
            # Found video URLs, try to download the best one
            best_url = video_urls[0]
            unified_display.filename = f"video_{int(time.time())}.mp4"

            unified_display.current_method = "Enhanced"
            unified_display.status = "Downloading"

            await update_progress_message_safe(bot, update.from_user.id, f"⬇️ Downloading from: {best_url[:50]}...")

            # Download the video
            filepath = await enhanced_detector.human_download_file(best_url, bot, update.chat.id, update.from_user.id)

            if filepath and os.path.exists(filepath):
                unified_display.status = "Uploading"
                await update_progress_message_safe(bot, update.from_user.id, "📤 Uploading to Telegram...")

                # Upload to Telegram
                await bot.send_video(
                    chat_id=update.chat.id,
                    video=filepath,
                    caption=f"✅ **Enhanced Detection Download Complete!**\n\n🔗 **Found {len(video_urls)} video URLs**\n📥 **Downloaded from:** {best_url[:100]}...",
                    reply_to_message_id=update.id
                )

                # Clean up
                try:
                    os.remove(filepath)
                except:
                    pass

                await progress_msg.edit_text("✅ Video downloaded and uploaded successfully!")
            else:
                # If first URL fails, try others
                if len(video_urls) > 1:
                    for i, alt_url in enumerate(video_urls[1:3], 2):  # Try up to 2 more URLs
                        await update_progress_message_safe(bot, update.from_user.id, f"🔄 Trying alternative URL {i}/{min(len(video_urls), 3)}...")

                        alt_filepath = await enhanced_detector.human_download_file(alt_url, bot, update.chat.id, update.from_user.id)
                        if alt_filepath and os.path.exists(alt_filepath):
                            await bot.send_video(
                                chat_id=update.chat.id,
                                video=alt_filepath,
                                caption=f"✅ **Enhanced Detection Download Complete!**\n\n🔗 **Downloaded from alternative URL {i}**",
                                reply_to_message_id=update.id
                            )

                            try:
                                os.remove(alt_filepath)
                            except:
                                pass

                            await safe_edit_message(bot, progress_msg, "✅ Video downloaded using alternative URL!")
                            return

                await safe_edit_message(bot, progress_msg, f"❌ Failed to download from {len(video_urls)} detected URLs")
        else:
            await progress_msg.edit_text("❌ No video URLs found. Try using 'auto detect' command for advanced detection or ensure the URL contains a video.")

    except Exception as e:
        logger.error(f"Direct video download error: {e}")
        await progress_msg.edit_text(f"❌ Download error: {str(e)}")
    finally:
        # Clean up progress tracking
        if update.from_user.id in progress_messages:
            del progress_messages[update.from_user.id]

async def update_progress_message(bot, user_id, status_text):
    """Update the unified progress message"""
    if user_id not in progress_messages:
        return

    try:
        progress_msg = progress_messages[user_id]
        unified_display.status = status_text

        await bot.edit_message_text(
            chat_id=progress_msg.chat.id,
            message_id=progress_msg.id,
            text=unified_display.get_unified_message(user_id)
        )
    except Exception as e:
        logger.error(f"Failed to update progress: {e}")

async def update_progress_message_safe(bot, user_id, status_text):
    """Safely update progress message with duplicate content check"""
    if user_id not in progress_messages:
        return

    try:
        progress_msg = progress_messages[user_id]
        old_status = unified_display.status
        unified_display.status = status_text

        new_text = unified_display.get_unified_message(user_id)

        # Only update if content has actually changed
        try:
            current_msg = await bot.get_messages(progress_msg.chat.id, progress_msg.id)
            if current_msg.text != new_text:
                await bot.edit_message_text(
                    chat_id=progress_msg.chat.id,
                    message_id=progress_msg.id,
                    text=new_text
                )
        except Exception as edit_error:
            # If we can't get current message, just try to update
            if "MESSAGE_NOT_MODIFIED" not in str(edit_error):
                logger.debug(f"Progress update failed: {edit_error}")

    except Exception as e:
        logger.error(f"Failed to update progress safely: {e}")

async def safe_edit_message(bot, message, text):
    """Safely edit a message, preventing MESSAGE_NOT_MODIFIED error"""
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.id,
            text=text
        )
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            logger.error(f"Failed to edit message: {e}")


# Progress callback for downloads
async def download_progress_hook(current, total, user_id, bot, filename=""):
    """Hook for download progress updates"""
    global unified_display

    if total > 0:
        unified_display.download_progress = (current / total) * 100
        unified_display.downloaded_size = humanbytes(current)
        unified_display.total_size = humanbytes(total)

        # Calculate speed
        if hasattr(unified_display, 'start_time'):
            elapsed = time.time() - unified_display.start_time
            if elapsed > 0:
                speed = current / elapsed
                unified_display.download_speed = humanbytes(speed) + "/s"

        if filename:
            unified_display.filename = filename

        await update_progress_message(bot, user_id, "Download")

async def extract_video_thumbnail(video_path, user_id):
    """Extract thumbnail from video file"""
    try:
        thumb_path = f"{Config.DOWNLOAD_LOCATION}/{user_id}_thumb.jpg"
        
        # Use ffmpeg to extract thumbnail
        import subprocess
        
        ffmpeg_cmd = [
            "ffmpeg", "-i", video_path,
            "-ss", "00:00:01", "-vframes", "1",
            "-q:v", "2", thumb_path, "-y"
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(thumb_path):
            # Process thumbnail
            from PIL import Image
            img = Image.open(thumb_path)
            
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize thumbnail
            img.thumbnail((320, 240), Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=85)
            
            return thumb_path
            
    except Exception as e:
        logger.error(f"Thumbnail extraction failed: {e}")
    
    return None

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size:
        return "0 B"
    power = 1024


@pyrogram.Client.on_callback_query()
async def handle_detection_callback(bot, callback_query):
    """Handle detection method callbacks"""
    data = callback_query.data
    
    if data.startswith("auto_detect|"):
        url_hash = data.split("|", 1)[1]
        url = getattr(echo, '_url_cache', {}).get(url_hash, "")
        if not url:
            await callback_query.answer("❌ URL expired, please send again")
            return
            
        await callback_query.answer("🔍 Starting auto detection...")
        
        # Create a fake message object for processing
        fake_message = type('obj', (object,), {
            'chat': callback_query.message.chat,
            'from_user': callback_query.from_user,
            'id': callback_query.message.id,
            'text': f"auto detect {url}"
        })()
        
        # Import and use auto detector
        from plugins.auto_download_detector import auto_detect_handler
        await auto_detect_handler(bot, fake_message)
        
    elif data.startswith("direct_download|"):
        url_hash = data.split("|", 1)[1]
        url = getattr(echo, '_url_cache', {}).get(url_hash, "")
        if not url:
            await callback_query.answer("❌ URL expired, please send again")
            return
            
        await callback_query.answer("⬇️ Starting direct download...")
        
        fake_message = type('obj', (object,), {
            'chat': callback_query.message.chat,
            'from_user': callback_query.from_user,
            'id': callback_query.message.id
        })()
        
        await handle_direct_video_download(bot, fake_message, url, is_direct=True)
        
    elif data.startswith("enhanced_detect|"):
        url_hash = data.split("|", 1)[1]
        url = getattr(echo, '_url_cache', {}).get(url_hash, "")
        if not url:
            await callback_query.answer("❌ URL expired, please send again")
            return
            
        await callback_query.answer("🌐 Starting enhanced detection...")
        
        fake_message = type('obj', (object,), {
            'chat': callback_query.message.chat,
            'from_user': callback_query.from_user,
            'id': callback_query.message.id
        })()
        
        await handle_direct_video_download(bot, fake_message, url, is_direct=False)


    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.1f} {power_labels[n]}B"