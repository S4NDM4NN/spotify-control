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
    QSlider,
)


from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence, QImage, QPixmap

import urllib.request

class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args)

        #settings from settings.yml
        self.spot_user_id = kwargs['user_id']
        self.spot_client_id = kwargs['client_id']
        self.spot_client_sec= kwargs['client_sec']

        #needed for spotipy
        self.spot_scope = 'user-read-playback-state user-modify-playback-state user-read-currently-playing'
        self.spot_redirect_uri = "http://localhost:9090"

        #Settings for spotify_control app
        self.settings = QtCore.QSettings("spotify_control", "spotify_control")
        #Set window title
        self.setWindowTitle("Spotify Control")

        #set a fixed size
        self.setFixedSize(318, 400)

        #setup our icon
        icon = QIcon("icon.ico")
        self.setWindowIcon(icon)
        # stop windows from using python icon in task bar
        if(sys.platform == "win32"):
            import ctypes
            appid = "python.spotify_control.gui"  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)        

        #create alb_art object
        self.alb_art = QLabel("album art")
        self.alb_art.setScaledContents(True)

        #song progress/length
        self.song_prog_label = QLabel("0:00")
        self.song_len_label = QLabel("0:00")

        #buttons
        self.prev_button = QPushButton()
        self.prev_button.setText("|<")
        self.next_button = QPushButton()
        self.next_button.setText(">|")
        self.paus_button = QPushButton()
        self.paus_button.setText("||")
        self.play_button = QPushButton()
        self.play_button.setText("|>")

        self.next_button.clicked.connect(self.next_clicked)
        self.play_button.clicked.connect(self.play_clicked)
        self.paus_button.clicked.connect(self.paus_clicked)
        self.prev_button.clicked.connect(self.prev_clicked)        

        #song metadata field
        self.song_info = QLabel("song by artist")
        self.song_info.setAlignment(Qt.AlignCenter)
        
        #slider progress bar..
        slide_style = """
            QSlider::groove:horizontal {
            border: 1px solid #bbb;
            background: white;
            height: 10px;
            border-radius: 4px;
            }

            QSlider::sub-page:horizontal {
            background: LightSlateGrey;
            border: 1px solid #777;
            height: 10px;
            border-radius: 4px;
            }

            QSlider::add-page:horizontal {
            background: #fff;
            border: 1px solid #777;
            height: 10px;
            border-radius: 4px;
            }

            QSlider::handle:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #eee, stop:1 #ccc);
            border: 1px solid #777;
            width: 5px;
            margin-top: -2px;
            margin-bottom: -2px;
            border-radius: 2px;
            }

            QSlider::handle:horizontal:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #fff, stop:1 #ddd);
            border: 1px solid #444;
            border-radius: 2px;
            }

            QSlider::sub-page:horizontal:disabled {
            background: #bbb;
            border-color: #999;
            }

            QSlider::add-page:horizontal:disabled {
            background: #eee;
            border-color: #999;
            }

            QSlider::handle:horizontal:disabled {
            background: #eee;
            border: 1px solid #aaa;
            border-radius: 4px;
            }
        """
        self.prog_slide = QSlider(Qt.Horizontal)
        self.prog_slide.setStyleSheet(slide_style)
        self.prog_slide.sliderReleased.connect(self.prog_slide_released)
        self.prog_slide.mouseReleaseEvent = self.prog_slide_clicked

        #parent of all layouts
        self.main_widget = QWidget()

        #main verticle layout for app
        self.v_layout = QVBoxLayout()
        self.v_layout.setSpacing(5)
        self.v_layout.setAlignment(Qt.AlignTop) 

        #controls layout
        self.con_layout = QHBoxLayout()
        #progress info layout
        self.prog_layout = QHBoxLayout()

        #add buttons to my controller layout
        self.con_layout.addWidget(self.prev_button)
        self.con_layout.addWidget(self.paus_button)
        self.con_layout.addWidget(self.play_button)
        self.con_layout.addWidget(self.next_button)

        #add progress info to progress layout
        self.prog_layout.addWidget(self.song_prog_label)
        self.prog_layout.addWidget(self.prog_slide)
        self.prog_layout.addWidget(self.song_len_label)  
        
        #build the verticle layout
        #album art at top
        self.v_layout.addWidget(self.alb_art)
        #song info next
        self.v_layout.addWidget(self.song_info)
        #control panel layout
        self.v_layout.addLayout(self.con_layout)
        #progress info layout
        self.v_layout.addLayout(self.prog_layout)
        #self.v_layout.addWidget(self.prog_bar)
        
        #add layout to make widget
        self.main_widget.setLayout(self.v_layout)
        self.setCentralWidget(self.main_widget)
       
        #setup timer for updating the spotify status
        self.refresh_spot = QTimer()
        self.refresh_spot.timeout.connect(self.get_spot_status)
        self.get_spot_status()

        #setup a timer to update the progress bar
        self.refres_pslide = QTimer()
        self.refres_pslide.timeout.connect(self.update_prog_info)
        self.refres_pslide.start(1000)
        

        # look at our settings to see if there is a setting called geometry saved.
        # Otherwise we default to an empty string
        geometry = self.settings.value("geometry", bytes("", "utf-8"))

        # restoreGeometry that will restore whatever values we give it.
        self.restoreGeometry(geometry)
    
    #when app is closed
    def closeEvent(self, event):
        #save geometry settings to open app in same screen space next launch
        geometry = self.saveGeometry()
        self.settings.setValue("geometry", geometry)
        super(MainWindow, self).closeEvent(event)
    
    #converts ms to 0:00 format
    def convert_time(self,ms):
        return f"{int((ms/(1000*60))%60):1}:{int((ms/1000)%60):02}"

    #used to update the progress bar as the song plays
    def update_prog_info(self):
        if(self.play_status):
            self.song_progress += 1000
            self.song_prog_label.setText(self.convert_time(self.song_progress))
            self.song_len_label.setText(self.convert_time(self.song_len))
            self.prog_slide.setValue(self.song_progress)
            self.prog_slide.setMaximum(self.song_len)


    def prog_slide_released(self):
        print("prog_slider_released")

        self.refresh_spot_token()
        try:
            self.spot.seek_track(self.prog_slide.value())
        except Exception:
            pass

        self.song_progress = self.prog_slide.value()

    #progress slider was clicked
    def prog_slide_clicked(self,clicked):
        print("pslide clicked...")
        
        self.refresh_spot_token()
        #calculate song percentage
        percent = .01*int(100 / self.prog_slide.width() * clicked.x())
        #use percentage to find where to seek to
        seek_to = int(int(self.song_len)*percent)
        #send seek to spotify
        try:
            self.spot.seek_track(seek_to)
        except Exception:
            pass

        #visually move progress bar
        self.prog_slide.setValue(seek_to)
        self.song_progress = seek_to    

    #get spotify status - metadata etc
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

        #if the song is paused in the player itsself, update our gui
        if(self.play_status):
            self.play_button.hide()
            self.paus_button.show()
        else:
            self.play_button.show()
            self.paus_button.hide()

        #refresh every 10 seconds, unless 10 seconds is going to go over the song time
        if(int(self.song_len)-int(self.song_progress) > 10000):#refresh every 10 seconds, unless we are really close to end of song
            self.refresh_spot.start(10000)
        else:
            self.refresh_spot.start(int(self.song_len)-int(self.song_progress)+1000)

        #update album art 
        data = urllib.request.urlopen(self.alb_art_url).read()
        image = QImage()
        image.loadFromData(data)
        self.pixmap = QPixmap(image)
        self.alb_art.setPixmap(self.pixmap)

    #refresh spotify api access token
    def refresh_spot_token(self):
        print("refresh_spot_token")
        self.spot_token = util.prompt_for_user_token(self.spot_user_id, self.spot_scope, 
                        client_id=self.spot_client_id,
                        client_secret=self.spot_client_sec,
                        redirect_uri=self.spot_redirect_uri)
        self.spot = spotipy.Spotify(auth=self.spot_token)
        print(f"token: {self.spot_token}")

    #action when play button is clicked
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
    
    #action when pause button is clicked
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

    #action when next button is clicked
    def next_clicked(self):
        self.refresh_spot_token()
        print("next")
        try:
            self.spot.next_track()
        except Exception:
            pass
        QTimer.singleShot(500, self.get_spot_status)
        
    #action when prev button is clicked
    def prev_clicked(self):
        self.refresh_spot_token()
        print("prev")
        try:
            self.spot.previous_track()    
        except Exception:
            pass
        QTimer.singleShot(500, self.get_spot_status)


#kick off the app
if __name__ == "__main__":
    app = QApplication(sys.argv)
    #read userid/client_id/secret from file
    with open("settings.yml", 'r') as stream:
        settings = yaml.safe_load(stream)

    window = MainWindow(None, user_id = settings['user_id'], client_id=settings['client_id'], client_sec = settings['client_sec'])
    window.show()
    sys.exit(app.exec_())