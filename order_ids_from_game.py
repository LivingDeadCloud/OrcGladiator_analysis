"""Ricava la tabella order string -> order id da game.dll (WC3 1.24).

game.dll registra gli ordini con sequenze x86 "push <ptr stringa>; push <id>; call ...".
Uso: python order_ids_from_game.py "C:/Program Files (x86)/Warcraft III/game.dll" order_ids.csv
"""
import csv, re, struct, sys

dll = open(sys.argv[1], 'rb').read()
pe = struct.unpack_from('<I', dll, 0x3C)[0]
base = struct.unpack_from('<I', dll, pe + 24 + 28)[0]
nsec = struct.unpack_from('<H', dll, pe + 6)[0]
so = pe + 24 + struct.unpack_from('<H', dll, pe + 20)[0]
sects = [struct.unpack_from('<8sIIII', dll, so + 40 * k)[1:] for k in range(nsec)]


def va2off(v):
    for vs, va, rs, raw in sects:
        if base + va <= v < base + va + rs:
            return raw + v - base - va


rows = {}
for m in re.finditer(rb'\x68(....)\x68(..)\x0d\x00', dll, re.S):
    ptr = struct.unpack('<I', m.group(1))[0]
    oid = 0xD0000 + struct.unpack('<H', m.group(2))[0]
    o = va2off(ptr)
    if o is None:
        continue
    e = dll.find(b'\0', o)
    s = dll[o:e]
    if 2 <= len(s) <= 40 and all(32 < c < 127 for c in s):
        rows.setdefault(s.decode(), oid)

with open(sys.argv[2], 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['order_string', 'order_id', 'order_hex'])
    for s, n in sorted(rows.items(), key=lambda x: x[1]):
        w.writerow([s, n, f'0x{n:06X}'])
print(len(rows), 'ordini; chainlightning =', hex(rows.get('chainlightning', 0)), 'smart =', hex(rows.get('smart', 0)))
