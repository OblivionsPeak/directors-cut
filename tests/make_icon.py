"""Generate icon.ico — clapperboard on dark, matching the UI theme."""
from PIL import Image, ImageDraw

BG = (13, 17, 23, 255)
RED = (229, 72, 77, 255)
WHITE = (230, 237, 243, 255)
DIM = (139, 148, 158, 255)


def draw_icon(size):
    S = 16
    W = size * S
    img = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, W - 1], radius=W * 0.22, fill=BG,
                        outline=RED, width=max(1, W // 32))

    # clapper top (angled bar with stripes)
    top = [(W * 0.16, W * 0.30), (W * 0.82, W * 0.20), (W * 0.85, W * 0.34), (W * 0.19, W * 0.44)]
    d.polygon(top, fill=RED)
    for i in range(4):
        x0 = W * (0.24 + i * 0.15)
        d.polygon([(x0, W * 0.29 - i * 0.02), (x0 + W * 0.06, W * 0.28 - i * 0.02),
                   (x0 + W * 0.045, W * 0.415 - i * 0.02), (x0 - W * 0.015, W * 0.425 - i * 0.02)],
                  fill=WHITE)
    # board body
    d.rounded_rectangle([W * 0.17, W * 0.46, W * 0.84, W * 0.82], radius=W * 0.04, fill=RED)
    # "play" triangle on the board
    d.polygon([(W * 0.42, W * 0.53), (W * 0.42, W * 0.75), (W * 0.64, W * 0.64)], fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


sizes = [256, 128, 64, 48, 32, 16]
frames = [draw_icon(s) for s in sizes]
frames[0].save('icon.ico', sizes=[(s, s) for s in sizes], append_images=frames[1:])
frames[0].save('static/icon.png')
print('wrote icon.ico + static/icon.png')
