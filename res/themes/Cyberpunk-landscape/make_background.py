# SPDX-License-Identifier: GPL-3.0-or-later
# Generates background.png for the Cyberpunk-landscape theme. Run from the repository root:
#   python res/themes/Cyberpunk-landscape/make_background.py
import math
from PIL import Image, ImageDraw, ImageFont

Y = (255, 239, 8)
# One colour per panel (keep in sync with theme.yaml)
CPU = (2, 216, 243)
GPU = (0, 255, 159)
RAM = (255, 60, 172)
DISK = (255, 159, 28)
NET = (64, 156, 255)
PING = (180, 120, 255)
SYS = (255, 85, 85)
CLAUDE = (217, 119, 87)
CURSOR = (225, 225, 225)
GOOGLE = (66, 133, 244)
DIM = (90, 84, 3)
FONT = 'res/fonts/generale-mono/GeneraleMonoA.ttf'
f12 = ImageFont.truetype(FONT, 12)
f11 = ImageFont.truetype(FONT, 11)

im = Image.new('RGB', (480, 320), (0, 0, 0))
d = ImageDraw.Draw(im)
d.line([(4, 35), (476, 35)], fill=DIM, width=1)


def panel(x, y, w, h, col):
    k = 8
    d.line([(x + k, y), (x + w, y), (x + w, y + h - k), (x + w - k, y + h), (x, y + h), (x, y + k), (x + k, y)],
           fill=col, width=1)
    for i in range(3):  # hatch accent, top right
        d.line([(x + w - 18 + i * 5, y + 7), (x + w - 14 + i * 5, y + 3)], fill=col, width=1)


def icon(name, x, y, col=Y):
    # 14x14 icons
    if name == 'cpu':
        d.rectangle([x + 3, y + 3, x + 10, y + 10], outline=col)
        d.rectangle([x + 5, y + 5, x + 8, y + 8], fill=col)
        for p in (4, 6, 9):
            d.line([(x + p, y), (x + p, y + 2)], fill=col); d.line([(x + p, y + 11), (x + p, y + 13)], fill=col)
            d.line([(x, y + p), (x + 2, y + p)], fill=col); d.line([(x + 11, y + p), (x + 13, y + p)], fill=col)
    elif name == 'gpu':
        d.rectangle([x, y + 3, x + 13, y + 10], outline=col)
        d.ellipse([x + 2, y + 4, x + 7, y + 9], outline=col)
        d.rectangle([x + 9, y + 5, x + 11, y + 8], fill=col)
        d.line([(x + 2, y + 11), (x + 2, y + 13)], fill=col); d.line([(x + 5, y + 11), (x + 5, y + 13)], fill=col)
    elif name == 'ram':
        d.rectangle([x, y + 4, x + 13, y + 9], outline=col)
        for p in (2, 5, 8, 11):
            d.rectangle([x + p, y + 6, x + p, y + 7], fill=col)
            d.line([(x + p, y + 10), (x + p, y + 12)], fill=col)
    elif name == 'disk':
        d.ellipse([x + 1, y + 1, x + 12, y + 5], outline=col)
        d.line([(x + 1, y + 3), (x + 1, y + 10)], fill=col); d.line([(x + 12, y + 3), (x + 12, y + 10)], fill=col)
        d.arc([x + 1, y + 4, x + 12, y + 9], 0, 180, fill=col)
        d.arc([x + 1, y + 8, x + 12, y + 13], 0, 180, fill=col)
    elif name == 'net':
        d.polygon([(x + 3, y + 1), (x, y + 5), (x + 6, y + 5)], fill=col); d.rectangle([x + 2, y + 5, x + 4, y + 12], fill=col)
        d.polygon([(x + 10, y + 12), (x + 7, y + 8), (x + 13, y + 8)], fill=col); d.rectangle([x + 9, y + 1, x + 11, y + 8], fill=col)
    elif name == 'ping':
        d.line([(x, y + 7), (x + 3, y + 7), (x + 5, y + 2), (x + 8, y + 12), (x + 10, y + 7), (x + 13, y + 7)], fill=col)
    elif name == 'claude':
        for a in range(0, 180, 30):
            dx, dy = 6.5 * math.cos(math.radians(a)), 6.5 * math.sin(math.radians(a))
            d.line([(x + 6.5 - dx, y + 6.5 - dy), (x + 6.5 + dx, y + 6.5 + dy)], fill=col, width=2)
    elif name == 'google':
        # Four-colour G: blue right and bar, green bottom, yellow left, red top
        for start, end, c in ((0, 45, GOOGLE), (45, 135, (52, 168, 83)), (135, 210, (251, 188, 5)),
                              (210, 315, (234, 67, 53))):
            d.arc([x, y, x + 12, y + 12], start, end, fill=c, width=2)
        d.line([(x + 6, y + 6), (x + 12, y + 6)], fill=GOOGLE, width=2)
    elif name == 'cursor':
        # Cursor logo: isometric cube, right face filled
        top, ne, se, bot, sw, nw, mid = ((x + 6, y), (x + 12, y + 3), (x + 12, y + 10), (x + 6, y + 13),
                                         (x, y + 10), (x, y + 3), (x + 6, y + 6))
        d.polygon([mid, ne, se, bot], fill=col)
        d.polygon([top, ne, se, bot, sw, nw], outline=col)
        d.line([nw, mid, ne], fill=col)
        d.line([mid, bot], fill=col)
    elif name == 'sun':
        d.ellipse([x + 4, y + 4, x + 9, y + 9], fill=col)
        for a in range(0, 360, 45):
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.line([(x + 6.5 + 4.5 * dx, y + 6.5 + 4.5 * dy), (x + 6.5 + 6.5 * dx, y + 6.5 + 6.5 * dy)], fill=col)
    elif name == 'clock':
        d.ellipse([x, y, x + 10, y + 10], outline=col)
        d.line([(x + 5, y + 2), (x + 5, y + 5), (x + 7, y + 6)], fill=col)
    elif name == 'sys':
        d.rectangle([x, y + 1, x + 13, y + 9], outline=col)
        d.line([(x + 6, y + 10), (x + 6, y + 12)], fill=col); d.line([(x + 7, y + 10), (x + 7, y + 12)], fill=col)
        d.line([(x + 3, y + 12), (x + 10, y + 12)], fill=col)
    elif name == 'fan':
        d.ellipse([x, y, x + 12, y + 12], outline=col)
        d.line([(x + 2, y + 2), (x + 10, y + 10)], fill=col); d.line([(x + 10, y + 2), (x + 2, y + 10)], fill=col)
        d.ellipse([x + 5, y + 5, x + 7, y + 7], fill=(0, 0, 0), outline=col)
    elif name == 'down':
        d.polygon([(x, y), (x + 10, y), (x + 5, y + 8)], fill=col)
    elif name == 'up':
        d.polygon([(x, y + 8), (x + 10, y + 8), (x + 5, y)], fill=col)


def title(x, y, name, text, col):
    icon(name, x + 6, y + 5, col)
    d.text((x + 25, y + 6), text, font=f12, fill=col)


COLS = (4, 163, 322)
ROWS = (38, 132, 226)
W, H = 154, 90
cells = (('cpu', 'CPU', CPU), ('gpu', 'GPU', GPU), ('ram', 'RAM', RAM),
         ('disk', 'DISK', DISK), ('net', 'NET', NET), ('sys', 'SYSTEM', SYS))
for i, (ic, text, col) in enumerate(cells):
    x, y = COLS[i % 3], ROWS[i // 3]
    panel(x, y, W, H, col)
    title(x, y, ic, text, col)

# Header: CPU fan, top process, weather
icon('fan', 6, 3, Y)
d.text((24, 5), 'FAN', font=f11, fill=Y)
d.text((6, 21), 'TOP', font=f11, fill=Y)
icon('sun', 186, 4, Y)
# Disk
x, y = COLS[0], ROWS[1]
d.text((x + 6, y + 73), 'TOTAL', font=f11, fill=DISK)
# Net
x, y = COLS[1], ROWS[1]
icon('down', x + 6, y + 24, NET)
icon('up', x + 6, y + 58, Y)
icon('ping', x + 54, y + 5, PING)
# System
x, y = COLS[2], ROWS[1]
for row, (left, right) in enumerate((('UP', 'VPN'), ('SSD', 'PROC'), ('GPU', 'GFAN'), ('DOCK', 'SWAP'))):
    d.text((x + 6, y + 24 + row * 16), left, font=f11, fill=SYS)
    d.text((x + 80, y + 24 + row * 16), right, font=f11, fill=SYS)
# Claude, Google, Cursor: same size as the six panels above (COLS x W)
x, y = COLS[0], ROWS[2]
panel(4, y, W, H, CLAUDE)
title(x, y, 'claude', 'CLAUDE', CLAUDE)
for row, text in enumerate(('5H', '7D', 'FB', 'API')):
    d.text((x + 6, y + 22 + row * 13), text, font=f12, fill=CLAUDE)
d.text((x + 6, y + 73), 'DAY', font=f11, fill=CLAUDE)
d.text((x + 78, y + 73), '5H', font=f11, fill=CLAUDE)
x = COLS[1]
panel(x, y, W, H, GOOGLE)
title(x, y, 'google', 'GOOGLE', GOOGLE)
for row, text in enumerate(('G 5H', 'G 7D', 'O 5H', 'O 7D')):
    d.text((x + 6, y + 22 + row * 16), text, font=f11, fill=GOOGLE)
x = COLS[2]
panel(x, y, W, H, CURSOR)
title(x, y, 'cursor', 'CURSOR', CURSOR)
d.text((x + 6, y + 22), 'MODEL', font=f11, fill=CURSOR)
d.text((x + 6, y + 38), 'OTHER', font=f11, fill=CURSOR)
d.text((x + 6, y + 54), 'BOT', font=f11, fill=CURSOR)
icon('clock', x + 6, y + 70, CURSOR)
d.text((x + 22, y + 71), 'RESETS', font=f11, fill=CURSOR)

im.save('res/themes/Cyberpunk-landscape/background.png')
