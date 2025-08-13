
import logging
import asyncio
import json
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
from urllib.parse import urljoin, urlparse
import pyrogram
from pyrogram import Client
from pyrogram.types import Message
from config import Config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class EnhancedDownloadDetector:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
    async def send_live_log(self, bot: Client, chat_id: int, message: str):
        """Send live log updates to the bot"""
        try:
            await bot.send_message(chat_id=chat_id, text=f"🔄 {message}")
            logger.info(f"Live log: {message}")
        except Exception as e:
            logger.error(f"Failed to send live log: {e}")

    def setup_driver(self):
        """Setup Chrome driver with enhanced options"""
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.set_page_load_timeout(30)
            return driver
        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            return None

    async def search_download_buttons(self, driver, bot: Client, chat_id: int):
        """Search for download buttons with multiple strategies"""
        await self.send_live_log(bot, chat_id, "🔍 Searching for download buttons...")
        
        download_button_selectors = [
            # Common download button patterns
            "a[href*='download']",
            "button[class*='download']",
            "a[class*='download']",
            ".download-btn",
            ".download-link",
            "#download",
            "a[href*='.mp4']",
            "a[href*='.mkv']",
            "a[href*='.webm']",
            "button[onclick*='download']",
            "a[onclick*='download']",
            # Video streaming site patterns
            ".video-download",
            ".dl-link",
            "[data-download]",
            "a[title*='download' i]",
            "button[title*='download' i]",
            "a:contains('Download')",
            "button:contains('Download')",
            # File hosting patterns
            ".file-download",
            ".premium-download",
            ".free-download",
            "a[href*='dl.php']",
            "a[href*='download.php']"
        ]
        
        found_buttons = []
        for selector in download_button_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        href = element.get_attribute('href') or element.get_attribute('onclick') or ''
                        text = element.text.strip()
                        found_buttons.append({
                            'element': element,
                            'href': href,
                            'text': text,
                            'selector': selector
                        })
                        await self.send_live_log(bot, chat_id, f"📍 Found: {text} - {href[:50]}...")
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                
        return found_buttons

    async def extract_video_urls_from_network(self, driver, bot: Client, chat_id: int):
        """Extract video URLs from network requests using developer tools"""
        await self.send_live_log(bot, chat_id, "🌐 Opening developer tools to monitor network...")
        
        try:
            # Enable browser logging
            driver.execute_cdp_cmd('Log.enable', {})
            driver.execute_cdp_cmd('Network.enable', {})
            
            # Get network logs
            logs = driver.get_log('performance')
            video_urls = []
            
            for log in logs:
                message = json.loads(log['message'])
                if message['message']['method'] == 'Network.responseReceived':
                    url = message['message']['params']['response']['url']
                    content_type = message['message']['params']['response'].get('mimeType', '')
                    
                    # Check for video content
                    if any(ext in url.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                        video_urls.append(url)
                        await self.send_live_log(bot, chat_id, f"🎥 Found video URL: {url[:60]}...")
                    elif 'video' in content_type.lower():
                        video_urls.append(url)
                        await self.send_live_log(bot, chat_id, f"🎥 Found video stream: {url[:60]}...")
            
            return video_urls
            
        except Exception as e:
            logger.error(f"Network monitoring failed: {e}")
            await self.send_live_log(bot, chat_id, f"❌ Network monitoring failed: {str(e)}")
            return []

    async def play_video_and_capture_url(self, driver, bot: Client, chat_id: int):
        """Play video and capture the actual playing URL"""
        await self.send_live_log(bot, chat_id, "▶️ Attempting to play video and capture URL...")
        
        try:
            # Look for video elements
            video_selectors = [
                'video',
                'video source',
                '.video-player video',
                '#video-player video',
                '.player video',
                'iframe[src*="player"]',
                'iframe[src*="video"]'
            ]
            
            video_urls = []
            
            for selector in video_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.tag_name == 'video':
                            src = element.get_attribute('src')
                            if src:
                                video_urls.append(src)
                                await self.send_live_log(bot, chat_id, f"🎬 Video element found: {src[:60]}...")
                            
                            # Try to play the video
                            try:
                                driver.execute_script("arguments[0].play();", element)
                                time.sleep(2)
                                current_src = element.get_attribute('currentSrc') or element.get_attribute('src')
                                if current_src and current_src not in video_urls:
                                    video_urls.append(current_src)
                                    await self.send_live_log(bot, chat_id, f"▶️ Playing video URL: {current_src[:60]}...")
                            except Exception as e:
                                logger.debug(f"Could not play video: {e}")
                                
                        elif element.tag_name == 'iframe':
                            iframe_src = element.get_attribute('src')
                            if iframe_src:
                                await self.send_live_log(bot, chat_id, f"🖼️ Found iframe: {iframe_src[:60]}...")
                                # Switch to iframe and search for video
                                try:
                                    driver.switch_to.frame(element)
                                    iframe_videos = driver.find_elements(By.TAG_NAME, 'video')
                                    for iframe_video in iframe_videos:
                                        iframe_video_src = iframe_video.get_attribute('src')
                                        if iframe_video_src:
                                            video_urls.append(iframe_video_src)
                                            await self.send_live_log(bot, chat_id, f"🎥 Iframe video: {iframe_video_src[:60]}...")
                                    driver.switch_to.default_content()
                                except Exception as e:
                                    logger.debug(f"Iframe processing failed: {e}")
                                    driver.switch_to.default_content()
                                    
                except Exception as e:
                    logger.debug(f"Video selector {selector} failed: {e}")
            
            return video_urls
            
        except Exception as e:
            logger.error(f"Video capture failed: {e}")
            await self.send_live_log(bot, chat_id, f"❌ Video capture failed: {str(e)}")
            return []

    async def extract_from_page_source(self, driver, bot: Client, chat_id: int):
        """Extract video URLs from page source using regex"""
        await self.send_live_log(bot, chat_id, "📄 Analyzing page source for video URLs...")
        
        try:
            page_source = driver.page_source
            
            # Comprehensive regex patterns for video URLs
            video_patterns = [
                r'(?:src|href|url)[\s]*[=:][\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'file[\s]*:[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'video[\s]*:[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'source[\s]*:[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'https?://[^\s"\'<>]+\.(?:mp4|mkv|webm|m4v|avi)(?:\?[^\s"\'<>]*)?',
                r'"file"[\s]*:[\s]*"([^"]*)"',
                r'"src"[\s]*:[\s]*"([^"]*\.(?:mp4|mkv|webm|m4v|avi)[^"]*)"',
                r'data-src[\s]*=[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                r'data-video[\s]*=[\s]*["\']([^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']'
            ]
            
            found_urls = set()
            
            for pattern in video_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    if match.startswith('http') and any(ext in match.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                        found_urls.add(match)
                        await self.send_live_log(bot, chat_id, f"🔗 Regex found: {match[:60]}...")
            
            return list(found_urls)
            
        except Exception as e:
            logger.error(f"Page source analysis failed: {e}")
            await self.send_live_log(bot, chat_id, f"❌ Page source analysis failed: {str(e)}")
            return []

    async def try_auto_download(self, driver, download_buttons, bot: Client, chat_id: int):
        """Attempt automatic download from found buttons"""
        await self.send_live_log(bot, chat_id, "⬇️ Attempting automatic download...")
        
        successful_downloads = []
        
        for button_info in download_buttons:
            try:
                element = button_info['element']
                href = button_info['href']
                
                await self.send_live_log(bot, chat_id, f"🔄 Trying: {button_info['text']}")
                
                # Try clicking the button
                if element.is_enabled() and element.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    time.sleep(1)
                    
                    # Try different click methods
                    try:
                        element.click()
                    except:
                        try:
                            ActionChains(driver).move_to_element(element).click().perform()
                        except:
                            driver.execute_script("arguments[0].click();", element)
                    
                    time.sleep(3)
                    
                    # Check if download started or new URL appeared
                    current_url = driver.current_url
                    if any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                        successful_downloads.append(current_url)
                        await self.send_live_log(bot, chat_id, f"✅ Download URL: {current_url}")
                    
                    # Check for direct file links
                    if href and any(ext in href.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                        successful_downloads.append(href)
                        await self.send_live_log(bot, chat_id, f"✅ Direct link: {href}")
                        
            except Exception as e:
                logger.debug(f"Button click failed: {e}")
                await self.send_live_log(bot, chat_id, f"⚠️ Button failed: {str(e)[:30]}...")
        
        return successful_downloads

    async def comprehensive_video_detection(self, url: str, bot: Client, chat_id: int):
        """Main method combining all detection strategies"""
        await self.send_live_log(bot, chat_id, f"🚀 Starting comprehensive detection for: {url[:50]}...")
        
        driver = self.setup_driver()
        if not driver:
            await self.send_live_log(bot, chat_id, "❌ Failed to setup browser driver")
            return []
        
        all_video_urls = []
        
        try:
            await self.send_live_log(bot, chat_id, "🌐 Loading page...")
            driver.get(url)
            time.sleep(5)
            
            # Strategy 1: Search for download buttons
            download_buttons = await self.search_download_buttons(driver, bot, chat_id)
            if download_buttons:
                auto_downloads = await self.try_auto_download(driver, download_buttons, bot, chat_id)
                all_video_urls.extend(auto_downloads)
            
            # Strategy 2: Extract from network monitoring
            network_urls = await self.extract_video_urls_from_network(driver, bot, chat_id)
            all_video_urls.extend(network_urls)
            
            # Strategy 3: Play video and capture URL
            video_urls = await self.play_video_and_capture_url(driver, bot, chat_id)
            all_video_urls.extend(video_urls)
            
            # Strategy 4: Page source analysis
            source_urls = await self.extract_from_page_source(driver, bot, chat_id)
            all_video_urls.extend(source_urls)
            
            # Remove duplicates and filter valid URLs
            unique_urls = list(set(all_video_urls))
            valid_urls = [url for url in unique_urls if url and url.startswith('http')]
            
            if valid_urls:
                await self.send_live_log(bot, chat_id, f"🎉 Found {len(valid_urls)} video URLs!")
                for i, video_url in enumerate(valid_urls, 1):
                    await self.send_live_log(bot, chat_id, f"🎥 {i}. {video_url[:80]}...")
            else:
                await self.send_live_log(bot, chat_id, "😔 No video URLs found with any method")
            
            return valid_urls
            
        except Exception as e:
            logger.error(f"Comprehensive detection failed: {e}")
            await self.send_live_log(bot, chat_id, f"❌ Detection failed: {str(e)}")
            return []
        
        finally:
            try:
                driver.quit()
            except:
                pass

# Initialize the detector
enhanced_detector = EnhancedDownloadDetector()

@pyrogram.Client.on_message(pyrogram.filters.regex(pattern=".*auto.*detect.*"))
async def auto_detect_handler(bot: Client, update: Message):
    """Handler for auto detection command"""
    if update.from_user.id in Config.AUTH_USERS:
        text = update.text
        
        # Extract URL from message
        url = None
        for entity in update.entities:
            if entity.type == "url":
                o = entity.offset
                l = entity.length
                url = text[o:o + l]
                break
        
        if not url:
            # Look for URLs in text
            url_pattern = r'https?://[^\s]+'
            urls = re.findall(url_pattern, text)
            if urls:
                url = urls[0]
        
        if url:
            status_msg = await update.reply_text("🔄 Starting enhanced auto detection...")
            
            try:
                video_urls = await enhanced_detector.comprehensive_video_detection(
                    url, bot, update.chat.id
                )
                
                if video_urls:
                    response = "✅ **Auto Detection Results:**\n\n"
                    for i, video_url in enumerate(video_urls, 1):
                        response += f"🎥 **{i}.** `{video_url}`\n\n"
                    
                    await status_msg.edit_text(response)
                    
                    # Try to download the first URL automatically
                    if video_urls:
                        await status_msg.reply_text(f"⬇️ Auto-downloading: {video_urls[0]}")
                        # Trigger the normal download process
                        download_msg = await update.reply_text(video_urls[0])
                        # The existing echo handler will process this
                else:
                    await status_msg.edit_text("😔 No video URLs found with enhanced detection")
                    
            except Exception as e:
                await status_msg.edit_text(f"❌ Auto detection failed: {str(e)}")
                logger.error(f"Auto detection error: {e}")
        else:
            await update.reply_text("❌ No URL found in message. Send: `auto detect https://example.com/video`")
