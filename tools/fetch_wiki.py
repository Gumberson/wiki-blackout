"""Download candidate articles from Wikipedia into .cache/ (standard library only).

Candidates are the Level 3 vital articles, the 12 seed puzzles, and any titles listed
in tools/extra_titles.txt (one per line). Every API response is cached, so re-running
only fetches what is missing. Use --refresh to fetch everything again.

    python tools/fetch_wiki.py
"""
import json, os, re, sys, time, hashlib, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
API = "https://en.wikipedia.org/w/api.php"
UA = "WikiBlackout/1.0 (https://github.com/Gumberson/wiki-blackout; daily puzzle generator)"
REFRESH = "--refresh" in sys.argv
_last = [0.0]


def api(params):
    """GET the API with caching and at most about one request per second."""
    params = dict(params, format="json", formatversion="2")
    q = urllib.parse.urlencode(sorted(params.items()))
    path = os.path.join(CACHE, "api", hashlib.sha1(q.encode()).hexdigest()[:16] + ".json")
    if os.path.exists(path) and not REFRESH:
        return json.load(open(path, encoding="utf-8"))
    wait = 1.1 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            break
        except Exception as e:  # retry slowly on network hiccups or rate limits
            if attempt == 3:
                raise
            print("  retrying after error:", e)
            time.sleep(5 * (attempt + 1))
    _last[0] = time.time()
    if "error" in data:
        raise RuntimeError(data["error"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return data


def vital_level3():
    """Return [(title, section)] from Wikipedia:Vital articles/Level 3."""
    text = api({"action": "parse", "page": "Wikipedia:Vital articles/Level 3", "prop": "wikitext", "redirects": "1"})["parse"]["wikitext"]
    out, section = [], ""
    for line in text.splitlines():
        h = re.match(r"^==\s*([^=].*?)\s*==\s*$", line)
        if h:
            section = h.group(1)
            continue
        if line.startswith("*") and "{{Icon" in line:
            m = re.search(r"\[\[([^\]|#]+)", line)
            if m and ":" not in m.group(1):
                out.append((m.group(1).strip(), section))
    return out


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def main():
    os.makedirs(CACHE, exist_ok=True)
    seed = json.load(open(os.path.join(ROOT, "tools", "seed.json"), encoding="utf-8"))
    cands = {t: s for t, s in vital_level3()}
    print(len(cands), "vital articles")
    extra = os.path.join(ROOT, "tools", "extra_titles.txt")
    if os.path.exists(extra):
        for line in open(extra, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                cands.setdefault(line.strip(), "Extra")
    for s in seed:
        cands.setdefault(s["title"], "Seed")
    titles = sorted(cands)

    pages = {}
    for i, batch in enumerate(chunks(titles, 20)):
        print(f"intros {i * 20 + len(batch)}/{len(titles)}")
        common = {"action": "query", "titles": "|".join(batch), "redirects": "1"}
        # Plain text for the puzzle, HTML only to read which names the lead puts in bold.
        plain = api(dict(common, prop="extracts|pageimages|info", exintro="1", explaintext="1", exlimit="20",
                         piprop="name", pilicense="free", pilimit="50", inprop="url"))
        html = api(dict(common, prop="extracts", exintro="1", exlimit="20"))
        alias = {}
        for k in ("normalized", "redirects"):
            for r in plain["query"].get(k, []):
                alias[r["from"]] = r["to"]
        hmap = {p["title"]: p.get("extract", "") for p in html["query"]["pages"]}
        for t in batch:
            real = alias.get(alias.get(t, t), alias.get(t, t))
            p = next((p for p in plain["query"]["pages"] if p["title"] == real), None)
            if not p or "missing" in p:
                print("  missing:", t)
                continue
            pages[p["title"]] = {"title": p["title"], "listed_as": t, "section": cands[t], "url": p["fullurl"],
                                 "extract": p.get("extract", ""), "html": hmap.get(p["title"], ""),
                                 "image_file": p.get("pageimage")}

    # Seed puzzles keep the image the prototype used.
    for s in seed:
        if s["title"] in pages:
            pages[s["title"]]["image_file"] = s["image_file"].replace(" ", "_")

    files = sorted({p["image_file"] for p in pages.values() if p["image_file"]})
    info = {}
    for i, batch in enumerate(chunks(files, 20)):
        print(f"images {i * 20 + len(batch)}/{len(files)}")
        r = api({"action": "query", "titles": "|".join("File:" + f for f in batch), "prop": "imageinfo",
                 "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "500",
                 "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|AttributionRequired|Credit"})
        alias = {n["to"]: n["from"] for n in r["query"].get("normalized", [])}
        for p in r["query"]["pages"]:
            if p.get("imageinfo"):
                key = alias.get(p["title"], p["title"])[5:].replace(" ", "_")
                info[key] = p["imageinfo"][0]
    for p in pages.values():
        p["imageinfo"] = info.get(p["image_file"]) if p["image_file"] else None

    json.dump(pages, open(os.path.join(CACHE, "articles.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(len(pages), "articles saved,", sum(1 for p in pages.values() if p["imageinfo"]), "with a free image")


if __name__ == "__main__":
    main()
