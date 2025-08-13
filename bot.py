#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Thank you @LazyDeveloperr 

import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import configuration
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

import pyrogram
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# Import web server for Render deployment
from web_server import start_web_server

def cleanup_old_sessions():
    """Remove any existing session files to prevent AuthKeyDuplicated errors"""
    session_files = [
        "BewafaAngelPriya.session",
        "BewafaAngelPriya.session-journal"
    ]
    
    for file in session_files:
        try:
            if os.path.exists(file):
                os.remove(file)
                logger.info(f"Removed old session file: {file}")
        except Exception as e:
            logger.error(f"Error removing session file {file}: {e}")

if __name__ == "__main__":
    # Clean up old sessions first
    cleanup_old_sessions()

    # Create download directory if not exists
    if not os.path.isdir(Config.DOWNLOAD_LOCATION):
        os.makedirs(Config.DOWNLOAD_LOCATION)
        logger.info(f"Created download directory: {Config.DOWNLOAD_LOCATION}")

    plugins = dict(root="plugins")
    
    # Configure the Client with in_memory session
    app = pyrogram.Client(
        "BewafaAngelPriya",
        bot_token=Config.TG_BOT_TOKEN,
        api_id=Config.APP_ID,
        api_hash=Config.API_HASH,
        plugins=plugins,
        in_memory=True,  # Prevents session file creation
        workers=100  # Adjust based on your needs
    )
    
    # Add auth users
    Config.AUTH_USERS.add(1484670284)

    # Start web server for Render deployment
    start_web_server()

    try:
        # Run the application
        logger.info("Starting bot application...")
        app.run()
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
        sys.exit(1)
