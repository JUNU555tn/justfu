#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Thank you LazyDeveloperr for helping us in this journey.

# the logging things
import logging
import time
from helper_funcs.display_progress import humanbytes
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import os
import requests

def DetectFileSize(url):
    r = requests.get(url, allow_redirects=True, stream=True)
    total_size = int(r.headers.get("content-length", 0))
    return total_size


def DownLoadFile(url, file_name, chunk_size, client, ud_type, message_id, chat_id):
    if os.path.exists(file_name):
        os.remove(file_name)
    if not url:
        return file_name
    r = requests.get(url, allow_redirects=True, stream=True)
    # https://stackoverflow.com/a/47342052/4723940
    total_size = int(r.headers.get("content-length", 0))
    downloaded_size = 0
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
                downloaded_size += chunk_size
            if client is not None:
                if ((total_size // downloaded_size) % 5) == 0:
                    time.sleep(0.3)
                    try:
                        client.edit_message_text(
                            chat_id,
                            message_id,
                            text="{}: {} of {}".format(
                                ud_type,
                                humanbytes(downloaded_size),
                                humanbytes(total_size)
                            )
                        )
                    except:
                        pass
    return file_name
import asyncio
import json
import subprocess
import logging
import os
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config

logger = logging.getLogger(__name__)

async def get_formats_from_link(url, bot, update):
    """Get available formats from YouTube URL using yt-dlp"""
    try:
        # Create temporary JSON file path
        json_file_path = f"{Config.DOWNLOAD_LOCATION}/{update.from_user.id}.json"
        
        # yt-dlp command to get formats with better extraction
        command = [
            "yt-dlp",
            "--dump-json",
            "--no-warnings",
            "--no-playlist",
            "--geo-bypass",
            "--ignore-errors",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "--referer", url,
            "--extractor-retries", "3",
            "--fragment-retries", "3",
            url
        ]
        
        # Execute yt-dlp command
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            # Parse JSON response
            response_json = json.loads(stdout.decode())
            
            # Save JSON for later use
            with open(json_file_path, "w", encoding="utf8") as f:
                json.dump(response_json, f, ensure_ascii=False, indent=4)
            
            # Create format buttons
            await create_format_buttons(bot, update, response_json)
            
            return response_json
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"yt-dlp error: {error_msg}")
            return None
            
    except Exception as e:
        logger.error(f"Format detection error: {e}")
        return None

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size or size == 0:
        return "Unknown"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.0f}{power_labels[n]}B"

async def get_format_filesize(format_info):
    """Get filesize from format info with fallback estimation"""
    filesize = format_info.get('filesize') or format_info.get('filesize_approx')
    
    if not filesize:
        # Estimate based on bitrate and duration if available
        tbr = format_info.get('tbr') or format_info.get('abr', 0)
        duration = format_info.get('duration', 0)
        if tbr and duration:
            filesize = int(tbr * duration * 125)  # Convert kbps to bytes
    
    return filesize or 0

async def create_format_buttons(bot, update, response_json):
    """Create inline keyboard with format options showing quality and file size"""
    try:
        formats = response_json.get('formats', [])
        duration = response_json.get('duration', 0)
        
        # Filter and organize formats
        video_formats = []
        audio_formats = []
        
        for fmt in formats:
            filesize = await get_format_filesize(fmt)
            
            if fmt.get('vcodec') != 'none' and fmt.get('height'):
                # Video format
                quality = f"{fmt.get('height')}p"
                ext = fmt.get('ext', 'mp4')
                format_id = fmt.get('format_id')
                fps = fmt.get('fps', '')
                
                video_formats.append({
                    'quality': quality,
                    'ext': ext,
                    'format_id': format_id,
                    'filesize': filesize,
                    'height': fmt.get('height', 0),
                    'fps': fps
                })
            elif fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                # Audio format
                abr = fmt.get('abr') or fmt.get('tbr', 0)
                quality = f"{int(abr)}kbps" if abr else "Audio"
                ext = fmt.get('ext', 'mp3')
                format_id = fmt.get('format_id')
                
                audio_formats.append({
                    'quality': quality,
                    'ext': ext,
                    'format_id': format_id,
                    'filesize': filesize
                })
        
        # Sort video formats by quality (height)
        video_formats.sort(key=lambda x: x['height'], reverse=True)
        
        # Remove duplicates and keep best quality for each resolution
        unique_video_formats = []
        seen_qualities = set()
        for fmt in video_formats:
            quality_key = f"{fmt['quality']}-{fmt['ext']}"
            if quality_key not in seen_qualities:
                seen_qualities.add(quality_key)
                unique_video_formats.append(fmt)
        
        # Create buttons
        buttons = []
        
        # Add video format buttons with quality and size
        for fmt in unique_video_formats[:6]:  # Limit to 6 video formats to reduce data
            size_text = humanbytes(fmt['filesize']) if fmt['filesize'] else "?"
            fps_text = f"{fmt['fps']}fps " if fmt['fps'] else ""
            button_text = f"📹 {fmt['quality']} {fps_text}/ {size_text}"
            # Shorten callback data to avoid BUTTON_DATA_INVALID error
            callback_data = f"video|{fmt['format_id']}|{fmt['ext']}"[:64]  # Telegram limit
            buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add audio format buttons with bitrate and size
        if audio_formats:
            # Sort by bitrate/quality
            audio_formats.sort(key=lambda x: x.get('filesize', 0), reverse=True)
            best_audio = audio_formats[0]
            size_text = humanbytes(best_audio['filesize']) if best_audio['filesize'] else "?"
            button_text = f"🎵 {best_audio['quality']} / {size_text}"
            # Shorten callback data
            callback_data = f"audio|{best_audio['format_id']}|{best_audio['ext']}"[:64]
            buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add file download option
        buttons.append([InlineKeyboardButton("📁 Best Quality File", callback_data="file|best|mp4")])
        
        # Add fallback options for generic sites
        buttons.append([InlineKeyboardButton("🎬 Generic Video", callback_data="video|best|mp4")])
        buttons.append([InlineKeyboardButton("📱 Mobile Quality", callback_data="video|worst|mp4")])
        
        # Calculate video info for display
        title = response_json.get('title', 'Video')
        uploader = response_json.get('uploader', 'Unknown')
        duration_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "Unknown"
        
        # Send format selection message
        info_text = f"🎬 **{title}**\n"
        info_text += f"👤 **Uploader:** {uploader}\n"
        info_text += f"⏱️ **Duration:** {duration_str}\n\n"
        info_text += "📥 **Select download quality:**"
        
        await bot.send_message(
            chat_id=update.chat.id,
            text=info_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=update.id
        )
        
    except Exception as e:
        logger.error(f"Button creation error: {e}")
