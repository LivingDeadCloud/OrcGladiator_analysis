"""Lettore MPQ minimale (formato v1, come in WC3 classico). Supporta zlib e bzip2."""
import bz2, struct, zlib

_CRYPT = []


def _init():
    seed = 0x00100001
    table = [0] * 0x500
    for i in range(0x100):
        idx = i
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            t1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            table[idx] = t1 | (seed & 0xFFFF)
            idx += 0x100
    _CRYPT.extend(table)


_init()


def hash_str(s, t):
    s1, s2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in s.upper().replace('/', '\\').encode('latin-1'):
        s1 = (_CRYPT[(t << 8) + ch] ^ (s1 + s2)) & 0xFFFFFFFF
        s2 = (ch + s1 + s2 + (s2 << 5) + 3) & 0xFFFFFFFF
    return s1


def decrypt(data, key):
    n = len(data) // 4
    vals = struct.unpack(f'<{n}I', data[:n * 4])
    out = []
    seed = 0xEEEEEEEE
    for v in vals:
        seed = (seed + _CRYPT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        d = (v ^ (key + seed)) & 0xFFFFFFFF
        out.append(d)
        key = ((~key << 0x15) + 0x11111111 | (key >> 0x0B)) & 0xFFFFFFFF
        seed = (d + seed + (seed << 5) + 3) & 0xFFFFFFFF
    return struct.pack(f'<{n}I', *out) + data[n * 4:]


class MPQ:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        off = 0
        while self.d[off:off + 4] != b'MPQ\x1a':
            off += 512
        self.off = off
        hsz, arcsz, ver, sec_shift, ht_pos, bt_pos, ht_n, bt_n = struct.unpack('<IIHHIIII', self.d[off + 4:off + 32])
        self.sector = 512 << sec_shift
        ht = decrypt(self.d[off + ht_pos:off + ht_pos + ht_n * 16], hash_str('(hash table)', 3))
        bt_raw = self.d[off + bt_pos:off + bt_pos + bt_n * 16]
        bt_raw = bt_raw.ljust(bt_n * 16, b'\0')
        bt = decrypt(bt_raw, hash_str('(block table)', 3))
        self.hashes = [struct.unpack('<IIHHI', ht[i * 16:i * 16 + 16]) for i in range(ht_n)]
        self.blocks = [struct.unpack('<IIII', bt[i * 16:i * 16 + 16]) for i in range(bt_n)]

    def find(self, name):
        n = len(self.hashes)
        i = hash_str(name, 0) % n
        a, b = hash_str(name, 1), hash_str(name, 2)
        for _ in range(n):
            h1, h2, _loc, _plat, blk = self.hashes[i]
            if blk == 0xFFFFFFFF:
                return None
            if h1 == a and h2 == b and blk < len(self.blocks):
                return blk
            i = (i + 1) % n
        return None

    def read(self, name):
        blk = self.find(name)
        if blk is None:
            return None
        pos, csize, fsize, flags = self.blocks[blk]
        base = self.off + pos
        key = None
        if flags & 0x10000:
            key = hash_str(name.split('\\')[-1], 3)
            if flags & 0x20000:
                key = ((key + pos) ^ fsize) & 0xFFFFFFFF
        if flags & 0x1000000:  # single unit
            raw = self.d[base:base + csize]
            if key is not None:
                raw = decrypt(raw, key)
            return self._decomp(raw, fsize) if (flags & 0x200 and csize < fsize) else raw[:fsize]
        nsec = (fsize + self.sector - 1) // self.sector
        if not flags & 0x300:
            raw = self.d[base:base + fsize]
            if key is not None:
                raw = b''.join(decrypt(raw[i:i + self.sector], (key + j) & 0xFFFFFFFF)
                               for j, i in enumerate(range(0, len(raw), self.sector)))
            return raw
        tbl = self.d[base:base + (nsec + 1) * 4]
        if key is not None:
            tbl = decrypt(tbl, (key - 1) & 0xFFFFFFFF)
        offs = struct.unpack(f'<{nsec + 1}I', tbl)
        out = bytearray()
        for j in range(nsec):
            s = self.d[base + offs[j]:base + offs[j + 1]]
            if key is not None:
                s = decrypt(s, (key + j) & 0xFFFFFFFF)
            want = min(self.sector, fsize - j * self.sector)
            out += self._decomp(s, want) if len(s) < want else s[:want]
        return bytes(out)

    @staticmethod
    def _decomp(s, want):
        m = s[0]
        data = s[1:]
        if m & 0x10:
            data = bz2.decompress(data)
        if m & 0x02:
            data = zlib.decompress(data)
        if m & ~0x12:
            raise NotImplementedError(f'compressione 0x{m:02X}')
        return data
