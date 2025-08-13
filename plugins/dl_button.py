
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K

# the logging things
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import asyncio
import aiohttp
import json
import math
import os
import shutil
import time
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# the secret configuration specific things
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

# the Strings used for this "thing"
from translation import Translation

import pyrogram
logging.getLogger("pyrogram").setLevel(logging.WARNING)

from helper_funcs.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
# https://stackoverflow.com/a/37631799/4723940
from PIL import Image

class AutoDownloadHandler:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--disable-plugins')
        self.chrome_options.add_argument('--disable-images')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument('--ignore-certificate-errors-spki-list')
        self.chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    def setup_driver(self):
        """Setup Chrome driver with enhanced options"""
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.set_page_load_timeout(30)
            return driver
        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            return None

    async def send_live_log(self, bot, chat_id, message):
        """Send live log updates"""
        try:
            await bot.send_message(chat_id=chat_id, text=f"🔄 {message}")
            logger.info(f"Live log: {message}")
        except Exception as e:
            logger.error(f"Failed to send live log: {e}")

    async def auto_click_download_with_redirects(self, url, bot, chat_id, message_id):
        """Auto-click download buttons and handle redirects to get final download URL"""
        driver = self.setup_driver()
        if not driver:
            await self.send_live_log(bot, chat_id, "❌ Browser unavailable for auto-clicking")
            return None

        try:
            await self.send_live_log(bot, chat_id, f"🌐 Loading page: {url[:50]}...")
            driver.get(url)
            time.sleep(3)

            # Look for download buttons with expanded selectors
            download_selectors = [
                "a[href*='download']",
                "button[class*='download']",
                "a[class*='download']",
                ".download-btn",
                ".download-link",
                "#download",
                "button[onclick*='download']",
                "a[onclick*='download']",
                ".btn-download",
                "[data-download]",
                "a[title*='download' i]",
                "button[title*='download' i]",
                "a[href*='get_file']",  # Added for sites like desitales2
                "a[href*='cdn.']",      # Added for CDN links
                "button[id*='download']",
                "input[type='button'][value*='download' i]"
            ]

            download_button = None
            for selector in download_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            text = element.text.lower()
                            href = element.get_attribute('href') or ''
                            onclick = element.get_attribute('onclick') or ''
                            
                            # Check for download indicators
                            if (any(keyword in text for keyword in ['download', 'dl', 'get', 'save']) or
                                'download' in href.lower() or 'get_file' in href.lower() or 
                                'cdn.' in href.lower() or 'download' in onclick.lower()):
                                download_button = element
                                await self.send_live_log(bot, chat_id, f"📍 Found download button: {text or href[:30]}...")
                                break
                    if download_button:
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")

            if not download_button:
                await self.send_live_log(bot, chat_id, "❌ No download button found")
                return None

            # Click the download button
            await self.send_live_log(bot, chat_id, "👆 Auto-clicking download button...")
            
            original_window = driver.current_window_handle
            original_url = driver.current_url
            all_original_windows = set(driver.window_handles)

            try:
                # Try different click methods
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", download_button)
                    time.sleep(1)
                    download_button.click()
                except:
                    try:
                        ActionChains(driver).move_to_element(download_button).click().perform()
                    except:
                        driver.execute_script("arguments[0].click();", download_button)

                # Wait longer for new tabs/redirects to occur
                time.sleep(5)

                # Check for new windows/tabs
                all_current_windows = set(driver.window_handles)
                new_windows = all_current_windows - all_original_windows
                
                if new_windows:
                    await self.send_live_log(bot, chat_id, f"🔄 {len(new_windows)} new tab(s) opened, checking for download...")
                    
                    for window in new_windows:
                        driver.switch_to.window(window)
                        time.sleep(3)  # Wait for tab to fully load
                        
                        new_url = driver.current_url
                        await self.send_live_log(bot, chat_id, f"🔗 New tab URL: {new_url[:60]}...")
                        
                        # Check if it's a direct video file URL (like cdn.es2.com/2000/2114/2114.mp4)
                        if any(ext in new_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v', '.flv']):
                            await self.send_live_log(bot, chat_id, f"✅ Found direct MP4 URL: {new_url}")
                            return new_url
                        
                        # Check for CDN patterns
                        if 'cdn.' in new_url.lower() and any(pattern in new_url.lower() for pattern in ['video', 'media', 'stream']):
                            await self.send_live_log(bot, chat_id, f"✅ Found CDN video URL: {new_url}")
                            return new_url
                        
                        # Use developer tools to find video elements
                        video_url = await self.find_video_with_dev_tools(driver, bot, chat_id)
                        if video_url:
                            return video_url
                        
                        # Look for more download links in the new tab
                        final_url = await self.extract_download_url_from_page(driver, bot, chat_id)
                        if final_url:
                            return final_url
                    
                    # Switch back to original window
                    if original_window in driver.window_handles:
                        driver.switch_to.window(original_window)

                # Check if current page changed to download URL
                current_url = driver.current_url
                if current_url != original_url:
                    await self.send_live_log(bot, chat_id, f"🔄 Page redirected: {current_url[:50]}...")
                    
                    if any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                        await self.send_live_log(bot, chat_id, "✅ Found direct download URL after redirect!")
                        return current_url
                    
                    # Look for download links on redirected page
                    final_url = await self.extract_download_url_from_page(driver, bot, chat_id)
                    if final_url:
                        return final_url

                # Look for download links that appeared after clicking
                await self.send_live_log(bot, chat_id, "🔍 Searching for download links on current page...")
                final_url = await self.extract_download_url_from_page(driver, bot, chat_id)
                if final_url:
                    return final_url

                await self.send_live_log(bot, chat_id, "❌ No download URL found after clicking")
                return None

            except Exception as click_error:
                logger.error(f"Click error: {click_error}")
                await self.send_live_log(bot, chat_id, f"❌ Click failed: {str(click_error)}")
                return None

        except Exception as e:
            logger.error(f"Auto-click error: {e}")
            await self.send_live_log(bot, chat_id, f"❌ Auto-click failed: {str(e)}")
            return None

        finally:
            try:
                driver.quit()
            except:
                pass

    async def find_video_with_dev_tools(self, driver, bot, chat_id):
        """Use developer tools approach to find video elements"""
        try:
            await self.send_live_log(bot, chat_id, "🔧 Using developer tools to find video...")
            
            # Check for video elements first
            video_elements = driver.find_elements(By.TAG_NAME, 'video')
            if video_elements:
                for video in video_elements:
                    src = video.get_attribute('src')
                    if src and any(ext in src.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                        await self.send_live_log(bot, chat_id, f"🎥 Found video element: {src[:60]}...")
                        return src
                    
                    # Check sources within video element
                    sources = video.find_elements(By.TAG_NAME, 'source')
                    for source in sources:
                        src = source.get_attribute('src')
                        if src and any(ext in src.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                            await self.send_live_log(bot, chat_id, f"🎥 Found video source: {src[:60]}...")
                            return src

            # Execute JavaScript to find video URLs like a developer would
            js_code = """
            var videoUrls = [];
            
            // Check all video elements
            document.querySelectorAll('video').forEach(function(video) {
                if (video.src) videoUrls.push(video.src);
                video.querySelectorAll('source').forEach(function(source) {
                    if (source.src) videoUrls.push(source.src);
                });
            });
            
            // Check all links and attributes for video files
            document.querySelectorAll('*').forEach(function(element) {
                ['src', 'href', 'data-src', 'data-video', 'data-url'].forEach(function(attr) {
                    var val = element.getAttribute(attr);
                    if (val && (val.includes('.mp4') || val.includes('.mkv') || val.includes('.webm') || val.includes('.avi') || val.includes('.m4v'))) {
                        videoUrls.push(val);
                    }
                });
            });
            
            // Look in window object for video URLs
            var windowKeys = Object.keys(window);
            windowKeys.forEach(function(key) {
                try {
                    var val = window[key];
                    if (typeof val === 'string' && (val.includes('.mp4') || val.includes('.mkv') || val.includes('.webm'))) {
                        videoUrls.push(val);
                    }
                } catch(e) {}
            });
            
            return [...new Set(videoUrls)];
            """
            
            video_urls = driver.execute_script(js_code)
            
            if video_urls:
                for url in video_urls:
                    if url.startswith('http') and any(ext in url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                        await self.send_live_log(bot, chat_id, f"🔧 Dev tools found: {url[:60]}...")
                        return url
            
            return None
            
        except Exception as e:
            logger.error(f"Developer tools search failed: {e}")
            return None

    async def extract_download_url_from_page(self, driver, bot, chat_id):
        """Extract download URLs from current page using developer tools and DOM analysis"""
        try:
            # First try the developer tools approach
            dev_tools_url = await self.find_video_with_dev_tools(driver, bot, chat_id)
            if dev_tools_url:
                return dev_tools_url

            # Enable network monitoring
            try:
                driver.execute_cdp_cmd('Network.enable', {})
                await self.send_live_log(bot, chat_id, "🌐 Monitoring network requests...")
            except:
                pass

            # Look for direct video links with expanded selectors
            video_selectors = [
                'a[href*=".mp4"]',
                'a[href*=".mkv"]', 
                'a[href*=".webm"]',
                'a[href*=".avi"]',
                'a[href*=".m4v"]',
                'video source',
                'video',
                '[data-src*=".mp4"]',
                '[data-video*=".mp4"]',
                'a[href*="cdn."]',
                'a[href*="get_file"]',
                '[src*=".mp4"]',
                '[data-url*=".mp4"]'
            ]

            for selector in video_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        href = (element.get_attribute('href') or 
                               element.get_attribute('src') or 
                               element.get_attribute('data-src') or
                               element.get_attribute('data-url') or
                               element.get_attribute('data-video'))
                        if href and any(ext in href.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                            await self.send_live_log(bot, chat_id, f"🎥 Found video URL: {href[:60]}...")
                            return href
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")

            # Analyze page source for video URLs with expanded patterns
            page_source = driver.page_source
            import re
            
            video_patterns = [
                r'(?:src|href|url)[\s]*[=:][\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'file[\s]*:[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'video[\s]*:[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'https?://[^\s"\'<>]+\.(?:mp4|mkv|webm|m4v|avi)(?:\?[^\s"\'<>]*)?',
                r'https?://cdn\.[^\s"\'<>]+/[^\s"\'<>]*\.(?:mp4|mkv|webm|m4v|avi)',
                r'get_file/[^"\'<>\s]+\.(?:mp4|mkv|webm|m4v|avi)',
                r'"(https?://[^"]*cdn[^"]*\.(?:mp4|mkv|webm|m4v|avi)[^"]*)"'
            ]

            for pattern in video_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    if match.startswith('http') and any(ext in match.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                        await self.send_live_log(bot, chat_id, f"🔗 Found video in source: {match[:60]}...")
                        return match

            # Try to get network logs
            try:
                logs = driver.get_log('performance')
                for log in logs:
                    message = json.loads(log['message'])
                    if message['message']['method'] == 'Network.responseReceived':
                        url = message['message']['params']['response']['url']
                        if any(ext in url.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                            await self.send_live_log(bot, chat_id, f"🌐 Found video in network: {url[:60]}...")
                            return url
            except Exception as network_error:
                logger.debug(f"Network log analysis failed: {network_error}")

            return None

        except Exception as e:
            logger.error(f"URL extraction failed: {e}")
            return None

# Initialize auto download handler
auto_download_handler = AutoDownloadHandler()

async def ddl_call_back(bot, update):
    logger.info(update)
    cb_data = update.data
    # youtube_dl extractors
    tg_send_type, youtube_dl_format, youtube_dl_ext = cb_data.split("=")
    thumb_image_path = Config.DOWNLOAD_LOCATION + \
        "/" + str(update.from_user.id) + ".jpg"
    youtube_dl_url = update.message.reply_to_message.text
    custom_file_name = os.path.basename(youtube_dl_url)
    
    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        if len(url_parts) == 2:
            youtube_dl_url = url_parts[0]
            custom_file_name = url_parts[1]
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

    user = await bot.get_me()
    mention = user["mention"]
    description = Translation.CUSTOM_CAPTION_UL_FILE.format(mention)
    start = datetime.now()
    
    await bot.edit_message_text(
        text="🤖 **Smart Download Starting...**\n\nTrying auto-click download button method...",
        chat_id=update.message.chat.id,
        message_id=update.message.message_id
    )

    # Try auto-clicking download button first
    try:
        auto_download_url = await auto_download_handler.auto_click_download_with_redirects(
            youtube_dl_url, bot, update.message.chat.id, update.message.message_id
        )
        
        if auto_download_url:
            await bot.edit_message_text(
                text="✅ **Auto-click successful!** Starting download...",
                chat_id=update.message.chat.id,
                message_id=update.message.message_id
            )
            youtube_dl_url = auto_download_url  # Use the auto-clicked URL
        else:
            await bot.edit_message_text(
                text="⚠️ **Auto-click failed.** Trying direct download...",
                chat_id=update.message.chat.id,
                message_id=update.message.message_id
            )
    except Exception as auto_error:
        logger.error(f"Auto-click error: {auto_error}")
        await bot.edit_message_text(
            text=f"❌ **Auto-click failed:** {str(auto_error)[:50]}...\n\nTrying direct download...",
            chat_id=update.message.chat.id,
            message_id=update.message.message_id
        )

    tmp_directory_for_each_user = Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id)
    if not os.path.isdir(tmp_directory_for_each_user):
        os.makedirs(tmp_directory_for_each_user)
    download_directory = tmp_directory_for_each_user + "/" + custom_file_name
    
    async with aiohttp.ClientSession() as session:
        c_time = time.time()
        try:
            await download_coroutine(
                bot,
                session,
                youtube_dl_url,
                download_directory,
                update.message.chat.id,
                update.message.message_id,
                c_time
            )
        except asyncio.TimeoutError:
            await bot.edit_message_text(
                text=Translation.SLOW_URL_DECED,
                chat_id=update.message.chat.id,
                message_id=update.message.message_id
            )
            return False
    
    if os.path.exists(download_directory):
        end_one = datetime.now()
        await bot.edit_message_text(
            text=Translation.UPLOAD_START,
            chat_id=update.message.chat.id,
            message_id=update.message.message_id
        )
        file_size = Config.TG_MAX_FILE_SIZE + 1
        try:
            file_size = os.stat(download_directory).st_size
        except FileNotFoundError as exc:
            download_directory = os.path.splitext(download_directory)[0] + "." + "mkv"
            file_size = os.stat(download_directory).st_size
        
        if file_size > Config.TG_MAX_FILE_SIZE:
            await bot.edit_message_text(
                chat_id=update.message.chat.id,
                text=Translation.RCHD_TG_API_LIMIT,
                message_id=update.message.message_id
            )
        else:
            # get the correct width, height, and duration for videos greater than 10MB
            width = 0
            height = 0
            duration = 0
            if tg_send_type != "file":
                metadata = extractMetadata(createParser(download_directory))
                if metadata is not None:
                    if metadata.has("duration"):
                        duration = metadata.get('duration').seconds
            
            # get the correct width, height, and duration for videos greater than 10MB
            if os.path.exists(thumb_image_path):
                width = 0
                height = 0
                metadata = extractMetadata(createParser(thumb_image_path))
                if metadata.has("width"):
                    width = metadata.get("width")
                if metadata.has("height"):
                    height = metadata.get("height")
                if tg_send_type == "vm":
                    height = width
                
                Image.open(thumb_image_path).convert("RGB").save(thumb_image_path)
                img = Image.open(thumb_image_path)
                if tg_send_type == "file":
                    img.resize((320, height))
                else:
                    img.resize((90, height))
                img.save(thumb_image_path, "JPEG")
            else:
                thumb_image_path = None
            
            start_time = time.time()
            
            # try to upload file
            if tg_send_type == "audio":
                audio = await bot.send_audio(
                    chat_id=update.message.chat.id,
                    audio=download_directory,
                    caption=description + f"\n\nSubmitted by {update.from_user.mention}\nUploaded by {mention}",
                    duration=duration,
                    thumb=thumb_image_path,
                    reply_to_message_id=update.message.reply_to_message.message_id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
                await audio.forward(Config.LOG_CHANNEL)
            elif tg_send_type == "file":
                document = await bot.send_document(
                    chat_id=update.message.chat.id,
                    document=download_directory,
                    thumb=thumb_image_path,
                    caption=description + f"\n\nSubmitted by {update.from_user.mention}\nUploaded by {mention}",
                    reply_to_message_id=update.message.reply_to_message.message_id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
                await document.forward(Config.LOG_CHANNEL)
            elif tg_send_type == "vm":
                video_note = await bot.send_video_note(
                    chat_id=update.message.chat.id,
                    video_note=download_directory,
                    duration=duration,
                    length=width,
                    thumb=thumb_image_path,
                    reply_to_message_id=update.message.reply_to_message.message_id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
                vm = await video_note.forward(Config.LOG_CHANNEL)
                await vm.reply_text(f"Submitted by {update.from_user.mention}\nUploaded by {mention}")
            elif tg_send_type == "video":
                video = await bot.send_video(
                    chat_id=update.message.chat.id,
                    video=download_directory,
                    caption=description + f"\n\nSubmitted by {update.from_user.mention}\nUploaded by {mention}",
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    thumb=thumb_image_path,
                    reply_to_message_id=update.message.reply_to_message.message_id,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time
                    )
                )
                await video.forward(Config.LOG_CHANNEL)
            else:
                logger.info("Did this happen? :\\")
            
            end_two = datetime.now()
            try:
                os.remove(download_directory)
                os.remove(thumb_image_path)
            except:
                pass
            
            time_taken_for_download = (end_one - start).seconds
            time_taken_for_upload = (end_two - end_one).seconds
            await bot.edit_message_text(
                text=Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(time_taken_for_download, time_taken_for_upload),
                chat_id=update.message.chat.id,
                message_id=update.message.message_id,
                disable_web_page_preview=True
            )
    else:
        await bot.edit_message_text(
            text=Translation.NO_VOID_FORMAT_FOUND.format("Download failed - could not auto-click or direct download"),
            chat_id=update.message.chat.id,
            message_id=update.message.message_id,
            disable_web_page_preview=True
        )

async def download_coroutine(bot, session, url, file_name, chat_id, message_id, start):
    downloaded = 0
    display_message = ""
    
    # Add headers for better compatibility
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'video/mp4,video/*,*/*;q=0.9',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Referer': url
    }
    
    async with session.get(url, timeout=Config.PROCESS_MAX_TIMEOUT, headers=headers) as response:
        total_length = int(response.headers.get("Content-Length", 0))
        content_type = response.headers.get("Content-Type", "")
        
        if "text" in content_type and total_length < 500:
            return await response.release()
        
        await bot.edit_message_text(
            chat_id,
            message_id,
            text="""🚀 **Smart Auto-Download Active**
⚡️ 𝗨𝗥𝗟: <a href='{}'>❝ 𝐀𝐮𝐭𝐨-𝐂𝐥𝐢𝐜𝐤 𝐔𝐫𝐥 ❞</a>
🎲 𝗙𝗶𝗹𝗲 𝗦𝗶𝘇𝗲: {}""".format(url, humanbytes(total_length))
        )
        
        with open(file_name, "wb") as f_handle:
            while True:
                chunk = await response.content.read(Config.CHUNK_SIZE)
                if not chunk:
                    break
                f_handle.write(chunk)
                downloaded += Config.CHUNK_SIZE
                now = time.time()
                diff = now - start
                if round(diff % 5.00) == 0 or downloaded == total_length:
                    percentage = downloaded * 100 / total_length
                    speed = downloaded / diff
                    elapsed_time = round(diff) * 1000
                    time_to_completion = round(
                        (total_length - downloaded) / speed) * 1000
                    estimated_total_time = elapsed_time + time_to_completion
                    try:
                        current_message = """\n\n**🤖 ⭑┗━┫⦀⦙ Auto-Click Download ⦙⦀┣━┛⭑**
⚡️ 𝗨𝗥𝗟: <a href='{}'>❝ 𝐀𝐮𝐭𝐨-𝐂𝐥𝐢𝐜𝐤 𝐔𝐫𝐥 ❞</a>
🎲 𝗙𝗶𝗹𝗲 𝗦𝗶𝘇𝗲: {}
⏳ 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝗲𝗱: {}
🧭 ЄTА: {}""".format(
    url,
    humanbytes(total_length),
    humanbytes(downloaded),
    TimeFormatter(estimated_total_time)
)
                        if current_message != display_message:
                            await bot.edit_message_text(
                                chat_id,
                                message_id,
                                text=current_message
                            )
                            display_message = current_message
                    except Exception as e:
                        logger.info(str(e))
                        pass
        return await response.release()
