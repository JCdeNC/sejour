"""Vitrine Expériences : copie les photos du catalogue Studio Devis dans experiences/img/.

Lit l'onglet Journées du Google Sheet catalogue, télécharge une version JPEG allégée
de chaque photo (Drive ou URL) et met à jour experiences/img/photos.json.
Une photo n'est retéléchargée que si son lien a changé dans le catalogue.
"""
import csv, hashlib, io, json, os, re, time, urllib.parse, urllib.request

CATALOGUE = ('https://docs.google.com/spreadsheets/d/1yJUIECBA8HIP6g_5p6hqw0hYN081tVXihU9KkVvl2G8'
             '/gviz/tq?tqx=out:csv&headers=1&sheet=' + urllib.parse.quote('Journées'))
DOSSIER = os.path.join(os.path.dirname(__file__), '..', 'experiences', 'img')
MANIFESTE = os.path.join(DOSSIER, 'photos.json')
LARGEUR = 800


def lire(url, essais=5):
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (vitrine-photos)'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.headers.get('Content-Type', ''), r.read()
        except Exception as e:  # 429 ou coupure : on patiente puis on réessaie
            print('  essai', i + 1, 'échoué :', e)
            time.sleep(10 * (i + 1))
    raise RuntimeError('téléchargement impossible : ' + url)


def lien_image(url):
    url = (url or '').strip()
    m = re.search(r'drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=\w+&)?id=)([\w-]{20,})', url) or re.search(r'[?&]id=([\w-]{20,})', url)
    if m:
        return 'https://lh3.googleusercontent.com/d/%s=w%d-rj-l78' % (m.group(1), LARGEUR)
    if 'images.pexels.com' in url:
        return url.split('?')[0] + '?auto=compress&cs=tinysrgb&fit=crop&w=%d&h=%d' % (LARGEUR, LARGEUR * 3 // 4)
    return url if url.startswith('http') else ''


def colonne(ligne, motif):
    for k, v in ligne.items():
        if re.search(motif, k or '', re.I):
            return (v or '').strip()
    return ''


def main():
    os.makedirs(DOSSIER, exist_ok=True)
    try:
        ancien = json.load(open(MANIFESTE, encoding='utf-8'))
    except Exception:
        ancien = {}
    _, brut = lire(CATALOGUE)
    lignes = list(csv.DictReader(io.StringIO(brut.decode('utf-8'))))
    nouveau = {}
    for l in lignes:
        code = colonne(l, r'^code$').upper()
        if not code or not re.match(r'^oui$', colonne(l, r'^active$'), re.I) or 'TRANSFERT' in colonne(l, r'^type$').upper():
            continue
        src = colonne(l, r'^photo \(lien') or colonne(l, r'^photo 2')
        url = lien_image(src)
        if not url or not re.match(r'^[A-Z0-9-]+$', code):
            continue
        fichier = code + '.jpg'
        chemin = os.path.join(DOSSIER, fichier)
        if ancien.get(code, {}).get('src') == src and os.path.exists(chemin):
            nouveau[code] = ancien[code]
            continue
        print(code, '←', src)
        try:
            typ, data = lire(url)
        except Exception as e:
            print('  ignorée :', e)
            if code in ancien and os.path.exists(chemin):
                nouveau[code] = ancien[code]
            continue
        if not typ.startswith('image/') or len(data) < 2000:
            print('  ignorée : ce n’est pas une image (%s)' % typ)
            continue
        open(chemin, 'wb').write(data)
        nouveau[code] = {'src': src, 'f': fichier, 'v': hashlib.sha1(data).hexdigest()[:8]}
        time.sleep(2)
    for f in os.listdir(DOSSIER):
        if f.endswith('.jpg') and f[:-4] not in nouveau:
            os.remove(os.path.join(DOSSIER, f))
            print('supprimée :', f)
    json.dump(nouveau, open(MANIFESTE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    print(len(nouveau), 'photos à jour')


if __name__ == '__main__':
    main()
