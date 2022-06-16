import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from discord.voice_client import VoiceClient
from random import choice
import yt_dlp
import asyncio

load_dotenv()
yt_dlp.utils.bug_reports_message = lambda: ''
ydl_opts = {
    'format': 'm4a/bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address':
    '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    # 'ffmpeg_location': 'ffmpeg\bin\ffmpeg.exe',
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
    }]
}

ffmpeg_options = {'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(ydl_opts)


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
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

def is_connected(ctx):
    voice_client = ctx.message.guild.voice_client
    return voice_client and voice_client.is_connected()


client = commands.Bot(command_prefix='!')
queue = []
loop = False
status = 'Online'


@client.event
async def on_ready():
    change_status.start()
    print('Bot is online!')


@client.command(name='ping', help='This command returns the latency')
async def ping(ctx):
    await ctx.send(f'**Pong!** Latency: {round(client.latency * 1000)}ms')


@client.command(name='join',
             help='This command makes the bot join the voice channel')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel")
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()


@client.command(name='leave',
             help='This command makes the bot leave the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("The bot is not connected to a voice channel.")


@client.command(name='loop', help='This command toggles loop mode')
async def loop_(ctx):
    global loop

    if loop:
        await ctx.send('Loop mode is now `False!`')
        loop = False
    
    else: 
        await ctx.send('Loop mode is now `True!`')
        loop = True


@client.command(name='play', help='This command plays music')
async def play(ctx):
    global queue

    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel")
        return
    
    elif len(queue) == 0:
        await ctx.send('Nothing in your queue! Use `?queue` to add a song!')

    else:
        try:
            channel = ctx.message.author.voice.channel
            await channel.connect()
        except: 
            pass

    server = ctx.message.guild
    voice_channel = server.voice_client
    while queue:
        try:
            while voice_channel.is_playing() or voice_channel.is_paused():
                await asyncio.sleep(2)
                pass

        except AttributeError:
            pass
        
        try:
            async with ctx.typing():
                player = await YTDLSource.from_url(queue[0], loop=client.loop)
                voice_channel.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                
                if loop:
                    queue.append(queue[0])

                del(queue[0])
                
            await ctx.send('**Now playing:** {}'.format(player.title))

        except:
            break


@client.command(name='volume', help='This command changes the bot\'s volume')
async def volume(ctx, volume: int):
    if ctx.voice_client is None:
        return await ctx.send("Not connected to a voice channel.")

    ctx.voice_client.source.volume = volume / 100
    await ctx.send(f"Changed volume to {volume}%")


@client.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("The bot is not playing anything at the moment.")


@client.command(name='resume', help='This command resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send(
            "The bot was not playing anything before this. Use the play command"
        )


@client.command(name='stop', help='This command stops the song')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    else:
        await ctx.send("The bot is not playing anything at the moment.")


@client.command(name='add', help='This command adds a song to the queue')
async def add(ctx, *, url):
    global queue

    queue.append(url)
    await ctx.send(f'`{url}` added to queue!')


@client.command(name='remove', help='This command removes a song from the queue')
async def remove(ctx, number):
    global queue

    try:
        del (queue[int(number)])
        await ctx.send(f'The queue is now `{queue}!`')

    except:
        await ctx.send(
            'The queue is either **empty** or the index is **out of range**')


@client.command(name='queue', help='This command shows the queue')
async def queue_(ctx):
    await ctx.send(f'The queue is now `{queue}!`')


@client.command(name='skip', help='This command skips the current song')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send('Skipped the current song!')
        play()
    else:
        await ctx.send("The bot is not playing anything at the moment.")


@tasks.loop(seconds=20)
async def change_status():
    await client.change_presence(activity=discord.Game(status))


client.run(os.getenv("TOKEN"))
