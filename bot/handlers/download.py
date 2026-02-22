"""
Download / retrieval handlers:
  /get <id>       — retrieve a file
  /list [page]    — interactive inline keyboard browser
  /search <name>  — search by filename
  /tag <tag>      — search by tag
  /share <code>   — claim a shared file
  /rename <id>    — rename a file
  /delete <id>    — delete a file record
  /mystats        — show quota usage



Callback handlers for the inline keyboards.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import random
import string
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database.connection import get_db
from bot.database.repositories.file_repo import FileRepository
from bot.database.repositories.quota_repo import QuotaRepository
from bot.utils.file_utils import format_size, parse_tags, get_shortlink, get_exp_time
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.keyboards import (
    build_delete_confirm_keyboard,
    build_expiry_keyboard,
    build_file_action_keyboard,
    build_file_list_keyboard,
)
from bot.utils.states import RenameStates, TagStates  # TokenStates no longer needed for shortlink verification

logger = logging.getLogger(__name__)
router = Router(name="download")
PAGE_SIZE = 8


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_user_ids


# ─────────────────────────────────────────────────────────────────────────────
# /get <file_id>
# ─────────────────────────────────────────────────────────────────────────────

async def _deliver_file(
    bot: Bot,
    chat_id: int,
    record_id: str,
    requesting_user_id: int,
) -> str | None:
    """
    Shared delivery helper used by /get and callback 'get:'.
    Returns an error string or None on success.
    Implements download quota enforcement.
    """
    repo = FileRepository(get_db())
    quota_repo = QuotaRepository(get_db())
    record = await repo.get_by_id(record_id)

    if not record:
        return "❌ File not found."
    if record.user_id != requesting_user_id:
        # Check if requester is using a share code elsewhere — not here
        return "❌ You don't have permission to access this file."

    # Check download quota (admins are exempt from enforcement)
    file_size = record.file_size or 0
    is_user_admin = is_admin(requesting_user_id)
    allowed, quota, reason = await quota_repo.can_download(
        requesting_user_id, file_size, is_user_admin
    )
    
    if not allowed:
        if reason == "bandwidth_exceeded":
            return (
                f"🚫 <b>Download quota exceeded!</b>\n\n"
                f"📦 Bandwidth used: {format_size(quota.bandwidth_used)} / {format_size(quota.bandwidth_limit)}\n"
                f"📊 Downloads today: {quota.download_count}\n\n"
                f"Your quota will reset at midnight UTC."
            )
        elif reason == "download_count_exceeded":
            return (
                f"🚫 <b>Daily download limit reached!</b>\n\n"
                f"📊 Downloads today: {quota.download_count} / {quota.download_limit}\n\n"
                f"Your quota will reset at midnight UTC."
            )
        return f"🚫 Download not allowed: {reason}"

    try:
        sent_message = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=record.channel_id,
            message_id=record.internal_message_id,
            caption=record.caption,
            protect_content=True,  # Prevents forwarding and saving
        )
        # Track download usage (for both admins and regular users)
        await quota_repo.add_download_usage(requesting_user_id, file_size)
        
        # Auto-delete the message after 60 seconds
        asyncio.create_task(
            _auto_delete_message(bot, chat_id, sent_message.message_id, record_id)
        )
    except Exception as exc:
        logger.exception("Delivery failed for record %s: %s", record_id, exc)
        return f"❌ Retrieval failed: <code>{type(exc).__name__}</code>"

    return None  # success


async def _auto_delete_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    record_id: str,
    delay_seconds: int = 60,
) -> None:
    """
    Automatically delete a retrieved file message after a delay.
    This prevents the file from persisting in the user's chat.
    """
    try:
        await asyncio.sleep(delay_seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info("Auto-deleted file message for record %s in chat %s", record_id, chat_id)
    except Exception as exc:
        logger.warning("Failed to auto-delete message %s in chat %s: %s", message_id, chat_id, exc)


@router.message(Command("get"))
async def cmd_get_file(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    quota_repo = QuotaRepository(get_db())
    if not message.text:
        return
    args = message.text.split(maxsplit=1)
    # Shortlink-based token verification for non-admins
    if not is_admin(user_id):
        verify_status = await quota_repo.get_verify_status(user_id)
        
        # Check if verification expired
        if verify_status.get("verified_time"):
            from datetime import timedelta
            verified_time = verify_status["verified_time"]
            if verified_time.tzinfo is None:
                verified_time = verified_time.replace(tzinfo=timezone.utc)
            
            time_diff = (datetime.now(timezone.utc) - verified_time).total_seconds()
            if time_diff > settings.verify_expire_seconds:
                # Expired - generate new token and shortlink
                await quota_repo.update_verify_status(user_id, is_verified=False)
                verify_status = await quota_repo.get_verify_status(user_id)
        
        # Generate verification message if not verified
        if not verify_status.get("is_verified"):
            # Generate random 10-character token
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            await quota_repo.update_verify_status(user_id, verify_token=token)
            
            # Create shortlink
            bot_username = await bot.get_me()
            shortlink = await get_shortlink(
                settings.shortlink_url,
                settings.shortlink_api,
                f"https://t.me/{bot_username.username}?start=verify_{token}"
            )
            
            # Create button
            btn = [[InlineKeyboardButton(text="• 🔗 Open Link •", url=shortlink)]]
            await message.answer(
                f"<b>Your token has expired...</b> Please refresh your token to continue..\n\n"
                f"<b>Token Timeout:</b> {get_exp_time(settings.verify_expire_seconds)}\n\n"
                f"<b>What is the token?</b>\n\n"
                f"This is an ads token. Passing one ad allows you to use the bot for {get_exp_time(settings.verify_expire_seconds)}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btn)
            )
            return
    if len(args) < 2:
        await message.answer("Usage: /get <code>&lt;file_id&gt;</code>", parse_mode="HTML")
        return
    err = await _deliver_file(bot, message.chat.id, args[1].strip(), message.from_user.id)
    if err:
        await message.answer(err, parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# /list — Interactive inline keyboard browser
# ─────────────────────────────────────────────────────────────────────────────

async def _send_file_list(target: Message | CallbackQuery, page: int) -> None:
    """Render the paginated file browser. Works for both messages and callbacks."""
    if isinstance(target, CallbackQuery):
        user_id = target.from_user.id
        send = target.message.edit_text
    else:
        user_id = target.from_user.id
        send = target.answer

    repo = FileRepository(get_db())
    total = await repo.count_by_user(user_id)

    if total == 0:
        text = "📂 You have no stored files yet. Send me a file to get started!"
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text)
        else:
            await target.answer(text)
        return

    total_pages = max(1, -(-total // PAGE_SIZE))
    page = max(1, min(page, total_pages))
    records = await repo.list_by_user(user_id, page=page, page_size=PAGE_SIZE)

    await send(
        f"📁 <b>Your Files</b> — Page {page}/{total_pages} ({total} total)\n"
        "Tap a file to download it:",
        parse_mode="HTML",
        reply_markup=build_file_list_keyboard(records, page, total_pages),
    )


@router.message(Command("list"))
async def cmd_list_files(message: Message) -> None:
    if not message.text:
        return
    args = message.text.split(maxsplit=1)
    try:
        page = int(args[1]) if len(args) > 1 else 1
    except ValueError:
        page = 1
    await _send_file_list(message, page)


@router.callback_query(F.data.startswith("page:"))
async def cb_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await _send_file_list(callback, page)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()  # Page indicator button — do nothing


# ─────────────────────────────────────────────────────────────────────────────
# Inline "get" from the browser list
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("get:"))
async def cb_get_file(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id
    quota_repo = QuotaRepository(get_db())

    # Shortlink-based token verification for non-admins
    if not is_admin(user_id):
        verify_status = await quota_repo.get_verify_status(user_id)
        
        # Check if verification expired
        if verify_status.get("verified_time"):
            from datetime import timedelta
            verified_time = verify_status["verified_time"]
            if verified_time.tzinfo is None:
                verified_time = verified_time.replace(tzinfo=timezone.utc)
            
            time_diff = (datetime.now(timezone.utc) - verified_time).total_seconds()
            if time_diff > settings.verify_expire_seconds:
                # Expired - generate new token and shortlink
                await quota_repo.update_verify_status(user_id, is_verified=False)
                verify_status = await quota_repo.get_verify_status(user_id)
        
        # Generate verification message if not verified
        if not verify_status.get("is_verified"):
            # Generate random 10-character token
            import random
            import string
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            await quota_repo.update_verify_status(user_id, verify_token=token)
            
            # Create shortlink
            bot_username = await bot.get_me()
            shortlink = await get_shortlink(
                settings.shortlink_url,
                settings.shortlink_api,
                f"https://t.me/{bot_username.username}?start=verify_{token}"
            )
            
            # Create button
            btn = [[InlineKeyboardButton(text="• 🔗 Open Link •", url=shortlink)]]
            await callback.message.answer(
                f"<b>Your token has expired...</b> Please refresh your token to continue..\n\n"
                f"<b>Token Timeout:</b> {get_exp_time(settings.verify_expire_seconds)}\n\n"
                f"<b>What is the token?</b>\n\n"
                f"This is an ads token. Passing one ad allows you to use the bot for {get_exp_time(settings.verify_expire_seconds)}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btn)
            )
            await callback.answer()
            return

    record_id = callback.data.split(":", 1)[1]
    await callback.answer("📥 Sending…")
    err = await _deliver_file(bot, callback.message.chat.id, record_id, user_id)
    if err:
        await callback.message.answer(err, parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# /search <query>
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Usage: /search <code>&lt;query&gt;</code>", parse_mode="HTML")
        return

    query = args[1].strip()
    repo = FileRepository(get_db())
    records = await repo.search_by_filename(message.from_user.id, query)

    if not records:
        await message.answer(f"🔍 No files matching <code>{query}</code>.", parse_mode="HTML")
        return

    lines = [f"🔍 <b>Results for:</b> <code>{query}</code>\n"]
    for rec in records:
        lines.append(
            f"• <code>{rec.id}</code> — <b>{rec.effective_name}</b>\n"
            f"  {rec.file_type} · {format_size(rec.file_size)} · "
            f"{rec.upload_date.strftime('%Y-%m-%d')}\n"
            f"  /get <code>{rec.id}</code>\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# Feature 2: Tag search — /tag <tagname>
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("tag"))
async def cmd_search_by_tag(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("Usage: /tag <code>&lt;tagname&gt;</code>", parse_mode="HTML")
        return

    tag = args[1].strip().lower().lstrip("#")
    repo = FileRepository(get_db())
    records = await repo.search_by_tag(message.from_user.id, tag)

    if not records:
        await message.answer(f"🏷️ No files tagged <code>#{tag}</code>.", parse_mode="HTML")
        return

    lines = [f"🏷️ <b>Files tagged</b> <code>#{tag}</code>\n"]
    for rec in records:
        lines.append(
            f"• <code>{rec.id}</code> — <b>{rec.effective_name}</b>\n"
            f"  /get <code>{rec.id}</code>\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# Feature: File sharing — /share <file_id>  and  /claim <code>
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("share"))
async def cmd_share(message: Message) -> None:
    """Generate a share code for a file (anyone with the code can claim it)."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /share <code>&lt;file_id&gt;</code>", parse_mode="HTML")
        return

    record_id = args[1].strip()
    repo = FileRepository(get_db())
    code = await repo.create_or_get_share_code(record_id, message.from_user.id)

    if not code:
        await message.answer("❌ File not found or access denied.")
        return

    await message.answer(
        f"🔗 <b>Share Code Generated</b>\n\n"
        f"Code: <code>{code}</code>\n\n"
        f"Anyone using this bot can claim the file with:\n"
        f"/claim <code>{code}</code>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("share:"))
async def cb_share(callback: CallbackQuery) -> None:
    record_id = callback.data.split(":", 1)[1]
    repo = FileRepository(get_db())
    code = await repo.create_or_get_share_code(record_id, callback.from_user.id)

    if not code:
        await callback.answer("❌ Could not generate share code.", show_alert=True)
        return

    await callback.message.answer(
        f"🔗 <b>Share Code:</b> <code>{code}</code>\n\n"
        f"Anyone can claim this file with:\n/claim <code>{code}</code>",
        parse_mode="HTML",
    )
    await callback.answer("Share code sent!")


@router.message(Command("claim"))
async def cmd_claim(message: Message, bot: Bot) -> None:
    """
    Claim a shared file using its share code.
    The bot copies the file from the internal channel to the claimer.
    """
    if not message.text:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /claim <code>&lt;share_code&gt;</code>", parse_mode="HTML")
        return

    code = args[1].strip().upper()
    repo = FileRepository(get_db())
    quota_repo = QuotaRepository(get_db())
    record = await repo.get_by_share_code(code)

    if not record:
        await message.answer("❌ Invalid or expired share code.")
        return

    user_id = message.from_user.id
    
    # Shortlink-based token verification for non-admins (same as /get)
    if not is_admin(user_id):
        verify_status = await quota_repo.get_verify_status(user_id)
        
        # Check if verification expired
        if verify_status.get("verified_time"):
            from datetime import timedelta
            verified_time = verify_status["verified_time"]
            if verified_time.tzinfo is None:
                verified_time = verified_time.replace(tzinfo=timezone.utc)
            
            time_diff = (datetime.now(timezone.utc) - verified_time).total_seconds()
            if time_diff > settings.verify_expire_seconds:
                # Expired - generate new token and shortlink
                await quota_repo.update_verify_status(user_id, is_verified=False)
                verify_status = await quota_repo.get_verify_status(user_id)
        
        # Generate verification message if not verified
        if not verify_status.get("is_verified"):
            # Generate random 10-character token
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            await quota_repo.update_verify_status(user_id, verify_token=token)
            
            # Create shortlink
            bot_username = await bot.get_me()
            shortlink = await get_shortlink(
                settings.shortlink_url,
                settings.shortlink_api,
                f"https://t.me/{bot_username.username}?start=verify_{token}"
            )
            
            # Create button
            btn = [[InlineKeyboardButton(text="• 🔗 Open Link •", url=shortlink)]]
            await message.answer(
                f"<b>Your token has expired...</b> Please refresh your token to continue..\n\n"
                f"<b>Token Timeout:</b> {get_exp_time(settings.verify_expire_seconds)}\n\n"
                f"<b>What is the token?</b>\n\n"
                f"This is an ads token. Passing one ad allows you to use the bot for {get_exp_time(settings.verify_expire_seconds)}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btn)
            )
            return
    if len(args) < 2:
        await message.answer("Usage: /claim <code>&lt;share_code&gt;</code>", parse_mode="HTML")
        return

    code = args[1].strip().upper()
    repo = FileRepository(get_db())
    quota_repo = QuotaRepository(get_db())
    record = await repo.get_by_share_code(code)

    if not record:
        await message.answer("❌ Invalid or expired share code.")
        return

    user_id = message.from_user.id
    file_size = record.file_size or 0
    is_user_admin = is_admin(user_id)
    
    allowed, quota, reason = await quota_repo.can_download(user_id, file_size, is_user_admin)
    if not allowed:
        if reason == "bandwidth_exceeded":
            await message.answer(
                f"🚫 <b>Download quota exceeded!</b>\n\n"
                f"📦 Bandwidth used: {format_size(quota.bandwidth_used)} / {format_size(quota.bandwidth_limit)}\n"
                f"📊 Downloads today: {quota.download_count}\n\n"
                f"Your quota will reset at midnight UTC.",
                parse_mode="HTML",
            )
            return
        elif reason == "download_count_exceeded":
            await message.answer(
                f"🚫 <b>Daily download limit reached!</b>\n\n"
                f"📊 Downloads today: {quota.download_count} / {quota.download_limit}\n\n"
                f"Your quota will reset at midnight UTC.",
                parse_mode="HTML",
            )
            return
        await message.answer(f"🚫 Download not allowed: {reason}", parse_mode="HTML")
        return

    try:
        sent_message = await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=record.channel_id,
            message_id=record.internal_message_id,
            caption=record.caption,
            protect_content=True,  # Prevents forwarding and saving
        )
        await repo.increment_share_uses(record.id)
        await quota_repo.add_download_usage(user_id, file_size)
        await message.answer(
            f"✅ <b>File received!</b>\n"
            f"📄 {record.effective_name} (shared by @{record.username or 'anonymous'})\n\n"
            f"⚠️ <b>This message will auto-delete in 60 seconds.</b>\n"
            f"🔒 <b>Forwarding and saving are disabled.</b>",
            parse_mode="HTML",
        )
        logger.info("User %s claimed file %s via code %s", user_id, record.id, code)
        
        # Auto-delete the message after 60 seconds
        asyncio.create_task(
            _auto_delete_message(bot, message.chat.id, sent_message.message_id, record.id)
        )
    except Exception as exc:
        logger.exception("Claim delivery failed: %s", exc)
        await message.answer(f"❌ Retrieval failed: <code>{type(exc).__name__}</code>", parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# Feature: Rename — FSM flow
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("rename"))
async def cmd_rename(message: Message, state: FSMContext) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /rename <code>&lt;file_id&gt;</code>", parse_mode="HTML")
        return
    await state.set_state(RenameStates.waiting_for_new_name)
    await state.update_data(record_id=args[1].strip())
    await message.answer("✏️ Send me the new display name for this file:")


@router.callback_query(F.data.startswith("rename:"))
async def cb_rename(callback: CallbackQuery, state: FSMContext) -> None:
    record_id = callback.data.split(":", 1)[1]
    await state.set_state(RenameStates.waiting_for_new_name)
    await state.update_data(record_id=record_id)
    await callback.message.answer("✏️ Send me the new display name for this file:")
    await callback.answer()


@router.message(RenameStates.waiting_for_new_name)
async def process_rename(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    record_id = data.get("record_id")
    new_name = message.text.strip()

    if not new_name or len(new_name) > 255:
        await message.answer("❌ Name must be 1–255 characters.")
        return

    repo = FileRepository(get_db())
    success = await repo.rename(record_id, message.from_user.id, new_name)
    await state.clear()

    if success:
        await message.answer(
            f"✅ File renamed to <b>{new_name}</b>", parse_mode="HTML"
        )
    else:
        await message.answer("❌ File not found or access denied.")


# ─────────────────────────────────────────────────────────────────────────────
# Feature: Tagging — FSM flow
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tag:"))
async def cb_tag(callback: CallbackQuery, state: FSMContext) -> None:
    record_id = callback.data.split(":", 1)[1]
    await state.set_state(TagStates.waiting_for_tags)
    await state.update_data(record_id=record_id)
    await callback.message.answer(
        "🏷️ Send me tags for this file.\n"
        "Example: <code>#invoice #2024 #work</code> or just <code>invoice 2024 work</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TagStates.waiting_for_tags)
async def process_tags(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    record_id = data.get("record_id")
    tags = parse_tags(message.text)

    if not tags:
        await message.answer("❌ No valid tags found. Try: <code>#invoice #2024</code>", parse_mode="HTML")
        return

    repo = FileRepository(get_db())
    success = await repo.set_tags(record_id, message.from_user.id, tags)
    await state.clear()

    if success:
        tag_display = " ".join(f"<code>#{t}</code>" for t in tags)
        await message.answer(f"✅ Tags set: {tag_display}", parse_mode="HTML")
    else:
        await message.answer("❌ File not found or access denied.")


# ─────────────────────────────────────────────────────────────────────────────
# Feature: Set Expiry — inline keyboard selection
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("expiry:"))
async def cb_expiry_menu(callback: CallbackQuery) -> None:
    record_id = callback.data.split(":", 1)[1]
    await callback.message.answer(
        "⏰ How long should this file be kept?",
        reply_markup=build_expiry_keyboard(record_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_expiry:"))
async def cb_set_expiry(callback: CallbackQuery) -> None:
    _, record_id, days_str = callback.data.split(":")
    days = int(days_str)

    repo = FileRepository(get_db())
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=days) if days > 0 else None
    )
    success = await repo.set_expiry(record_id, callback.from_user.id, expires_at)

    if success:
        msg = (
            f"⏰ File will expire on <b>{expires_at.strftime('%Y-%m-%d')}</b>"
            if expires_at
            else "✅ File expiry removed — it will be kept indefinitely."
        )
        await callback.message.answer(msg, parse_mode="HTML")
    else:
        await callback.message.answer("❌ File not found or access denied.")
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# Delete with confirmation
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("delete"))
async def cmd_delete(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Usage: /delete <code>&lt;file_id&gt;</code>", parse_mode="HTML")
        return
    record_id = args[1].strip()
    await message.answer(
        f"🗑️ Delete file <code>{record_id}</code>? This cannot be undone.",
        parse_mode="HTML",
        reply_markup=build_delete_confirm_keyboard(record_id),
    )


@router.callback_query(F.data.startswith("delete_confirm:"))
async def cb_delete_confirm(callback: CallbackQuery) -> None:
    record_id = callback.data.split(":", 1)[1]
    await callback.message.edit_text(
        f"🗑️ Delete file <code>{record_id}</code>? This cannot be undone.",
        parse_mode="HTML",
        reply_markup=build_delete_confirm_keyboard(record_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_do:"))
async def cb_delete_do(callback: CallbackQuery) -> None:
    record_id = callback.data.split(":", 1)[1]
    db = get_db()
    file_repo = FileRepository(db)
    quota_repo = QuotaRepository(db)

    record = await file_repo.get_by_id(record_id)
    if record and record.user_id == callback.from_user.id:
        deleted = await file_repo.delete_by_id(record_id, callback.from_user.id)
        if deleted:
            await callback.message.edit_text(
                f"🗑️ File <code>{record_id}</code> deleted.", parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("❌ Deletion failed.")
    else:
        await callback.message.edit_text("❌ File not found or access denied.")
    await callback.answer()


@router.callback_query(F.data.startswith("delete_cancel:"))
async def cb_delete_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("✅ Deletion cancelled.")
    await callback.answer()


# ─────────────────────────────────────────────────────────────────────────────
# /mystats — quota usage
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("mystats"))
async def cmd_mystats(message: Message) -> None:
    quota_repo = QuotaRepository(get_db())
    quota = await quota_repo.get(message.from_user.id)
    
    await quota_repo.check_and_reset_if_needed(message.from_user.id)
    quota = await quota_repo.get(message.from_user.id)

    bar_length = 20
    if quota.is_unlimited:
        bar = "∞ unlimited"
        pct_str = "Unlimited"
    else:
        usage_percent = (quota.bandwidth_used / quota.bandwidth_limit) * 100
        filled = int(usage_percent / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        pct_str = f"{usage_percent:.1f}%"
    
    downloads_str = str(quota.download_count) if quota.download_limit == 0 else f"{quota.download_count} / {quota.download_limit}"
    reset_str = quota.quota_reset_time.strftime('%Y-%m-%d %H:%M UTC') if quota.quota_reset_time else "Not set"

    await message.answer(
        f"📊 <b>Your Download Stats</b>\n\n"
        f"📥 <b>Downloads today:</b> {downloads_str}\n"
        f"📦 <b>Bandwidth used:</b> {format_size(quota.bandwidth_used)}\n"
        f"📋 <b>Bandwidth limit:</b> {'Unlimited' if quota.is_unlimited else format_size(quota.bandwidth_limit)}\n\n"
        f"[{bar}] {pct_str}\n\n"
        f"⏰ <b>Resets at:</b> {reset_str}",
        parse_mode="HTML",
    )


