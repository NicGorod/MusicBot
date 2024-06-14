from typing import Final, List, Dict
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message
from discord.ext import commands
import discord
import yt_dlp as youtube_dl
import asyncio
from googleapiclient.discovery import build
import re

# STEP 0: LOAD OUR TOKEN FROM SOMEWHERE SAFE
load_dotenv()
TOKEN: Final[str] = 'MTI0OTE3NDMwMzM2MzAzOTI3Nw.GC0aKC.pFPeTKx64CknPeIjzhAQIQBPKAa-1PQK8y0_IE'
YOUTUBE_API_KEY: Final[str] = 'AIzaSyC8PodPvuUKdHUlabEepE7QEMabNy72_KY'

# Ensure PyNaCl is imported correctly
try:
    import nacl
except ImportError:
    print("PyNaCl library needed in order to use voice. Please install it using 'pip install pynacl'.")

# Ensure Opus is loaded
if not discord.opus.is_loaded():
    discord.opus.load_opus('/opt/homebrew/lib/libopus.0.dylib')  # Use the full path

# STEP 1: BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True
intents.voice_states = True  # Enable voice state intents for voice functionality
client: commands.Bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

# Options for yt_dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Bind to IPv4 since IPv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 1',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Queue to store songs
song_queue: Dict[int, List] = {}


# Helper function to check if a string is a URL
def is_url(string):
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ...or ipv6
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, string) is not None


# STEP 2: MESSAGE FUNCTIONALITY
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(Message was empty because intents were not enabled probably)')
        return

    if is_private := user_message[0] == '?':
        user_message = user_message[1:]

    try:
        response: str = get_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)
    except Exception as e:
        print(e)

# STEP 3: HANDLING THE STARTUP FOR OUR BOT
@client.event
async def on_ready() -> None:
    print(f'{client.user} is now running!')

# STEP 4: HANDLING INCOMING MESSAGES
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return

    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)

    print(f'[{channel}] {username}: "{user_message}"')
    await send_message(message, user_message)
    await client.process_commands(message)  # Ensure commands are processed

# Music commands
@client.command()
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel")
        return
    else:
        channel = ctx.message.author.voice.channel

    if ctx.voice_client is not None:
        return await ctx.voice_client.move_to(channel)

    await channel.connect()

@client.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()


# Function to play the next song in the queue
async def play_next(ctx):
    if ctx.guild.id not in song_queue or len(song_queue[ctx.guild.id]) == 0:
        return

    url = song_queue[ctx.guild.id].pop(0)
    await play_song(ctx, url)

async def play_song(ctx, url):
    try:
        player = await YTDLSource.from_url(url, loop=client.loop, stream=True)
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
            await ctx.send(f'Now playing: {player.title}')
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

@client.command()
async def play(ctx, *, query):
    try:
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                return

        if not is_url(query):
            # Perform a YouTube search
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            request = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                maxResults=1
            )
            response = request.execute()
            query = f"https://www.youtube.com/watch?v={response['items'][0]['id']['videoId']}"

        if ctx.guild.id not in song_queue:
            song_queue[ctx.guild.id] = []

        # Stop the current song and play the new song immediately
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop()

        # Add the new song to the front of the queue
        song_queue[ctx.guild.id].insert(0, query)
        await play_next(ctx)

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")



@client.command()
async def next(ctx, *, query):
    try:
        if not is_url(query):
            # Perform a YouTube search
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            request = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                maxResults=1
            )
            response = request.execute()
            query = f"https://www.youtube.com/watch?v={response['items'][0]['id']['videoId']}"

        if ctx.guild.id not in song_queue:
            song_queue[ctx.guild.id] = []

        song_queue[ctx.guild.id].insert(0, query)
        await ctx.send(f'Song added to the front of the queue.')

    except Exception as e:
        await ctx.send(f"An error occurred while adding to the front of the queue: {e}")


@client.command()
async def search(ctx, *, search_query):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=search_query,
            part='snippet',
            type='video',
            maxResults=1
        )
        response = request.execute()
        video_url = f"https://www.youtube.com/watch?v={response['items'][0]['id']['videoId']}"

        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                return

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            if ctx.guild.id not in song_queue:
                song_queue[ctx.guild.id] = []

            song_queue[ctx.guild.id].insert(0, video_url)
            ctx.voice_client.stop()  # This will trigger play_next(ctx)
        else:
            await play_song(ctx, video_url)

    except Exception as e:
        await ctx.send(f"An error occurred while searching: {e}")


@client.command()
async def queue_search(ctx, *, search_query):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            q=search_query,
            part='snippet',
            type='video',
            maxResults=1
        )
        response = request.execute()
        video_url = f"https://www.youtube.com/watch?v={response['items'][0]['id']['videoId']}"

        if ctx.guild.id not in song_queue:
            song_queue[ctx.guild.id] = []

        song_queue[ctx.guild.id].append(video_url)
        await ctx.send(f'Song "{response["items"][0]["snippet"]["title"]}" added to queue. Queue position: {len(song_queue[ctx.guild.id])}')

        if ctx.voice_client and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await play_next(ctx)
    except Exception as e:
        await ctx.send(f"An error occurred while searching: {e}")

@client.command()
async def queue(ctx, *, query):
    try:
        if not is_url(query):
            # Perform a YouTube search
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            request = youtube.search().list(
                q=query,
                part='snippet',
                type='video',
                maxResults=1
            )
            response = request.execute()
            query = f"https://www.youtube.com/watch?v={response['items'][0]['id']['videoId']}"

        if ctx.guild.id not in song_queue:
            song_queue[ctx.guild.id] = []

        song_queue[ctx.guild.id].append(query)
        await ctx.send(f'Song added to queue. Queue position: {len(song_queue[ctx.guild.id])}')

        if ctx.voice_client and not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await play_next(ctx)

    except Exception as e:
        await ctx.send(f"An error occurred while adding to the queue: {e}")

@client.command()
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()

@client.command()
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()

@client.command()
async def skip(ctx):
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()

@client.command()
async def stop(ctx):
    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()
        song_queue[ctx.guild.id] = []
        await ctx.send("Stopped playing and cleared the queue.")

@client.command()
async def disconnect(ctx):
    await ctx.voice_client.disconnect()

@client.command()
async def queued(ctx):
    if ctx.guild.id not in song_queue or len(song_queue[ctx.guild.id]) == 0:
        await ctx.send("The queue is currently empty.")
    else:
        queue_list = "\n".join([f"{index + 1}. {url}" for index, url in enumerate(song_queue[ctx.guild.id])])
        await ctx.send(f"Current queue:\n{queue_list}")

@client.command()
async def clear(ctx):
    if ctx.guild.id in song_queue:
        song_queue[ctx.guild.id] = []
    await ctx.send("The queue has been cleared.")

@client.command(name='help')
async def custom_help(ctx):
    help_text = """
    **Music Bot Commands:**
    `!join` - Bot joins the voice channel.
    `!leave` - Bot leaves the voice channel.
    `!play <url>` - Play a song immediately from a YouTube URL.
    `!queue <url>` - Add a song to the queue from a YouTube URL.
    `!pause` - Pause the currently playing song.
    `!resume` - Resume the paused song.
    `!skip` - Skip the currently playing song and play the next in queue.
    `!stop` - Stop playing and clear the queue but remain in the voice channel.
    `!disconnect` - Disconnect the bot from the voice channel.
    `!queued` - Show the list of currently queued songs.
    `!clear` - Clear the queue.
    """
    await ctx.send(help_text)

@play.before_invoke
@join.before_invoke
async def ensure_voice(ctx):
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You are not connected to a voice channel.")
            raise commands.CommandError("Author not connected to a voice channel.")
    elif ctx.voice_client.is_playing():
        ctx.voice_client.stop()




# STEP 5: MAIN ENTRY POINT
def main() -> None:
    client.run(TOKEN)

if __name__ == '__main__':
    main()
