from pyrogram import filters, Client
from devgagan import app
import os
from devgagan.core.mongo import db
from devgagan.core.func import subscribe
from config import API_ID as api_id, API_HASH as api_hash
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)

# ---------------- Helper: Delete old session ----------------
async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"
    deleted = False

    try:
        if os.path.exists(session_file):
            os.remove(session_file)
            deleted = True
        if os.path.exists(memory_file):
            os.remove(memory_file)
            deleted = True
    except Exception:
        pass

    # Delete session from DB if exists
    await db.remove_session(user_id)
    return deleted

# ---------------- Logout ----------------
@app.on_message(filters.command("logout"))
async def logout_user(client, message):
    user_id = message.chat.id
    deleted = await delete_session_files(user_id)
    if deleted:
        await message.reply("✅ Logout Successful!")
    else:
        await message.reply("✅ Logout Successful!")

# ---------------- Login ----------------
@app.on_message(filters.command("login"))
async def login_user(_, message):
    joined = await subscribe(_, message)
    if joined == 1:
        return

    user_id = message.chat.id

    # Auto delete old session first
    await delete_session_files(user_id)

    # Ask for phone number
    number_msg = await _.ask(user_id, "Enter your phone number with country code:\nExample: +19876543210", filters=filters.text)
    phone_number = number_msg.text

    client = Client(f"session_{user_id}", api_id, api_hash)
    try:
        await client.connect()
        await message.reply("📲 Sending OTP...")
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply("❌ Invalid API ID or HASH. Restart the session.")
        return
    except PhoneNumberInvalid:
        await message.reply("❌ Invalid phone number. Restart the session.")
        return
    except Exception as e:
        await message.reply(f"❌ Failed to send OTP: {e}")
        return

    # Ask for OTP
    try:
        otp_msg = await _.ask(
            user_id,
            "Please check your Telegram account for the OTP. Enter it as `1 2 3 4 5` format.",
            filters=filters.text,
            timeout=600
        )
    except TimeoutError:
        await message.reply("⏰ OTP timeout. Restart login.")
        await client.disconnect()
        return

    phone_code = otp_msg.text.replace(" ", "")

    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await otp_msg.reply("❌ Invalid OTP. Restart login.")
        await client.disconnect()
        return
    except PhoneCodeExpired:
        await otp_msg.reply("❌ OTP expired. Restart login.")
        await client.disconnect()
        return
    except SessionPasswordNeeded:
        try:
            pwd_msg = await _.ask(user_id, "Two-step verification enabled. Enter your password:", filters=filters.text, timeout=300)
            await client.check_password(pwd_msg.text)
        except TimeoutError:
            await message.reply("⏰ Password timeout. Restart login.")
            await client.disconnect()
            return
        except PasswordHashInvalid:
            await pwd_msg.reply("❌ Invalid password. Restart login.")
            await client.disconnect()
            return

    # Export new session string and update DB
    session_string = await client.export_session_string()
    await db.set_session(user_id, session_string)

    await client.disconnect()
    await otp_msg.reply("✅ Login successful!")
