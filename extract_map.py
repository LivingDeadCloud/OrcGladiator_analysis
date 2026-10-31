"""Estrae dal file della mappa (.w3x) i file necessari all'analisi e li salva in data_map/raw/.

Uso: python extract_map.py "C:/Program Files (x86)/Warcraft III/Maps/Download/Orc Gladiators Revenge 1.29fc.w3x"
"""
import os, sys
from mpq import MPQ

BS = chr(92)  # backslash
NAMES = ['war3map.j', 'scripts' + BS + 'war3map.j', 'war3map.wts', 'war3map.w3a', 'war3map.w3u', 'war3map.w3t',
         'war3map.w3h', 'war3map.w3q', 'war3map.w3b', 'war3map.w3d', 'war3mapMisc.txt']

m = MPQ(sys.argv[1])
os.makedirs('data_map/raw', exist_ok=True)
for n in NAMES:
    try:
        d = m.read(n)
    except Exception as e:
        print(n, 'errore', e); continue
    if d:
        open(os.path.join('data_map/raw', n.split(BS)[-1]), 'wb').write(d)
        print(n, len(d))
    else:
        print(n, 'non presente')
