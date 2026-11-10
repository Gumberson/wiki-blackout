import json, sys, base64, re, os
raw, img = sys.argv[1], sys.argv[2]
data = json.load(open('data.json', encoding='utf-8'))
pi = {p['title']: p['pageimage'].replace('_', ' ') for p in json.load(open(raw + '/pageimages.json', encoding='utf-8'))['query']['pages']}
meta = {m['file'][5:]: m for m in json.load(open(img + '/meta.json', encoding='utf-8'))}
total = 0
for f in data:
    m = meta[pi[f['title']]]
    b = open(os.path.join(img, m['local']), 'rb').read()
    mime = 'image/png' if b[:4] == b'\x89PNG' else 'image/jpeg'
    artist = re.sub(r'\s+', ' ', m['artist'].splitlines()[0]).strip()
    artist = re.sub(r'^Original author:\s*', '', artist)
    if len(artist) > 70: artist = artist[:67].rstrip() + '…'
    f['image'] = {'src': f'data:{mime};base64,' + base64.b64encode(b).decode(), 'artist': artist, 'license': m['license'], 'page': m['page']}
    total += len(f['image']['src'])
    print(f['title'], '|', artist, '|', m['license'])
json.dump(data, open('data_img.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(total // 1024, 'KB of images')
