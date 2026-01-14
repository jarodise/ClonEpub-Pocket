import sys
import struct
import zlib


def write_png(width, height, color_hex, filename):
    # Parse color
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)

    # Build PNG chunks
    def chunk(tag, data):
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", 0xFFFFFFFF & zlib.crc32(tag + data))
        )

    # Header
    png = b"\x89PNG\r\n\x1a\n"

    # IHDR: Width, Height, BitDepth(8), ColorType(2=RGB), Compression(0), Filter(0), Interlace(0)
    png += chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))

    # IDAT: Data
    # For filter type 0 (None), each scanline is [0] + [RGB] * width
    line_data = b"\x00" + struct.pack("BBB", r, g, b) * width
    raw_data = line_data * height
    compressed = zlib.compress(raw_data)
    png += chunk(b"IDAT", compressed)

    # IEND
    png += chunk(b"IEND", b"")

    with open(filename, "wb") as f:
        f.write(png)
    print(f"Generated {filename}")


# Generate 600x400 background with color #1a1f26 (Theme bg-secondary)
write_png(600, 400, "1a1f26", "electron/assets/dmg-background.png")
