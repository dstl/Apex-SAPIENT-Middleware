#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""ModelMerger class keeps a QStandardItemModel tree, and updates it with new data.

The TreeRow class corresponds very closely with the QStandardItem class (but is slightly less
flexible), and ModelMerger converts recursively-nested TreeRow objects into the columns and
recursively-nested child rows of QStandardItem objects in a QStandardItemModel.

But it is more than just a convenience function for converting from one type to another. It has one
extra facility: the model (in both formats) is remembered, and next time a conversion is performed
the QStandardItem objects are added, removed and edited in the appropriate parent rather than being
constructed from scratch.

To allow this, the TreeRow class has a "key" member, which identifies rows within their parent
objects. Therefore, if the model is constructed with rows having keys [1, 3, 5], and then is
updated with rows having keys [3, 4, 5], then the ModelMerger class is able to deduce that the
three new rows should be constructed by deleting the first old row, keeping the old second and third
rows (updating them if they have changed), and inserting a new row in the middle.

Translating a large "replace the whole model" into a series of add, remove and update operations is
much more efficient on the QT end, and avoids frustrations such as parent items collapsing and
user selections being lost every time the control is updated.
"""

from collections import namedtuple
import logging
from operator import attrgetter
from typing import List
from PySide6.QtGui import QStandardItemModel, QStandardItem


_TOO_MUCH_TRACE = False

logger = logging.getLogger("apex_gui")


TreeRow = namedtuple(
    "TreeRow",
    [
        "key",  # Any; something that the rows are ordered by.
        "columns",  # List[Dict[Qt.ItemDataRole, Any]]; the values for the columns in this row
        "flags",  # Qt.ItemFlags; flags for the row (applied to all columns)
        "children",  # List[TreeRow]; children, must be sorted by their keys already.
    ],
)


class ModelMerger:
    """Keeps a QStandardItemModel tree, and updates it with new data.

    There are two members that are always kept perfectly in sync:

    * self.model is a QStandardItemModel
    * self.model_data is a list of TreeRow objects.

    As explained in the file docstring, when given an updated model_data, the model is updated by
    inserting, deleting and updating rows according the key member, rather than unconditionally
    deleting all existing rows and inserting all rows in the new model parameter.
    """

    def __init__(self, column_names):
        """Initialises ModelMerger with an empty model."""
        self.model_data = []  # List of TreeRows
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(column_names)
        self.column_count = len(column_names)
        if _TOO_MUCH_TRACE:
            logger.debug("Initialised with {} columns: {}".format(self.column_count, column_names))

    def merge(self, new_model_data):
        self._merge(self.model.invisibleRootItem(), self.model_data, new_model_data, 0)

    def _merge(
        self,
        model_item,
        model_data: List[TreeRow],
        new_model_data: List[TreeRow],
        depth,
    ):
        """Merges the rows in the QStandardItem with new data.

        To avoid just deleting and adding everything, the model_data list (which corresponds exactly
        with model_item child rows) is compared against new_model_data. In particular, the key field
        is used to determine what counts as a new row or an existing row that has been updated.
        """
        new_model_data.sort(key=attrgetter("key"))
        index = 0
        new_index = 0
        while index < len(model_data) or new_index < len(new_model_data):
            existing_row = model_data[index] if index < len(model_data) else None
            new_row = new_model_data[new_index] if new_index < len(new_model_data) else None
            if existing_row is None or (new_row is not None and existing_row.key > new_row.key):
                # Insert row from new model into existing one.
                if _TOO_MUCH_TRACE:
                    logger.debug("   " * depth + "Adding new item with key {}".format(new_row.key))
                existing_row = TreeRow(
                    key=new_row.key,
                    columns=list(new_row.columns),
                    flags=new_row.flags,
                    children=[],
                )
                model_data.insert(index, existing_row)
                ModelMerger._insert_row(model_item, index, new_row)
                self._merge(
                    model_item.child(index),
                    existing_row.children,
                    new_row.children,
                    depth + 1,
                )
                index += 1  # We inserted a row, so this keeps us pointing at same row as before.
                new_index += 1  # This points us at the next row.
            elif new_row is None or (existing_row is not None and existing_row.key < new_row.key):
                # Remove row from existing model.
                if _TOO_MUCH_TRACE:
                    logger.debug("   " * depth + "Removing item key {}".format(existing_row.key))
                model_item.removeRow(index)
                del model_data[index]
                # index is now pointing at the next row because we just deleted a row.
                # new_index is pointing at same row as before this loop iteration.
            else:
                # Rows match; update columns from new model and merge children.
                assert existing_row is not None and new_row is not None
                if _TOO_MUCH_TRACE:
                    cells_changed = sum(
                        1 if x != y else 0 for x, y in zip(existing_row.columns, new_row.columns)
                    )
                    logger.debug(
                        "   " * depth
                        + "Updating item with key {}".format(new_row.key)
                        + (" ({} cells changed)".format(cells_changed) if cells_changed else "")
                    )
                assert existing_row.columns is not new_row.columns
                ModelMerger._update_row(model_item, index, existing_row.columns, new_row.columns)
                existing_row.columns[:] = new_row.columns
                self._merge(
                    model_item.child(index),
                    existing_row.children,
                    new_row.children,
                    depth + 1,
                )
                index += 1
                new_index += 1
                # index and new_index are now both pointing at next row in their lists.

    @staticmethod
    def _insert_row(parent_model_item, row_index, new_row):
        column_items = []
        for column_index, data in enumerate(new_row.columns):
            item = QStandardItem()
            item.setFlags(new_row.flags)
            for role, value in data.items():
                item.setData(value, role)
            column_items.append(item)
        parent_model_item.insertRow(row_index, column_items)

    @staticmethod
    def _update_row(parent_model_item, row_index, old_columns, new_columns):
        for column_index, (old_data, new_data) in enumerate(zip(old_columns, new_columns)):
            # Do not update the item if data is identical
            if new_data == old_data:
                continue

            # Check for removed roles; setData() only clears data when explicitly requested
            cleared_keys = set()
            for old_key in old_data.keys():
                if old_key not in new_data:
                    new_data[old_key] = None
                    cleared_keys.add(old_key)

            # Update all the roles of the item
            item = parent_model_item.child(row_index, column_index)
            item.model().setItemData(item.index(), new_data)

            # Avoid polluting our cache with entries corresponding to deleted roles
            for old_key in cleared_keys:
                del new_data[old_key]
