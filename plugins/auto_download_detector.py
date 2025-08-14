
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
from bs4 import BeautifulSoup
import subprocess
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class EnhancedDownloadDetector:
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
        self.chrome_options.add_argument('--disable-javascript')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument('--ignore-certificate-errors-spki-list')
        self.chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        # Set chrome binary path explicitly
        self.chrome_options.binary_location = '/usr/bin/google-chrome-stable'
        
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
            # Try to install Chrome first
            self.install_chrome()
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.set_page_load_timeout(30)
            return driver
        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            return None
    
    def install_chrome(self):
        """Install Chrome if not available"""
        try:
            # Check if Chrome is already installed
            result = subprocess.run(['which', 'google-chrome-stable'], capture_output=True)
            if result.returncode != 0:
                logger.info("Installing Google Chrome...")
                # Install Chrome
                commands = [
                    'wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -',
                    'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list',
                    'apt-get update -qq',
                    'apt-get install -y google-chrome-stable'
                ]
                for cmd in commands:
                    subprocess.run(cmd, shell=True, check=True)
        except Exception as e:
            logger.error(f"Failed to install Chrome: {e}")

    async def fallback_direct_analysis(self, url: str, bot: Client, chat_id: int):
        """Fallback method using direct HTTP requests and BeautifulSoup"""
        await self.send_live_log(bot, chat_id, "🔄 Using fallback direct analysis method...")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': url
            }
            
            # Get the page content
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            found_urls = []
            
            await self.send_live_log(bot, chat_id, "🔍 Analyzing page content...")
            
            # Look for download buttons and links
            download_selectors = [
                'a[href*="download"]',
                'button[onclick*="download"]',
                'a[href*=".mp4"]',
                'a[href*=".mkv"]',
                'a[href*=".webm"]',
                'a[href*=".avi"]',
                'a[href*=".m4v"]',
                'a[class*="download"]',
                'button[class*="download"]',
                '.download-btn',
                '.download-link',
                '#download',
                '[data-download]'
            ]
            
            for selector in download_selectors:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href') or element.get('onclick', '')
                    if href:
                        # Clean up onclick handlers
                        if 'onclick' in str(element):
                            onclick = element.get('onclick', '')
                            url_match = re.search(r'["\']([^"\']*(?:\.mp4|\.mkv|\.webm|\.avi|\.m4v)[^"\']*)["\']', onclick)
                            if url_match:
                                href = url_match.group(1)
                        
                        if href.startswith('http') and any(ext in href.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                            found_urls.append(href)
                            await self.send_live_log(bot, chat_id, f"📍 Found download link: {href[:60]}...")
            
            # Look for video sources in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    content = script.string
                    # Common video URL patterns
                    patterns = [
                        r'file\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m4v)[^"\']*)["\']',
                        r'src\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m4v)[^"\']*)["\']',
                        r'video\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m4v)[^"\']*)["\']',
                        r'url\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m4v)[^"\']*)["\']',
                        r'https?://[^\s"\'<>]+\.(?:mp4|mkv|webm|avi|m4v)(?:\?[^\s"\'<>]*)?'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                match = match[0]
                            if match.startswith('http'):
                                found_urls.append(match)
                                await self.send_live_log(bot, chat_id, f"🎥 Found video in script: {match[:60]}...")
            
            # Look for video elements
            video_elements = soup.find_all(['video', 'source'])
            for element in video_elements:
                src = element.get('src') or element.get('data-src')
                if src and src.startswith('http'):
                    found_urls.append(src)
                    await self.send_live_log(bot, chat_id, f"📹 Found video element: {src[:60]}...")
            
            # Look for iframe sources
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src')
                if src:
                    try:
                        # Recursively check iframe content
                        iframe_response = requests.get(src, headers=headers, timeout=15)
                        iframe_soup = BeautifulSoup(iframe_response.content, 'html.parser')
                        iframe_videos = iframe_soup.find_all(['video', 'source'])
                        for video in iframe_videos:
                            video_src = video.get('src') or video.get('data-src')
                            if video_src and video_src.startswith('http'):
                                found_urls.append(video_src)
                                await self.send_live_log(bot, chat_id, f"🖼️ Found iframe video: {video_src[:60]}...")
                    except Exception as e:
                        logger.debug(f"Failed to analyze iframe {src}: {e}")
            
            # Remove duplicates
            unique_urls = list(set(found_urls))
            
            if unique_urls:
                await self.send_live_log(bot, chat_id, f"✅ Fallback method found {len(unique_urls)} URLs!")
            else:
                await self.send_live_log(bot, chat_id, "😔 No video URLs found with fallback method")
            
            return unique_urls
            
        except Exception as e:
            logger.error(f"Fallback analysis failed: {e}")
            await self.send_live_log(bot, chat_id, f"❌ Fallback analysis failed: {str(e)}")
            return []

    async def try_direct_download_patterns(self, url: str, bot: Client, chat_id: int):
        """Try common direct download URL patterns"""
        await self.send_live_log(bot, chat_id, "🔄 Trying direct download patterns...")
        
        try:
            base_url = url.rstrip('/')
            domain = urlparse(url).netloc
            
            # Common download URL patterns
            patterns = [
                f"{base_url}/download",
                f"{base_url}/dl",
                f"{base_url}/get",
                f"{base_url}.mp4",
                f"{base_url}.mkv",
                f"{base_url}.webm",
                f"{base_url}/video.mp4",
                f"{base_url}/stream.mp4",
                base_url.replace('/video/', '/download/'),
                base_url.replace('/watch/', '/download/'),
                base_url.replace('/view/', '/download/'),
                base_url.replace('http://', 'https://').replace('/video/', '/stream/'),
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': url
            }
            
            found_urls = []
            
            for pattern in patterns:
                try:
                    response = requests.head(pattern, headers=headers, timeout=10, allow_redirects=True)
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if response.status_code == 200 and ('video' in content_type or any(ext in pattern.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi'])):
                        found_urls.append(pattern)
                        await self.send_live_log(bot, chat_id, f"✅ Direct pattern found: {pattern[:60]}...")
                        
                except Exception as e:
                    logger.debug(f"Pattern {pattern} failed: {e}")
            
            return found_urls
            
        except Exception as e:
            logger.error(f"Direct pattern matching failed: {e}")
            return []

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
            "a[href*='download.php']",
            # New tab opening patterns
            "a[target='_blank']",
            "button[onclick*='window.open']",
            "a[onclick*='window.open']",
            # Play button patterns that might lead to download
            ".play-btn",
            ".play-button",
            "button[class*='play']",
            "a[class*='play']"
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
        """Attempt automatic download from found buttons like a human"""
        await self.send_live_log(bot, chat_id, "⬇️ Attempting human-like automatic download...")
        
        successful_downloads = []
        
        for button_info in download_buttons:
            try:
                element = button_info['element']
                href = button_info['href']
                text = button_info['text'].lower()
                
                await self.send_live_log(bot, chat_id, f"🔄 Human-clicking: {button_info['text']}")
                
                # Human-like behavior: scroll to element slowly
                if element.is_enabled() and element.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                    time.sleep(2)  # Wait for smooth scroll
                    
                    # Human-like mouse movement and hover
                    actions = ActionChains(driver)
                    actions.move_to_element(element)
                    actions.perform()
                    time.sleep(1)  # Hover pause
                    
                    # Try multiple human-like click methods
                    click_successful = False
                    
                    # Method 1: Regular click
                    try:
                        await self.send_live_log(bot, chat_id, "👆 Attempting regular click...")
                        element.click()
                        click_successful = True
                    except Exception as e:
                        logger.debug(f"Regular click failed: {e}")
                    
                    # Method 2: Action chain click
                    if not click_successful:
                        try:
                            await self.send_live_log(bot, chat_id, "👆 Attempting action chain click...")
                            ActionChains(driver).move_to_element(element).click().perform()
                            click_successful = True
                        except Exception as e:
                            logger.debug(f"Action chain click failed: {e}")
                    
                    # Method 3: JavaScript click
                    if not click_successful:
                        try:
                            await self.send_live_log(bot, chat_id, "👆 Attempting JavaScript click...")
                            driver.execute_script("arguments[0].click();", element)
                            click_successful = True
                        except Exception as e:
                            logger.debug(f"JavaScript click failed: {e}")
                    
                    # Method 4: Force click with coordinates
                    if not click_successful:
                        try:
                            await self.send_live_log(bot, chat_id, "👆 Attempting coordinate click...")
                            location = element.location
                            size = element.size
                            x = location['x'] + size['width'] // 2
                            y = location['y'] + size['height'] // 2
                            actions = ActionChains(driver)
                            actions.move_by_offset(x, y).click().perform()
                            click_successful = True
                        except Exception as e:
                            logger.debug(f"Coordinate click failed: {e}")
                    
                    if click_successful:
                        await self.send_live_log(bot, chat_id, "✅ Button clicked successfully!")
                        
                        # Wait for page to respond like human
                        time.sleep(3)
                        
                        # Check for download dialogs, new tabs, or redirects
                        original_window = driver.current_window_handle
                        current_windows = driver.window_handles
                        
                        # Check if new tab/window opened
                        if len(current_windows) > 1:
                            await self.send_live_log(bot, chat_id, "🔄 New window detected, checking...")
                            for window in current_windows:
                                if window != original_window:
                                    driver.switch_to.window(window)
                                    time.sleep(3)  # Wait for page to load
                                    new_url = driver.current_url
                                    
                                    # Check if it's a direct video URL
                                    if any(ext in new_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                                        successful_downloads.append(new_url)
                                        await self.send_live_log(bot, chat_id, f"✅ Direct video URL in new window: {new_url}")
                                    else:
                                        # Look for video elements or download links in the new tab
                                        try:
                                            video_elements = driver.find_elements(By.TAG_NAME, 'video')
                                            for video in video_elements:
                                                video_src = video.get_attribute('src')
                                                if video_src and video_src.startswith('http'):
                                                    successful_downloads.append(video_src)
                                                    await self.send_live_log(bot, chat_id, f"✅ Video element in new tab: {video_src}")
                                            
                                            # Look for download buttons in new tab
                                            new_tab_downloads = driver.find_elements(By.CSS_SELECTOR, 
                                                'a[href*=".mp4"], a[href*=".mkv"], a[href*=".webm"], a[href*="download"]')
                                            for link in new_tab_downloads:
                                                link_href = link.get_attribute('href')
                                                if link_href:
                                                    successful_downloads.append(link_href)
                                                    await self.send_live_log(bot, chat_id, f"✅ Download link in new tab: {link_href}")
                                        except Exception as new_tab_error:
                                            logger.debug(f"New tab analysis failed: {new_tab_error}")
                                    
                                    driver.close()
                            driver.switch_to.window(original_window)
                        
                        # Check current URL for changes
                        current_url = driver.current_url
                        if any(ext in current_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                            successful_downloads.append(current_url)
                            await self.send_live_log(bot, chat_id, f"✅ Current page is download URL: {current_url}")
                        
                        # Check for download links that appeared after click
                        await asyncio.sleep(2)  # Wait for dynamic content
                        new_download_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*=".mp4"], a[href*=".mkv"], a[href*=".webm"], a[href*=".avi"], a[href*=".m4v"]')
                        for link in new_download_links:
                            link_href = link.get_attribute('href')
                            if link_href and link_href not in successful_downloads:
                                successful_downloads.append(link_href)
                                await self.send_live_log(bot, chat_id, f"✅ New download link appeared: {link_href}")
                        
                        # If we have href, validate it as download link
                        if href and any(ext in href.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                            if href not in successful_downloads:
                                successful_downloads.append(href)
                                await self.send_live_log(bot, chat_id, f"✅ Using button href: {href}")
                    
                    else:
                        await self.send_live_log(bot, chat_id, f"❌ All click methods failed for: {text}")
                        
            except Exception as e:
                logger.debug(f"Human-like download attempt failed: {e}")
                await self.send_live_log(bot, chat_id, f"⚠️ Download attempt failed: {str(e)[:50]}...")
        
        return successful_downloads

    async def human_download_file(self, download_url: str, bot: Client, chat_id: int, user_id: int):
        """Download file like a human would"""
        try:
            await self.send_live_log(bot, chat_id, f"⬇️ Starting human-like download...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': download_url
            }
            
            # Create download directory
            download_dir = f"./DOWNLOADS/{user_id}"
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            
            # Get file info
            response = requests.head(download_url, headers=headers, timeout=30, allow_redirects=True)
            
            if response.status_code == 200:
                content_length = int(response.headers.get('content-length', 0))
                content_type = response.headers.get('content-type', '')
                
                # Determine file extension
                file_ext = '.mp4'  # default
                if '.mkv' in download_url.lower(): file_ext = '.mkv'
                elif '.webm' in download_url.lower(): file_ext = '.webm'
                elif '.avi' in download_url.lower(): file_ext = '.avi'
                elif '.m4v' in download_url.lower(): file_ext = '.m4v'
                
                filename = f"video_{int(time.time())}{file_ext}"
                filepath = os.path.join(download_dir, filename)
                
                await self.send_live_log(bot, chat_id, f"📁 Downloading to: {filename}")
                if content_length > 0:
                    await self.send_live_log(bot, chat_id, f"📊 File size: {self.humanbytes(content_length)}")
                
                # Download with progress
                with requests.get(download_url, headers=headers, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(filepath, 'wb') as f:
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Update progress every 1MB
                                if downloaded % (1024*1024) == 0:
                                    if content_length > 0:
                                        progress = (downloaded / content_length * 100)
                                        await self.send_live_log(bot, chat_id, f"📥 Downloaded: {progress:.1f}% ({self.humanbytes(downloaded)}/{self.humanbytes(content_length)})")
                                    else:
                                        await self.send_live_log(bot, chat_id, f"📥 Downloaded: {self.humanbytes(downloaded)}")
                
                await self.send_live_log(bot, chat_id, f"✅ Download completed: {filepath}")
                return filepath
            else:
                await self.send_live_log(bot, chat_id, f"❌ Download failed: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            await self.send_live_log(bot, chat_id, f"❌ Download error: {str(e)}")
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

    async def direct_cdn_download(self, cdn_urls: list, bot: Client, chat_id: int, user_id: int):
        """Directly download from CDN URLs without yt-dlp"""
        for i, cdn_url in enumerate(cdn_urls, 1):
            try:
                await self.send_live_log(bot, chat_id, f"📥 Direct CDN download {i}/{len(cdn_urls)}: {cdn_url[:60]}...")
                
                filepath = await self.human_download_file(cdn_url, bot, chat_id, user_id)
                
                if filepath and os.path.exists(filepath):
                    await self.send_live_log(bot, chat_id, "✅ CDN download successful! Uploading to Telegram...")
                    
                    # Upload the downloaded file
                    await bot.send_video(
                        chat_id=chat_id,
                        video=filepath,
                        caption="✅ **Direct CDN Download Complete!**\n\nDownloaded without yt-dlp using human-like method",
                        reply_to_message_id=None
                    )
                    
                    # Clean up
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    
                    return True
                else:
                    await self.send_live_log(bot, chat_id, f"❌ CDN download {i} failed")
                    
            except Exception as e:
                await self.send_live_log(bot, chat_id, f"❌ CDN download {i} error: {str(e)}")
                
        return False

    async def follow_get_file_redirects(self, get_file_urls: list, bot: Client, chat_id: int):
        """Follow get_file URLs to find final CDN video URLs"""
        final_urls = []
        
        for get_file_url in get_file_urls:
            if 'get_file' in get_file_url:
                try:
                    await self.send_live_log(bot, chat_id, f"🔄 Following redirect: {get_file_url[:60]}...")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Referer': get_file_url
                    }
                    
                    # Follow redirects to get final URL
                    response = requests.get(get_file_url, headers=headers, allow_redirects=True, timeout=30)
                    
                    if response.status_code == 200:
                        final_url = response.url
                        
                        # Check if we got a CDN URL (the final video URL)
                        if 'cdn.' in final_url and any(ext in final_url.lower() for ext in ['.mp4', '.mkv', '.webm', '.avi', '.m4v']):
                            await self.send_live_log(bot, chat_id, f"✅ Found CDN URL: {final_url}")
                            final_urls.append(final_url)
                        else:
                            # If not a direct video URL, check the response content for video URLs
                            await self.send_live_log(bot, chat_id, f"🔍 Analyzing redirect response for video URLs...")
                            
                            # Look for video URLs in the response
                            import re
                            video_patterns = [
                                r'https?://cdn\.[^"\'<>\s]+\.(?:mp4|mkv|webm|m4v|avi)(?:\?[^"\'<>\s]*)?',
                                r'"(https?://[^"]*cdn[^"]*\.(?:mp4|mkv|webm|m4v|avi)[^"]*)"',
                                r'src\s*=\s*["\']([^"\']*cdn[^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']',
                                r'video["\']?\s*:\s*["\']([^"\']*cdn[^"\']*\.(?:mp4|mkv|webm|m4v|avi)[^"\']*)["\']'
                            ]
                            
                            for pattern in video_patterns:
                                matches = re.findall(pattern, response.text, re.IGNORECASE)
                                for match in matches:
                                    if isinstance(match, tuple):
                                        match = match[0]
                                    if match.startswith('http') and 'cdn.' in match and any(ext in match.lower() for ext in ['.mp4', '.mkv', '.webm', '.m4v', '.avi']):
                                        await self.send_live_log(bot, chat_id, f"✅ Found CDN URL in response: {match}")
                                        final_urls.append(match)
                            
                            # If still no CDN URL found, check for auto-play URLs
                            if not final_urls:
                                await self.send_live_log(bot, chat_id, f"🔍 Looking for auto-play video URLs...")
                                # Sometimes the video URL is in JavaScript for auto-play
                                js_patterns = [
                                    r'autoplay["\']?\s*:\s*["\']([^"\']*\.mp4[^"\']*)["\']',
                                    r'src\s*:\s*["\']([^"\']*\.mp4[^"\']*)["\']',
                                    r'file\s*:\s*["\']([^"\']*\.mp4[^"\']*)["\']'
                                ]
                                
                                for pattern in js_patterns:
                                    matches = re.findall(pattern, response.text, re.IGNORECASE)
                                    for match in matches:
                                        if match.startswith('http'):
                                            await self.send_live_log(bot, chat_id, f"✅ Found auto-play URL: {match}")
                                            final_urls.append(match)
                    else:
                        await self.send_live_log(bot, chat_id, f"❌ Redirect failed: HTTP {response.status_code}")
                        
                except Exception as e:
                    await self.send_live_log(bot, chat_id, f"❌ Error following redirect: {str(e)}")
                    logger.error(f"Redirect error: {e}")
        
        return final_urls

    async def comprehensive_video_detection(self, url: str, bot: Client, chat_id: int):
        """Main method combining all detection strategies with human-like downloading"""
        await self.send_live_log(bot, chat_id, f"🚀 Starting comprehensive detection for: {url[:50]}...")
        
        all_video_urls = []
        downloaded_files = []
        
        # Strategy 1: Try direct download patterns first (fastest)
        direct_urls = await self.try_direct_download_patterns(url, bot, chat_id)
        all_video_urls.extend(direct_urls)
        
        # Strategy 2: Use fallback direct analysis (reliable)
        fallback_urls = await self.fallback_direct_analysis(url, bot, chat_id)
        all_video_urls.extend(fallback_urls)
        
        # Strategy 2.5: Follow get_file redirects to find CDN URLs
        get_file_urls = [url for url in fallback_urls if 'get_file' in url]
        if get_file_urls:
            await self.send_live_log(bot, chat_id, f"🔄 Found {len(get_file_urls)} get_file URLs, following redirects...")
            cdn_urls = await self.follow_get_file_redirects(get_file_urls, bot, chat_id)
            all_video_urls.extend(cdn_urls)
        
        # Strategy 3: Try selenium if available
        driver = self.setup_driver()
        if driver:
            try:
                await self.send_live_log(bot, chat_id, "🌐 Loading page with browser...")
                driver.get(url)
                time.sleep(5)
                
                # Search for download buttons
                download_buttons = await self.search_download_buttons(driver, bot, chat_id)
                if download_buttons:
                    auto_downloads = await self.try_auto_download(driver, download_buttons, bot, chat_id)
                    all_video_urls.extend(auto_downloads)
                
                # Extract from network monitoring
                network_urls = await self.extract_video_urls_from_network(driver, bot, chat_id)
                all_video_urls.extend(network_urls)
                
                # Play video and capture URL
                video_urls = await self.play_video_and_capture_url(driver, bot, chat_id)
                all_video_urls.extend(video_urls)
                
                # Page source analysis
                source_urls = await self.extract_from_page_source(driver, bot, chat_id)
                all_video_urls.extend(source_urls)
                
            except Exception as e:
                logger.error(f"Selenium detection failed: {e}")
                await self.send_live_log(bot, chat_id, f"⚠️ Browser method failed: {str(e)}")
            
            finally:
                try:
                    driver.quit()
                except:
                    pass
        else:
            await self.send_live_log(bot, chat_id, "⚠️ Browser unavailable, using fallback methods only")
        
        # Remove duplicates and filter valid URLs
        unique_urls = list(set(all_video_urls))
        valid_urls = [url for url in unique_urls if url and url.startswith('http')]
        
        if valid_urls:
            await self.send_live_log(bot, chat_id, f"🎉 Found {len(valid_urls)} video URLs!")
            for i, video_url in enumerate(valid_urls, 1):
                await self.send_live_log(bot, chat_id, f"🎥 {i}. {video_url[:80]}...")
        else:
            await self.send_live_log(bot, chat_id, "😔 No video URLs found with any method")
        
        return valid_urls, downloaded_files

# Initialize the detector
enhanced_detector = EnhancedDownloadDetector()

# Add alias for backward compatibility
class AutoDownloadDetector:
    def __init__(self):
        self.enhanced_detector = EnhancedDownloadDetector()
    
    async def detect_and_download(self, url: str, bot, chat_id: int, user_id: int):
        """Wrapper method for backward compatibility"""
        try:
            video_urls, downloaded_files = await self.enhanced_detector.comprehensive_video_detection(url, bot, chat_id)
            
            if video_urls:
                # Try to download the first video URL found
                best_url = video_urls[0]
                filepath = await self.enhanced_detector.human_download_file(best_url, bot, chat_id, user_id)
                
                if filepath:
                    return True
            return False
        except Exception as e:
            logger.error(f"AutoDownloadDetector error: {e}")
            return False

@pyrogram.Client.on_message(pyrogram.filters.regex(pattern=".*auto.*detect.*"))
async def auto_detect_handler(bot: Client, update: Message):
    """Handler for auto detection and download command"""
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
            status_msg = await update.reply_text("🔄 Starting enhanced auto detection and download...")
            
            try:
                video_urls, downloaded_files = await enhanced_detector.comprehensive_video_detection(
                    url, bot, update.chat.id
                )
                
                if video_urls:
                    response = "✅ **Auto Detection Results:**\n\n"
                    for i, video_url in enumerate(video_urls, 1):
                        response += f"🎥 **{i}.** `{video_url}`\n\n"
                    
                    await status_msg.edit_text(response)
                    
                    # Auto-download the best quality video URL
                    if video_urls:
                        best_url = video_urls[0]  # First URL is usually best quality
                        await bot.send_message(
                            chat_id=update.chat.id,
                            text=f"🤖 **Human-like Auto Download Started**\n\n📥 Clicking download button like human...\n🔗 URL: `{best_url}`",
                            reply_to_message_id=update.message_id
                        )
                        
                        # Trigger the normal download process with the detected URL
                        download_msg = await update.reply_text(best_url)
                        # The existing echo handler will process this with yt-dlp
                        
                else:
                    await status_msg.edit_text("😔 No video URLs found with enhanced detection")
                    
            except Exception as e:
                await status_msg.edit_text(f"❌ Auto detection failed: {str(e)}")
                logger.error(f"Auto detection error: {e}")
        else:
            await update.reply_text("❌ No URL found in message. Send: `auto detect https://example.com/video`")

@pyrogram.Client.on_message(pyrogram.filters.regex(pattern=".*human.*download.*"))
async def human_download_handler(bot: Client, update: Message):
    """Handler for human-like download command"""
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
            status_msg = await update.reply_text("🤖 Starting human-like download simulation...")
            
            try:
                # Download file like a human would
                filepath = await enhanced_detector.human_download_file(
                    url, bot, update.chat.id, update.from_user.id
                )
                
                if filepath and os.path.exists(filepath):
                    await status_msg.edit_text("✅ Human-like download completed! Uploading to Telegram...")
                    
                    # Upload the downloaded file
                    await bot.send_video(
                        chat_id=update.chat.id,
                        video=filepath,
                        caption="🤖 **Human-like Download Complete**\n\nDownloaded and uploaded automatically!",
                        reply_to_message_id=update.message_id
                    )
                    
                    # Clean up
                    try:
                        os.remove(filepath)
                    except:
                        pass
                else:
                    await status_msg.edit_text("❌ Human-like download failed")
                    
            except Exception as e:
                await status_msg.edit_text(f"❌ Human download failed: {str(e)}")
                logger.error(f"Human download error: {e}")
        else:
            await update.reply_text("❌ No URL found in message. Send: `human download https://example.com/video.mp4`")
