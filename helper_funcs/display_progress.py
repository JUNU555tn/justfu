#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Thank you LazyDeveloperr for helping us in this journey.

# the logging things
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import math
import os
import time

# the secret configuration specific things
if bool(os.environ.get("WEBHOOK", False)):
    from sample_config import Config
else:
    from config import Config

# the Strings used for this "thing"
from translation import Translation


async def progress_for_pyrogram(
    current,
    total,
    ud_type,
    message,
    start
):
    now = time.time()
    diff = now - start
    if round(diff % 5.00) == 0 or current == total:  # Update every 5 seconds instead of 10
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

        # Enhanced progress bar with emojis
        filled = math.floor(percentage / 5)
        progress_bar = ''.join(['🟢' for i in range(filled)]) + ''.join(['⚪' for i in range(20 - filled)])

        # Speed with color indicators
        speed_text = humanbytes(speed)
        if speed > 10 * 1024 * 1024:  # >10MB/s
            speed_emoji = "🚀"
        elif speed > 1 * 1024 * 1024:  # >1MB/s
            speed_emoji = "⚡"
        else:
            speed_emoji = "🐌"

        progress_text = f"""
🎯 **{ud_type}**

📊 **Progress:** {round(percentage, 1)}%
{progress_bar}

📁 **Size:** {humanbytes(current)} / {humanbytes(total)}
{speed_emoji} **Speed:** {speed_text}/s
⏱️ **ETA:** {estimated_total_time if estimated_total_time != '' else "0s"}
⏰ **Elapsed:** {elapsed_time if elapsed_time != '' else "0s"}
"""

        try:
            await message.edit(
                text=progress_text,
                parse_mode="markdown"
            )
        except Exception as e:
            # Fallback to simple text if markdown fails
            try:
                simple_text = f"{ud_type}\n\nProgress: {round(percentage, 1)}%\n{humanbytes(current)} / {humanbytes(total)}\nSpeed: {speed_text}/s\nETA: {estimated_total_time if estimated_total_time != '' else '0s'}"
                await message.edit(text=simple_text)
            except:
                pass


def humanbytes(size):
    # https://stackoverflow.com/a/49361727/4723940
    # 2**10 = 1024
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2]