"""Compatibility facade for the Qt help dialog."""

from ui.dialogs.help import (
    help_file_path,
    load_help_text,
    markdown_to_plain,
    open_help,
    user_docs_dir,
)

__all__ = [
    "help_file_path",
    "load_help_text",
    "markdown_to_plain",
    "open_help",
    "user_docs_dir",
]
