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

    # ✅ FIX: Ask for phone number using listen() instead of ask()
    await message.reply("📱 **Enter your phone number with country code:**\n\nExample: +919876543210")
    try:
        number_msg = await _.listen(user_id, filters=filters.text, timeout=300)
        phone_number = number_msg.text
    except Exception as e:
        await message.reply(f"❌ Timeout or error: {str(e)}")
        return

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

    # ✅ FIX: Ask for OTP using listen() instead of ask()
    try:
        await message.reply("🔐 **Enter the OTP sent to your phone:**\n\nFormat: 1 2 3 4 5")
        otp_msg = await _.listen(
            user_id,
            filters=filters.text,
            timeout=600
        )
    except Exception as e:
        await message.reply(f"⏰ OTP timeout or error: {str(e)}")
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
            await message.reply("🔒 **Two-step verification enabled. Enter your password:**")
            pwd_msg = await _.listen(user_id, filters=filters.text, timeout=300)
            await client.check_password(pwd_msg.text)
        except Exception as e:
            await message.reply(f"⏰ Password timeout or error: {str(e)}")
            await client.disconnect()
            return
        except PasswordHashInvalid:
            await message.reply("❌ Invalid password. Restart login.")
            await client.disconnect()
            return

    # Export new session string and update DB
    session_string = await client.export_session_string()
    await db.set_session(user_id, session_string)

    await client.disconnect()
    await message.reply("✅ Login successful!")
