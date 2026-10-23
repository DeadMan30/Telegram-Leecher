# copyright 2023 © Xron Trix | https://github.com/Xrontrix10


import os
import json
import GPUtil
import shutil
import logging
import subprocess
from asyncio import sleep
from threading import Thread
from datetime import datetime
from os import makedirs, path as ospath
from colab_leecher.utility.variables import BOT, MSG, BotTimes, Paths, Messages
from colab_leecher.utility.helper import (
    fit_caption,
    getSize,
    fileType,
    keyboard,
    multipartArchive,
    sizeUnit,
    speedETA,
    status_bar,
    sysINFO,
    getTime,
)
from colab_leecher.utility.splitter import split_by_bytes


# telegram bot api limit per file
MAX_UPLOAD_SIZE = 2097152000


async def videoConverter(file: str):
    global BOT, MSG, BotTimes

    def convert_to_mp4(input_file, out_file):
        # cpu fallback
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_file,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-strict",
            "-2",
            out_file,
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    async def msg_updater(c: int, tr, engine: str):
        global Messages
        messg = f"╭「" + "░" * c + "█" + "░" * (11 - c) + "」"
        messg += f"\n├⏳ **Status »** __Running 🏃🏼‍♂️__\n├🕹 **Attempt »** __{tr}__"
        messg += f"\n├⚙️ **Engine »** __{engine}__\n├💪🏼 **Handler »** __{core}__"
        messg += f"\n╰🍃 **Time Spent »** __{getTime((datetime.now() - BotTimes.start_time).seconds)}__"
        try:
            await MSG.status_msg.edit_text(
                text=fit_caption(Messages.task_msg + mtext + messg + sysINFO()),
                reply_markup=keyboard(),
            )
        except Exception:
            pass

    name, ext = ospath.splitext(file)

    if ext.lower() in [".mkv", ".mp4"]:
        return file  # Return if It's already mp4 / mkv file

    c, out_file, Err = 0, f"{name}.{BOT.Options.video_out}", False
    gpu = len(GPUtil.getAvailable())

    quality_args = ["-preset", "slow", "-qp", "0"] if BOT.Options.convert_quality else []

    # ignored = "-hwaccel cuvid -c:v h264_cuvid"
    if gpu == 1:
        cmd = ["ffmpeg", "-y", "-i", file] + quality_args + ["-c:v", "h264_nvenc", "-c:a", "copy", out_file]
        core = "GPU"
    else:
        cmd = ["ffmpeg", "-y", "-i", file] + quality_args + ["-c:v", "libx264", "-c:a", "copy", out_file]
        core = "CPU"

    mtext = f"<b>🎥 Converting Video »</b>\n\n{ospath.basename(file)}\n\n"

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    while proc.poll() is None:
        await msg_updater(c, "1st", "FFmpeg 🏍")
        c = (c + 1) % 12
        await sleep(3)

    _, stderr_bytes = proc.communicate()
    if proc.returncode != 0:
        logging.error(f"FFmpeg conversion failed: {stderr_bytes.decode('utf-8', errors='replace')}")

    if ospath.exists(out_file) and getSize(out_file) == 0:
        os.remove(out_file)
        Err = True
    elif not ospath.exists(out_file):
        Err = True

    if Err:
        proc = Thread(target=convert_to_mp4, name="FFmpeg", args=(file, out_file))
        proc.start()
        core = "CPU"
        while proc.is_alive():  # wait for conversion
            await msg_updater(c, "2nd", "FFmpeg-CPU 🛵")
            c = (c + 1) % 12
            await sleep(3)

    if ospath.exists(out_file) and getSize(out_file) == 0:
        os.remove(out_file)
        Err = True
    elif not ospath.exists(out_file):
        Err = True
    else:
        Err = False

    if Err:
        logging.error("This Video Can't Be Converted !")
        return file
    else:
        os.remove(file)
        return out_file


async def sizeChecker(file_path, remove: bool):
    global Paths
    max_size = MAX_UPLOAD_SIZE
    file_size = os.stat(file_path).st_size

    if file_size > max_size:
        if not ospath.exists(Paths.temp_zpath):
            makedirs(Paths.temp_zpath)
        _, filename = ospath.split(file_path)
        filename = filename.lower()
        if (
            filename.endswith(".zip")
            or filename.endswith(".rar")
            or filename.endswith(".7z")
            or filename.endswith(".tar")
            or filename.endswith(".gz")
        ):
            await splitArchive(file_path, max_size)
        else:
            f_type = fileType(file_path)
            if f_type == "video" and BOT.Options.is_split:
                if BOT.Options.raw_split:
                    await splitVideoRaw(file_path, max_size, remove)
                else:
                    # splitVideo takes MB, not bytes
                    await splitVideo(file_path, max_size // (1024 * 1024), remove)
            else:
                await archive(file_path, True, remove)
            await sleep(2)
        return True
    else:
        return False


async def archive(path, is_split, remove: bool):
    global BOT, Messages
    dir_p, p_name = ospath.split(path)
    if len(BOT.Options.custom_name) != 0:
        name = BOT.Options.custom_name
    elif ospath.isfile(path):
        name = ospath.basename(path)
    else:
        name = Messages.download_name
    Messages.status_head = f"<b>🔐 ZIPPING » </b>\n\n<code>{name}</code>\n"
    Messages.download_name = f"{name}.zip"
    BotTimes.task_start = datetime.now()

    if len(BOT.Options.zip_pswd) == 0:
        cmd = ["zip"]
        if ospath.isdir(path):
            cmd.append("-r")
        if is_split:
            cmd.extend(["-s", "2000m"])
        cmd.extend(["-0", f"{Paths.temp_zpath}/{name}.zip", p_name])
        proc = subprocess.Popen(cmd, cwd=dir_p, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    else:
        cmd = ["7z", "a", "-mx=0", "-tzip", f"-p{BOT.Options.zip_pswd}"]
        if is_split:
            cmd.append("-v2000m")
        cmd.extend([f"{Paths.temp_zpath}/{name}.zip", path])
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    total_size = getSize(path)
    total_in_unit = sizeUnit(total_size)
    while proc.poll() is None:
        speed_string, eta, percentage = speedETA(
            BotTimes.task_start, getSize(Paths.temp_zpath), total_size
        )
        await status_bar(
            Messages.status_head,
            speed_string,
            percentage,
            getTime(eta),
            sizeUnit(getSize(Paths.temp_zpath)),
            total_in_unit,
            "Xr-Zipp 🔒",
        )
        await sleep(1)

    _, stderr_bytes = proc.communicate()
    if proc.returncode != 0:
        logging.error(f"Archive failed with code {proc.returncode}: {stderr_bytes.decode('utf-8', errors='replace')}")

    if remove:
        if ospath.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path)


async def extract(zip_filepath, remove: bool):
    global BOT, Paths, Messages
    _, filename = ospath.split(zip_filepath)
    Messages.status_head = f"<b>📂 EXTRACTING »</b>\n\n<code>{filename}</code>\n"
    p = f"-p{BOT.Options.unzip_pswd}" if len(BOT.Options.unzip_pswd) != 0 else None
    name, ext = ospath.splitext(filename)
    file_pattern, real_name, temp_unzip_path, total_ = (
        "",
        name,
        Paths.temp_unzip_path,
        0,
    )
    if ext == ".rar":
        cmd = ["unrar", "x"]
        if "part" in name:
            cmd.extend(["-kb", "-idq"])
            file_pattern = "rar"
        if p:
            cmd.append(p)
        cmd.extend([zip_filepath, temp_unzip_path])
    elif ext == ".tar":
        cmd = ["tar", "-xvf", zip_filepath, "-C", temp_unzip_path]
    elif ext == ".gz":
        cmd = ["tar", "-zxvf", zip_filepath, "-C", temp_unzip_path]
    else:
        cmd = ["7z", "x"]
        if p:
            cmd.append(p)
        cmd.extend([zip_filepath, f"-o{temp_unzip_path}"])
        if ext == ".001":
            file_pattern = "7z"
        elif ext == ".z01":
            file_pattern = "zip"

    if file_pattern == "":
        total_ = getSize(zip_filepath)
        total = sizeUnit(total_)
    else:
        real_name, total_ = multipartArchive(zip_filepath, file_pattern, False)
        total = sizeUnit(total_)

    BotTimes.task_start = datetime.now()

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    while proc.poll() is None:
        speed_string, eta, percentage = speedETA(
            BotTimes.task_start,
            getSize(temp_unzip_path),
            total_,
        )
        await status_bar(
            Messages.status_head,
            speed_string,
            percentage,
            getTime(eta),
            sizeUnit(getSize(temp_unzip_path)),
            total,
            "Xr-Unzip 🔓",
        )
        await sleep(1)

    _, stderr_bytes = proc.communicate()
    if proc.returncode != 0:
        logging.error(f"Extract failed with code {proc.returncode}: {stderr_bytes.decode('utf-8', errors='replace')}")

    if remove:
        multipartArchive(zip_filepath, file_pattern, True)

        if ospath.exists(zip_filepath):
            os.remove(zip_filepath)

    Messages.download_name = real_name


async def splitArchive(file_path, max_size):
    global Paths, BOT, MSG, Messages
    _, filename = ospath.split(file_path)
    Messages.status_head = f"<b>✂️ SPLITTING » </b>\n\n<code>{filename}</code>\n"
    total_size = ospath.getsize(file_path)

    BotTimes.task_start = datetime.now()

    # split archive by bytes
    for _, _part_path, written in split_by_bytes(file_path, Paths.temp_zpath, max_size):
        speed_string, eta, percentage = speedETA(
            BotTimes.task_start, written, total_size
        )
        await status_bar(
            Messages.status_head,
            speed_string,
            percentage,
            getTime(eta),
            sizeUnit(written),
            sizeUnit(total_size),
            "Xr-Split ✂️",
        )


async def splitVideo(file_path, max_size, remove: bool):
    global Paths, BOT, MSG, Messages
    _, filename = ospath.split(file_path)
    just_name, extension = ospath.splitext(filename)

    # get video bitrate
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path]

    bitrate = None
    try:
        output = subprocess.check_output(cmd)
        video_info = json.loads(output)
        bitrate = float(video_info["format"]["bit_rate"])
    except Exception:
        logging.error("Error: Could not get video bitrate")
        bitrate = 1000

    if bitrate <= 0:
        bitrate = 1000

    # calc segment duration
    target_size_bits = max_size * 8 * 1024 * 1024

    duration = int(target_size_bits / bitrate)
    if duration <= 0:
        duration = 1

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(duration),
        "-reset_timestamps",
        "1",
        f"{Paths.temp_zpath}/{just_name}.part%03d{extension}",
    ]

    Messages.status_head = f"<b>✂️ SPLITTING » </b>\n\n<code>{filename}</code>\n"
    BotTimes.task_start = datetime.now()

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    total_size = getSize(file_path)
    total_in_unit = sizeUnit(total_size)
    while proc.poll() is None:
        speed_string, eta, percentage = speedETA(
            BotTimes.task_start, getSize(Paths.temp_zpath), total_size
        )
        await status_bar(
            Messages.status_head,
            speed_string,
            percentage,
            getTime(eta),
            sizeUnit(getSize(Paths.temp_zpath)),
            total_in_unit,
            "Xr-Split ✂️",
        )
        await sleep(1)

    _, stderr_bytes = proc.communicate()
    if proc.returncode != 0:
        logging.error(
            f"FFmpeg split failed with code {proc.returncode}: {stderr_bytes.decode('utf-8', errors='replace')}"
        )

    created_parts = [
        p
        for p in os.listdir(Paths.temp_zpath)
        if ospath.isfile(ospath.join(Paths.temp_zpath, p))
        and getSize(ospath.join(Paths.temp_zpath, p)) > 0
    ]
    # fallback to byte split if ffmpeg made no parts
    if not created_parts:
        logging.warning(
            "ffmpeg segmenting produced no parts, falling back to raw byte split"
        )
        return await splitVideoRaw(file_path, max_size * 1024 * 1024, remove)

    if remove and ospath.exists(file_path):
        os.remove(file_path)


async def splitVideoRaw(file_path, max_size, remove: bool):
    global Paths, BOT, MSG, Messages
    _, filename = ospath.split(file_path)
    Messages.status_head = f"<b>✂️ SPLITTING » </b>\n\n<code>{filename}</code>\n"
    BotTimes.task_start = datetime.now()

    total_size = getSize(file_path)
    total_in_unit = sizeUnit(total_size)
    parts = []

    # split by bytes
    for _, part_path, written in split_by_bytes(file_path, Paths.temp_zpath, max_size):
        parts.append(part_path)
        speed_string, eta, percentage = speedETA(
            BotTimes.task_start, written, total_size
        )
        await status_bar(
            Messages.status_head,
            speed_string,
            percentage,
            getTime(eta),
            sizeUnit(written),
            total_in_unit,
            "Xr-RawSplit ✂️",
        )
        # yield to stay responsive
        await sleep(0)

    if remove and ospath.exists(file_path):
        os.remove(file_path)

    return parts
