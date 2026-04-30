from PIL import Image, ImageDraw

# img = Image.open("img/another_new_tel_img.png").convert("RGBA")
# img = img.resize((256, 256))
# img.save("img/another_new_tel.ico", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])

def scale_center(img, scale):
    w, h = img.size
    new_w, new_h = int(w * scale), int(h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(img, ((w - new_w)//2, (h - new_h)//2), img)
    return canvas

def circle_to_ico(input_path, output_path, radius=None):
    img = Image.open(input_path).convert("RGBA")
    w, h = img.size
    cx, cy = w // 2, h // 2

    radius = radius or min(w, h) // 2
    radius = min(radius, min(w, h) // 2)

    # Create circular mask
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=255
    )

    # Apply mask (this is the key step)
    img.putalpha(mask)

    # Crop to circle bounds
    img = img.crop((cx - radius, cy - radius, cx + radius, cy + radius))

    # Make square canvas (required for ICO)
    size = max(img.size)
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    square.paste(img, ((size - img.width)//2, (size - img.height)//2), img)

    # Save ICO
    # square.save(output_path, format="ICO", sizes=[(256,256),(48,48),(32,32),(16,16)])
    square.save(
    output_path,
    format="ICO",
    sizes=[(16,16), (32,32), (48,48), (256,256)]
)
# usage
circle_to_ico("img/11.png", "img/11_3.ico", radius=375)