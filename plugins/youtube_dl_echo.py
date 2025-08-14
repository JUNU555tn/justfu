
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
        r'(?:https?://)?(?:www\.)?(?:vimeo\.com)',
        r'(?:https?://)?(?:www\.)?(?:dailymotion\.com)',
        r'(?:https?://)?(?:www\.)?(?:twitch\.tv)',
        r'(?:https?://)?(?:www\.)?(?:instagram\.com)',
        r'(?:https?://)?(?:www\.)?(?:facebook\.com)',
        r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)',
        r'(?:https?://)?(?:www\.)?(?:tiktok\.com)'
    ]
    
    for pattern in youtube_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
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
    
    # Check if it's a YouTube or yt-dlp supported URL
    if is_youtube_url(url):
        # Use yt-dlp for YouTube and supported platforms
        await handle_youtube_download(bot, update, url)
    else:
        # Use enhanced detection for direct video URLs
        await handle_direct_video_download(bot, update, url)

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

async def handle_direct_video_download(bot, update, url):
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
        # Check if URL is already a direct video link
        if any(ext in url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
            # Direct video URL - download immediately
            unified_display.current_method = "Direct"
            unified_display.status = "Downloading"
            await update_progress_message_safe(bot, update.from_user.id, "⬇️ Direct video URL detected, downloading...")
            
            enhanced_detector = EnhancedDownloadDetector()
            filepath = await enhanced_detector.human_download_file(url, bot, update.chat.id, update.from_user.id)
            
            if filepath and os.path.exists(filepath):
                unified_display.status = "Uploading"
                await update_progress_message_safe(bot, update.from_user.id, "📤 Uploading to Telegram...")
                
                # Upload to Telegram
                await bot.send_video(
                    chat_id=update.chat.id,
                    video=filepath,
                    caption="✅ **Direct Video Download Complete!**\n\nDownloaded from direct video URL",
                    reply_to_message_id=update.id
                )
                
                # Clean up
                try:
                    os.remove(filepath)
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
                                
                            await progress_msg.edit_text("✅ Video downloaded using alternative URL!")
                            return
                
                await progress_msg.edit_text(f"❌ Failed to download from {len(video_urls)} detected URLs")
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

def humanbytes(size):
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
