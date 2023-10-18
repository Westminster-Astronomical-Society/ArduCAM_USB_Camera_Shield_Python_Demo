#! /usr/bin/env python

import sys
import numpy as np

from PyQt5 import QtGui
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSpacerItem, QSizePolicy
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread

from arducam import ArducamCamera
from image_convert import convert_image, histeq, save_image

config_file = 'EK034_IMX462_RAW10_10b_long_exposure_20230906/IMX462_MIPI_2Lane_RAW10_10b_1280x720.cfg'

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        camera = ArducamCamera()
        
        if not camera.openCamera(config_file):
            raise RuntimeError("Failed to open camera.")
    
        camera.start()
        
        camera.setCtrl("setFramerate", 6000)
        camera.setCtrl("setExposureTime", 10000)
        camera.setCtrl("setGain", 800)
    
        while self._run_flag:
            ret, img_stream, cfg = camera.read()
            if ret:
                arducam_img = convert_image(img_stream, cfg, camera.color_mode)
                arducam_img =histeq(arducam_img)
                self.change_pixmap_signal.emit(arducam_img)

        # shut down camera
        camera.stop()
        camera.closeCamera()

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt ArduCam demo")
        self.disply_width = 1280
        self.display_height = 720
        
        # create the label that holds the image
        self.image_label = QLabel(self)
        self.image_label.resize(self.disply_width, self.display_height)
        
        # create a text label
        self.text_label = QLabel("ArduCam Demo")
        
        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.image_label)
        self.vbox.addWidget(self.text_label)

        # set the vbox layout as the widgets layout
        self.setLayout(self.vbox)

        # create the video capture thread
        self.thread = VideoThread()
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.update_image)
        # start the thread
        self.thread.start()

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

    @pyqtSlot(np.ndarray)
    def update_image(self, arducam_img):
        """Updates the image_label with a new opencv image"""
        
        qt_img = self.convert_cv_qt(arducam_img)
        self.image_label.setPixmap(qt_img)

    def convert_cv_qt(self, arducam_img):
        """Convert from an opencv image to QPixmap"""
        h, w, ch = arducam_img.shape
        bytes_per_line = ch * w
        qt_format = QtGui.QImage(
            arducam_img.data, w, h, bytes_per_line, QtGui.QImage.Format_BGR888
        )
        image = qt_format.scaled(
            self.disply_width, self.display_height, Qt.KeepAspectRatio
        )
        return QPixmap.fromImage(image)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
