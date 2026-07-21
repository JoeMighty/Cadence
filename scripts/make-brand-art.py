"""Draw the Cadence mark into the app icon and the installer bitmaps.

One definition of the mark, used everywhere, so the icon and the installer
can't drift apart.

The mark is an open C of radiating strokes. Centring its *bounding box* leaves
it looking shifted right, because the long thin stroke reaches left while the
strokes bunch up on the right: the eye follows the weight, not the box. So it
is placed by its centre of mass instead, which is COM_DX units right of the
box centre. That is the whole reason this file exists rather than a one-liner.

    uv run --no-project --with pillow python scripts/make-brand-art.py

Then regenerate the icon set from the source it writes:

    cd app && npm run tauri icon ../build/icon-source.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ACCENT = (88, 86, 214)  # --accent, the purple of the app icon
ACCENT_LIT = (125, 122, 255)  # --accent in dark mode, for gradients
PAPER = (255, 255, 255)
HAIRLINE = (228, 228, 232)

ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = ROOT / "app" / "src-tauri" / "installer"
ICON_SOURCE = ROOT / "build" / "icon-source.png"

# The mark, exactly as the site and app draw it (SVG viewBox -2 -2 36 36).
MARK = [
    (18.02, 23.53, 19.26, 28.17),
    (14.02, 21.45, 11.01, 29.72),
    (10.27, 20.02, 5.02, 23.69),
    (11.20, 16.00, 0.40, 16.00),
    (10.27, 11.98, 5.02, 8.31),
    (14.02, 10.55, 11.01, 2.28),
    (18.02, 8.47, 19.26, 3.83),
]
STROKE = 3.0  # the SVG's stroke-width
_CAP = STROKE / 2  # round caps push the ink out by half the stroke

# Ink bounds including caps, in viewBox units.
INK_X0 = min(min(s[0], s[2]) for s in MARK) - _CAP
INK_X1 = max(max(s[0], s[2]) for s in MARK) + _CAP
INK_Y0 = min(min(s[1], s[3]) for s in MARK) - _CAP
INK_Y1 = max(max(s[1], s[3]) for s in MARK) + _CAP
INK_W, INK_H = INK_X1 - INK_X0, INK_Y1 - INK_Y0

# How far right of the ink's box centre its centre of mass falls, measured by
# rasterising the mark. Subtracting this is what makes it look centred.
COM_DX = 1.40


def draw_mark(d: ImageDraw.ImageDraw, cx: float, cy: float, ink_h: float, fill) -> None:
    """Stamp the mark so its visual weight lands on (cx, cy), ink_h px tall."""
    s = ink_h / INK_H
    box_cx = cx - COM_DX * s  # optical centring, see module docstring
    ox = box_cx - (INK_X0 + INK_X1) / 2 * s
    oy = cy - (INK_Y0 + INK_Y1) / 2 * s
    w = max(1, round(STROKE * s))
    r = w / 2
    for x1, y1, x2, y2 in MARK:
        p1, p2 = (ox + x1 * s, oy + y1 * s), (ox + x2 * s, oy + y2 * s)
        d.line([p1, p2], fill=fill, width=w)
        for px, py in (p1, p2):  # round caps, which PIL won't do itself
            d.ellipse([px - r, py - r, px + r, py + r], fill=fill)


def app_icon(size: int, supersample: int = 4) -> Image.Image:
    """The mark reversed out of the rounded purple square."""
    n = size * supersample
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=round(n * 0.154), fill=ACCENT + (255,))
    draw_mark(d, n / 2, n / 2, n * 0.625, PAPER + (255,))
    return img.resize((size, size), Image.LANCZOS)


def font(px: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", px)
        except OSError:
            continue
    return ImageFont.load_default()


def banner() -> Image.Image:
    """493x58. WiX writes the page title over the left, so art sits right."""
    img = Image.new("RGB", (493, 58), PAPER)
    d = ImageDraw.Draw(img)
    for x in range(300, 493):  # a whisper of colour from the right edge
        t = (x - 300) / 192
        d.line([(x, 0), (x, 57)],
               fill=tuple(round(PAPER[i] + (ACCENT[i] - PAPER[i]) * t * 0.10) for i in range(3)))

    img.paste(app_icon(34).convert("RGB"), (441, 12), app_icon(34))
    for i, h in enumerate((10, 16, 10)):  # ticks echoing the mark's strokes
        x = 419 - i * 9
        d.rounded_rectangle([x, 29 - h // 2, x + 3, 29 + h // 2], radius=2, fill=ACCENT_LIT)

    d.line([(0, 57), (493, 57)], fill=HAIRLINE)
    return img


def dialog() -> Image.Image:
    """493x312. WiX writes its text from about x=135, so art stays left of it."""
    img = Image.new("RGB", (493, 312), (250, 250, 250))
    d = ImageDraw.Draw(img)
    panel = 130
    for y in range(312):
        t = y / 311
        d.line([(0, y), (panel, y)],
               fill=tuple(round(ACCENT[i] + (ACCENT_LIT[i] - ACCENT[i]) * t) for i in range(3)))

    draw_mark(d, panel / 2, 126, 74, PAPER)
    f = font(15)
    label = "CADENCE"
    d.text((panel / 2 - d.textlength(label, font=f) / 2, 178), label, font=f, fill=PAPER)
    d.line([(panel / 2 - 18, 204), (panel / 2 + 18, 204)], fill=ACCENT_LIT, width=2)
    d.line([(panel, 0), (panel, 312)], fill=HAIRLINE)
    return img


if __name__ == "__main__":
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    ICON_SOURCE.parent.mkdir(parents=True, exist_ok=True)

    app_icon(1024).save(ICON_SOURCE)
    print(f"{ICON_SOURCE.relative_to(ROOT)}: 1024x1024")
    for name, im in (("banner", banner()), ("dialog", dialog())):
        path = INSTALLER_DIR / f"{name}.bmp"
        im.convert("RGB").save(path, "BMP")  # 24-bit, which is what WiX reads
        print(f"{path.relative_to(ROOT)}: {im.size[0]}x{im.size[1]}")
