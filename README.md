# YouTube Video/Audio Downloader

A robust GUI application for downloading YouTube videos and audio using yt-dlp with PyQt5.

## Features

- Download videos and audio from YouTube
- Select between Video+Audio or Audio-only downloads
- Choose from various quality options
- Modern and responsive GUI
- Cross-platform support (especially optimized for macOS)
- TLS/SSL support for secure connections
- Real-time progress tracking
- Detailed log output

## Requirements

- Python 3.6+
- PyQt5
- yt-dlp

## Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/youtube-downloader.git
cd youtube-downloader
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install PyQt5 yt-dlp
```

## Usage

Run the application:
```bash
python youtube_down.py
```

1. Enter a YouTube URL
2. Click "Fetch Info" to get available formats
3. Choose Video+Audio or Audio-only
4. Select your preferred quality
5. Choose download folder
6. Click "DOWNLOAD"

## License

Personal use only. Not for redistribution.
