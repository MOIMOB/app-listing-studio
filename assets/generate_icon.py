"""
Generates assets/icon.ico — run once to (re)create the icon.
  python assets/generate_icon.py

Writes a proper multi-size ICO with PNG-compressed frames because Pillow's
built-in ICO saver doesn't reliably produce multi-size files across versions.
"""

import io
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PIL import Image, ImageDraw

OUT   = os.path.join(os.path.dirname(__file__), "icon.ico")
SIZES = [16, 24, 32, 48, 64, 128, 256]


# ── Icon drawing ───────────────────────────────────────────────────────────────

def draw_frame(size: int) -> Image.Image:
    s    = size
    img  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background: dark purple → vivid violet
    top    = (30,  10,  60)
    bottom = (109, 40, 217)
    for y in range(s):
        t  = y / max(s - 1, 1)
        rc = int(top[0] + (bottom[0] - top[0]) * t)
        gc = int(top[1] + (bottom[1] - top[1]) * t)
        bc = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (s - 1, y)], fill=(rc, gc, bc, 255))

    # Clip to rounded square
    radius = max(s // 5, 2)
    mask   = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img.putalpha(mask)
    draw = ImageDraw.Draw(img)

    # Phone outline — 42 % wide, 62 % tall, centred slightly above middle
    pw = max(int(s * 0.42), 4)
    ph = max(int(s * 0.62), 6)
    px = (s - pw) // 2
    py = int(s * 0.18)
    pr = max(pw // 5, 1)
    bw = max(s // 22, 1)
    white = (255, 255, 255, 230)

    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=pr, fill=(255, 255, 255, 28))
    for i in range(bw):
        draw.rounded_rectangle(
            [px + i, py + i, px + pw - i, py + ph - i],
            radius=max(pr - i, 1), outline=white,
        )

    # Punch-hole camera
    if s >= 32:
        cr = max(int(s * 0.028), 1)
        cx = s // 2
        cy = py + max(int(ph * 0.07), 1) + cr
        draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=white)

    # Four-point sparkle in top-right corner
    if s >= 24:
        sx  = int(s * 0.76)
        sy  = int(s * 0.12)
        arm = max(int(s * 0.10), 2)
        thin = max(arm // 3, 1)
        spark = (255, 255, 255, 200)
        draw.ellipse([sx - thin, sy - arm,  sx + thin, sy + arm],  fill=spark)
        draw.ellipse([sx - arm,  sy - thin, sx + arm,  sy + thin], fill=spark)
        draw.ellipse([sx - thin, sy - thin, sx + thin, sy + thin], fill=spark)

    return img


# ── ICO file builder ───────────────────────────────────────────────────────────

def build_ico(images: list[Image.Image]) -> bytes:
    """
    Build a multi-size ICO file manually.
    Each frame is stored as a PNG chunk (modern ICO, Windows Vista+).
    """
    # Compress each frame to PNG bytes
    blobs = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blobs.append(buf.getvalue())

    n = len(images)
    header_size   = 6
    dir_entry_sz  = 16
    payload_offset = header_size + n * dir_entry_sz

    # ICO header: reserved=0, type=1 (ICO), count=n
    header = struct.pack("<HHH", 0, 1, n)

    directory = b""
    offset = payload_offset
    for img, blob in zip(images, blobs):
        w, h = img.size
        directory += struct.pack(
            "<BBBBHHII",
            w if w < 256 else 0,   # width  (0 means 256)
            h if h < 256 else 0,   # height (0 means 256)
            0,                     # colour count (0 = no palette)
            0,                     # reserved
            1,                     # colour planes
            32,                    # bits per pixel
            len(blob),             # size of image data
            offset,                # offset of image data
        )
        offset += len(blob)

    return header + directory + b"".join(blobs)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    frames = [draw_frame(s) for s in SIZES]
    ico_bytes = build_ico(frames)
    with open(OUT, "wb") as f:
        f.write(ico_bytes)

    print(f"Icon written -> {OUT}")
    print(f"File size   : {len(ico_bytes):,} bytes")
    print(f"Sizes       : {SIZES}")

    # Quick verify: round-trip through PIL
    test = Image.open(OUT)
    loaded = []
    try:
        while True:
            loaded.append(test.size)
            test.seek(test.tell() + 1)
    except EOFError:
        pass
    print(f"PIL read    : {loaded}")


if __name__ == "__main__":
    main()
