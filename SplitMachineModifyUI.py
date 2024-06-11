"""
CustomQtDialog.py - Example of how to create a custom Qt dialog in Deadline monitor
Copyright Thinkbox Software 2016
"""

import sys

from System.IO import *
from Deadline.Scripting import *

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import PyQt5.QtCore
import PyQt5.QtWidgets
import PyQt5.QtGui
from scripts.General.u_SplitMachineModify import u_SplitMachineModify

########################################################################
# Globals
########################################################################
dialog = None

########################################################################
# Custom QDialog with some basic controls.
########################################################################


class CustomQtDialog(QDialog):

    def __init__(self, parent=None):
        super(CustomQtDialog, self).__init__(parent)

        # set the main layout as a vertical one
        self.mainLayout = QVBoxLayout()
        self.setLayout(self.mainLayout)

        binDir = RepositoryUtils.GetBinDirectory()
        randomImage = Path.Combine(binDir, "/submission/MayaVRayDBR/Main/SubmitVRay.png")

        # display an image
        self.pixMap = QPixmap(randomImage)
        self.imageLabel = QLabel()
        self.imageLabel.setPixmap(self.pixMap)
        self.mainLayout.addWidget(self.imageLabel)

        # a label to display stuff
        self.displayLabel = QLabel("This script allows you to manually run the split machine modify scripts. "
                                   "\nThese allow the split machines to run other types of jobs when there is no "
                                   "Houdini / Maya jobs on the farm."
                                   "\n\nDisable Splits: Disables render27, 33 and 34 splits, "
                                   "then adds the Nuke/Arnold/Mantra limit(s) limit to them"
                                   "\n\nEnable Splits: Enables render27, 33 and 34 splits, re-queues any jobs on them, "
                                   "then removes the Nuke/Arnold/Mantra limit(s) from them")
        self.mainLayout.addWidget(self.displayLabel)

        # this horizontal layout will contain a bunch of buttons
        self.buttonLayout = QHBoxLayout()
        self.button1 = QPushButton("Disable Splits")
        self.buttonLayout.addWidget(self.button1)

        self.button2 = QPushButton("Enable Splits")
        self.buttonLayout.addWidget(self.button2)

        self.closeButton = QPushButton("Close")
        self.buttonLayout.addWidget(self.closeButton)

        self.mainLayout.addLayout(self.buttonLayout)

        # hook up the button signals to our slots
        self.button1.clicked.connect(self.button1Pressed)
        self.button2.clicked.connect(self.button2Pressed)
        self.closeButton.clicked.connect(self.closeButtonPressed)

    @pyqtSlot(bool)
    def button1Pressed(self, checked):
        u_SplitMachineModify.disable_splits()
        self.displayLabel.setText("You disabled the splits, allowing them to render Nuke/Arnold/Mantra.")
    @pyqtSlot(bool)
    def button2Pressed(self, checked):
        u_SplitMachineModify.reset_splits()
        self.displayLabel.setText("You enabled the splits, returning them to be able to render Houdini / Maya")
    @pyqtSlot(bool)
    def closeButtonPressed(self, checked):
        self.done(0)

########################################################################
# Main Function Called By Deadline
########################################################################


def __main__():
    global dialog

    # Create an instance of our custom dialog, and show it
    dialog = CustomQtDialog()
    dialog.setVisible(True)