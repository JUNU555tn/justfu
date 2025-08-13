#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K | X-Noid

# the logging things
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
import urllib.parse, filetype, shutil, time, tldextract, asyncio, json, math, os, requests, re
from PIL import Image
# the secret configuration specific things
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

# the Strings used for this "thing"
from translation import Translation

import pyrogram
logging.getLogger("pyrogram").setLevel(logging.WARNING)
from helper_funcs.display_progress import humanbytes
from helper_funcs.help_uploadbot import DownLoadFile
from helper_funcs.display_progress import progress_for_pyrogram
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import UserNotParticipant
from pyrogram import Client, enums

def estimate_file_size_by_quality(height, duration=None):
    """Estimate file size based on video quality"""
    if not duration:
        duration = 600  # Default 10 minutes

    # Rough estimates in MB per minute for different qualities
    quality_rates = {
        2160: 25,    # 4K - ~25MB/min
        1440: 12,    # 1440p - ~12MB/min  
        1080: 8,     # 1080p - ~8MB/min
        720: 4,      # 720p - ~4MB/min
        480: 2.5,    # 480p - ~2.5MB/min
        360: 1.5,    # 360p - ~1.5MB/min
        240: 1       # 240p - ~1MB/min
    }

    duration_minutes = duration / 60
    rate = quality_rates.get(height, 2)
    estimated_mb = rate * duration_minutes

    if estimated_mb >= 1024:
        return f"{estimated_mb/1024:.1f}GB"
    else:
        return f"{estimated_mb:.0f}MB"

# Check if LK21 is available due to Python compatibility issues
try:
    import lk21
    LK21_AVAILABLE = True
    logger.info("lk21 module loaded successfully.")
except ImportError:
    LK21_AVAILABLE = False
    logger.warning("Using alternative bypass method for LK21 compatible sites.")

# Custom LK21 bypass implementation
def custom_lk21_bypass(url):
    """
    Custom bypass for LK21-compatible sites
    """
    try:
        import re

        # Common headers to bypass detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        session = requests.Session()
        session.headers.update(headers)

        # Get the page content
        response = session.get(url)
        response.raise_for_status()

        # Look for common video URL patterns
        video_patterns = [
            r'file\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'src\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'source\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'"file"\s*:\s*"([^"]+\.mp4[^"]*)"',
            r'data-src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'href=["\']([^"\']+\.mp4[^"\']*)["\']'
        ]

        content = response.text

        for pattern in video_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Return the first valid match
                for match in matches:
                    if match.startswith('http'):
                        logger.info(f"Found video URL via custom bypass: {match}")
                        return match

        # If no direct video URL found, try to extract from JavaScript
        js_patterns = [
            r'var\s+\w+\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'let\s+\w+\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'const\s+\w+\s*=\s*["\']([^"\']+\.mp4[^"\']*)["\']'
        ]

        for pattern in js_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                for match in matches:
                    if match.startswith('http'):
                        logger.info(f"Found video URL in JavaScript: {match}")
                        return match

        logger.warning("Could not extract video URL using custom bypass")
        return None

    except Exception as e:
        logger.error(f"Error in custom LK21 bypass: {str(e)}")
        return None


async def send_live_log(bot: Client, chat_id: int, message: str):
    """Send live log updates"""
    try:
        await bot.send_message(chat_id=chat_id, text=f"📊 {message}")
        logger.info(f"Live log: {message}")
    except Exception as e:
        logger.error(f"Failed to send live log: {e}")

@pyrogram.Client.on_message(pyrogram.filters.regex(pattern=".*http.*"))
async def echo(bot: Client, update: Message):
    if update.from_user.id in Config.AUTH_USERS:
        logger.info(update.from_user)
        url = update.text
        youtube_dl_username = None
        youtube_dl_password = None
        file_name = None
        folder = f'./lk21/{update.from_user.id}/'
        bypass = ['zippyshare', 'hxfile', 'mediafire', 'anonfiles', 'antfiles', 'gofile', 'uploadhaven', 'solidfiles', 'uploaded', 'turbobit']
        ext = tldextract.extract(url)
        if ext.domain in bypass:
            pablo = await update.reply_text('🔄 Bypass link detected, processing...')
            time.sleep(1)
            if os.path.isdir(folder):
                await update.reply_text("⚠️ Don't spam, wait till your previous task is done.")
                await pablo.delete()
                return
            os.makedirs(folder)
            await pablo.edit_text('🔍 Bypassing URL...')

            if LK21_AVAILABLE:
                try:
                    bypasser = lk21.Bypass()
                    xurl = bypasser.bypass_url(url)
                except Exception as e:
                    logger.error(f"LK21 bypass failed: {e}")
                    await pablo.edit_text('❌ Bypass failed, trying alternative method...')
                    # Fall back to direct download
                    xurl = url
            else:
                # Use custom bypass method when lk21 is not available
                try:
                    await pablo.edit_text('🔄 Using alternative bypass method...')
                    xurl = custom_lk21_bypass(url)
                    if xurl is None:
                        # Fall back to simple redirect following
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                        response = requests.get(url, headers=headers, allow_redirects=True)
                        xurl = response.url
                        logger.info(f"Alternative bypass successful: {xurl}")
                except Exception as e:
                    logger.error(f"Alternative bypass failed: {e}")
                    xurl = url

            if ' | ' in url:
                url_parts = url.split(' | ')
                url = url_parts[0]
                file_name = url_parts[1]
            else:
                if xurl.find('/'):
                    urlname = xurl.rsplit('/', 1)[1]
                file_name = urllib.parse.unquote(urlname)
                if '+' in file_name:
                    file_name = file_name.replace('+', ' ')
            dldir = f'{folder}{file_name}'
            await pablo.edit_text('📥 Starting download...')

            # Download with progress
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                with requests.get(xurl, stream=True, headers=headers, allow_redirects=True) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = time.time()

                    with open(dldir, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

                                # Update progress every 1MB or 10%
                                if downloaded % (1024*1024) == 0 or (total_size and downloaded % (total_size//10) == 0):
                                    if total_size:
                                        progress = (downloaded / total_size) * 100
                                        speed = downloaded / (time.time() - start_time)
                                        await pablo.edit_text(
                                            f'📥 Downloading... {progress:.1f}%\n'
                                            f'📊 {humanbytes(downloaded)}/{humanbytes(total_size)}\n'
                                            f'⚡ Speed: {humanbytes(speed)}/s'
                                        )
            except Exception as e:
                logger.error(f"Download failed: {e}")
                await pablo.edit_text('❌ Download failed, trying direct method...')
                r = requests.get(xurl, allow_redirects=True)
                open(dldir, 'wb').write(r.content)
            try:
                file = filetype.guess(dldir)
                xfiletype = file.mime
            except AttributeError:
                xfiletype = file_name
            if xfiletype in ['video/mp4', 'video/x-matroska', 'video/webm', 'audio/mpeg']:
                metadata = extractMetadata(createParser(dldir))
                if metadata is not None:
                    if metadata.has("duration"):
                        duration = metadata.get('duration').seconds
            await pablo.edit_text('📤 Starting upload...')
            start_time = time.time()
            if xfiletype in ['video/mp4', 'video/x-matroska', 'video/webm']:
                await bot.send_video(
                    chat_id=update.chat.id,
                    video=dldir,
                    caption=file_name,
                    duration=duration,
                    reply_to_message_id=update.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        pablo,
                        start_time
                    )
                )
            elif xfiletype == 'audio/mpeg':
                await bot.send_audio(
                    chat_id=update.chat.id,
                    audio=dldir,
                    caption=file_name,
                    duration=duration,
                    reply_to_message_id=update.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        pablo,
                        start_time
                    )
                )
            else:
                await bot.send_document(
                    chat_id=update.chat.id,
                    document=dldir,
                    caption=file_name,
                    reply_to_message_id=update.id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        pablo,
                        start_time
                    )
                )
            await pablo.delete()
            shutil.rmtree(folder)
            return

        if "|" in url:
            url_parts = url.split("|")
            if len(url_parts) == 2:
                url = url_parts[0]
                file_name = url_parts[1]
            elif len(url_parts) == 4:
                url = url_parts[0]
                file_name = url_parts[1]
                youtube_dl_username = url_parts[2]
                youtube_dl_password = url_parts[3]
            else:
                for entity in update.entities:
                    if entity.type == "text_link":
                        url = entity.url
                    elif entity.type == "url":
                        o = entity.offset
                        l = entity.length
                        url = url[o:o + l]
            if url is not None:
                url = url.strip()
            if file_name is not None:
                file_name = file_name.strip()
            # https://stackoverflow.com/a/761825/4723940
            if youtube_dl_username is not None:
                youtube_dl_username = youtube_dl_username.strip()
            if youtube_dl_password is not None:
                youtube_dl_password = youtube_dl_password.strip()
            logger.info(url)
            logger.info(file_name)
        else:
            for entity in update.entities:
                if entity.type == "text_link":
                    url = entity.url
                elif entity.type == "url":
                    o = entity.offset
                    l = entity.length
                    url = url[o:o + l]
        if Config.HTTP_PROXY != "":
            command_to_exec = [
                "yt-dlp",
                "--no-warnings",
                "--youtube-skip-dash-manifest",
                "-j",
                url,
                "--proxy", Config.HTTP_PROXY
            ]
        else:
            command_to_exec = [
                "yt-dlp",
                "--no-warnings",
                "--youtube-skip-dash-manifest",
                "-j",
                url
            ]
        if youtube_dl_username is not None:
            command_to_exec.append("--username")
            command_to_exec.append(youtube_dl_username)
        if youtube_dl_password is not None:
            command_to_exec.append("--password")
            command_to_exec.append(youtube_dl_password)
        # logger.info(command_to_exec)
        process = await asyncio.create_subprocess_exec(
            *command_to_exec,
            # stdout must a pipe to be accessible as process.stdout
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Wait for the subprocess to finish
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        # logger.info(e_response)
        t_response = stdout.decode().strip()
        # logger.info(t_response)
        # https://github.com/rg3/youtube-dl/issues/2630#issuecomment-38635239
        if e_response and "nonnumeric port" not in e_response:
            # logger.warn("Status : FAIL", exc.returncode, exc.output)
            error_message = e_response.replace("please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output.", "")
            if "This video is only available for registered users." in error_message:
                error_message += Translation.SET_CUSTOM_USERNAME_PASSWORD

            await send_live_log(bot, update.chat.id, "❌ yt-dlp failed, trying enhanced detection...")

            await bot.send_message(
                chat_id=update.chat.id,
                text="❌ yt-dlp failed, trying enhanced detection with human-like clicking...",
                reply_to_message_id=update.id
            )

            from plugins.auto_download_detector import enhanced_detector
            await bot.send_message(
                chat_id=update.chat.id,
                text="🤖 Launching human-like auto-detection and download...",
                reply_to_message_id=update.id
            )

            try:
                detected_urls, downloaded_files = await enhanced_detector.comprehensive_video_detection(
                    url, bot, update.chat.id
                )

                if detected_urls:
                    await bot.send_message(
                        chat_id=update.chat.id,
                        text=f"✅ Enhanced detection found {len(detected_urls)} URLs with human-like clicking!",
                        reply_to_message_id=update.id
                    )

                    # Try each detected URL with yt-dlp until one works
                    download_successful = False

                    for i, detected_url in enumerate(detected_urls, 1):
                        logger.info(f"Trying detected URL {i}/{len(detected_urls)} with yt-dlp: {detected_url}")

                        await bot.send_message(
                            chat_id=update.chat.id,
                            text=f"🔄 Attempting download {i}/{len(detected_urls)}: Human-clicked URL",
                            reply_to_message_id=update.id
                        )

                        download_directory = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id)
                        os.makedirs(download_directory, exist_ok=True)

                        command_to_exec = [
                            "yt-dlp",
                            "-f", "best[ext=mp4]/best",
                            "--merge-output-format", "mp4",
                            "--no-check-certificate",
                            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            detected_url,
                            "-o", download_directory
                        ]

                        if Config.HTTP_PROXY != "":
                            command_to_exec.append("--proxy")
                            command_to_exec.append(Config.HTTP_PROXY)

                        try:
                            process = await asyncio.create_subprocess_exec(
                                *command_to_exec,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.STDOUT
                            )

                            stdout, _ = await process.communicate()

                            if process.returncode == 0:
                                # Success with detected URL
                                logger.info(f"Human-clicked download successful with URL {i}")
                                await bot.send_message(
                                    chat_id=update.chat.id,
                                    text=f"✅ Human-like download successful! Processing file...",
                                    reply_to_message_id=update.id
                                )
                                download_successful = True
                                break
                            else:
                                logger.warning(f"URL {i} failed: {stdout.decode()}")

                        except Exception as url_error:
                            logger.error(f"Error with URL {i}: {url_error}")
                            continue

                    if not download_successful:
                        # All detected URLs failed, show them for manual use
                        response = "❌ **All download methods failed**\n\n"
                        response += "🤖 **Human clicked and found these URLs:**\n\n"
                        for i, detected_url in enumerate(detected_urls, 1):
                            response += f"🎥 **{i}.** `{detected_url}`\n\n"
                        response += "💡 **Tip:** Try copying one of these URLs and send it directly to the bot"

                        await bot.edit_message_text(
                            text=response,
                            chat_id=update.chat.id,
                            message_id=update.id,
                            disable_web_page_preview=True
                        )
                        return
                else:
                    await bot.send_message(
                        chat_id=update.chat.id,
                        text="😔 Human-like detection found no downloadable video URLs",
                        reply_to_message_id=update.id
                    )
                    return

            except Exception as detection_error:
                logger.error(f"Human-like detection error: {detection_error}")
                await bot.send_message(
                    chat_id=update.chat.id,
                    text=f"❌ Human-like detection failed: {str(detection_error)}",
                    reply_to_message_id=update.id
                )
                return


            await bot.send_message(
                chat_id=update.chat.id,
                text=Translation.NO_VOID_FORMAT_FOUND.format(str(error_message)),
                reply_to_message_id=update.id,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            return False
        if t_response:
            # logger.info(t_response)
            x_reponse = t_response
            if "\n" in x_reponse:
                x_reponse = x_reponse.split("\n")[0]  # Take only the first line
            response_json = json.loads(x_reponse)
            save_ytdl_json_path = Config.DOWNLOAD_LOCATION + \
                "/" + str(update.from_user.id) + ".json"
            with open(save_ytdl_json_path, "w", encoding="utf8") as outfile:
                json.dump(response_json, outfile, ensure_ascii=False)
            # logger.info(response_json)
            inline_keyboard = []
            duration = None
            if "duration" in response_json:
                duration = response_json["duration"]
            if "formats" in response_json:
                for formats in response_json["formats"]:
                    format_id = formats.get("format_id")
                    format_string = formats.get("format_note")
                    if format_string is None:
                        format_string = formats.get("format")
                    format_ext = formats.get("ext")

                    # Enhanced file size calculation
                    approx_file_size = ""
                    if "filesize" in formats and formats["filesize"]:
                        approx_file_size = humanbytes(formats["filesize"])
                    elif "filesize_approx" in formats and formats["filesize_approx"]:
                        approx_file_size = "~" + humanbytes(formats["filesize_approx"])

                    # Get resolution info
                    resolution = ""
                    if formats.get("height"):
                        if formats.get("height") >= 2160:
                            resolution = "4K"
                        elif formats.get("height") >= 1080:
                            resolution = "1080p"
                        elif formats.get("height") >= 720:
                            resolution = "720p"
                        elif formats.get("height") >= 480:
                            resolution = "480p"
                        elif formats.get("height") >= 360:
                            resolution = "360p"
                        else:
                            resolution = f"{formats.get('height')}p"

                    # Enhanced format display with size estimation
                    if resolution and approx_file_size:
                        display_quality = f"{resolution} {approx_file_size}"
                    elif resolution:
                        # Try to estimate size if not available
                        if duration and formats.get("height"):
                            estimated_size = estimate_file_size_by_quality(formats.get("height"), duration)
                            display_quality = f"{resolution} ~{estimated_size}"
                        else:
                            display_quality = resolution
                    elif format_string:
                        display_quality = format_string
                    else:
                        display_quality = format_ext

                    cb_string_video = "{}|{}|{}".format(
                        "video", format_id, format_ext)
                    cb_string_file = "{}|{}|{}".format(
                        "file", format_id, format_ext)
                    if format_string is not None and not "audio only" in format_string:
                        ikeyboard = [
                            InlineKeyboardButton(
                                f"📹 {display_quality} Video",
                                callback_data=(cb_string_video).encode("UTF-8")
                            ),
                            InlineKeyboardButton(
                                f"📁 {display_quality} File",
                                callback_data=(cb_string_file).encode("UTF-8")
                            )
                        ]
                        """if duration is not None:
                            cb_string_video_message = "{}|{}|{}".format(
                                "vm", format_id, format_ext)
                            ikeyboard.append(
                                InlineKeyboardButton(
                                    "VM",
                                    callback_data=(
                                        cb_string_video_message).encode("UTF-8")
                                )
                            )"""
                    else:
                        # special weird case :\
                        ikeyboard = [
                            InlineKeyboardButton(
                                "SVideo [" +
                                "] ( " +
                                approx_file_size + " )",
                                callback_data=(cb_string_video).encode("UTF-8")
                            ),
                            InlineKeyboardButton(
                                "DFile [" +
                                "] ( " +
                                approx_file_size + " )",
                                callback_data=(cb_string_file).encode("UTF-8")
                            )
                        ]
                    inline_keyboard.append(ikeyboard)
                if duration is not None:
                    cb_string_64 = "{}|{}|{}".format("audio", "64k", "mp3")
                    cb_string_128 = "{}|{}|{}".format("audio", "128k", "mp3")
                    cb_string = "{}|{}|{}".format("audio", "320k", "mp3")
                    inline_keyboard.append([
                        InlineKeyboardButton(
                            "MP3 " + "(" + "64 kbps" + ")", callback_data=cb_string_64.encode("UTF-8")),
                        InlineKeyboardButton(
                            "MP3 " + "(" + "128 kbps" + ")", callback_data=cb_string_128.encode("UTF-8"))
                    ])
                    inline_keyboard.append([
                        InlineKeyboardButton(
                            "MP3 " + "(" + "320 kbps" + ")", callback_data=cb_string.encode("UTF-8"))
                    ])
            else:
                format_id = response_json["format_id"]
                format_ext = response_json["ext"]
                cb_string_file = "{}|{}|{}".format(
                    "file", format_id, format_ext)
                cb_string_video = "{}|{}|{}".format(
                    "video", format_id, format_ext)
                inline_keyboard.append([
                    InlineKeyboardButton(
                        "SVideo",
                        callback_data=(cb_string_video).encode("UTF-8")
                    ),
                    InlineKeyboardButton(
                        "DFile",
                        callback_data=(cb_string_file).encode("UTF-8")
                    )
                ])
                cb_string_file = "{}={}={}".format(
                    "file", format_id, format_ext)
                cb_string_video = "{}={}={}".format(
                    "video", format_id, format_ext)
                inline_keyboard.append([
                    InlineKeyboardButton(
                        "video",
                        callback_data=(cb_string_video).encode("UTF-8")
                    ),
                    InlineKeyboardButton(
                        "file",
                        callback_data=(cb_string_file).encode("UTF-8")
                    )
                ])
            reply_markup = InlineKeyboardMarkup(inline_keyboard)
            # logger.info(reply_markup)
            thumbnail = Config.DEF_THUMB_NAIL_VID_S
            thumbnail_image = Config.DEF_THUMB_NAIL_VID_S
            if "thumbnail" in response_json:
                if response_json["thumbnail"] is not None:
                    thumbnail = response_json["thumbnail"]
                    thumbnail_image = response_json["thumbnail"]
            # Enhanced thumbnail handling with multiple fallbacks
            thumb_image_path = None

            # Try to download and process the original thumbnail
            if thumbnail_image:
                try:
                    await send_live_log(bot, update.chat.id, "📸 Downloading video thumbnail...")

                    # Try different image formats
                    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        temp_thumb_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + ext

                        try:
                            downloaded_thumb = DownLoadFile(
                                thumbnail_image,
                                temp_thumb_path,
                                Config.CHUNK_SIZE,
                                None,
                                Translation.DOWNLOAD_START,
                                update.id,
                                update.chat.id
                            )

                            if os.path.exists(downloaded_thumb):
                                # Try to process the image
                                try:
                                    im = Image.open(downloaded_thumb)
                                    # Convert to RGB and save as JPEG
                                    final_thumb_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + ".jpg"
                                    if im.mode in ('RGBA', 'LA', 'P'):
                                        # Convert to RGB for formats with transparency
                                        background = Image.new('RGB', im.size, (255, 255, 255))
                                        if im.mode == 'P':
                                            im = im.convert('RGBA')
                                        background.paste(im, mask=im.split()[-1] if im.mode == 'RGBA' else None)
                                        im = background
                                    elif im.mode != 'RGB':
                                        im = im.convert('RGB')

                                    # Resize thumbnail to appropriate size
                                    im.thumbnail((320, 240), Image.Resampling.LANCZOS)
                                    im.save(final_thumb_path, "JPEG", quality=85)
                                    thumb_image_path = final_thumb_path
                                    await send_live_log(bot, update.chat.id, "✅ Thumbnail processed successfully")
                                    break

                                except Exception as img_error:
                                    logger.error(f"Failed to process thumbnail {ext}: {img_error}")
                                    try:
                                        os.remove(downloaded_thumb)
                                    except:
                                        pass
                                    continue

                        except Exception as download_error:
                            logger.error(f"Failed to download thumbnail {ext}: {download_error}")
                            continue

                    # If all thumbnail processing failed, try direct URL approach
                    if not thumb_image_path:
                        try:
                            await send_live_log(bot, update.chat.id, "🔄 Trying alternative thumbnail method...")

                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            }
                            response = requests.get(thumbnail_image, headers=headers, timeout=10)

                            if response.status_code == 200:
                                final_thumb_path = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + ".jpg"

                                # Try to process the image data directly
                                try:
                                    from io import BytesIO
                                    im = Image.open(BytesIO(response.content))
                                    if im.mode in ('RGBA', 'LA', 'P'):
                                        background = Image.new('RGB', im.size, (255, 255, 255))
                                        if im.mode == 'P':
                                            im = im.convert('RGBA')
                                        background.paste(im, mask=im.split()[-1] if im.mode == 'RGBA' else None)
                                        im = background
                                    elif im.mode != 'RGB':
                                        im = im.convert('RGB')

                                    im.thumbnail((320, 240), Image.Resampling.LANCZOS)
                                    im.save(final_thumb_path, "JPEG", quality=85)
                                    thumb_image_path = final_thumb_path
                                    await send_live_log(bot, update.chat.id, "✅ Alternative thumbnail method successful")

                                except Exception as direct_error:
                                    logger.error(f"Direct thumbnail processing failed: {direct_error}")

                        except Exception as alt_error:
                            logger.error(f"Alternative thumbnail method failed: {alt_error}")

                except Exception as main_error:
                    logger.error(f"Main thumbnail processing failed: {main_error}")

            # Final fallback - check for user's custom thumbnail
            if not thumb_image_path:
                custom_thumb = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + ".jpg"
                if os.path.exists(custom_thumb):
                    thumb_image_path = custom_thumb
                    await send_live_log(bot, update.chat.id, "📎 Using custom thumbnail")
                else:
                    await send_live_log(bot, update.chat.id, "⚠️ No thumbnail available, proceeding without one")
            await bot.send_message(
                chat_id=update.chat.id,
                text=Translation.FORMAT_SELECTION.format(thumbnail) + "\n" + Translation.SET_CUSTOM_USERNAME_PASSWORD,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=update.id
            )
        else:
            # fallback for nonnumeric port a.k.a seedbox.io
            inline_keyboard = []
            cb_string_file = "{}={}={}".format(
                "file", "LFO", "NONE")
            cb_string_video = "{}={}={}".format(
                "video", "OFL", "ENON")
            inline_keyboard.append([
                InlineKeyboardButton(
                    "SVideo",
                    callback_data=(cb_string_video).encode("UTF-8")
                ),
                InlineKeyboardButton(
                    "DFile",
                    callback_data=(cb_string_file).encode("UTF-8")
                )
            ])
            reply_markup = InlineKeyboardMarkup(inline_keyboard)
            await bot.send_message(
                chat_id=update.chat.id,
                text=Translation.FORMAT_SELECTION.format(""),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=update.id
            )