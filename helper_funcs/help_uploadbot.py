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
        
        # yt-dlp command to get formats
        command = [
            "yt-dlp",
            "--dump-json",
            "--no-warnings",
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

async def create_format_buttons(bot, update, response_json):
    """Create inline keyboard with format options"""
    try:
        formats = response_json.get('formats', [])
        
        # Filter and organize formats
        video_formats = []
        audio_formats = []
        
        for fmt in formats:
            if fmt.get('vcodec') != 'none' and fmt.get('height'):
                # Video format
                quality = f"{fmt.get('height')}p"
                ext = fmt.get('ext', 'mp4')
                format_id = fmt.get('format_id')
                filesize = fmt.get('filesize') or 0
                
                video_formats.append({
                    'quality': quality,
                    'ext': ext,
                    'format_id': format_id,
                    'filesize': filesize
                })
            elif fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                # Audio format
                quality = f"{fmt.get('abr', 'unknown')}kbps"
                ext = fmt.get('ext', 'mp3')
                format_id = fmt.get('format_id')
                
                audio_formats.append({
                    'quality': quality,
                    'ext': ext,
                    'format_id': format_id
                })
        
        # Sort video formats by quality
        video_formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
        
        # Create buttons
        buttons = []
        
        # Add video format buttons
        for fmt in video_formats[:6]:  # Limit to 6 video formats
            button_text = f"📹 {fmt['quality']} ({fmt['ext']})"
            callback_data = f"video|{fmt['format_id']}|{fmt['ext']}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add audio format buttons
        if audio_formats:
            best_audio = audio_formats[0]
            button_text = f"🎵 Audio ({best_audio['ext']})"
            callback_data = f"audio|{best_audio['format_id']}|{best_audio['ext']}"
            buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add file download option
        buttons.append([InlineKeyboardButton("📁 File", callback_data="file|best|mp4")])
        
        # Send format selection message
        await bot.send_message(
            chat_id=update.chat.id,
            text=f"🎬 **{response_json.get('title', 'Video')}**\n\nSelect download quality:",
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=update.id
        )
        
    except Exception as e:
        logger.error(f"Button creation error: {e}")
