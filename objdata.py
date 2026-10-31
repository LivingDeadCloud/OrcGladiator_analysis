"""Parser dei file object data di WC3 (w3u, w3t, w3a, w3h, w3q, w3b) e della string table .wts."""
import re, struct

LEVELED = {'w3a', 'w3d', 'w3q'}


def parse_wts(data):
    txt = data.decode('utf-8', 'replace')
    return {int(m.group(1)): m.group(2).strip() for m in
            re.finditer(r'STRING (\d+)\s*(?://[^\n]*\n\s*)?\{\r?\n(.*?)\r?\n\}', txt, re.S)}


def parse_obj(data, kind, wts=None):
    p = 4
    leveled = kind in LEVELED
    objs = {}

    def rd(fmt):
        nonlocal p
        v = struct.unpack_from(fmt, data, p); p += struct.calcsize(fmt)
        return v[0] if len(v) == 1 else v

    def rstr():
        nonlocal p
        e = data.index(0, p); s = data[p:e].decode('utf-8', 'replace'); p = e + 1
        return s

    for table in ('original', 'custom'):
        n = rd('<I')
        for _ in range(n):
            orig = data[p:p + 4].decode('latin-1'); new = data[p + 4:p + 8]; p += 8
            new = new.decode('latin-1') if new != b'\0\0\0\0' else None
            nmods = rd('<I')
            mods = {}
            for _ in range(nmods):
                fid = data[p:p + 4].decode('latin-1'); p += 4
                typ = rd('<I')
                lvl = 0
                if leveled:
                    lvl, _dp = rd('<II')
                if typ == 0:
                    v = rd('<i')
                elif typ in (1, 2):
                    v = round(rd('<f'), 4)
                else:
                    v = rstr()
                    if wts and v.startswith('TRIGSTR_'):
                        v = wts.get(int(v[8:]), v)
                p += 4  # end / id
                mods[(fid, lvl)] = v
            objs[new or orig] = {'base': orig, 'custom': new is not None, 'mods': mods}
    return objs


def clean(s):
    """Rimuove i codici colore |cffxxxxxx ... |r."""
    if not isinstance(s, str):
        return s
    return re.sub(r'\|c[0-9a-fA-F]{8}|\|r|\|n', ' ', s).strip()
