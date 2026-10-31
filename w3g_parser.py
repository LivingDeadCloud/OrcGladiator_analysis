"""Parser per replay Warcraft III classici (formato 1.24, build 6059).

Uso: python w3g_parser.py <replay.w3g> <cartella_output>
Produce: players.csv, actions.csv (una riga per azione), chat.csv, leaves.csv
"""
import csv, os, struct, sys, zlib
from collections import Counter

ORDER_NAMES = {
    0x0D0003: 'smart', 0x0D0004: 'stop', 0x0D0008: 'cancel', 0x0D000C: 'setrally', 0x0D000D: 'getitem',
    0x0D000F: 'attack', 0x0D0010: 'attackground', 0x0D0011: 'attackonce',
    0x0D0012: 'move', 0x0D0014: 'AImove', 0x0D0016: 'patrol', 0x0D0019: 'holdposition',
    0x0D0021: 'dropitem',
    **{0x0D0022 + i: f'moveslot{i + 1}' for i in range(6)},
    **{0x0D0028 + i: f'useslot{i + 1}' for i in range(6)},
}


def order_name(oid):
    if oid in ORDER_NAMES:
        return ORDER_NAMES[oid]
    raw = struct.pack('<I', oid)
    if all(32 <= b < 127 for b in raw):
        return raw[::-1].decode('ascii')  # rawcode tipo 'AHhb'
    return f'0x{oid:06X}'


def read_cstr(b, p):
    e = b.index(0, p)
    return b[p:e].decode('utf-8', 'replace'), e + 1


def decompress(path):
    d = open(path, 'rb').read()
    assert d.startswith(b'Warcraft III recorded game')
    hs, _, _, _, nb = struct.unpack('<IIIII', d[28:48])
    sub = struct.unpack('<4sIHHII', d[48:68])
    pos, buf = hs, bytearray()
    for _ in range(nb):
        c, u, _crc = struct.unpack('<HHI', d[pos:pos + 8]); pos += 8
        dec = zlib.decompressobj().decompress(d[pos:pos + c]); pos += c
        buf += dec[:u].ljust(u, b'\0')
    return bytes(buf), {'game': sub[0][::-1].decode(), 'version': sub[1], 'build': sub[2], 'length_ms': sub[4]}


def parse(path):
    b, meta = decompress(path)
    players = {}
    p = 4
    # record host
    assert b[p] == 0x00
    pid = b[p + 1]; name, p = read_cstr(b, p + 2)
    extra = b[p]; p += 1 + extra
    players[pid] = name
    gname, p = read_cstr(b, p)
    p += 1  # null
    e = b.index(0, p); enc = b[p:e]; p = e + 1  # stringa codificata impostazioni mappa
    meta['game_name'] = gname
    meta['map'] = decode_encoded(enc)
    p += 4 + 4 + 4  # n players, game type, language
    while b[p] == 0x16:
        pid = b[p + 1]; name, p = read_cstr(b, p + 2)
        extra = b[p]; p += 1 + extra
        p += 4
        players[pid] = name
    assert b[p] == 0x19
    n = struct.unpack('<H', b[p + 1:p + 3])[0]
    slots_n = b[p + 3]
    q = p + 4
    slots = []
    for i in range(slots_n):
        s = b[q:q + 9]
        slots.append({'slot': i, 'pid': s[0], 'status': s[2], 'computer': s[3], 'team': s[4], 'color': s[5], 'race': s[6]})
        q += 9
    p = p + 3 + n  # n include anche random seed, select mode, start spots

    actions, chat, leaves = [], [], []
    t = 0
    while p < len(b):
        bid = b[p]
        if bid in (0x1A, 0x1B, 0x1C):
            p += 5
        elif bid in (0x1E, 0x1F):
            ln, dt = struct.unpack('<HH', b[p + 1:p + 5])
            end = p + 3 + ln
            q = p + 5
            t += dt
            while q < end:
                apid = b[q]; alen = struct.unpack('<H', b[q + 1:q + 3])[0]
                parse_actions(b[q + 3:q + 3 + alen], apid, t, actions)
                q += 3 + alen
            p = end
        elif bid == 0x20:
            apid = b[p + 1]; ln = struct.unpack('<H', b[p + 2:p + 4])[0]
            flags = b[p + 4]
            q = p + 5
            mode = None
            if flags == 0x20:
                mode = struct.unpack('<I', b[q:q + 4])[0]; q += 4
            msg, _ = read_cstr(b, q)
            chat.append({'time_ms': t, 'pid': apid, 'player': players.get(apid), 'mode': mode, 'message': msg})
            p = p + 4 + ln
        elif bid == 0x22:
            p += 2 + b[p + 1]
        elif bid == 0x17:
            reason, apid, result = struct.unpack('<IBI', b[p + 1:p + 10])
            leaves.append({'time_ms': t, 'pid': apid, 'player': players.get(apid), 'reason': hex(reason), 'result': hex(result)})
            p += 14
        elif bid == 0x00:
            break
        else:
            raise ValueError(f'blocco sconosciuto 0x{bid:02X} a {p}')
    return meta, players, slots, actions, chat, leaves


def decode_encoded(e):
    out, mask = bytearray(), 0
    for i, c in enumerate(e):
        if i % 8 == 0:
            mask = c
        else:
            out.append(c - 1 if not (mask & (1 << (i % 8))) else c)
    try:
        s = bytes(out)
        return s[13:].split(b'\0')[0].decode('utf-8', 'replace')
    except Exception:
        return ''


def parse_actions(a, pid, t, out):
    q = 0
    def add(kind, **kw):
        out.append({'time_ms': t, 'pid': pid, 'kind': kind, **kw})
    while q < len(a):
        aid = a[q]; q += 1
        if aid == 0x01: add('pause')
        elif aid == 0x02: add('resume')
        elif aid == 0x03: q += 1
        elif aid in (0x04, 0x05): pass
        elif aid == 0x06: _, q = read_cstr(a, q)
        elif aid == 0x07: q += 4
        elif aid == 0x10:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); q += 14
            add('order_notarget', order=order_name(oid), flags=flags)
        elif aid == 0x11:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); x, y = struct.unpack('<ff', a[q + 14:q + 22]); q += 22
            add('order_point', order=order_name(oid), flags=flags, x=round(x, 1), y=round(y, 1))
        elif aid == 0x12:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); x, y = struct.unpack('<ff', a[q + 14:q + 22])
            o1, o2 = struct.unpack('<II', a[q + 22:q + 30]); q += 30
            add('order_target', order=order_name(oid), flags=flags, x=round(x, 1), y=round(y, 1),
                target=f'{o1:08X}-{o2:08X}', target_is_unit=not (o1 == 0xFFFFFFFF and o2 == 0xFFFFFFFF))
        elif aid == 0x13:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); x, y = struct.unpack('<ff', a[q + 14:q + 22]); q += 38
            add('give_item', order=order_name(oid), flags=flags, x=round(x, 1), y=round(y, 1))
        elif aid == 0x14:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); x, y = struct.unpack('<ff', a[q + 14:q + 22]); q += 43
            add('order_two_targets', order=order_name(oid), flags=flags, x=round(x, 1), y=round(y, 1))
        elif aid == 0x16:
            mode, n = struct.unpack('<BH', a[q:q + 3]); q += 3 + 8 * n
            add('select', mode='add' if mode == 1 else 'remove', n=n)
        elif aid == 0x17:
            g, n = struct.unpack('<BH', a[q:q + 3]); q += 3 + 8 * n
            add('assign_group', group=g, n=n)
        elif aid == 0x18:
            add('select_group', group=a[q]); q += 2
        elif aid == 0x19:
            q += 12; add('select_subgroup')
        elif aid == 0x1A: pass
        elif aid in (0x1B, 0x1C): q += 9
        elif aid == 0x1D: q += 8
        elif aid == 0x1E: q += 5
        elif aid == 0x21: q += 8
        elif aid in (0x20, 0x22, 0x23, 0x24, 0x25, 0x26, 0x29, 0x2A, 0x2B, 0x2C, 0x2F, 0x30, 0x31, 0x32): pass
        elif aid == 0x27: q += 5
        elif aid == 0x28: q += 5
        elif aid == 0x2D: q += 5
        elif aid == 0x2E: q += 4
        elif aid == 0x50: q += 5
        elif aid == 0x51: q += 9
        elif aid == 0x60:
            q += 8; s, q = read_cstr(a, q); add('trigger_chat', text=s)
        elif aid == 0x61: add('esc')
        elif aid == 0x62: q += 12
        elif aid in (0x65, 0x66, 0x67): add('submenu')
        elif aid == 0x68:
            x, y = struct.unpack('<ff', a[q:q + 8]); q += 12; add('minimap_ping', x=round(x, 1), y=round(y, 1))
        elif aid in (0x69, 0x6A): q += 16
        elif aid == 0x6B:
            s1, q = read_cstr(a, q); s2, q = read_cstr(a, q); s3, q = read_cstr(a, q)
            v = struct.unpack('<I', a[q:q + 4])[0]; q += 4
            add('sync_int', s1=s1, s2=s2, s3=s3, value=v)
        elif aid == 0x75: q += 1
        else:
            add('unknown', aid=hex(aid), rest=a[q - 1:].hex())
            return


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    meta, players, slots, actions, chat, leaves = parse(src)
    players = {k: v.replace('�', '') for k, v in players.items()}
    # tempo di gioco al netto delle pause (e' quello mostrato dall'orologio del replay)
    pauses, start = [], None
    for a in actions:
        if a['kind'] == 'pause' and start is None:
            start = a['time_ms']
        elif a['kind'] == 'resume' and start is not None:
            pauses.append((start, a['time_ms'])); start = None

    def game_time(t):
        return t - sum(min(t, e) - s for s, e in pauses if t > s)
    for rows in (actions, chat, leaves):
        for r in rows:
            r['game_time_ms'] = game_time(r['time_ms'])
            if 'player' in r:
                r['player'] = players.get(r['pid'])
    meta['pauses_ms'] = pauses
    print(meta)
    slot_by_pid = {s['pid']: s for s in slots if s['status'] == 2}
    with open(os.path.join(outdir, 'players.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['pid', 'player', 'slot', 'team', 'color'])
        for pid, name in players.items():
            s = slot_by_pid.get(pid, {})
            w.writerow([pid, name, s.get('slot'), s.get('team'), s.get('color')])
    cols = ['time_ms', 'game_time_ms', 'pid', 'player', 'kind', 'order', 'flags', 'x', 'y', 'target', 'target_is_unit',
            'mode', 'n', 'group', 'text', 's1', 's2', 's3', 'value', 'aid', 'rest']
    with open(os.path.join(outdir, 'actions.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore'); w.writeheader()
        for a in actions:
            w.writerow({**a, 'player': players.get(a['pid'])})
    for fname, rows in (('chat.csv', chat), ('leaves.csv', leaves)):
        with open(os.path.join(outdir, fname), 'w', newline='', encoding='utf-8') as f:
            if rows:
                w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(len(actions), 'azioni,', len(chat), 'chat,', len(leaves), 'uscite')
    print(Counter(a['kind'] for a in actions))


if __name__ == '__main__':
    main()

