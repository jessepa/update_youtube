#!/usr/bin/env python3
"""
YouTube Video/Audio Downloader GUI - PyQt5 Version
A robust GUI application for downloading YouTube videos and audio using yt-dlp.
Uses PyQt5 for reliable cross-platform support, especially on macOS.
"""

import os
import sys
import warnings

# Suppress warnings
os.environ['TK_SILENCE_DEPRECATION'] = '1'
warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QLineEdit, QPushButton, 
                            QRadioButton, QButtonGroup, QListWidget, QTextEdit, 
                            QFileDialog, QMessageBox, QGroupBox, QProgressBar,
                            QSplitter, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor
import threading
import queue
import json
import ssl
import urllib.request
from pathlib import Path
import yt_dlp
import re


class VideoInfoThread(QThread):
    """Thread for fetching video information"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, url, ydl_opts):
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts
    
    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                
                if info is None:
                    self.error.emit("Failed to extract video information")
                    return
                
                # Process formats
                formats = info.get('formats', [])
                video_formats = []
                audio_formats = []
                
                for fmt in formats:
                    if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                        height = fmt.get('height', 0)
                        fps = fmt.get('fps', 0)
                        ext = fmt.get('ext', 'unknown')
                        filesize = fmt.get('filesize')
                        size_str = f" (~{filesize // (1024*1024)}MB)" if filesize else ""
                        
                        if height:
                            quality_str = f"{height}p"
                            if fps and fps > 30:
                                quality_str += f"{fps}"
                            quality_str += f" ({ext}){size_str}"
                            video_formats.append((quality_str, fmt['format_id'], fmt))
                    
                    elif fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                        abr = fmt.get('abr', 0)
                        ext = fmt.get('ext', 'unknown')
                        filesize = fmt.get('filesize')
                        size_str = f" (~{filesize // (1024*1024)}MB)" if filesize else ""
                        
                        if abr:
                            quality_str = f"{int(abr)}kbps ({ext}){size_str}"
                            audio_formats.append((quality_str, fmt['format_id'], fmt))
                
                # Sort formats
                video_formats.sort(key=lambda x: x[2].get('height', 0), reverse=True)
                audio_formats.sort(key=lambda x: x[2].get('abr', 0), reverse=True)
                
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
                
                result = {
                    'title': title,
                    'duration': duration_str,
                    'video_formats': video_formats,
                    'audio_formats': audio_formats
                }
                
                self.finished.emit(result)
                
        except Exception as e:
            self.error.emit(f"Error fetching video info: {str(e)}")


class DownloadThread(QThread):
    """Thread for downloading videos"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, url, save_path, ydl_opts):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.ydl_opts = ydl_opts
    
    def progress_hook(self, d):
        """Progress hook for yt-dlp"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            self.progress.emit(f"Downloading... {percent} at {speed}")
        elif d['status'] == 'finished':
            self.progress.emit(f"Download finished: {os.path.basename(d['filename'])}")
    
    def run(self):
        try:
            self.ydl_opts['progress_hooks'] = [self.progress_hook]
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit("Download completed successfully!")
        except Exception as e:
            self.error.emit(f"Download failed: {str(e)}")


class YouTubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Video/Audio Downloader")
        self.setGeometry(100, 100, 1000, 800)
        
        # Configure SSL context for TLS
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Variables
        self.video_formats = []
        self.audio_formats = []
        self.video_thread = None
        self.download_thread = None
        
        self.setup_yt_dlp()
        self.init_ui()
        self.apply_styles()
    
    def setup_yt_dlp(self):
        """Configure yt-dlp with TLS settings"""
        self.ydl_opts_base = {
            'no_warnings': False,
            'extract_flat': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': True,
            'ssl_context': self.ssl_context,
            'quiet': True,
        }
    
    def init_ui(self):
        """Initialize the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("🎬 YouTube Video/Audio Downloader")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # URL input section
        url_group = QGroupBox("YouTube URL")
        url_layout = QVBoxLayout(url_group)
        
        url_input_layout = QHBoxLayout()
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter YouTube URL here...")
        self.url_entry.setMinimumHeight(35)
        url_input_layout.addWidget(self.url_entry)
        
        self.fetch_btn = QPushButton("Fetch Info")
        self.fetch_btn.setMinimumHeight(35)
        self.fetch_btn.setMinimumWidth(120)
        self.fetch_btn.clicked.connect(self.fetch_video_info)
        url_input_layout.addWidget(self.fetch_btn)
        
        url_layout.addLayout(url_input_layout)
        main_layout.addWidget(url_group)
        
        # Download type selection
        type_group = QGroupBox("Download Type")
        type_layout = QHBoxLayout(type_group)
        
        self.download_type_group = QButtonGroup()
        self.radio_video = QRadioButton("🎬 Video + Audio")
        self.radio_audio = QRadioButton("🎵 Audio Only")
        self.radio_video.setChecked(True)
        
        self.download_type_group.addButton(self.radio_video, 0)
        self.download_type_group.addButton(self.radio_audio, 1)
        
        type_layout.addWidget(self.radio_video)
        type_layout.addWidget(self.radio_audio)
        type_layout.addStretch()
        
        main_layout.addWidget(type_group)
        
        # Format selection section
        format_splitter = QSplitter(Qt.Horizontal)
        
        # Video formats
        video_group = QGroupBox("🎥 Video Quality")
        video_layout = QVBoxLayout(video_group)
        self.video_list = QListWidget()
        self.video_list.setMinimumHeight(200)
        video_layout.addWidget(self.video_list)
        format_splitter.addWidget(video_group)
        
        # Audio formats
        audio_group = QGroupBox("🔊 Audio Quality")
        audio_layout = QVBoxLayout(audio_group)
        self.audio_list = QListWidget()
        self.audio_list.setMinimumHeight(200)
        audio_layout.addWidget(self.audio_list)
        format_splitter.addWidget(audio_group)
        
        main_layout.addWidget(format_splitter)
        
        # Save location
        save_group = QGroupBox("💾 Save Location")
        save_layout = QHBoxLayout(save_group)
        
        self.save_entry = QLineEdit()
        self.save_entry.setText(str(Path.home() / "Downloads"))
        self.save_entry.setReadOnly(True)
        self.save_entry.setMinimumHeight(35)
        save_layout.addWidget(self.save_entry)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setMinimumHeight(35)
        self.browse_btn.setMinimumWidth(120)
        self.browse_btn.clicked.connect(self.browse_folder)
        save_layout.addWidget(self.browse_btn)
        
        main_layout.addWidget(save_group)
        
        # Download section
        download_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("📥 DOWNLOAD")
        self.download_btn.setMinimumHeight(50)
        self.download_btn.setMinimumWidth(200)
        download_font = QFont()
        download_font.setPointSize(14)
        download_font.setBold(True)
        self.download_btn.setFont(download_font)
        self.download_btn.clicked.connect(self.start_download)
        download_layout.addWidget(self.download_btn)
        
        # Status section
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Ready")
        status_font = QFont()
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        status_layout.addWidget(self.status_label)
        
        self.progress_label = QLabel("")
        status_layout.addWidget(self.progress_label)
        status_layout.addStretch()
        
        download_layout.addLayout(status_layout)
        download_layout.addStretch()
        
        main_layout.addLayout(download_layout)
        
        # Log output
        log_group = QGroupBox("📋 Log Output")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        log_font = QFont("Courier")
        log_font.setPointSize(10)
        self.log_text.setFont(log_font)
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
    
    def apply_styles(self):
        """Apply modern styling to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: #f5f5f5;
            }
            QLineEdit {
                border: 2px solid #cccccc;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QListWidget {
                border: 2px solid #cccccc;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #0078d4;
                font-size: 11px;
            }
            QTextEdit {
                border: 2px solid #cccccc;
                border-radius: 6px;
                background-color: white;
                font-family: 'Courier New', monospace;
            }
            QRadioButton {
                font-size: 12px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #cccccc;
                border-radius: 8px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #0078d4;
                border-radius: 8px;
                background-color: #0078d4;
            }
        """)
    
    def log_message(self, message):
        """Add message to log output"""
        self.log_text.append(message)
        self.log_text.ensureCursorVisible()
    
    def validate_url(self, url):
        """Validate YouTube URL"""
        youtube_patterns = [
            r'(?:https?://)(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)(?:www\.)?youtube\.com/v/[\w-]+',
        ]
        
        for pattern in youtube_patterns:
            if re.match(pattern, url):
                return True
        return False
    
    def fetch_video_info(self):
        """Fetch video information and available formats"""
        url = self.url_entry.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a YouTube URL")
            return
        
        if not self.validate_url(url):
            QMessageBox.warning(self, "Error", "Please enter a valid YouTube URL")
            return
        
        self.fetch_btn.setEnabled(False)
        self.status_label.setText("Fetching video information...")
        self.progress_label.setText("Working...")
        
        # Clear previous formats
        self.video_list.clear()
        self.audio_list.clear()
        self.video_formats.clear()
        self.audio_formats.clear()
        
        # Start video info thread
        self.video_thread = VideoInfoThread(url, self.ydl_opts_base.copy())
        self.video_thread.finished.connect(self.on_video_info_received)
        self.video_thread.error.connect(self.on_video_info_error)
        self.video_thread.start()
    
    def on_video_info_received(self, info):
        """Handle received video information"""
        self.fetch_btn.setEnabled(True)
        self.status_label.setText("Video info fetched")
        self.progress_label.setText("Ready")
        
        self.log_message(f"Title: {info['title']}")
        self.log_message(f"Duration: {info['duration']}")
        
        # Store formats
        self.video_formats = info['video_formats']
        self.audio_formats = info['audio_formats']
        
        # Populate lists
        for quality, format_id, fmt in self.video_formats:
            self.video_list.addItem(quality)
        
        for quality, format_id, fmt in self.audio_formats:
            self.audio_list.addItem(quality)
        
        # Select first items
        if self.video_list.count() > 0:
            self.video_list.setCurrentRow(0)
        if self.audio_list.count() > 0:
            self.audio_list.setCurrentRow(0)
        
        self.download_btn.setEnabled(True)
    
    def on_video_info_error(self, error_msg):
        """Handle video info error"""
        self.fetch_btn.setEnabled(True)
        self.status_label.setText("Error")
        self.progress_label.setText("")
        self.log_message(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Error", error_msg)
    
    def browse_folder(self):
        """Open folder browser dialog"""
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", 
                                                 self.save_entry.text())
        if folder:
            self.save_entry.setText(folder)
    
    def start_download(self):
        """Start the download process"""
        url = self.url_entry.text().strip()
        save_path = self.save_entry.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a YouTube URL")
            return
        
        if not save_path or not os.path.exists(save_path):
            QMessageBox.warning(self, "Error", "Please select a valid save location")
            return
        
        # Get selected formats
        video_row = self.video_list.currentRow()
        audio_row = self.audio_list.currentRow()
        
        if self.radio_video.isChecked():
            if video_row < 0:
                QMessageBox.warning(self, "Error", "Please select a video quality")
                return
            if audio_row < 0:
                QMessageBox.warning(self, "Error", "Please select an audio quality")
                return
        else:
            if audio_row < 0:
                QMessageBox.warning(self, "Error", "Please select an audio quality")
                return
        
        # Prepare download options
        ydl_opts = self.ydl_opts_base.copy()
        ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s.%(ext)s')
        
        if self.radio_video.isChecked():
            # Download video + audio
            video_format_id = self.video_formats[video_row][1]
            audio_format_id = self.audio_formats[audio_row][1]
            ydl_opts['format'] = f"{video_format_id}+{audio_format_id}/best"
            ydl_opts['merge_output_format'] = 'mp4'
        else:
            # Download audio only
            audio_format_id = self.audio_formats[audio_row][1]
            ydl_opts['format'] = audio_format_id
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        self.download_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.status_label.setText("Downloading...")
        self.progress_label.setText("Starting download...")
        
        # Start download thread
        self.download_thread = DownloadThread(url, save_path, ydl_opts)
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.error.connect(self.on_download_error)
        self.download_thread.start()
    
    def on_download_progress(self, message):
        """Handle download progress updates"""
        self.progress_label.setText(message)
        self.log_message(message)
    
    def on_download_finished(self, message):
        """Handle download completion"""
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.status_label.setText("Download completed")
        self.progress_label.setText("Done")
        self.log_message(message)
        QMessageBox.information(self, "Success", message)
    
    def on_download_error(self, error_msg):
        """Handle download error"""
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.status_label.setText("Download failed")
        self.progress_label.setText("Failed")
        self.log_message(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Download Error", error_msg)


def main():
    """Main function to run the application"""
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Downloader")
    app.setOrganizationName("YouTube Downloader")
    
    # Set application style
    app.setStyle('Fusion')
    
    window = YouTubeDownloader()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
