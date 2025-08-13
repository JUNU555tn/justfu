#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K

# the logging things
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import asyncio
import json
import math
import os
import shutil
import time
from datetime import datetime

# the secret configuration specific things
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

# the Strings used for this "thing"
from translation import Translation

import pyrogram
logging.getLogger("pyrogram").setLevel(logging.WARNING)

from pyrogram.types import InputMediaPhoto
from pyrogram import enums
from helper_funcs.display_progress import progress_for_pyrogram, humanbytes
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
# https://stackoverflow.com/a/37631799/4723940
from PIL import Image
from helper_funcs.help_Nekmo_ffmpeg import generate_screen_shots


async def youtube_dl_call_back(bot, update):
    cb_data = update.data
    # youtube_dl extractors
    tg_send_type, youtube_dl_format, youtube_dl_ext = cb_data.split("|")
    thumb_image_path = Config.DOWNLOAD_LOCATION + \
        "/" + str(update.from_user.id) + ".jpg"
    save_ytdl_json_path = Config.DOWNLOAD_LOCATION + \
        "/" + str(update.from_user.id) + ".json"
    try:
        with open(save_ytdl_json_path, "r", encoding="utf8") as f:
            response_json = json.load(f)
    except (FileNotFoundError) as e:
        await bot.delete_messages(
            chat_id=update.message.chat.id,
            message_ids=update.message.message_id,
            revoke=True
        )
        return False
    youtube_dl_url = update.message.reply_to_message.text
    custom_file_name = str(response_json.get("title")) + \
        "_" + youtube_dl_format + "." + youtube_dl_ext
    youtube_dl_username = None
    youtube_dl_password = None
    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        if len(url_parts) == 2:
            youtube_dl_url = url_parts[0]
            custom_file_name = url_parts[1]
        elif len(url_parts) == 4:
            youtube_dl_url = url_parts[0]
            custom_file_name = url_parts[1]
            youtube_dl_username = url_parts[2]
            youtube_dl_password = url_parts[3]
        else:
            for entity in update.message.reply_to_message.entities:
                if entity.type == "text_link":
                    youtube_dl_url = entity.url
                elif entity.type == "url":
                    o = entity.offset
                    l = entity.length
                    youtube_dl_url = youtube_dl_url[o:o + l]
        if youtube_dl_url is not None:
            youtube_dl_url = youtube_dl_url.strip()
        if custom_file_name is not None:
            custom_file_name = custom_file_name.strip()
        # https://stackoverflow.com/a/761825/4723940
        if youtube_dl_username is not None:
            youtube_dl_username = youtube_dl_username.strip()
        if youtube_dl_password is not None:
            youtube_dl_password = youtube_dl_password.strip()
        logger.info(youtube_dl_url)
        logger.info(custom_file_name)
    else:
        for entity in update.message.reply_to_message.entities:
            if entity.type == "text_link":
                youtube_dl_url = entity.url
            elif entity.type == "url":
                o = entity.offset
                l = entity.length
                youtube_dl_url = youtube_dl_url[o:o + l]
    await bot.edit_message_text(
        text=Translation.DOWNLOAD_START,
        chat_id=update.message.chat.id,
        message_id=update.message.id
    )
    user = await bot.get_me()
    mention = f"@{user.username}" if user.username else user.first_name
    description = Translation.CUSTOM_CAPTION_UL_FILE.format(mention)
    if "fulltitle" in response_json:
        description = response_json["fulltitle"][0:1021]
        # escape Markdown and special characters
    tmp_directory_for_each_user = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id)
    if not os.path.isdir(tmp_directory_for_each_user):
        os.makedirs(tmp_directory_for_each_user)
    download_directory = tmp_directory_for_each_user + "/" + custom_file_name
    command_to_exec = []
    if tg_send_type == "audio":
        command_to_exec = [
            "yt-dlp",
            "-c",
            "--max-filesize", str(Config.TG_MAX_FILE_SIZE),
            "--prefer-ffmpeg",
            "--extract-audio",
            "--audio-format", youtube_dl_ext,
            "--audio-quality", youtube_dl_format,
            youtube_dl_url,
            "-o", download_directory
        ]
    else:
        # command_to_exec = ["youtube-dl", "-f", youtube_dl_format, "--hls-prefer-ffmpeg", "--recode-video", "mp4", "-k", youtube_dl_url, "-o", download_directory]
        minus_f_format = youtube_dl_format
        if "youtu" in youtube_dl_url:
            minus_f_format = youtube_dl_format + "+bestaudio"
        command_to_exec = [
            "yt-dlp",
            "-c",
            "--max-filesize", str(Config.TG_MAX_FILE_SIZE),
            "--embed-subs",
            "-f", minus_f_format,
            "--hls-prefer-ffmpeg", 
            "--merge-output-format", "mp4",
            youtube_dl_url,
            "-o", download_directory
        ]
    if Config.HTTP_PROXY != "":
        command_to_exec.append("--proxy")
        command_to_exec.append(Config.HTTP_PROXY)
    if youtube_dl_username is not None:
        command_to_exec.append("--username")
        command_to_exec.append(youtube_dl_username)
    if youtube_dl_password is not None:
        command_to_exec.append("--password")
        command_to_exec.append(youtube_dl_password)
    command_to_exec.append("--no-warnings")
    # command_to_exec.append("--quiet")
    logger.info(command_to_exec)
    start = datetime.now()
    
    # Create subprocess with real-time output monitoring
    process = await asyncio.create_subprocess_exec(
        *command_to_exec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    
    # Monitor download progress in real-time
    output_lines = []
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        line_text = line.decode().strip()
        output_lines.append(line_text)
        logger.info(line_text)
        
        # Parse download progress and update message
        if "[download]" in line_text and "%" in line_text:
            try:
                # Extract progress percentage
                if "%" in line_text and "of" in line_text:
                    progress_part = line_text.split("%")[0]
                    percentage = progress_part.split()[-1]
                    
                    # Extract size info
                    size_part = line_text.split("of")
                    if len(size_part) > 1:
                        downloaded_size = size_part[0].split()[-1]
                        total_size = size_part[1].split()[0]
                        
                        progress_text = f"📥 Downloading... {percentage}%\n📊 {downloaded_size} of {total_size}"
                        
                        # Extract speed if available
                        if "at" in line_text:
                            speed = line_text.split("at")[-1].strip()
                            progress_text += f"\n⚡ Speed: {speed}"
                        
                        await bot.edit_message_text(
                            text=progress_text,
                            chat_id=update.message.chat.id,
                            message_id=update.message.id
                        )
            except Exception as e:
                logger.error(f"Error parsing progress: {e}")
    
    await process.wait()
    t_response = "\n".join(output_lines)
    e_response = ""
    ad_string_to_replace = "please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output."
    if e_response and ad_string_to_replace in e_response:
        error_message = e_response.replace(ad_string_to_replace, "")
        await bot.edit_message_text(
            chat_id=update.message.chat.id,
            message_id=update.message.id,
            text=error_message
        )
        return False
    if t_response:
        # logger.info(t_response)
        os.remove(save_ytdl_json_path)
        end_one = datetime.now()
        time_taken_for_download = (end_one -start).seconds
        file_size = Config.TG_MAX_FILE_SIZE + 1
        
        # Try to find the actual downloaded file
        actual_file = None
        base_name = os.path.splitext(download_directory)[0]
        
        # Check for various possible file extensions
        possible_extensions = ['.mp4', '.mkv', '.webm', '.m4a', '.mp3']
        
        for ext in possible_extensions:
            test_file = base_name + ext
            if os.path.exists(test_file):
                actual_file = test_file
                break
        
        # If no direct match, check the download directory for any files
        if not actual_file:
            download_dir = os.path.dirname(download_directory)
            if os.path.exists(download_dir):
                files = [f for f in os.listdir(download_dir) if f.endswith(tuple(possible_extensions))]
                if files:
                    # Get the most recently created file
                    files.sort(key=lambda x: os.path.getctime(os.path.join(download_dir, x)), reverse=True)
                    actual_file = os.path.join(download_dir, files[0])
        
        if actual_file and os.path.exists(actual_file):
            download_directory = actual_file
            file_size = os.stat(download_directory).st_size
        else:
            raise FileNotFoundError(f"Could not find downloaded file. Expected: {download_directory}")
        if file_size > Config.TG_MAX_FILE_SIZE:
            await bot.edit_message_text(
                chat_id=update.message.chat.id,
                text=Translation.RCHD_TG_API_LIMIT.format(time_taken_for_download, humanbytes(file_size)),
                message_id=update.message.id
            )
        else:
            is_w_f = False
            images = await generate_screen_shots(
                download_directory,
                tmp_directory_for_each_user,
                False,
                None,
                0,
                10
            )

            # Handle case when ffmpeg is not available
            if images is None:
                logger.warning("Could not generate screenshots, proceeding without them")
            await bot.edit_message_text(
                text=Translation.UPLOAD_START,
                chat_id=update.message.chat.id,
                message_id=update.message.id
            )
            # get the correct width, height, and duration for videos greater than 10MB
            # ref: message from @BotSupport
            width = 0
            height = 0
            duration = 0
            if tg_send_type != "file":
                metadata = extractMetadata(createParser(download_directory))
                if metadata is not None:
                    if metadata.has("duration"):
                        duration = metadata.get('duration').seconds
            # Enhanced thumbnail handling with automatic extraction
            if not os.path.exists(thumb_image_path):
                # Try to extract thumbnail from the downloaded video
                try:
                    await bot.edit_message_text(
                        text="📸 Extracting thumbnail from video...",
                        chat_id=update.message.chat.id,
                        message_id=update.message.id
                    )
                    
                    # Extract thumbnail from video using ffmpeg
                    video_thumb_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + "_video_thumb.jpg"
                    
                    # Try to use ffmpeg to extract a frame
                    import subprocess
                    try:
                        ffmpeg_command = [
                            "ffmpeg", "-i", download_directory,
                            "-ss", "00:00:01", "-vframes", "1",
                            "-q:v", "2", video_thumb_path, "-y"
                        ]
                        
                        result = subprocess.run(ffmpeg_command, 
                                              capture_output=True, 
                                              timeout=30)
                        
                        if result.returncode == 0 and os.path.exists(video_thumb_path):
                            thumb_image_path = video_thumb_path
                            logger.info("Successfully extracted thumbnail from video")
                        else:
                            logger.warning("ffmpeg thumbnail extraction failed")
                    
                    except subprocess.TimeoutExpired:
                        logger.warning("ffmpeg thumbnail extraction timed out")
                    except FileNotFoundError:
                        logger.warning("ffmpeg not available for thumbnail extraction")
                    except Exception as ffmpeg_error:
                        logger.error(f"ffmpeg error: {ffmpeg_error}")
                
                except Exception as extract_error:
                    logger.error(f"Thumbnail extraction failed: {extract_error}")
            
            # Process existing thumbnail
            if os.path.exists(thumb_image_path):
                try:
                    width = 0
                    height = 0
                    
                    # Get thumbnail metadata
                    metadata = extractMetadata(createParser(thumb_image_path))
                    if metadata and metadata.has("width"):
                        width = metadata.get("width")
                    if metadata and metadata.has("height"):
                        height = metadata.get("height")
                    if tg_send_type == "vm":
                        height = width
                    
                    # Process and resize thumbnail
                    img = Image.open(thumb_image_path)
                    
                    # Convert to RGB if needed
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Resize based on type
                    if tg_send_type == "file":
                        img.thumbnail((320, 240), Image.Resampling.LANCZOS)
                    else:
                        img.thumbnail((90, 90), Image.Resampling.LANCZOS)
                    
                    img.save(thumb_image_path, "JPEG", quality=85)
                    
                except Exception as thumb_error:
                    logger.error(f"Thumbnail processing error: {thumb_error}")
                    # Remove corrupted thumbnail
                    try:
                        os.remove(thumb_image_path)
                        thumb_image_path = None
                    except:
                        pass
            else:
                thumb_image_path = None
            start_time = time.time()
            # try to upload file
            if tg_send_type == "audio":
                await bot.send_audio(
                    chat_id=update.message.chat.id,
                    audio=download_directory,
                    caption=description,
                    parse_mode=enums.ParseMode.HTML,
                    duration=duration,
                    # performer=response_json["uploader"],
                    # title=response_json["title"],
                    # reply_markup=reply_markup,
                    thumb=thumb_image_path,
                    reply_to_message_id=update.message.reply_to_message.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
            elif tg_send_type == "file":
                await bot.send_document(
                    chat_id=update.message.chat.id,
                    document=download_directory,
                    thumb=thumb_image_path,
                    caption=description,
                    parse_mode=enums.ParseMode.HTML,
                    # reply_markup=reply_markup,
                    reply_to_message_id=update.message.reply_to_message.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
            elif tg_send_type == "vm":
                await bot.send_video_note(
                    chat_id=update.message.chat.id,
                    video_note=download_directory,
                    duration=duration,
                    length=width,
                    thumb=thumb_image_path,
                    reply_to_message_id=update.message.reply_to_message.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
            elif tg_send_type == "video":
                await bot.send_video(
                    chat_id=update.message.chat.id,
                    video=download_directory,
                    caption=description,
                    parse_mode=enums.ParseMode.HTML,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    # reply_markup=reply_markup,
                    thumb=thumb_image_path,
                    reply_to_message_id=update.message.reply_to_message.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
            else:
                logger.info("Did this happen? :\\")
            end_two = datetime.now()
            time_taken_for_upload = (end_two - end_one).seconds
            #
            media_album_p = []
            if images is not None:
                i = 0
                caption = "© @LazyDeveloperr"
                if is_w_f:
                    caption = "@LazyDeveloperr"
                for image in images:
                    if os.path.exists(str(image)):
                        if i == 0:
                            media_album_p.append(
                                InputMediaPhoto(
                                    media=image,
                                    caption=caption,
                                    parse_mode=enums.ParseMode.HTML
                                )
                            )
                        else:
                            media_album_p.append(
                                InputMediaPhoto(
                                    media=image
                                )
                            )
                        i = i + 1
            await bot.send_media_group(
                chat_id=update.message.chat.id,
                disable_notification=True,
                reply_to_message_id=update.message.reply_to_message.id,
                media=media_album_p
            )
            #
            try:
                shutil.rmtree(tmp_directory_for_each_user)
                os.remove(thumb_image_path)
            except:
                pass
            await bot.edit_message_text(
                text=Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(time_taken_for_download, time_taken_for_upload),
                chat_id=update.message.chat.id,
                message_id=update.message.id,
                disable_web_page_preview=True
            )