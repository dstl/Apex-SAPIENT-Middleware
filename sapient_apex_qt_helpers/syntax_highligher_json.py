#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#
"""Implementation of QSyntaxHighlighter for JSON, intended for simple cases with no errors."""
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QTextBlockUserData


class _CharType(Enum):
    NORMAL = 0  # Free text; should only be numbers, null, true or false
    PUNCTUATION = 1  # Square brackets, braces, comma, colon
    STRING = 2  # Quoted string (value or standalone)
    STRING_KEY = 3  # Quoted string (key of a map)


_char_type_formats_dicts = {
    _CharType.NORMAL: {"color": Qt.blue, "bold": True},
    _CharType.PUNCTUATION: {"color": Qt.black},
    _CharType.STRING: {"color": Qt.darkGreen, "bold": True},
    _CharType.STRING_KEY: {"color": Qt.darkCyan, "bold": True},
}


class _JsonBlockState(QTextBlockUserData):
    """Holds data about state at end of block.

    This holds a list of delimiters, optionally with a colon at the end. This allows knowing whether
    a string should be highlighted as a key (if before a colon in a map) or a value (if after a
    colon in a map, or anywhere in a list, or at the top level). We need the full list of delimiters
    because we need to know the current container (map or list) when we encounter a comma to know
    whether we should switch back to key format, and we may have passed through other containers
    since the open delimiter of this one.
    """

    def __init__(self, delims):
        super().__init__()
        self.delims = delims


class SyntaxHighlighterJson(QSyntaxHighlighter):
    def __init__(self, document, font):
        super().__init__(document)
        self.state_formats = {}
        for state, format_dict in _char_type_formats_dicts.items():
            new_format = QTextCharFormat()
            new_format.setFont(font)
            new_format.setForeground(format_dict["color"])
            new_format.setFontItalic(format_dict.get("italic", False))
            if format_dict.get("bold", False):
                new_format.setFontWeight(QFont.Bold)
            self.state_formats[state] = new_format

    def highlightBlock(self, text):
        punctuation_chars = ("{", "}", "[", "]", ":", ",", " ")
        punc_or_quote_chars = punctuation_chars + ("",)

        delims = []
        prev_block = self.currentBlock().previous()
        if prev_block is not None:
            prev_user_data = prev_block.userData()
            if prev_user_data is not None:
                delims = list(prev_user_data.delims)

        position = 0
        while position < len(text):
            # Each iteration of this loop:
            # * identifies the current character type based on the first character
            # * looks for where this type of character ends
            # * updates the stack of opening delimiters along the way

            if text[position] == '"':
                if delims and delims[-1] == "{":
                    char_type = _CharType.STRING_KEY
                else:
                    char_type = _CharType.STRING
                # Find next quote
                next_quote = text.find('"', position + 1)
                # Keep searching past "\""
                while next_quote != -1 and text[next_quote - 1] == "\\":
                    next_quote = text.find('"', next_quote + 1)
                next_position = next_quote + 1 if next_quote != -1 else len(text)

            elif text[position] in punctuation_chars:
                char_type = _CharType.PUNCTUATION
                next_position = position
                while next_position < len(text) and text[next_position] in punctuation_chars:
                    # Move from value back to key
                    if text[next_position] in (",", "}") and delims and delims[-1] == ":":
                        delims.pop()
                    # Move from key to value
                    if text[next_position] == ":" and not (delims and delims[-1] == ":"):
                        delims.append(":")
                    # Allow closing bracket
                    if text[next_position] == "]" and delims and delims[-1] == "[":
                        delims.pop()
                    if text[next_position] == "}" and delims and delims[-1] == "{":
                        delims.pop()
                    # Allow opening bracket
                    if text[next_position] in ("[", "{"):
                        delims.append(text[next_position])

                    next_position += 1

            else:
                char_type = _CharType.NORMAL
                next_position = position
                while next_position < len(text) and text[next_position] not in punc_or_quote_chars:
                    next_position += 1

            self.setFormat(position, next_position - position, self.state_formats[char_type])
            position = next_position

        old_block_data = self.currentBlockUserData()
        if old_block_data is None or old_block_data.delims != delims:
            self.setCurrentBlockUserData(_JsonBlockState(delims))
            # Update state to force next block to be updated
            self.setCurrentBlockState(self.currentBlockState() + 1)


# # # # # # # # # # # # # # # # # # # # #
# Module self-test

# language=json
_test_json = r"""
{
  "foo": null,
  "bar": [1, 2, "steve", [1, 2], {"a": b}],
  "has quote": "foo\"bar"
  23: {
    "x": "foo",
    "y": [
      "a", "b", "c", true, false, not_a_keyword, not valid syntax, -1.2e3
    ]
  }
}
"""


def _test_main():
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit

    app = QApplication(sys.argv)
    window = QMainWindow()
    editor = QTextEdit()
    font = QFont("Consolas")
    font.setStyleHint(QFont.TypeWriter)
    font.setPointSize(10)
    SyntaxHighlighterJson(editor.document(), font)
    editor.setPlainText(_test_json)
    window.setCentralWidget(editor)
    window.show()
    app.exec()


if __name__ == "__main__":
    _test_main()
