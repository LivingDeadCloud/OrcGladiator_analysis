"""Estrae le icone delle 10 classi giocate (icona del bottone dell'eroe) e le salva come PNG.

Uso (dalla cartella principale del progetto):
    python estrai_icone.py [file_mappa.w3x] [cartella_file_gioco]
Default: la mappa in replay_originali/ o presentazione/, i file del gioco in replay_originali/gioco/
(war3.mpq, War3x.mpq, War3Patch.mpq). Serve Pillow (legge i .blp).
Output: presentazione/sorgente/icone/<classe>.png (64x64) e icone/icone.csv con l'origine di ogni icona.

Le icone personalizzate (War Hammer, Druid Staff) sono dentro la mappa; le altre sono icone standard del gioco.
"""
import csv, glob, io, os, sys
from objdata import parse_obj, parse_wts
from mpq import MPQ
from PIL import Image

OUT = os.path.join('presentazione', 'sorgente', 'icone')


def trova_mappa():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for pat in ('replay_originali/*.w3x', 'replay_originali/**/*.w3x', 'presentazione/*.w3x'):
        f = glob.glob(pat, recursive=True)
        if f:
            return f[0]
    raise SystemExit('Mappa .w3x non trovata: passala come primo argomento.')


def main():
    os.makedirs(OUT, exist_ok=True)
    gioco = sys.argv[2] if len(sys.argv) > 2 else os.path.join('replay_originali', 'gioco')
    archivi = [MPQ(trova_mappa())]
    for nome in ('War3Patch.mpq', 'War3x.mpq', 'war3.mpq'):   # stesso ordine di priorita' del gioco
        p = os.path.join(gioco, nome)
        if os.path.exists(p):
            archivi.append(MPQ(p))
    nomi_archivi = ['mappa'] + [n for n in ('War3Patch.mpq', 'War3x.mpq', 'war3.mpq') if os.path.exists(os.path.join(gioco, n))]

    wts = parse_wts(open('data_map/raw/war3map.wts', 'rb').read())
    w3u = parse_obj(open('data_map/raw/war3map.w3u', 'rb').read(), 'w3u', wts)
    righe = []
    for r in csv.DictReader(open('data_map/class_roles.csv', encoding='utf-8')):
        mods = {f: v for (f, _l), v in w3u[r['pick_code']]['mods'].items()}
        ico = mods.get('uico', '')
        dati, fonte = None, ''
        for nome, arc in zip(nomi_archivi, archivi):
            dati = arc.read(ico)
            if dati:
                fonte = nome
                break
        dest = os.path.join(OUT, r['classe'].lower().replace(' ', '_') + '.png')
        if dati:
            img = Image.open(io.BytesIO(dati)).convert('RGBA').resize((64, 64), Image.LANCZOS)
            img.save(dest)
        righe.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'icona_gioco': ico, 'fonte': fonte or 'NON TROVATA',
                      'file': os.path.basename(dest) if dati else ''})
        print(f"{r['classe']:14s} {fonte or 'NON TROVATA':12s} {ico}")
    with open(os.path.join(OUT, 'icone.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, list(righe[0]))
        w.writeheader()
        w.writerows(righe)
    mancanti = [x['classe'] for x in righe if not x['file']]
    if mancanti:
        print('\nMancano', len(mancanti), 'icone: copia war3.mpq, War3x.mpq e War3Patch.mpq in', gioco)


if __name__ == '__main__':
    main()
