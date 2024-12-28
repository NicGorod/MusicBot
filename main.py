from typing import Final, List, Dict
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
# Playback flag
is_playing_flag: Dict[int, bool] = {}

# Helper function to check if a string is a URL
def is_url(string):
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?))' # domain
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, string) is not None

async def play_next(ctx):
    guild_id = ctx.guild.id

    if guild_id not in song_queue or len(song_queue[guild_id]) == 0:
        is_playing_flag[guild_id] = False
        return

    url = song_queue[guild_id][0]  # Peek at the next song in the queue
    try:
        await play_song(ctx, url)
        song_queue[guild_id].pop(0)  # Remove the song only after it starts playing
    except Exception as e:
        await ctx.send(f"An error occurred while playing the next song: {e}")
        is_playing_flag[guild_id] = False



async def play_song(ctx, url, manual_override=False):
    guild_id = ctx.guild.id

    try:
        player = await YTDLSource.from_url(url, loop=client.loop, stream=True)
        is_playing_flag[guild_id] = True

        def after_playing(error):
            if error:
                print(f"Error occurred: {error}")
            if not manual_override:  # Skip queue progression for manual playback
                asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop)

        # Start playback
        ctx.voice_client.play(player, after=after_playing)
        await ctx.send(f'Now playing: {player.title}')
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")



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
        guild_id = ctx.guild.id
        is_playing_flag[guild_id] = False

@client.command()
async def play(ctx, *, query):
    guild_id = ctx.guild.id

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

        # Stop the current song and play the requested song immediately without modifying the queue
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        await play_song(ctx, query, manual_override=True)

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")
        is_playing_flag[guild_id] = False


@client.command()
async def queue(ctx, *, query):
    guild_id = ctx.guild.id

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

        if guild_id not in song_queue:
            song_queue[guild_id] = []

        song_queue[guild_id].append(query)
        await ctx.send(f'Song added to queue. Queue position: {len(song_queue[guild_id])}')

        if not is_playing_flag.get(guild_id, False):
            await play_next(ctx)

    except Exception as e:
        await ctx.send(f"An error occurred while adding to the queue: {e}")

@client.command()
async def stop(ctx):
    guild_id = ctx.guild.id

    if guild_id in is_playing_flag:
        is_playing_flag[guild_id] = False

    if ctx.voice_client:
        ctx.voice_client.stop()
        song_queue[guild_id] = []
        await ctx.send("Stopped playing and cleared the queue.")

@client.command()
async def skip(ctx):
    guild_id = ctx.guild.id

    # Ensure the voice client exists and is playing
    if ctx.voice_client and ctx.voice_client.is_playing():
        # Stop the current playback
        ctx.voice_client.stop()

        # If there are songs in the queue, proceed to the next song
        if guild_id in song_queue and len(song_queue[guild_id]) > 0:
            await play_next(ctx)
        else:
            # If the queue is empty, set the playing flag to false
            is_playing_flag[guild_id] = False
            await ctx.send("Skipped the song. No more songs in the queue.")
    else:
        await ctx.send("No song is currently playing to skip.")


@client.command()
async def queued(ctx):
    guild_id = ctx.guild.id

    if guild_id not in song_queue or len(song_queue[guild_id]) == 0:
        await ctx.send("The queue is currently empty.")
    else:
        queue_list = "\n".join([f"{index + 1}. {url}" for index, url in enumerate(song_queue[guild_id])])
        await ctx.send(f"Current queue:\n{queue_list}")

@client.command()
async def clear(ctx):
    guild_id = ctx.guild.id

    if guild_id in song_queue:
        song_queue[guild_id] = []
    await ctx.send("The queue has been cleared.")
    is_playing_flag[guild_id] = False

@client.command()
async def pause(ctx):
    """Pause the currently playing song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the current song.")
    else:
        await ctx.send("No song is currently playing.")

@client.command()
async def resume(ctx):
    """Resume the paused song."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the current song.")
    else:
        await ctx.send("No song is currently paused.")

@client.command()
async def queue_next(ctx, *, query):
    """Add a song to the top of the queue to play after the current song."""
    guild_id = ctx.guild.id

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

        if guild_id not in song_queue:
            song_queue[guild_id] = []

        # Insert the song at the top of the queue
        song_queue[guild_id].insert(0, query)
        await ctx.send(f'Song added to the top of the queue: {query}')

    except Exception as e:
        await ctx.send(f"An error occurred while adding to the queue: {e}")


@client.command(name='help')
async def custom_help(ctx):
    help_text = """
    **Music Bot Commands:**
    !join - Bot joins the voice channel.
    !leave - Bot leaves the voice channel.
    !play <url> - Play a song immediately from a YouTube URL.
    !queue <url> - Add a song to the queue from a YouTube URL.
    !queue_next <url> -  Put given song at top of queue
    !pause - Pause the currently playing song.
    !resume - Resume the paused song.
    !skip - Skip the currently playing song and play the next in queue.
    !stop - Stop playing and clear the queue but remain in the voice channel.
    !leave - Disconnect the bot from the voice channel.
    !queued - Show the list of currently queued songs.
    !clear - Clear the queue.
    """
    await ctx.send(help_text)

# STEP 5: MAIN ENTRY POINT
def main() -> None:
    client.run(TOKEN)

if __name__ == '__main__':
    main()
