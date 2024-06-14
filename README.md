Made by Nicolas Gorodnitchi

Desc: discord bot for playing music off of youtube

Current functionalities: Direct play using youtube links, full stack dt queue functionality, full stop and wipe, search instead of url

# Known bugs: 
if something is playing and something is queued then when !play is called nothing plays, queue remains but the program is deadlocked and does not quit gracefully


# Next steps:
1. Fix bugs
2. Swap url play and search
3. Add soundcloud functionality


# Dependecies and installation commands:
Install discord.py: 
pip install discord.py

Install yt-dlp: 
pip install yt-dlp

Install PyNaCl: 
pip install pynacl

Install python-dotenv: 
pip install python-dotenv

Install google api:
pip install google-api-python-client
or
python3 -m pip install -U google-api-python-client

# Install ffmpeg

On macOS: brew install ffmpeg

On Ubuntu Linux: 
sudo apt update
sudo apt install ffmpeg

On windows:
Download the FFmpeg build from FFmpeg's official site.
Extract the files and add the bin directory to your system's PATH environment variable.
