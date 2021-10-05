import os
import signal
import re
import traceback
import sys
import subprocess
import io
from io import StringIO
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pytgcalls import idle as pyidle
from pytgcalls import PyTgCalls
from pytgcalls import StreamType
from pytgcalls.types.input_stream import AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio, MediumQualityAudio
from pytgcalls.types.input_stream.quality import HighQualityVideo, MediumQualityVideo, LowQualityVideo
from youtube_dl import YoutubeDL
from youtubesearchpython import VideosSearch
from time import time
from dotenv import load_dotenv
from datetime import datetime

# System Uptime
START_TIME = datetime.utcnow()
TIME_DURATION_UNITS = (
    ('Week', 60 * 60 * 24 * 7),
    ('Day', 60 * 60 * 24),
    ('Hour', 60 * 60),
    ('Min', 60),
    ('Sec', 1)
)
async def _human_time_duration(seconds):
    if seconds == 0:
        return 'inf'
    parts = []
    for unit, div in TIME_DURATION_UNITS:
        amount, seconds = divmod(int(seconds), div)
        if amount > 0:
            parts.append('{} {}{}'
                         .format(amount, unit, "" if amount == 1 else "s"))
    return ', '.join(parts)


# VPS 
if os.path.exists(".env"):
    load_dotenv(".env")

# YTDL
async def get_youtube_stream(ytlink):
        proc = await asyncio.create_subprocess_exec(
            'youtube-dl',
            '-g',
            '-f',
            # CHANGE THIS BASED ON WHAT YOU WANT
            'best[height<=?720][width<=?1280]',
            f'{ytlink}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return stdout.decode().split('\n')[0]

# TimePass 
async def aexec(code, client, m):
    c = m.chat.id
    message = m
    rm = m.reply_to_message
    if m.reply_to_message:
        id = m.reply_to_message.message_id
    else:
        id = m.message_id
    exec(
        f"async def __aexec(client, m, c, rm, message, id): "
        + "".join(f"\n {l}" for l in code.split("\n"))
    )
    return await locals()["__aexec"](client, m, c, rm, message, id)
p = print

async def bash(cmd):
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout , stderr= await process.communicate()
    return stdout.decode()

# Client and PyTgCalls
API_ID = int(os.getenv("API_ID", "6"))
API_HASH = os.getenv("API_HASH", "eb06d4abfb49dc3eeb1aeb98ae0f581e")
SESSION = os.getenv("SESSION")
CHAT = int(os.getenv("CHAT", "6"))
HNDLR = os.getenv("HNDLR", "!")

bot = Client(SESSION, API_ID, API_HASH)
self_or_contact_filter = filters.create(
    lambda _, __, message:
    (message.from_user and message.from_user.is_contact) or message.outgoing
)
call_py = PyTgCalls(bot)
GROUP_CALL = []


@bot.on_message(self_or_contact_filter & filters.command('eval', prefixes=f"{HNDLR}"))
async def evaluate(client, m: Message):
    status_message = await m.reply_text("`Running ...`")
    try:
        cmd = m.text.split(" ", maxsplit=1)[1]
    except IndexError:
        await status_message.delete()
        return
    reply_to_id = m.message_id
    if m.reply_to_message:
        reply_to_id = m.reply_to_message.message_id
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None
    try:
        await aexec(cmd, client, m)
    except Exception:
        exc = traceback.format_exc()
    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    evaluation = ""
    if exc:
        evaluation = exc
    elif stderr:
        evaluation = stderr
    elif stdout:
        evaluation = stdout
    else:
        evaluation = "Success"
    final_output = f"<b>Command:</b>\n<code>{cmd}</code>\n\n<b>Output</b>:\n<code>{evaluation.strip()}</code>"
    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as out_file:
            out_file.write(str(final_output))
        await m.reply_document(
            document=filename,
            caption=f"`Output.txt`",
            disable_notification=True,
            reply_to_message_id=reply_to_id,
        )
        os.remove(filename)
        await status_message.delete()
    else:
        await status_message.edit(final_output)
        
@bot.on_message(self_or_contact_filter & filters.command('bash', prefixes=f"{HNDLR}"))
async def terminal(client, m: Message):
    shtxt = await m.reply_text("`Processing...`")
    try: 
        cmd = m.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await shtxt.edit("`No cmd given`")
    
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    OUT = f"**☞ BASH\n\n• COMMAND:**\n`{cmd}` \n\n"
    e = stderr.decode()
    if e:
        OUT += f"**• ERROR:** \n`{e}`\n\n"
    t = stdout.decode()
    if t:
        _o = t.split("\n")
        o = "\n".join(_o)
        OUT += f"**• OUTPUT:**\n`{o}`"
    if not e and not t:
        OUT += f"**• OUTPUT:**\n`Success`"
    if len(OUT) > 4096:
        ultd = OUT.replace("`", "").replace("*", "").replace("_", "")
        with io.BytesIO(str.encode(ultd)) as out_file:
            out_file.name = "bash.txt"
            await m.reply_document(
                document=out_file,
                caption=f"`Bash.txt`",
                reply_to_message_id=m.message_id
            )
            await shtxt.delete()
    else:
        await shtxt.edit(OUT)


@bot.on_message(self_or_contact_filter & filters.command("vstream", prefixes=f"{HNDLR}"))
async def stream(client, m: Message):
   if len(m.command) < 2:
      await m.reply("`Give A Link/LiveLink/.m3u8 URL/YTLink to Stream from 🎶`")
   else:
      if len(m.command)==2:
         link = m.text.split(None, 1)[1]
         q = HighQualityVideo()
         huehue = await m.reply("`Trying to Stream 💭`")
      elif len(m.command)==3:
         op = m.text.split(None, 1)[1]
         link = op.split(None, 1)[0]
         quality = op.split(None, 1)[1]
         if quality=="720":
            q = HighQualityVideo()
         elif quality=="480":
            q = MediumQualityVideo()
         elif quality=="360":
            q = LowQualityVideo()
         else:
            q = HighQualityVideo()
            await m.reply("`Use 360/480/720`")
         huehue = await m.reply("`Trying to Stream 💭`")
      else:
         await m.reply("`!vstream {link} {720/480/360}`")
      chat_id = m.chat.id

      # Filtering out YouTube URL's
      regex = r"^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.+"
      match = re.match(regex,link)
      if match:
         try:
            livelink = await get_youtube_stream(link)
         except Exception as e:
            await huehue.edit(f"**YTDL ERROR** \n{e}")
      else:
         livelink = link
      print(livelink)

      # Playing
      if chat_id in GROUP_CALL:
         try:
            await call_py.leave_group_call(chat_id)
            await asyncio.sleep(2)
            await call_py.join_group_call(
               chat_id,
               AudioVideoPiped(
                  livelink,
                  HighQualityAudio(),
                  q
               )
            )
            await huehue.delete()
            await m.reply(f"Started [Streaming]({livelink}) in {chat_id}!", disable_web_page_preview=True)
         except Exception as ep:
            await m.reply(f"{ep}")
      else:
         try:
            await call_py.join_group_call(
               chat_id,
               AudioVideoPiped(
                  livelink,
                  HighQualityAudio(),
                  q
               )
            )
            GROUP_CALL.append(chat_id)
            await huehue.delete()
            await m.reply(f"Started [Streaming]({livelink}) in {chat_id}!", disable_web_page_preview=True)
         except Exception as ep:
            await m.reply(f"{ep}")

@bot.on_message(self_or_contact_filter & filters.command("vplay", prefixes=f"{HNDLR}"))
async def play(client, m: Message):
   replied = m.reply_to_message
   chat_id = m.chat.id
   if replied:
      if replied.document or replied.video:
         huehue = await replied.reply("`Downloading 📩`")
         location = await replied.download()
         if len(m.command) < 2:
            q = HighQualityVideo()
         else:
            pq = m.text.split(None, 1)[1]
            if pq=="720":
               q = HighQualityVideo()
            elif pq=="480":
               q = MediumQualityVideo()
            elif pq=="360":
               q = LowQualityVideo()
            else:
               q = HighQualityVideo()
               await huehue.edit("`Only 720, 480, 360 Allowed` \n`Now Streaming in 720p`")
         if chat_id in GROUP_CALL:
            try:
               await call_py.leave_group_call(chat_id)
               await asyncio.sleep(2)
               await call_py.join_group_call(
                  chat_id,
                  AudioVideoPiped(
                     location,
                     HighQualityAudio(),
                     q
                  )
               )
               await huehue.delete()
               await replied.reply(f"Started Playing in {chat_id}!", disable_web_page_preview=True)
            except Exception as ep:
               await m.reply(f"{ep}")
         else:
            try:
               await call_py.join_group_call(
                  chat_id,
                  AudioVideoPiped(
                     location,
                     HighQualityAudio(),
                     q
                  )
               )
               GROUP_CALL.append(chat_id)
               await huehue.delete()
               await replied.reply(f"Started Playing in {chat_id}!", disable_web_page_preview=True)
            except Exception as ep:
               await m.reply(f"{ep}")
      else:
         if len(m.command) < 2:
            await replied.reply("`Either Reply to a VIDEO or Give me Query/YT Link to Play`")
         else:
            try:
               query = m.text.split(None, 1)[1]
               hmmop = await m.reply("`Searching 🔎`")
               search = VideosSearch(query, limit=1)
               for result in search.result()["result"]:
                  ytid = result['id']
                  url = f"https://www.youtube.com/watch?v={ytid}"
            except Exception as ey:
               print(ey)
               await m.reply("`Found Nothing :( Try searching something Else.`")
            ytlink = await get_youtube_stream(url)
            print(ytlink)
            # Playing
            if chat_id in GROUP_CALL:
               try:
                  await call_py.leave_group_call(chat_id)
                  await asyncio.sleep(2)
                  await call_py.join_group_call(
                     chat_id,
                     AudioVideoPiped(
                        ytlink,
                        HighQualityAudio(),
                        MediumQualityVideo()
                     )
                  )
                  await hmmop.delete()
                  await m.reply(f"Started [Streaming]({ytlink}) in {chat_id}!", disable_web_page_preview=True)
               except Exception as ep:
                  await m.reply(f"{ep}")
            else:
               try:
                  await call_py.join_group_call(
                     chat_id,
                     AudioVideoPiped(
                        ytlink,
                        HighQualityAudio(),
                        MediumQualityVideo()
                     )
                  )
                  GROUP_CALL.append(chat_id)
                  await hmmop.delete()
                  await m.reply(f"Started [Streaming]({livelink}) in {chat_id}!", disable_web_page_preview=True)
               except Exception as ep:
                  await m.reply(f"{ep}")
   
   else:
         if len(m.command) < 2:
            await replied.reply("`Either Reply to a VIDEO or Give me Query/YT Link to Play`")
         else:
            try:
               query = m.text.split(None, 1)[1]
               hmmop = await m.reply("`Searching 🔎`")
               search = VideosSearch(query, limit=1)
               for result in search.result()["result"]:
                  ytid = result['id']
                  url = f"https://www.youtube.com/watch?v={ytid}"
            except Exception as ey:
               print(ey)
               await m.reply("`Found Nothing :( Try searching something Else.`")
            ytlink = await get_youtube_stream(url)
            print(ytlink)
            # Playing
            if chat_id in GROUP_CALL:
               try:
                  await call_py.leave_group_call(chat_id)
                  await asyncio.sleep(2)
                  await call_py.join_group_call(
                     chat_id,
                     AudioVideoPiped(
                        ytlink,
                        HighQualityAudio(),
                        MediumQualityVideo()
                     )
                  )
                  await hmmop.delete()
                  await m.reply(f"Started [Streaming]({ytlink}) in `{chat_id}`", disable_web_page_preview=True)
               except Exception as ep:
                  await m.reply(f"{ep}")
            else:
               try:
                  await call_py.join_group_call(
                     chat_id,
                     AudioVideoPiped(
                        ytlink,
                        HighQualityAudio(),
                        MediumQualityVideo()
                     )
                  )
                  GROUP_CALL.append(chat_id)
                  await hmmop.delete()
                  await m.reply(f"Started [Streaming]({ytlink}) in `{chat_id}`", disable_web_page_preview=True)
               except Exception as ep:
                  await m.reply(f"{ep}")

@bot.on_message(self_or_contact_filter & filters.command("vstop", prefixes=f"{HNDLR}"))
async def stop(client, m: Message):
   try:
      chat_id = m.chat.id
      if chat_id in GROUP_CALL:
         GROUP_CALL.remove(chat_id)
      else:
         pass
      await call_py.leave_group_call(chat_id)
      await m.reply("`Stopped Streaming 🍦`")
   except Exception as e:
      print(e)

@bot.on_message(self_or_contact_filter & filters.command("ping", prefixes=f"{HNDLR}"))
async def ping(client, m: Message):
   start = time()
   current_time = datetime.utcnow()
   m_reply = await m.reply_text("`...`")
   delta_ping = time() - start
   uptime_sec = (current_time - START_TIME).total_seconds()
   uptime = await _human_time_duration(int(uptime_sec))
   await m_reply.edit(f"`Pong 🏓!` `{delta_ping * 1000:.3f} ms` \n**Uptime 🤖** - `{uptime}`")

@bot.on_message(self_or_contact_filter & filters.command("killall", prefixes=f"{HNDLR}"))
async def kill(client, m: Message):   
   os.system("pkill ffmpeg")
   try:
      os.system("rm -rf downloads")
   except Exception as e:
      print(e)
   for x in GROUP_CALL:
      await call_py.leave_group_call(x)
      GROUP_CALL.remove(x)
   await m.reply("`Cleaned all the Temporary Files 🗑️ and Stopped All Processes and Left all Voice Chats`")

@bot.on_message(self_or_contact_filter & filters.command("help", prefixes=f"{HNDLR}"))
async def help(client, m: Message):
   await m.reply(f"**🛠 HELP MENU** \n\n`{HNDLR}ping` \n`{HNDLR}vplay query` \n`{HNDLR}vstream link` \n`{HNDLR}vstop` \n`{HNDLR}restart`")

@bot.on_message(self_or_contact_filter & filters.command("pause", prefixes=f"{HNDLR}"))
async def pause(client, m: Message):
   chat_id = m.chat.id
   await call_py.pause_stream(chat_id)
   await m.reply("`Paused Streaming ⏸️`")

@bot.on_message(self_or_contact_filter & filters.command("resume", prefixes=f"{HNDLR}"))
async def resume(client, m: Message):
   chat_id = m.chat.id
   await call_py.resume_stream(chat_id)
   await m.reply("`Resumed Streaming ▶`") 

@bot.on_message(self_or_contact_filter & filters.command("update", prefixes=f"{HNDLR}"))
async def update(client, m: Message):
   hmm = await bash("git pull -f")
   await m.reply(f"`{hmm}`")
   os.execl(sys.executable, "python3", "-m", "vidstream.py")

@bot.on_message(self_or_contact_filter & filters.command("restart", prefixes=f"{HNDLR}"))
async def restart(client, m: Message):
   umm = await m.reply_text("`Restarting ⚙️..`")
   try:
      asyncio.get_event_loop().create_task(os.kill(os.getpid(), signal.SIGUSR1))
   except Exception as e:
      await umm.edit(f"**An Error Occurred :-** \n`{e}`")



bot.start()
call_py.start()
pyidle()
idle()
