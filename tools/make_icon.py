"""Gera assets/icon.png e assets/icon.ico. Rode: python tools/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024  # desenha grande e reduz, para bordas suaves
TOP, BOTTOM = (86, 130, 255), (38, 72, 214)


def build() -> Image.Image:
    gradient = Image.new("RGB", (SIZE, SIZE))
    pixels = gradient.load()
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        for x in range(SIZE):
            pixels[x, y] = color

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=230, fill=255)
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)

    draw = ImageDraw.Draw(icon)
    white, stroke, cx = (255, 255, 255, 255), 92, SIZE // 2
    draw.line([(cx, 240), (cx, 610)], fill=white, width=stroke)  # haste da seta
    draw.line([(cx - 190, 440), (cx, 630), (cx + 190, 440)], fill=white, width=stroke, joint="curve")  # ponta
    for x, y in ((cx, 240), (cx - 190, 440), (cx + 190, 440), (cx, 630)):
        draw.ellipse((x - stroke // 2, y - stroke // 2, x + stroke // 2, y + stroke // 2), fill=white)
    draw.rounded_rectangle((cx - 250, 730, cx + 250, 730 + stroke), radius=stroke // 2, fill=white)  # bandeja
    return icon


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(exist_ok=True)
    icon = build()
    icon.resize((256, 256), Image.LANCZOS).save(out / "icon.png")
    icon.save(out / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("Ícones gerados em", out)
