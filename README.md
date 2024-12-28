Made by Nicolas Gorodnitchi

Desc: Discord bot for playing music off of youtube

Current functionalities: 
-Direct play using youtube links or search using Google API
-queue functionality, play next in queue
-full stop and wipe, pause, resume
-Can overide something playing and maintain a queue

# Known bugs: 
None at the moment

# Next steps:
1. Add soundcloud functionality if demand found

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
Extract the files and add the bin directory to your system's PATH environment variable. Adjust code to point to it
