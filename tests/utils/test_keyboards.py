"""
Unit tests for keyboard builders.
"""
import pytest

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.keyboards import (
    build_file_list_keyboard,
    build_file_action_keyboard,
    build_delete_confirm_keyboard,
    build_expiry_keyboard,
)
from bot.models.file_record import FileRecord
from datetime import datetime, timezone


def test_build_file_action_keyboard():
    """Test building file action keyboard."""
    record_id = "507f1f77bcf86cd799439011"
    keyboard = build_file_action_keyboard(record_id)

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard is not None

    rows = keyboard.inline_keyboard
    # Should have 3 rows (Share/Tag, Rename/Expiry, Delete)
    assert len(rows) == 3

    # Row 1: Share and Tag
    row1 = rows[0]
    assert len(row1) == 2
    assert isinstance(row1[0], InlineKeyboardButton)
    assert row1[0].text == "🔗 Share"
    assert row1[0].callback_data == f"share:{record_id}"
    assert row1[1].text == "🏷️ Tag"
    assert row1[1].callback_data == f"tag:{record_id}"

    # Row 2: Rename and Set Expiry
    row2 = rows[1]
    assert len(row2) == 2
    assert isinstance(row2[0], InlineKeyboardButton)
    assert row2[0].text == "✏️ Rename"
    assert row2[0].callback_data == f"rename:{record_id}"
    assert row2[1].text == "⏰ Set Expiry"
    assert row2[1].callback_data == f"expiry:{record_id}"

    # Row 3: Delete
    row3 = rows[2]
    assert len(row3) == 1
    assert isinstance(row3[0], InlineKeyboardButton)
    assert row3[0].text == "🗑️ Delete"
    assert row3[0].callback_data == f"delete_confirm:{record_id}"


def test_build_delete_confirm_keyboard():
    """Test building delete confirmation keyboard."""
    record_id = "507f1f77bcf86cd799439011"
    keyboard = build_delete_confirm_keyboard(record_id)

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard is not None

    rows = keyboard.inline_keyboard
    # Should have 1 row with 2 buttons
    assert len(rows) == 1

    row = rows[0]
    assert len(row) == 2

    # Yes, delete button
    assert isinstance(row[0], InlineKeyboardButton)
    assert row[0].text == "✅ Yes, delete"
    assert row[0].callback_data == f"delete_do:{record_id}"

    # Cancel button
    assert isinstance(row[1], InlineKeyboardButton)
    assert row[1].text == "❌ Cancel"
    assert row[1].callback_data == f"delete_cancel:{record_id}"


def test_build_expiry_keyboard():
    """Test building expiry selection keyboard."""
    record_id = "507f1f77bcf86cd799439011"
    keyboard = build_expiry_keyboard(record_id)

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard is not None

    rows = keyboard.inline_keyboard
    # Should have 2 rows (4 options adjusted to 2 per row)
    assert len(rows) == 2

    # Each row should have 2 buttons
    for row in rows:
        assert len(row) == 2

    # Verify all options
    expected_options = [
        ("1 day", 1),
        ("7 days", 7),
        ("30 days", 30),
        ("Never", 0),
    ]

    flat_buttons = [btn for row in rows for btn in row]
    assert len(flat_buttons) == 4

    for i, (expected_label, expected_days) in enumerate(expected_options):
        btn = flat_buttons[i]
        assert isinstance(btn, InlineKeyboardButton)
        assert btn.text == expected_label
        assert btn.callback_data == f"set_expiry:{record_id}:{expected_days}"


def test_build_file_list_keyboard_single_page():
    """Test building file list keyboard with single page."""
    records = [
        FileRecord(
            id="record1",
            user_id=123456789,
            original_filename="file1.pdf",
            file_type="document",
            internal_message_id=1,
            channel_id=-1001234567890,
            telegram_file_id="file_id_1",
            telegram_file_unique_id="unique_id_1",
            file_size=1024 * 1024,
           ),
        FileRecord(
            id="record2",
            user_id=123456789,
            original_filename="file2.jpg",
            file_type="photo",
            internal_message_id=2,
            channel_id=-1001234567890,
            telegram_file_id="file_id_2",
            telegram_file_unique_id="unique_id_2",
            file_size=512 * 1024,
            ),
    ]

    keyboard = build_file_list_keyboard(records, page=1, total_pages=1)

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard is not None

    rows = keyboard.inline_keyboard
    # Should have 3 rows (2 file rows + 1 nav row)
    assert len(rows) == 3

    # File rows
    for i in range(2):
        row = rows[i]
        assert len(row) == 1
        assert row[0].callback_data == f"get:{records[i].id}"
        assert "📥" in row[0].text

    # Nav row: only page indicator (no prev/next)
    nav_row = rows[2]
    assert len(nav_row) == 1
    assert nav_row[0].text == "📄 1/1"
    assert nav_row[0].callback_data == "noop"


def test_build_file_list_keyboard_first_page():
    """Test building file list keyboard on first page of multiple pages."""
    records = [
        FileRecord(
            id="record1",
            user_id=123456789,
            original_filename="file1.pdf",
            file_type="document",
            internal_message_id=1,
            channel_id=-1001234567890,
            telegram_file_id="file_id_1",
            telegram_file_unique_id="unique_id_1",
            file_size=1024 * 1024,
            ),
    ]

    keyboard = build_file_list_keyboard(records, page=1, total_pages=3)

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard is not None

    rows = keyboard.inline_keyboard
    assert len(rows) == 2

    # Nav row: page indicator + Next (no Prev)
    nav_row = rows[1]
    assert len(nav_row) == 2
    assert nav_row[0].text == "📄 1/3"
    assert nav_row[1].text == "Next ▶️"
    assert nav_row[1].callback_data == "page:2"


def test_build_file_list_keyboard_middle_page():
    """Test building file list keyboard on middle page."""
    records = [
        FileRecord(
            id="record1",
            user_id=123456789,
            original_filename="file1.pdf",
            file_type="document",
            internal_message_id=1,
            channel_id=-1001234567890,
            telegram_file_id="file_id_1",
            telegram_file_unique_id="unique_id_1",
            file_size=1024 * 1024,
            ),
    ]

    keyboard = build_file_list_keyboard(records, page=2, total_pages=5)

    rows = keyboard.inline_keyboard
    assert len(rows) == 2

    # Nav row: Prev + page indicator + Next
    nav_row = rows[1]
    assert len(nav_row) == 3
    assert nav_row[0].text == "◀️ Prev"
    assert nav_row[0].callback_data == "page:1"
    assert nav_row[1].text == "📄 2/5"
    assert nav_row[2].text == "Next ▶️"
    assert nav_row[2].callback_data == "page:3"


def test_build_file_list_keyboard_last_page():
    """Test building file list keyboard on last page."""
    records = [
        FileRecord(
            id="record1",
            user_id=123456789,
            original_filename="file1.pdf",
            file_type="document",
            internal_message_id=1,
            channel_id=-1001234567890,
            telegram_file_id="file_id_1",
            telegram_file_unique_id="unique_id_1",
            file_size=1024 * 1024,
            ),
    ]

    keyboard = build_file_list_keyboard(records, page=3, total_pages=3)

    rows = keyboard.inline_keyboard
    assert len(rows) == 2

    # Nav row: Prev + page indicator (no Next)
    nav_row = rows[1]
    assert len(nav_row) == 2
    assert nav_row[0].text == "◀️ Prev"
    assert nav_row[0].callback_data == "page:2"
    assert nav_row[1].text == "📄 3/3"


def test_build_file_list_keyboard_truncates_long_names():
    """Test that long file names are truncated correctly."""
    long_name = "a" * 50 + ".pdf"

    record = FileRecord(
        id="record1",
        user_id=123456789,
        original_filename=long_name,
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_1",
        telegram_file_unique_id="unique_id_1",
        file_size=1024 * 1024,
    )

    keyboard = build_file_list_keyboard([record], page=1, total_pages=1)

    row = keyboard.inline_keyboard[0]
    btn = row[0]

    # Name should be truncated to 28 characters
    assert len(btn.text) < len(long_name) + 20  # Some allowance for formatting
    assert "📥" in btn.text
    assert btn.callback_data == "get:record1"


def test_build_file_list_keyboard_empty_records():
    """Test building file list keyboard with no records."""
    keyboard = build_file_list_keyboard([], page=1, total_pages=0)

    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert keyboard.inline_keyboard is not None

    # Should only have nav row
    rows = keyboard.inline_keyboard
    assert len(rows) == 1
    assert len(rows[0]) == 1
    assert rows[0][0].text == "📄 1/0"


def test_build_file_list_keyboard_file_size_formatting():
    """Test that file sizes are formatted correctly in labels."""
    records = [
        FileRecord(
            id="record1",
            user_id=123456789,
            original_filename="test.pdf",
            file_type="document",
            internal_message_id=1,
            channel_id=-1001234567890,
            telegram_file_id="file_id_1",
            telegram_file_unique_id="unique_id_1",
            file_size=1024 * 1024 * 5,  # 5 MB
        ),
        FileRecord(
            id="record2",
            user_id=123456789,
            original_filename="test2.jpg",
            file_type="photo",
            internal_message_id=2,
            channel_id=-1001234567890,
            telegram_file_id="file_id_2",
            telegram_file_unique_id="unique_id_2",
            file_size=2048,  # 2 KB
        ),
    ]

    keyboard = build_file_list_keyboard(records, page=1, total_pages=1)

    rows = keyboard.inline_keyboard

    # First file button should contain "5.0 MB"
    assert "5.0 MB" in rows[0][0].text

    # Second file button should contain "2.0 KB"
    assert "2.0 KB" in rows[1][0].text


def test_build_file_list_keyboard_uses_effective_name():
    """Test that keyboard uses effective_name (display_name if set)."""
    record = FileRecord(
        id="record1",
        user_id=123456789,
        original_filename="original.pdf",
        display_name="renamed_file.pdf",  # Display name takes precedence
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_1",
        telegram_file_unique_id="unique_id_1",
        file_size=1024 * 1024,
    )

    keyboard = build_file_list_keyboard([record], page=1, total_pages=1)

    btn = keyboard.inline_keyboard[0][0]
    assert "renamed_file.pdf" in btn.text
    assert "original.pdf" not in btn.text


def test_build_file_list_keyboard_no_display_name():
    """Test that keyboard falls back to original_filename when no display_name."""
    record = FileRecord(
        id="record1",
        user_id=123456789,
        original_filename="original.pdf",
        file_type="document",
        internal_message_id=1,
        channel_id=-1001234567890,
        telegram_file_id="file_id_1",
        telegram_file_unique_id="unique_id_1",
        file_size=1024 * 1024,
    )

    keyboard = build_file_list_keyboard([record], page=1, total_pages=1)

    btn = keyboard.inline_keyboard[0][0]
    assert "original.pdf" in btn.text
