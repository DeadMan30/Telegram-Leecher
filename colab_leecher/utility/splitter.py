# copyright 2024 © Xron Trix | https://github.com/Xrontrix10


import os
from os import path as ospath

# 8 MiB reads keep memory flat for any part size
BUFFER_SIZE = 8 * 1024 * 1024


# yields (index, part_path, total_written) per part
def split_by_bytes(src_path, out_dir, max_size, buffer_size=BUFFER_SIZE):
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    if buffer_size > max_size:
        buffer_size = max_size
    os.makedirs(out_dir, exist_ok=True)

    name = ospath.basename(src_path)
    total_size = ospath.getsize(src_path)
    index, written = 1, 0

    with open(src_path, "rb") as src:
        while written < total_size:
            part_path = ospath.join(out_dir, f"{name}.{str(index).zfill(3)}")
            part_written = 0
            with open(part_path, "wb") as part:
                while part_written < max_size:
                    chunk = src.read(min(buffer_size, max_size - part_written))
                    if not chunk:
                        break
                    part.write(chunk)
                    part_written += len(chunk)
            # drop empty part, avoids endless loop on 0 byte source
            if part_written == 0:
                os.remove(part_path)
                break
            written += part_written
            yield index, part_path, written
            index += 1
