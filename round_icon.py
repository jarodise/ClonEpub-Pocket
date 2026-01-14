from PIL import Image, ImageDraw


def add_corners(im, rad):
    circle = Image.new("L", (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)

    alpha = Image.new("L", im.size, 255)
    w, h = im.size

    # Corners
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))

    # Edges (fill the rest with black (transparent in mask logic? No, mask: 0=transparent, 255=opaque))
    # Wait, my logic above: mask 0 is transparent.
    # circle drawing: fill=255 (opaque).
    # Background of circle image is 0 (transparent).

    # So I need to create a base alpha of 255 (opaque) and cut out corners?
    # No, usually easier: create a black (0) image, draw white (255) rounded rect.

    mask = Image.new("L", im.size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle((0, 0, w, h), radius=rad, fill=255)

    im.putalpha(mask)
    return im


def process_icon():
    input_path = "temp_icon/clonepub_icon.svg.png"
    output_path = "temp_icon/clonepub_icon_rounded.png"

    img = Image.open(input_path).convert("RGBA")

    # Resize to 1024x1024 if not
    if img.size != (1024, 1024):
        img = img.resize((1024, 1024), Image.Resampling.LANCZOS)

    # Apply rounded corners
    # Apple uses ~22% curvature for squircles, standard is approx 18-20% radius for clean round rect
    # 1024 * 0.18 = ~184
    radius = 184

    img = add_corners(img, radius)
    img.save(output_path)
    print(f"Saved {output_path}")


if __name__ == "__main__":
    process_icon()
