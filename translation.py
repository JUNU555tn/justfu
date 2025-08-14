#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class Translation(object):
    START_TEXT = """Hello {},
This is a Telegram Bot to Upload your Youtube-dl Supported Videos into Telegram as Streamable Video.

<b>Please Send me a Youtube-dl Supported URL</b>, See /help for More info.

<b>Subscribe: @LazyDeveloper</b>
"""
    LAZY_DEVELOPER_TEXT = """Hello {},
Welcome to the Lazy Developer Bot! 🚀

This bot can download videos from various platforms and upload them to Telegram.

Available Commands:
• Send any video URL for automatic download
• YouTube links will use yt-dlp
• Other video sites will use enhanced detection

Made with ❤️ by @LazyDeveloper
"""

    HELP_USER = """**How to use me:**

1. Send me any video URL
2. I will detect and download the video
3. Then upload it to Telegram

**Supported sites:** YouTube, Vimeo, Instagram, TikTok, and many more!

**Commands:**
/start - Start the bot
/help - Show this help message

Made with ❤️ by @LazyDeveloper"""

    NOT_AUTH_USER_TEXT = "Sorry, you are not authorized to use this bot."

    DOWNLOAD_START = "📥 Download started..."

    CUSTOM_CAPTION_UL_FILE = "Downloaded by {}"

    AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS = "✅ Downloaded in {} seconds. Uploaded in {} seconds."

    NO_VOID_FORMAT_FOUND = "❌ {}"

    UPLOAD_START = "📤 Uploading..."