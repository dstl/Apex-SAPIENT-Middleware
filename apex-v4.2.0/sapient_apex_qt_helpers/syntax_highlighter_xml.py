#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Implementation of QSyntaxHighlighter for XML, intended for simple cases with no errors."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont


class _State(Enum):
    NORMAL = 0  # Just any text not in an element or comment
    COMMENT = 1  # Text in a comment
    ELEMENT = 2  # Text in an element but not including attributes
    ELEMENT_END = 3  # Trailing characters in an element, typically > or />
    ATTRIBUTE_NAME = 4  # Attribute name
    ATTRIBUTE_SINGLE = 5  # Text in an attribute value that uses single quotation marks
    ATTRIBUTE_DOUBLE = 6  # Text in an attribute value that uses double quotation marks


_state_formats_dicts = {
    _State.NORMAL: {"color": Qt.black},
    _State.COMMENT: {"color": Qt.gray, "italic": True},
    _State.ELEMENT: {"color": Qt.darkCyan, "bold": True},
    _State.ATTRIBUTE_NAME: {"color": Qt.blue, "bold": True},
    _State.ATTRIBUTE_SINGLE: {"color": Qt.darkGreen, "bold": True},
}
_state_formats_dicts.update(
    {
        _State.ELEMENT_END: _state_formats_dicts[_State.ELEMENT],
        _State.ATTRIBUTE_DOUBLE: _state_formats_dicts[_State.ATTRIBUTE_SINGLE],
    }
)


@dataclass
class _StatePosition:
    """State of parsing at a particular index into a string"""

    # Current type of state
    state: _State
    # Position in the string where that state begins (formatting for it starts here)
    position: int
    # Position to start search for next state (= position + len(start delimiter))
    position_search: Optional[int] = None

    def __post_init__(self):
        # position_search defaults to position (if there is no start delimiter e.g. for NORMAL)
        if self.position_search is None:
            self.position_search = self.position


_regex_in_element = re.compile(">|\\s")  # Either > or a whitespace character
_regex_in_attribute_name = re.compile("[>'\"]")  # Any one of > or single quote or double quote


def _get_next_state(text: str, state_position: _StatePosition) -> Optional[_StatePosition]:
    if state_position.state == _State.NORMAL:
        tag_index = text.find("<", state_position.position_search)
        if tag_index == -1:
            return None
        if text[tag_index + 1 : tag_index + 4] == "!--":
            return _StatePosition(_State.COMMENT, tag_index, tag_index + 4)
        else:
            return _StatePosition(_State.ELEMENT, tag_index, tag_index + 1)

    elif state_position.state == _State.COMMENT:
        end_index = text.find("-->", state_position.position_search)
        if end_index == -1:
            return None
        end_index += 3  # Include "-->" in the comment formatting
        return _StatePosition(_State.NORMAL, end_index)

    elif state_position.state == _State.ELEMENT:
        result = _regex_in_element.search(text, state_position.position_search)
        if not result:
            # A line break ends the element text
            return _StatePosition(_State.ATTRIBUTE_NAME, len(text))
        if result[0] == ">":
            return _StatePosition(_State.NORMAL, result.end())
        else:
            return _StatePosition(_State.ATTRIBUTE_NAME, result.end())

    elif state_position.state == _State.ELEMENT_END:
        end_index = text.index(">", state_position.position_search)
        end_index += 1  # Include ">" in the formatting
        return _StatePosition(_State.NORMAL, end_index)

    elif state_position.state == _State.ATTRIBUTE_NAME:
        result = _regex_in_attribute_name.search(text, state_position.position_search)
        if not result:
            return None
        if result[0] == ">":
            # Attribute state was a false alarm; we already heading for the end of the element
            return _StatePosition(_State.ELEMENT_END, state_position.position_search)
        elif result[0] == "'":
            return _StatePosition(_State.ATTRIBUTE_SINGLE, result.start(), result.end())
        elif result[0] == '"':
            return _StatePosition(_State.ATTRIBUTE_DOUBLE, result.start(), result.end())
        else:
            raise ValueError(f"Impossible regex match: {result}")

    elif state_position.state in (_State.ATTRIBUTE_SINGLE, _State.ATTRIBUTE_DOUBLE):
        quotation_mark = "'" if state_position.state == _State.ATTRIBUTE_SINGLE else '"'
        end_index = text.find(quotation_mark, state_position.position_search)
        if end_index == -1:
            return None
        end_index += 1  # Include close quotation mark in formatting
        return _StatePosition(_State.ATTRIBUTE_NAME, end_index)

    else:
        raise ValueError(f"Unknown syntax state {state_position.state}")


def _debug_print(*args, **kwargs):
    # Uncomment this print statement to print state during parsing
    # print(*args, **kwargs)
    pass


class SyntaxHighlighterXml(QSyntaxHighlighter):
    def __init__(self, document, font):
        super().__init__(document)
        self.state_formats = {}
        for state, format_dict in _state_formats_dicts.items():
            new_format = QTextCharFormat()
            new_format.setFont(font)
            new_format.setForeground(format_dict["color"])
            new_format.setFontItalic(format_dict.get("italic", False))
            if format_dict.get("bold", False):
                new_format.setFontWeight(QFont.Bold)
            self.state_formats[state] = new_format

    def highlightBlock(self, text):
        prev_state = self.previousBlockState()
        if prev_state == -1:
            prev_state = _State.NORMAL
        state_position = _StatePosition(_State(prev_state), 0)
        _debug_print("For text:", text)
        _debug_print("Start state:", state_position)
        while state_position.position < len(text):
            # What is the state after the current one?
            next_state = _get_next_state(text, state_position)
            # If the state does not change by the end of the string, add a virtual "next state"
            # that is equal to the current one but ends at the end of the string, so that the
            # following setFormat statement formats the rest of the string.
            if next_state is None:
                next_state = _StatePosition(state=state_position.state, position=len(text))
            else:
                _debug_print("Next state:", next_state)
            # Format from the start of the current state up until the start of the new state we
            # have just found. This could be zero characters (e.g. an element immediately followed
            # by a comment will be in the NORMAL state for zero characters in between).
            state_format = self.state_formats[state_position.state]
            count = next_state.position - state_position.position
            self.setFormat(state_position.position, count, state_format)
            # Update the state ready for the next loop iteration.
            state_position = next_state
        _debug_print("Final state:", state_position)
        self.setCurrentBlockState(state_position.state.value)


# # # # # # # # # # # # # # # # # # # # #
# Module self-test

_test_xml = """
<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<!-- Attempt at testing most XML edge cases plusa few allowable errors -->
<Test>sdf
    <Long
        attr="elemen
        t"
sadff="blah"blah="asdfd">
        <!-- Multiline
"        Comment -->
 "       Test <!--> -->
    </Long><baz/> asdf<foo/>
    <one><two at="val"><!-- once caused an infinite loop -->
    <foo
bar="sodfij"/>
    <>asdf
    <test xzc="bar"baz='asd' doifj="oijsd" />
<!--^    ^    ^    ^                      ^
    |    |    |    |                      `- attribute then immediately element end
    |    |    |    `- - attribute
    |    |    `- - - quote
    |    `- - - attribute
    `- - - element
 -->
    < teij />
</Test>
"""


def _test_main():
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit

    app = QApplication(sys.argv)
    window = QMainWindow()
    editor = QTextEdit()
    SyntaxHighlighterXml(editor.document())
    editor.setPlainText(_test_xml)
    window.setCentralWidget(editor)
    window.show()
    app.exec()


if __name__ == "__main__":
    _test_main()
