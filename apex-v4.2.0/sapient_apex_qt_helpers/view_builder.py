#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Given a dictionary keyed on widgets and strings, set properties and add children.

The build_view() function in this file gives an easy way to set properties, connect signals and add
child widgets and layouts to widgets. For example (this is the __init__ method of a window):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit = QLineEdit()
        view = {
            "windowTitle": "My Form",
            QVBoxLayout(): {
                QGroupBox("Name"): {
                    QVBoxLayout(): {
                        self.edit: {
                            "text": "Write name here...",
                        },
                        QPushButton(): {
                            "text": "Clear!",
                            "clicked": self.edit.clear,
                        },
                    }
                },
                QPushButton(): {
                    "text": "Show Greetings",
                    "clicked": self.greetings,
                },
            },
        }
        build_view(self, view)

The above code is equivalent to the following:

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Form")

        # Create widgets
        self.edit = QLineEdit("Write name here...")
        showButton = QPushButton("Show Greetings")
        clearButton = QPushButton("Clear!")

        # Fill in top-level layout
        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        nameGroupBox = QGroupBox("Name")
        mainLayout.addWidget(nameGroupBox)
        mainLayout.addWidget(showButton)

        # Fill in group box
        groupBoxLayout = QVBoxLayout()
        nameGroupBox.setLayout(groupBoxLayout)
        groupBoxLayout.addWidget(self.edit)
        groupBoxLayout.addWidget(clearButton)

        # Connect slots
        showButton.clicked.connect(self.greetings)
        clearButton.clicked.connect(self.edit.clear)
"""

import sys

from PySide6.QtCore import QMetaMethod
from PySide6.QtWidgets import (
    QWidget,
    QLayout,
    QMenu,
    QMenuBar,
    QGridLayout,
    QFormLayout,
    QTabWidget,
    QSplitter,
    QBoxLayout,
    QMainWindow,
    QVBoxLayout,
)


def _add_to_parent(parent, child, child_params):
    """Adds a child object into a parent"""

    def raise_error():
        raise TypeError(
            "build_view does not support parent type {} with child type {}".format(
                type(parent).__name__, type(child).__name__
            )
        )

    def wrap_in_widget_if_layout():
        if isinstance(child, QLayout):
            wrapper_widget = QWidget()
            wrapper_widget.setLayout(child)
            return wrapper_widget
        elif isinstance(child, QWidget):
            return child
        else:
            raise_error()

    # Menus and actions
    if isinstance(parent, QLayout) and isinstance(child, QMenuBar):
        parent.setMenuBar(child)
    elif isinstance(parent, QMenuBar) or isinstance(parent, QMenu):
        if isinstance(child, QMenu):
            parent.addMenu(child)
        else:
            raise_error()

    # Parent is a QLayout (note: QLayout containing QMenuBar is handled above)
    elif isinstance(parent, QLayout):
        if isinstance(parent, QBoxLayout) or isinstance(parent, QGridLayout):
            # These support adding a QLayout directly without wrapping in a QWidget
            if isinstance(child, QWidget):
                parent.addWidget(child, *child_params)
            elif isinstance(child, QLayout):
                parent.addLayout(child, *child_params)
            else:
                raise_error()
        elif isinstance(parent, QFormLayout):
            # This has the child as the second parameter e.g. ("Edit:", QTextEdit())
            parent.addRow(*child_params, child)
        else:
            # Any other layout (includes QStackedLayout)
            parent.addWidget(wrap_in_widget_if_layout(), *child_params)

    # Parent is a QWidget (note: QWidget containing QAction is handled above)
    elif isinstance(parent, QWidget):
        # Some subclasses of QWidget need special handling...
        if isinstance(parent, QTabWidget):
            parent.addTab(wrap_in_widget_if_layout(), *child_params)
        elif isinstance(parent, QSplitter):
            parent.addWidget(wrap_in_widget_if_layout())
        elif isinstance(parent, QMainWindow):
            assert parent.centralWidget() is None
            parent.setCentralWidget(wrap_in_widget_if_layout())
        else:
            # For general QWidget, use setLayout to nest the child
            if parent.layout() is not None:
                raise ValueError("Multiple children for QWidget; nest in a QLayout instead")
            if isinstance(child, QWidget):
                wrapper_layout = QVBoxLayout()
                wrapper_layout.addWidget(child)
                parent.setLayout(wrapper_layout)
            elif isinstance(child, QLayout):
                parent.setLayout(child)
            else:
                raise_error()

    # No other parent types are (currently) supported)
    else:
        raise TypeError(f"build_view: Unsupported parent type {type(parent).__name__}")


def _set_property_or_signal(obj, name, value):
    """Sets a property or signal with the given name to the given value.

    This is done by looking through the object's QMetaObject instance for the property or signal
    with that name. In addition, we directly check for a normal method starting with "set" followed
    by the given name (e.g. for "fooBar" we try obj.setFooBar()).
    """
    meta_obj = obj.metaObject()

    for i in range(meta_obj.propertyCount()):
        if name == meta_obj.property(i).name():
            write_success = meta_obj.property(i).write(obj, value)
            if not write_success:
                break
            return

    for i in range(meta_obj.methodCount()):
        is_this_signal = (
            name == meta_obj.method(i).name().data().decode()
            and meta_obj.method(i).methodType() == QMetaMethod.Signal
        )
        if is_this_signal:
            bound_signal = getattr(obj, name)
            bound_signal.connect(value)
            return

    set_method_name = "set" + name[:1].upper() + name[1:]
    set_method = getattr(obj, set_method_name, None)
    if set_method is not None:
        if isinstance(value, tuple):
            set_method(*value)
        else:
            set_method(value)
        return

    raise KeyError(f'Widget {type(obj).__name__} could not set property or signal "{name}"')


def build_view(parent, view):
    if isinstance(view, tuple) and len(view) == 1:
        # Can easily happen from putting trailing comma at end of dictionary literal
        view = view[0]
    assert isinstance(view, dict)
    for k, v in view.items():
        try:
            # If the key is a string then this is a property or signal
            if isinstance(k, str):
                _set_property_or_signal(parent, k, v)
                continue
            # Otherwise this is a child widget (or layout, menu, etc.)
            if isinstance(parent, QFormLayout):
                # Special case for QFormLayout: child item is second parameter
                (
                    label,
                    child,
                ) = k
                child_params = (label,)
            elif isinstance(k, tuple) or isinstance(k, list):
                child, *child_params = k
            else:
                child = k
                child_params = ()
            if isinstance(child, type):
                raise TypeError(f"Type {child} passed as key instead of specific instance")
            _add_to_parent(parent, child, child_params)
            build_view(child, v)
        except Exception:
            print(
                f"Exception for widget {type(parent).__name__} setting child {k}",
                file=sys.stderr,
            )
            raise
