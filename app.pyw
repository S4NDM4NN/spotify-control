import sys
import yaml 
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy.util as util

from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

import ctypes
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence, QImage, QPixmap

import urllib.request

class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args)
        #print(kwargs)
        #have to prompt for this eventually...
        self.spot_user_id = kwargs['user_id']

        self.spot_scope = 'user-read-playback-state user-modify-playback-state user-read-currently-playing'

        self.spot_redirect_uri = "http://localhost:9090"
        self.spot_client_id = kwargs['client_id']
        self.spot_client_sec= kwargs['client_sec']

        self.settings = QtCore.QSettings("spot_control", "spot_control")
        self.setWindowTitle("Spot Control")
        #self.setGeometry(0, 0, 310, 300)
        self.setFixedSize(318, 400)

        #setup our icon
        icon = QIcon("icon.ico")
        self.setWindowIcon(icon)
        # stop windows from using python icon in task bar
        appid = "python.mobilepass.gui"  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)        

        self.alb_art = QLabel("album art")
        
        self.alb_art.setScaledContents(True)

        self.song_prog_label = QLabel("0:00")
        self.song_len_label = QLabel("0:00")

        self.prev_button = QPushButton()
        self.prev_button.setText("|<")
        self.next_button = QPushButton()
        self.next_button.setText(">|")
        self.paus_button = QPushButton()
        self.paus_button.setText("||")
        self.play_button = QPushButton()
        self.play_button.setText("|>")

        self.song_info = QLabel("song by artist")
        self.song_info.setAlignment(Qt.AlignCenter)
        pbar_style = """
            QProgressBar{
                background-color: LightSlateGrey;
                border: 1px solid black;
                border-radius: 5px;
                text-align: center;
                font-size: 1px;
                color: Ivory;
            }
            QProgressBar::chunk {
                background-color: DarkSlateGrey;
                width: 1px;
                margin: 0px;
            }
        """
        self.prog_bar = QProgressBar()
        self.prog_bar.setFormat("")
        self.prog_bar.setStyleSheet(pbar_style)
        self.prog_bar.mouseReleaseEvent = self.pbar_clicked
        

        self.next_button.clicked.connect(self.next_clicked)
        self.play_button.clicked.connect(self.play_clicked)
        self.paus_button.clicked.connect(self.paus_clicked)
        self.prev_button.clicked.connect(self.prev_clicked)

        self.h_layout = QHBoxLayout()
        self.con_layout = QHBoxLayout()
        self.prog_layout = QHBoxLayout()
        self.v_layout = QVBoxLayout()
        self.v_layout.setSpacing(5)
        self.v_layout.setAlignment(Qt.AlignTop) 
    
        self.main_widget = QWidget()

        #self.main_widget.setFixedWidth(319)

        
        self.con_layout.addWidget(self.prev_button)
        self.con_layout.addWidget(self.paus_button)
        self.con_layout.addWidget(self.play_button)
        self.con_layout.addWidget(self.next_button)

        self.prog_layout.addWidget(self.song_prog_label)
        self.prog_layout.addWidget(self.prog_bar)
        self.prog_layout.addWidget(self.song_len_label)  
        

        self.v_layout.addWidget(self.alb_art)
        self.v_layout.addWidget(self.song_info)
        self.v_layout.addLayout(self.con_layout)
        self.v_layout.addLayout(self.prog_layout)
        
        #self.h_layout.addLayout(self.con_layout)
        self.main_widget.setLayout(self.v_layout)
        self.setCentralWidget(self.main_widget)

        self.alb_art.adjustSize()

        #initial token update... this will be moved eventually so it can take user id before this starts...
        #self.refresh_spot_token()
        
        
        self.refresh_spot = QTimer()
        self.refresh_spot.timeout.connect(self.get_spot_status)
        self.get_spot_status()

        self.refresh_pbar = QTimer()
        self.refresh_pbar.timeout.connect(self.update_prog_info)
        self.refresh_pbar.start(1000)
        #

        # look at our settings to see if there is a setting called geometry saved.
        # Otherwise we default to an empty string
        geometry = self.settings.value("geometry", bytes("", "utf-8"))

        # restoreGeometry that will restore whatever values we give it.
        self.restoreGeometry(geometry)

    def closeEvent(self, event):
        geometry = self.saveGeometry()
        self.settings.setValue("geometry", geometry)
        super(MainWindow, self).closeEvent(event)
   
    def convert_time(self,ms):
        return f"{int((ms/(1000*60))%60):1}:{int((ms/1000)%60):02}"

    def update_prog_info(self):
        if(self.play_status):
            self.song_progress += 1000
            self.prog_bar.setMaximum(self.song_len)
            self.prog_bar.setAlignment(Qt.AlignCenter)
            self.prog_bar.setRange(0, self.song_len)
            self.prog_bar.setValue(self.song_progress)
            self.song_prog_label.setText(self.convert_time(self.song_progress))
            self.song_len_label.setText(self.convert_time(self.song_len))        


    def get_spot_status(self):
        self.refresh_spot_token()
        print("get_spot_status")
        curr_playing = self.spot.currently_playing()

        self.play_status = curr_playing['is_playing']
        self.song_title = curr_playing['item']['name']
        self.song_album = curr_playing['item']['album']['name']
        self.song_len = curr_playing['item']['duration_ms']
        self.song_progress = curr_playing['progress_ms']
        self.artist_list = ', '.join([artist['name'] for artist in curr_playing['item']['artists']])

        self.song_info.setText(f"{self.song_title} by {self.artist_list}")
        self.alb_art_url = curr_playing['item']['album']['images'][0]['url']


        if(self.play_status):
            self.play_button.hide()
            self.paus_button.show()
        else:
            self.play_button.show()
            self.paus_button.hide()

        if(int(self.song_len)-int(self.song_progress) > 10000):#refresh every 10 seconds, unless we are really close to end of song
            self.refresh_spot.start(10000)
        else:
            self.refresh_spot.start(int(self.song_len)-int(self.song_progress)+1000)

        data = urllib.request.urlopen(self.alb_art_url).read()

        image = QImage()
        image.loadFromData(data)
        self.pixmap = QPixmap(image)
        
        self.alb_art.setPixmap(self.pixmap)


    def refresh_spot_token(self):
        print("refresh_spot_token")
        self.spot_token = util.prompt_for_user_token(self.spot_user_id, self.spot_scope, 
                        client_id=self.spot_client_id,
                        client_secret=self.spot_client_sec,
                        redirect_uri=self.spot_redirect_uri)
        self.spot = spotipy.Spotify(auth=self.spot_token)
        print(f"token: {self.spot_token}")

    def pbar_clicked(self,clicked):
        print("pbar clicked...")
        self.refresh_spot_token()

        percent = .01*int(100 / self.prog_bar.width() * clicked.x())

        try:
            self.spot.seek_track(int(int(self.song_len)*percent))
        except Exception:
            pass

        QTimer.singleShot(500, self.get_spot_status)

    def play_clicked(self):
        self.refresh_spot_token()
        print("play")
        self.play_button.hide()
        self.paus_button.show()
        try:
            self.spot.start_playback()
        except Exception:
            pass
    
        QTimer.singleShot(500, self.get_spot_status)

    def paus_clicked(self):
        self.refresh_spot_token()
        print("pause")
        self.paus_button.hide()
        self.play_button.show()
        try:
            self.spot.pause_playback()
        except Exception:
            pass
        QTimer.singleShot(500, self.get_spot_status)

    def next_clicked(self):
        self.refresh_spot_token()
        print("next")
        try:
            self.spot.next_track()
        except Exception:
            pass
        QTimer.singleShot(500, self.get_spot_status)
        


    def prev_clicked(self):
        """Go to next song"""
        self.refresh_spot_token()
        print("prev")
        try:
            self.spot.previous_track()    
        except Exception:
            pass
        QTimer.singleShot(500, self.get_spot_status)




if __name__ == "__main__":

    app = QApplication(sys.argv)

    #read userid/client_id/secret from file
    with open("settings.yml", 'r') as stream:
        settings = yaml.safe_load(stream)

    window = MainWindow(None, user_id = settings['user_id'], client_id=settings['client_id'], client_sec = settings['client_sec'])
    window.show()

    sys.exit(app.exec_())