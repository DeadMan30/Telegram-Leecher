# copyright 2023 © Xron Trix | https://github.com/Xrontrix10

import logging
import yt_dlp
from asyncio import sleep
from threading import Thread
from os import makedirs, path as ospath
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import YTDL, MSG, Messages, Paths
from colab_leecher.utility.helper import getTime, keyboard, sizeUnit, status_bar, sysINFO

# Fetch available formats for a given URL
def get_video_formats(url):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'listformats': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
    return formats

# Create inline keyboard buttons for video quality selection
def create_quality_buttons(formats):
    keyboard = []
    
    for f in formats:
        quality = f.get('format_note', 'Unknown')
        button_text = f"{quality} ({f.get('height', 'N/A')}p)"
        callback_data = f"{f.get('format_id')}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(keyboard)

async def YTDL_Status(link, num):
    global Messages, YTDL
    name = await get_YT_Name(link)
    Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

    YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link,))
    YTDL_Thread.start()

    while YTDL_Thread.is_alive():  # Until ytdl is downloading
        if YTDL.header:
            sys_text = sysINFO()
            message = YTDL.header
            try:
                await MSG.status_msg.edit_text(text=Messages.task_msg + Messages.status_head + message + sys_text, reply_markup=keyboard())
            except Exception:
                pass
        else:
            try:
                await status_bar(
                    down_msg=Messages.status_head,
                    speed=YTDL.speed,
                    percentage=float(YTDL.percentage),
                    eta=YTDL.eta,
                    done=YTDL.done,
                    left=YTDL.left,
                    engine="Xr-YtDL 🏮",
                )
            except Exception:
                pass

        await sleep(2.5)

class MyLogger:
    def __init__(self):
        pass

    def debug(self, msg):
        global YTDL
        if "item" in str(msg):
            msgs = msg.split(" ")
            YTDL.header = f"\n⏳ __Getting Video Information {msgs[-3]} of {msgs[-1]}__"

    @staticmethod
    def warning(msg):
        pass

    @staticmethod
    def error(msg):
        # if msg != "ERROR: Cancelling...":
        # print(msg)
        pass

def YouTubeDL(url, format_id=None):
    global YTDL

    def my_hook(d):
        global YTDL

        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes", 0)
            dl_bytes = d.get("downloaded_bytes", 0)
            percent = d.get("downloaded_percent", 0)
            speed = d.get("speed", "N/A")
            eta = d.get("eta", 0)

            if total_bytes:
                percent = round((float(dl_bytes) * 100 / float(total_bytes)), 2)

            YTDL.header = ""
            YTDL.speed = sizeUnit(speed) if speed else "N/A"
            YTDL.percentage = percent
            YTDL.eta = getTime(eta) if eta else "N/A"
            YTDL.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
            YTDL.left = sizeUnit(total_bytes) if total_bytes else "N/A"

        elif d["status"] == "downloading fragment":
            pass
        else:
            logging.info(d)

    ydl_opts = {
        "format": format_id or "best",
        "allow_multiple_video_streams": True,
        "allow_multiple_audio_streams": True,
        "writethumbnail": True,
        "--concurrent-fragments": 4,
        "allow_playlist_files": True,
        "overwrites": True,
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
        "progress_hooks": [my_hook],
        "writesubtitles": "srt",
        "extractor_args": {"subtitlesformat": "srt"},
        "logger": MyLogger(),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if not ospath.exists(Paths.thumbnail_ytdl):
            makedirs(Paths.thumbnail_ytdl)
        try:
            info_dict = ydl.extract_info(url, download=False)
            YTDL.header = "⌛ __Please WAIT a bit...__"
            if "_type" in info_dict and info_dict["_type"] == "playlist":
                playlist_name = info_dict["title"]
                if not ospath.exists(ospath.join(Paths.down_path, playlist_name)):
                    makedirs(ospath.join(Paths.down_path, playlist_name))
                ydl_opts["outtmpl"] = {
                    "default": f"{Paths.down_path}/{playlist_name}/%(title)s.%(ext)s",
                    "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                }
                for entry in info_dict["entries"]:
                    video_url = entry["webpage_url"]
                    try:
                        ydl.download([video_url])
                    except yt_dlp.utils.DownloadError as e:
                        if e.exc_info[0] == 36:
                            ydl_opts["outtmpl"] = {
                                "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                                "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                            }
                            ydl.download([video_url])
            else:
                YTDL.header = ""
                ydl_opts["outtmpl"] = {
                    "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                    "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                }
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as e:
                    if e.exc_info[0] == 36:
                        ydl_opts["outtmpl"] = {
                            "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                            "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                        }
                        ydl.download([url])
        except Exception as e:
            logging.error(f"YTDL ERROR: {e}")

async def get_YT_Name(link):
    with yt_dlp.YoutubeDL({"logger": MyLogger()}) as ydl:
        try:
            info = ydl.extract_info(link, download=False)
            if "title" in info and info["title"]: 
                return info["title"]
            else:
                return "UNKNOWN DOWNLOAD NAME"
        except Exception as e:
            await cancelTask(f"Can't Download from this link. Because: {str(e)}")
            return "UNKNOWN DOWNLOAD NAME"

# Pyrogram handler functions
async def start(link):
    formats = get_video_formats(link)
    buttons = create_quality_buttons(formats)
    await message.reply_text('Choose video quality:', reply_markup=buttons, quote=True)

async def handle_quality_selection(callback_query):
    url = callback_query.message.reply_to_message.text.split('URL: ')[-1]
    format_id = callback_query.data
    
    formats = get_video_formats(url)
    format_to_download = next(f for f in formats if f.get('format_id') == format_id)
    
    YouTubeDL(link, format_id=format_id)
    
    await callback_query.answer()
    await callback_query.message.reply_text("Download complete!")
