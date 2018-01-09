# -*- coding: utf-8 -*-
"""

    fslib.fs_filepicker
    ~~~~~~~~~~~~~~~~~~~

    This module provides the QT main window for accessing a pyfilesystem2

    This file is part of fs_filepicker.

    :copyright: Copyright 2017 Reimar Bauer
    :license: APACHE-2.0, see LICENSE for details.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""
import sys
import logging
import argparse
import fs
import humanfriendly
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon
from fslib import ui_filepicker, __version__
from fslib.utils import match_extension, WidgetImageText, WidgetText
from fslib.icons import icons
from fslib.utils import root_url


class FilePicker(QtWidgets.QDialog, ui_filepicker.Ui_Dialog):
    def __init__(self, parent=None, fs_url=u"~/", file_pattern=u'*.*', title=u'FS File Picker',
                 default_filename=None, show_save_action=False):
        super(FilePicker, self).__init__(parent)
        self.setupUi(self)
        self.setFixedSize(self.size())
        self.file_icon = icons('text-x-generic.png')
        self.dir_icon = icons('folder.png')
        self.selected_dir = None
        self.filename = None
        self.wparm = None
        self.setWindowTitle(title)
        self.fs_url = unicode(fs_url)
        self.fs_home_url = u"~/"
        self.fs_root_url = root_url()
        self.active_url = self.fs_url
        self.parent_url = self.fs_url
        self.fs = None
        self.file_list_items = []
        self.directory_history = []
        self.last_index = 0
        self.last_dir_index = 0
        self.default_filename = default_filename
        self.file_pattern = file_pattern
        self.show_save_action = show_save_action
        self.button_icons()
        self.show_action()
        self.ui_FileType.setText(self.file_pattern)
        self.fs_button()
        self.ui_FileType.returnPressed.connect(self.selection_file_type)
        self.ui_SelectedName.textChanged.connect(self.selection_name)
        self.ui_Cancel.clicked.connect(self.cancel)
        self.action_buttons()
        self.ui_FileList.itemClicked.connect(self.show_name)
        self.ui_mkdir.clicked.connect(self.make_dir)
        self.ui_history_top.clicked.connect(self.history_top)
        self.ui_history_previous.clicked.connect(self.history_previous)
        self.ui_history_next.clicked.connect(self.history_next)
        self.ui_home.clicked.connect(self.home_button)
        self.ui_root.clicked.connect(self.root_button)
        self.ui_fs.clicked.connect(self.fs_button)
        self.ui_FileList.cellClicked.connect(self.onCellClicked)
        self.ui_FileList.cellDoubleClicked.connect(self.onCellDoubleClicked)
        self.ui_DirList.currentIndexChanged.connect(self.selection_directory)

    def button_icons(self):
        """
        Set icon image to button
        """
        self.ui_history_top.setText("")
        self.ui_history_top.setIcon(QIcon(icons('go-top.png')))
        self.ui_history_next.setText("")
        self.ui_history_next.setIcon(QIcon(icons('go-next.png')))
        self.ui_history_previous.setText("")
        self.ui_history_previous.setIcon(QIcon(icons('go-previous.png')))
        self.ui_mkdir.setText("")
        self.ui_mkdir.setIcon(QIcon(icons('folder-new.png')))
        self.ui_home.setText("")
        self.ui_home.setIconSize(QtCore.QSize(64, 64))
        self.ui_home.setIcon(QIcon(icons('go-home.png')))
        self.ui_root.setText("")
        self.ui_root.setIconSize(QtCore.QSize(64, 64))
        self.ui_root.setIcon(QIcon(icons('computer.png')))
        self.ui_fs.setText("")
        self.ui_fs.setIconSize(QtCore.QSize(64, 64))
        self.ui_fs.setIcon(QIcon(icons('fs_logo.png', origin=u'fs')))

    def home_button(self):
        """
        Action home button
        """
        self.active_url = self.fs_home_url
        self.directory_history = []
        if self.fs:
            self.fs.close()
        if self.wparm is not None:
            self.wparm = None
        self.fs = fs.open_fs(self.active_url)
        self.browse_folder()
        self.selection_directory()

    def fs_button(self):
        """
        Action fs button
        """
        self.active_url = self.fs_url
        self.directory_history = []
        if self.fs:
            self.fs.close()
        if self.wparm is not None:
            self.wparm = None
        try:
            self.fs = fs.open_fs(self.active_url)
        # ToDo lookup external library why it is not e.g. OpenFailed
        except fs.errors.CreateFailed:
            logging.error(u"{} does not exist!".format(self.active_url))
            exit()
        self.browse_folder()
        self.selection_directory()

    def root_button(self):
        """
        Action root button
        """
        self.active_url = self.fs_root_url
        self.directory_history = []
        if self.fs:
            self.fs.close()
        if self.wparm is not None:
            self.wparm = None
        self.fs = fs.open_fs(self.active_url)
        self.browse_folder()
        self.selection_directory()

    def action_buttons(self):
        """
        Open / Save button action connect
        """
        try:
            self.ui_Action.clicked.connect(self.action)
        except AttributeError:
            pass

    def browse_folder(self, subdir=u"."):
        """
        list folder in drop down
        """
        if self.show_save_action:
            self.ui_Action.setEnabled(True)
        self.ui_DirList.clear()
        if subdir == u".":
            _sub_dir = self.active_url
        else:
            _sub_dir = subdir
        if len(self.directory_history) == 0:
            self.directory_history.append(_sub_dir)
        for item in reversed(self.directory_history):
            self.ui_DirList.addItem(item)
        self.ui_DirList.setCurrentIndex(self.last_dir_index)

    def selection_directory(self):
        """
        Fills the filenames based on file_type into a FileList, also directories
        """
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.selected_dir = self.ui_DirList.currentText()
        self.ui_FileList.clearContents()
        file_type = self.ui_FileType.text()
        self.file_list_items = []
        self.dir_list_items = []
        self.ui_FileList.verticalHeader().setVisible(False)
        self.ui_FileList.horizontalHeader().setVisible(True)
        self.ui_FileList.setHorizontalHeaderLabels([u'Name', u'Size', u'Modified'])
        self.ui_FileList.setShowGrid(False)
        self.ui_FileList.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.AdjustToContents)

        if self.selected_dir == self.active_url:
            _sel_dir = u"."
        else:
            _sel_dir = self.selected_dir
        # don't scan on clear
        if not _sel_dir == u"":
            try:
                for item in sorted(self.fs.listdir(_sel_dir)):
                    _item = fs.path.combine(_sel_dir, item)
                    try:
                        if not self.fs.isdir(_item) and match_extension(item, [file_type]):
                            try:
                                info = self.fs.getinfo(_item, namespaces=[u'details', u'access', u'stat'])
                            except (fs.errors.ResourceNotFound, UnicodeEncodeError):
                                info = None
                            self.file_list_items.append({_item: info})
                        elif self.fs.isdir(_item):
                            try:
                                info = self.fs.getinfo(_item, namespaces=[u'details', u'access', u'stat'])
                            except (fs.errors.ResourceNotFound, UnicodeEncodeError):
                                info = None
                            self.dir_list_items.append({_item: info})
                    except fs.errors.PermissionDenied:
                        logging.info(u"can't access {}".format(item))
            except UnicodeDecodeError as e:
                logging.error(u"Error: {}".format(e))

        self.ui_FileList.setRowCount(len(self.file_list_items) + len(self.dir_list_items))
        index = 0
        for item in self.dir_list_items:
            info = item.values()[0]
            try:
                _mod_time = info.modified.strftime(u"%Y-%m-%d %H:%M:%S")
            except TypeError:
                _mod_time = u""

            _size = u"Folder"

            self.ui_FileList.setCellWidget(index, 0, WidgetImageText(fs.path.basename(item.keys()[0]),
                                                                     self.dir_icon, item))
            self.ui_FileList.setCellWidget(index, 1, WidgetText(_size))
            self.ui_FileList.setCellWidget(index, 2, WidgetText(_mod_time))
            index = index + 1
        for item in self.file_list_items:
            info = item.values()[0]
            try:
                _mod_time = info.modified.strftime(u"%Y-%m-%d %H:%M:%S")
            except (AttributeError, TypeError):
                _mod_time = u""
            try:
                _size = unicode(humanfriendly.format_size(info.size))
            except (AttributeError, TypeError):
                _size = u""
            self.ui_FileList.setCellWidget(index, 0, WidgetImageText(fs.path.basename(item.keys()[0]),
                                                                     self.file_icon, item))
            self.ui_FileList.setCellWidget(index, 1, WidgetText(_size))
            self.ui_FileList.setCellWidget(index, 2, WidgetText(_mod_time))
            index = index + 1
        if self.last_index == 0 and not self.show_save_action:
            self.ui_FileList.clearSelection()
            if self.ui_FileList.currentItem() is not None:
                self.ui_SelectedName.setText(self.ui_FileList.currentItem().text())
        self.ui_FileList.resizeRowsToContents()
        QtWidgets.QApplication.restoreOverrideCursor()

    @QtCore.pyqtSlot(int, int)
    def onCellClicked(self, row, column):
        """
        Action for ui_FileList WidgetImageText
        :param row: position
        :param column: position
        """
        # Any cell click is always in column 0
        column = 0
        self.wparm = self.ui_FileList.cellWidget(row, column)
        if self.wparm is not None:
            if "text" in self.wparm.img:
                self.ui_SelectedName.setText(self.wparm.text)

    @QtCore.pyqtSlot(int, int)
    def onCellDoubleClicked(self, row, column):
        """
        Action for ui_FileList WidgetImageText on doubleclick
        :param row: position
        :param column: position
        """
        column = 0
        self.wparm = self.ui_FileList.cellWidget(row, column)
        try:
            if self.wparm is not None:
                if "folder" in self.wparm.img:
                    _folder_names = [name.keys()[0] for name in self.dir_list_items]
                    self.directory_history.append(self.wparm.value.keys()[0])
                    self.browse_folder(subdir=self.wparm.value.keys()[0])
        except AttributeError:
            pass

    def selection_file_type(self):
        """
        Action for line edit of file type
        """
        self.selection_directory()
        self.ui_FileList.clearSelection()
        if not self.show_save_action:
            self.ui_SelectedName.setText(None)

    def selection_name(self):
        """
        Action for filename changes, line edit text input
        """
        self.filename = self.ui_SelectedName.text()
        dirname = u'./'
        if self.wparm is not None:
            if self.wparm.value == u'./{}'.format(self.wparm.text):
                dirname = fs.path.dirname(u'./{}'.format(self.wparm.text))
            else:
                dirname = fs.path.dirname(self.wparm.value.keys()[0])
        _filename = fs.path.combine(dirname, self.filename)
        _file_names = [name.keys()[0] for name in self.file_list_items]

        if self.fs.exists(_filename) and _filename in _file_names:
            self.ui_Action.setEnabled(True)
            all_items = self.dir_list_items + _file_names
            try:
                self.ui_FileList.selectRow(all_items.index(_filename))
            except TypeError:
                pass
        else:
            if not self.show_save_action:
                self.ui_Action.setEnabled(False)
            self.ui_FileList.clearSelection()

    def show_name(self):
        """
        Action for showing clicked name as filename
        """
        try:
            self.filename = self.ui_SelectedName.text()
        except AttributeError:
            self.filename = None
        if self.filename == u"":
            self.filename = None
        self.ui_SelectedName.setText(self.filename)
        if self.fs.exists(fs.path.join(self.selected_dir, self.filename)):
            self.ui_Action.setEnabled(True)

    def cancel(self):
        """
        Action on cancel button
        """
        self.filename = None
        self.close()

    def show_action(self):
        """
        Changes the Open Button into a Save Button

        :param show_save_action: True for showing the Save dialog
        """
        if self.show_save_action:
            self.ui_SelectedName.setEnabled(True)
            self.ui_Action.setText("Save")
            if self.default_filename is not None:
                self.ui_SelectedName.setText(self.default_filename)

    def make_dir(self):
        """
        Shows the make dir dialog und creates a new directory
        """
        new_dir_name, ok = QtWidgets.QInputDialog.getText(self, u"New Folder", u"Enter a new folder name:",
                                                          QtWidgets.QLineEdit.Normal, "")

        if ok:
            if self.wparm is None:
                dirname = u''
            else:
                dirname = self.selected_dir
            new_dir = fs.path.combine(dirname, new_dir_name)
            if not self.fs.isdir(new_dir):
                self.fs.makedir(new_dir)
                self.last_dir_index = list(reversed(self.directory_history)).index(self.selected_dir)
                self.browse_folder(subdir=self.selected_dir)
            else:
                ok = QtWidgets.QMessageBox.warning(self, u"New Folder", u"Can't create this Folder: {}".format(new_dir))

    def history_top(self):
        """
        Action for top dir in history_list
        """
        self.browse_folder(self.active_url)

    def history_next(self):
        """
        Action for next dir in history_list
        """
        index = list(reversed(self.directory_history)).index(self.selected_dir) - 1
        if index >= 0:
            self.ui_DirList.setCurrentIndex(index)

    def history_previous(self):
        """
        Action for previous dir in history_list
        """
        index = list(reversed(self.directory_history)).index(self.selected_dir) + 1
        if index < len(self.directory_history):
            self.ui_DirList.setCurrentIndex(index)

    def action(self):
        """
        Action on Open / Save button
        """
        if self.show_save_action:
            self.filename = self.ui_SelectedName.text()
            if self.filename == u"":
                return
            dirname = u'./'
            if self.wparm is not None:
                if self.wparm.value == u'./{}'.format(self.wparm.text):
                    dirname = fs.path.dirname(u'./{}'.format(self.wparm.text))
                else:
                    dirname = fs.path.dirname(self.wparm.value)
            filename = fs.path.join(dirname, self.filename)
            if self.fs.isdir(filename):
                sel = QtWidgets.QMessageBox.warning(
                    self, u"Warning",
                    u"You can't create a file with this name: {0}".format(self.filename),
                    QtWidgets.QMessageBox.No)
            elif self.fs.exists(filename):
                sel = QtWidgets.QMessageBox.question(
                    self, u"Replace Filename",
                    u"This will replace the filename: {0}. Continue?".format(self.filename),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if sel == QtWidgets.QMessageBox.Yes:
                    self.close()
                else:
                    pass
            else:
                self.close()
        else:
            try:
                self.filename = self.ui_SelectedName.text()
                if self.filename == u"":
                    self.filename = None
            except AttributeError:
                pass
            else:
                self.close()


def fs_filepicker(parent=None, fs_url=u'~/', file_pattern=u'*.*', title=u'FS File Picker',
                  default_filename=None, show_save_action=False):
    """
    Selects a file by FilePicker for a given pyfilesystem2 Url.

    :param parent: parent Widget
    :param fs_url: pyfilesystem2 url
    :param file_pattern: filter pattern of pyfilesystem2
    :param title: title of QtWidget
    :return: selected filename
    """
    fp = FilePicker(parent, fs_url, file_pattern, title=title,
                    default_filename=default_filename, show_save_action=show_save_action)
    fp.setModal(True)
    fp.exec_()
    filename = None
    if fp.filename is not None:
        dirname = u'./'
        if fp.wparm is not None:
            dirname = fp.selected_dir
        if dirname.startswith(fp.active_url):
            filename = u"{}{}".format(dirname, fp.filename)
        else:
            filename = fs.path.combine(u"{}{}".format(fp.active_url, dirname), fp.filename)
    return filename


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="show version", action="store_true", default=False)
    parser.add_argument("-s", "--save", help="show save button", action="store_true", default=False)
    parser.add_argument("-d", "--default_name", help="default name for saving", default=None)
    parser.add_argument("-u", "--fs_url", help="fs url to filesystem", default=u"~/")
    parser.add_argument("-f", "--file_pattern", help="file pattern", default=u"*.*")
    parser.add_argument("-t", "--title", help="title of window", default=u'FS File Picker')

    args = parser.parse_args()
    if args.version:
        print("***********************************************************************")
        print("\n            File Picker Version \n")
        print("***********************************************************************")
        print("Version:", __version__)
        sys.exit()
    app = QtWidgets.QApplication([])

    return fs_filepicker(parent=None, fs_url=args.fs_url, file_pattern=args.file_pattern,
                         title=args.title, default_filename=args.default_name,
                         show_save_action=args.save)

if __name__ == '__main__':
    print(main())
