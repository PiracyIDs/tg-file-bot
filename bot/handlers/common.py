"""
Common handlers: /start, /help, catch-all.
"""
from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from bot.config import settings
from bot.database.connection import get_db
from bot.database.repositories.quota_repo import QuotaRepository
from bot.utils.file_utils import get_exp_time

router = Router(name="common")

# Helper functions
def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_user_ids

HELP_TEXT = (
    "👋 <b>File Storage Bot</b> — Enhanced Edition\n\n"

    "<b>📤 Upload</b>\n"
    "Just send any file, photo, video, audio, or voice message.\n\n"

    "<b>📥 Retrieve</b>\n"
    "/get <code>&lt;file_id&gt;</code> — Retrieve a file by ID\n"
    "/list — Browse your files (interactive)\n"
    "/search <code>&lt;query&gt;</code> — Search by filename\n\n"

    "<b>🏷️ Organisation</b>\n"
    "/tag <code>&lt;tagname&gt;</code> — Find files by tag\n"
    "/rename <code>&lt;file_id&gt;</code> — Rename a file\n\n"

    "<b>🔗 Sharing</b>\n"
    "/share <code>&lt;file_id&gt;</code> — Generate a share code\n"
    "/claim <code>&lt;code&gt;</code> — Claim a file shared by someone\n\n"
    "<b>📊 Account</b>\n"
    "/mystats — View your download quota usage\n"
    "/delete <code>&lt;file_id&gt;</code> — Delete a file\n\n"

    "<b>💡 Tips</b>\n"
    "• After uploading, use the action buttons to tag, rename, share, or set expiry.\n"
    "• Duplicate files are detected automatically.\n"
    "• Files can be set to auto-expire after 1, 7, or 30 days.\n"
    "• Download quota resets daily at midnight UTC.\n"
    "• Non-admins must verify their token before downloading."
)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    """
    /start command handler with token verification support.
    - /start alone: Show help text
    - /start verify_{token}: Verify token via shortlink
    """
    user_id = message.from_user.id
    
    # Check if this is a token verification request
    if message.text and len(message.text) > 7:
        text = message.text.strip()
        
        # Check for verify_{token} pattern (e.g., /start verify_ABC1234567)
        if "verify_" in text:
            _, token = text.split("_", 1)
            
            quota_repo = QuotaRepository(get_db())
            verify_status = await quota_repo.get_verify_status(user_id)
            
            # Verify the token
            if verify_status.get("verify_token") != token:
                await message.answer(
                    "⚠️ <b>Invalid token</b>.\n\nPlease use /start again to get a new verification token.",
                    parse_mode="HTML"
                )
                return
            
            # Token is valid, mark as verified
            await quota_repo.update_verify_status(user_id, is_verified=True)
            current_count = await quota_repo.get_verify_count(user_id)
            await quota_repo.set_verify_count(user_id, current_count + 1)
            
            await message.answer(
                f"✅ <b>Token verified!</b>\n\n"
                f"You can now download files for <b>{get_exp_time(settings.verify_expire_seconds)}</b>.\n\n"
                f"Use /get, /list, or tap files to download.",
                parse_mode="HTML"
            )
            return
    
    # Regular /start - show help
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message()
async def unhandled(message: Message) -> None:
    await message.answer(
        "❓ Send me a file to store it, or use /help to see all commands."
    )
