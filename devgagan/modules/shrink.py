# ---------------------------------------------------
# File Name: shrink.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/PdfsHubbb
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import random
import requests
import string
import aiohttp
from devgagan import app
from devgagan.core.func import *
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB, WEBSITE_URL, AD_API, LOG_GROUP

# ----------------- MongoDB setup -----------------
tclient = AsyncIOMotorClient(MONGO_DB)
tdb = tclient["telegram_bot"]
token = tdb["tokens"]

async def create_ttl_index():
    await token.create_index("expires_at", expireAfterSeconds=0)

Param = {}

# ----------------- Utility functions -----------------
async def generate_random_param(length=8):
    """Generate a random parameter."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def get_shortened_url(deep_link):
    """Shorten link using ShrinkForEarn API"""
    api_url = f"https://{WEBSITE_URL}/api"
    params = {
        "api": AD_API,
        "url": deep_link,
        "format": "json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "success":
                    return data.get("shortenedUrl")
    return deep_link  # fallback to original link if failed

async def is_user_verified(user_id):
    """Check if a user has an active session."""
    session = await token.find_one({"user_id": user_id})
    return session is not None

# ----------------- Handlers -----------------
@app.on_message(filters.command("start"))
async def token_handler(client, message):
    """Handle the /start command."""
    join = await subscribe(client, message)
    if join == 1:
        return

    user_id = message.chat.id
    if len(message.command) <= 1:
        # ✅ Custom image
        image_url = "https://i.postimg.cc/tCJ0M27D/IMG-20250823-145001-279.jpg"

        # ✅ Buttons
        join_button = InlineKeyboardButton("📢 Join Channel", url="https://t.me/PdfsHubbb")
        premium = InlineKeyboardButton("💎 Get Premium", url="https://t.me/DarkEnd7")
        help_button = InlineKeyboardButton("❓ Help", callback_data="https://t.me/DarkEnd7")

        keyboard = InlineKeyboardMarkup([
            [join_button],
            [premium],
            [help_button]
        ])

        # ✅ Welcome message
        await message.reply_photo(
            image_url,
            caption=(
                f"Hey {message.from_user.first_name}! 👋\n\n"
                "🚀 **What I Can Do:**\n"
                "✨ Save posts from channels & groups where forwarding is restricted\n"
                "✨ Download media from YT, Insta, and more\n"
                "✨ For private channels, use /login\n"
                "✨ Type /help for all commands\n\n"
                "💎 **Premium Features:**\n"
                "🔹 Use /token to get 3 hours of **free premium**\n"
                "🔹 Upgrade with /upgrade for unlimited access\n"
                "🔹 Faster speed, unlimited saves & priority support 🚀\n\n"
                "✅ Send me any post link now to start saving instantly!"
            ),
            reply_markup=keyboard
        )
        return

    # ✅ Token handling
    param = message.command[1] if len(message.command) > 1 else None
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("You are a premium user no need of token 😉")
        return

    if param:
        if user_id in Param and Param[user_id] == param:
            await token.insert_one({
                "user_id": user_id,
                "param": param,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=3),
            })
            del Param[user_id]
            await message.reply("✅ You have been verified successfully! Enjoy your session for next 3 hours.")
            return
        else:
            await message.reply("❌ Invalid or expired verification link. Please generate a new token.")
            return

@app.on_message(filters.command("token"))
async def smart_handler(client, message):
    user_id = message.chat.id
    freecheck = await chk_user(message, user_id)
    if freecheck != 1:
        await message.reply("You are a premium user no need of token 😉")
        return

    if await is_user_verified(user_id):
        await message.reply("✅ Your free session is already active enjoy!")
    else:
        param = await generate_random_param()
        Param[user_id] = param   

        deep_link = f"https://t.me/{client.me.username}?start={param}"
        shortened_url = await get_shortened_url(deep_link)

        if not shortened_url:
            await message.reply("❌ Failed to generate the token link. Please try again.")
            return

        button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Verify the token now...", url=shortened_url)]]
        )
        await message.reply(
            "Click the button below to verify your free access token: \n\n"
            "> What will you get ? \n"
            "1. No time bound upto 3 hours \n"
            "2. Batch command limit will be FreeLimit + 20 \n"
            "3. All functions unlocked",
            reply_markup=button
        )
