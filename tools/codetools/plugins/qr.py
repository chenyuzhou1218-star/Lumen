"""QR codes, from the standard: byte mode, error correction level M, versions 1 to 15. No library."""
from __future__ import annotations

from PIL import Image

from kit import Action, Field, Plugin, Stop, done, need, number

# version: (total codewords, ec per block, groups [(blocks, data per block)])
TABLE = {1: (26, 10, [(1, 16)]), 2: (44, 16, [(1, 28)]), 3: (70, 26, [(1, 44)]), 4: (100, 18, [(2, 32)]), 5: (134, 24, [(2, 43)]), 6: (172, 16, [(4, 27)]),
         7: (196, 18, [(4, 31)]), 8: (242, 22, [(2, 38), (2, 39)]), 9: (292, 22, [(3, 36), (2, 37)]), 10: (346, 26, [(4, 43), (1, 44)]), 11: (404, 30, [(1, 50), (4, 51)]),
         12: (466, 22, [(6, 36), (2, 37)]), 13: (532, 22, [(8, 37), (1, 38)]), 14: (581, 24, [(4, 40), (5, 41)]), 15: (655, 24, [(5, 41), (5, 42)])}
ALIGN = {2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50], 11: [6, 30, 54], 12: [6, 32, 58], 13: [6, 34, 62], 14: [6, 26, 46, 66], 15: [6, 26, 48, 70]}
EXP = [0] * 512
LOG = [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 256:
        _x ^= 0x11d
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def _rs(data: list, n: int) -> list:
    gen = [1]
    for i in range(n):
        new = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            new[j] ^= c
            new[j + 1] ^= EXP[LOG[c] + i] if c else 0
        gen = new
    rem = list(data) + [0] * n
    for i in range(len(data)):
        c = rem[i]
        if c:
            for j, g in enumerate(gen):
                if g:
                    rem[i + j] ^= EXP[LOG[c] + LOG[g]]
    return rem[len(data):]


def _bits_format(mask: int) -> list:
    data = (0b00 << 3) | mask  # M
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ (((rem >> 9) & 1) * 0x537)
    value = ((data << 10) | rem) ^ 0x5412
    return [(value >> i) & 1 for i in range(15)]


def _version_bits(v: int) -> list:
    rem = v
    for _ in range(12):
        rem = (rem << 1) ^ (((rem >> 11) & 1) * 0x1f25)
    value = (v << 12) | rem
    return [(value >> i) & 1 for i in range(18)]


def _codewords(text: bytes, version: int) -> list:
    total, ec, groups = TABLE[version]
    capacity = sum(b * d for b, d in groups)
    bits = [0, 1, 0, 0]
    size = 8 if version < 10 else 16
    bits += [(len(text) >> i) & 1 for i in range(size - 1, -1, -1)]
    for byte in text:
        bits += [(byte >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, capacity * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    data = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0
    while len(data) < capacity:
        data.append((0xec, 0x11)[pad % 2])
        pad += 1
    blocks, at = [], 0
    for count, length in groups:
        for _ in range(count):
            blocks.append(data[at:at + length])
            at += length
    out = []
    for i in range(max(map(len, blocks))):
        out += [b[i] for b in blocks if i < len(b)]
    parity = [_rs(b, ec) for b in blocks]
    for i in range(ec):
        out += [p[i] for p in parity]
    return out


def _matrix(version: int, words: list, mask: int) -> list:
    n = 17 + 4 * version
    m = [[None] * n for _ in range(n)]

    def finder(r, c):
        for i in range(-1, 8):
            for j in range(-1, 8):
                if 0 <= r + i < n and 0 <= c + j < n:
                    edge = max(abs(i - 3), abs(j - 3))
                    m[r + i][c + j] = 1 if edge in (0, 1, 3) else 0

    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)
    for i in range(8, n - 8):
        m[6][i] = m[i][6] = 1 - i % 2
    pos = ALIGN.get(version, [])
    last = len(pos) - 1
    for x, r in enumerate(pos):
        for y, c in enumerate(pos):
            if (x, y) not in ((0, 0), (0, last), (last, 0)):  # those three would land on the finders; the ones on the timing lines stay
                for i in range(-2, 3):
                    for j in range(-2, 3):
                        m[r + i][c + j] = 1 if max(abs(i), abs(j)) != 1 else 0
    m[n - 8][8] = 1
    fmt = _bits_format(mask)
    spots = [(0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (7, 8), (8, 8), (8, 7), (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0)]
    other = [(8, n - 1 - i) for i in range(8)] + [(n - 15 + i, 8) for i in range(8, 15)]
    for i in range(15):
        r, c = spots[i]
        m[r][c] = fmt[i]
        r, c = other[i]
        m[r][c] = fmt[i]
    if version >= 7:
        vb = _version_bits(version)
        for i in range(18):
            a, b = i // 3, i % 3 + n - 11
            m[a][b] = m[b][a] = vb[i]
    bits = [(w >> i) & 1 for w in words for i in range(7, -1, -1)]
    at, up, c = 0, True, n - 1
    while c > 0:
        if c == 6:
            c -= 1
        for r in (range(n - 1, -1, -1) if up else range(n)):
            for cc in (c, c - 1):
                if m[r][cc] is None:
                    bit = bits[at] if at < len(bits) else 0
                    at += 1
                    if _mask(mask, r, cc):
                        bit ^= 1
                    m[r][cc] = bit
        up = not up
        c -= 2
    return m


def _mask(k, r, c) -> bool:
    return [(r + c) % 2 == 0, r % 2 == 0, c % 3 == 0, (r + c) % 3 == 0, (r // 2 + c // 3) % 2 == 0, (r * c) % 2 + (r * c) % 3 == 0, ((r * c) % 2 + (r * c) % 3) % 2 == 0, ((r + c) % 2 + (r * c) % 3) % 2 == 0][k]


def _penalty(m: list) -> int:
    n = len(m)
    score = 0
    for lines in (m, list(zip(*m))):
        for row in lines:
            run, last = 0, None
            for v in row:
                if v == last:
                    run += 1
                    if run == 5:
                        score += 3
                    elif run > 5:
                        score += 1
                else:
                    run, last = 1, v
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(map(sum, m)) * 100 / (n * n)
    return score + int(abs(dark - 50) / 5) * 10


def encode(text: str) -> list:
    raw = text.encode('utf-8')
    for v, (total, ec, groups) in TABLE.items():
        capacity = sum(b * d for b, d in groups)
        if len(raw) + (2 if v < 10 else 3) <= capacity:
            words = _codewords(raw, v)
            return min((_matrix(v, words, k) for k in range(8)), key=_penalty)
    raise Stop('内容太长了，最多大约五百个字节')


def make(a, out):
    text = str(need(a, 'text', '内容'))
    m = encode(text)
    scale = int(number(a, 'size', 10))
    n = len(m)
    border = 4
    im = Image.new('RGB', ((n + 2 * border) * scale,) * 2, 'white')
    px = im.load()
    for r in range(n):
        for c in range(n):
            if m[r][c]:
                for y in range(scale):
                    for x in range(scale):
                        px[(c + border) * scale + x, (r + border) * scale + y] = (0, 0, 0)
    path = out / 'qr.png'
    im.save(path)
    return done(f'{n}×{n} 格，内容 {len(text.encode())} 字节', files=[path], pictures=[path])


PLUGIN = Plugin('qr', '二维码', '创作', '把文字或网址做成二维码，手机能扫', [
    Action('make', '生成', [Field('text', '内容', 'area', 'https://example.com'), Field('size', '每格像素', 'number', 10)], make, sample={'text': '你好 Lumen https://example.com'})])
