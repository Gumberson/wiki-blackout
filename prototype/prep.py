import json, re, sys
src, out = sys.argv[1], sys.argv[2]
pages = {p['title']: p for p in json.load(open(src, encoding='utf-8'))['query']['pages']}
# order = daily rotation; accept = answers that count; hide = words that stay blacked out until solved
spec = [
 ("Octopus", ["octopus","octopuses","octopi","octopodes"], ["octopus","octopuses","octopodes","octopi","octopoda"]),
 ("Mount Everest", ["everest","mount everest","mt everest","chomolungma","sagarmatha","qomolangma","jomolangma"], ["everest","chomolungma","sagarmatha","qomolangma","jomolangma","chamolangma"]),
 ("Coffee", ["coffee"], ["coffee","coffees"]),
 ("Chess", ["chess"], ["chess"]),
 ("Titanic", ["titanic","rms titanic"], ["titanic"]),
 ("Volcano", ["volcano","volcanoes","volcanos"], ["volcano","volcanoes","volcanic","volcanism"]),
 ("Leonardo da Vinci", ["leonardo","da vinci","leonardo da vinci","vinci"], ["leonardo","vinci"]),
 ("Honey", ["honey"], ["honey","honeys"]),
 ("Great Wall of China", ["great wall","great wall of china"], ["wall","walls","great"]),
 ("Piano", ["piano","pianoforte"], ["piano","pianos","pianoforte","pianist","pianists"]),
 ("Moon", ["moon","the moon","luna"], ["moon","moons","lunar","luna"]),
 ("Olympic Games", ["olympics","olympic games","olympic"], ["olympic","olympics","olympiad","olympia"]),
]
MAXW = 380
data = []
for title, accept, hide in spec:
    p = pages[title]
    t = p['extract']
    t = re.sub(r'\(\s*[;,]?\s*\)', '', t)           # empty brackets left by stripped pronunciations
    t = re.sub(r'\(\s*[;,]\s*', '(', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r' ([,.;:])', r'\1', t)
    paras = [x.strip() for x in t.split('\n') if x.strip()]
    keep, n = [], 0
    for para in paras:
        w = len(para.split())
        if keep and (n >= 200 or n + w > MAXW): break
        keep.append(para); n += w
    data.append({"title": title, "url": p['fullurl'], "accept": accept, "hide": hide, "paras": keep})
    print(f"{title}: {n} words, {len(keep)} paras | {keep[0][:160]}")
json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
