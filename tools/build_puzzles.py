"""Turn the articles cached by fetch_wiki.py into daily puzzle files (standard library only).

    python tools/build_puzzles.py            # add new puzzles after the existing ones
    python tools/build_puzzles.py --rebuild  # throw away site/puzzles and schedule from scratch

Puzzle No. 1 is START. Each day gets site/puzzles/<n>.json and site/puzzles/meta.json
records the start date and how many files exist. Existing files are never rewritten
unless --rebuild is given, because people may already have played them.
A readable summary of every puzzle goes to .cache/report.txt for checking by eye.
"""
import datetime, html, json, os, random, re, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "puzzles")
START = datetime.date(2026, 11, 10)
MINW, MAXW = 150, 380          # words of intro text a puzzle should have
MAX_LOCKED = 0.16              # reject if more than this share of words stays hidden until the end
SKIP_PREFIX = ("History of ", "List of ", "Outline of ", "Timeline of ", "Index of ")

# Same filler words the page reveals first; they are never hidden as title words.
STOP = set(("a an the of and or but nor in on at to for from by with as is was were are be been being it its "
            "this that these those which who whom whose what when where while than then there their they them he she his her him "
            "has have had not no also such into onto over under about after before during between among against through up down "
            "out off one two three first second other some more most many much can could may might will would should do does did "
            "so if each any all both only same very known called used including well").split())
ROMAN = re.compile(r"^(?=[ivxl]+$)m{0,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()


def norm_guess(s):  # mirrors normGuess() in site/index.html
    s = fold(s).replace("&", " and ")
    s = re.sub(r"[.'’]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"^(the|a|an) ", "", s)


def tokens(s):
    return re.findall(r"[^\W_]+", s)


def locked(k, hide):  # mirrors locked() in site/index.html
    return any(k == h or k == h + "s" or k == h + "es" or (len(h) >= 5 and k.startswith(h[:-1]) and len(k) <= len(h) + 3)
               for h in hide)


# ---------- text cleaning ----------
IPA = set("əˈˌːɪʊʃʒθðŋɑɒɔæɛʌɜɡʔɹɐɨʉɯɤøœɶʏɵɘɞɚɝɾɽʎʟɲɳɴʀʁχħʕɦɕʑçʝɣβɸʂʐʈɖɟʋⁿˀʰʲʷ̃")
# Pronunciation respellings such as ok-TOP-ə-də, DAY-kart, sur-VAN-teez: short syllables, one in capitals.
RESPELL = re.compile(r"^(?=.*[A-Z]{2})(?=.*[a-zə])[A-Za-zə]{1,5}(?:-[A-Za-zə]{1,5})+$")
OPEN, CLOSE = "\x01", "\x02"  # stand-ins for brackets already cleaned, so outer brackets can be cleaned next


def latin_only(s):
    for c in s:
        if c.isalpha() and not ("LATIN" in unicodedata.name(c, "") or c in IPA):
            return False
    return True


def junk_bit(bit):
    """True for the parts of a bracket that are pronunciation, sound files or other scripts."""
    t = " ".join(w for w in bit.split() if not RESPELL.match(w.strip(",;:")))
    t = t.strip()
    if not t or re.match(r"^-\w+$", t):
        return True
    if any(c in IPA for c in t) or re.search(r"/[^/\s][^/]*/", t) or not latin_only(t):
        return True
    if re.match(r"^(also|or|uk|us|uk also|us also|ipa|audio|listen|pronounced|pronunciation)\b\W*$", t, re.I):
        return True
    if re.match(r"^(pronounced|listen)\b", t, re.I):
        return True
    if re.match(r"^[\w .]{1,25}:\s*$", t):  # a label like "Chinese:" whose value was removed
        return True
    return False


def clean_brackets(text):
    def fix(m):
        inner = m.group(1).replace("⁠", "")
        out = []
        for s in re.split(r"\s*;\s*", inner):
            bits = [" ".join(w for w in b.split() if not RESPELL.match(w.strip(",;:")))
                    for b in re.split(r"\s*,\s*", s) if not junk_bit(b)]
            if bits and not junk_bit(", ".join(bits)):
                out.append(", ".join(bits))
        return OPEN + "; ".join(out) + CLOSE if out else ""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\(([^()]*)\)", fix, text)
    text = re.sub(r"\[[^\[\]]*\]", lambda m: "" if any(c in IPA for c in m.group(0)) else m.group(0), text)
    return text.replace(OPEN, "(").replace(CLOSE, ")")


def clean(text):
    text = clean_brackets(text.replace("⁠", ""))
    text = re.sub(r"\(\s*[;,]?\s*\)", "", text)
    text = re.sub(r"\(\s*[;,]\s*", "(", text)
    text = re.sub(r"\s*[;,]\s*\)", ")", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" ([,.;:])", r"\1", text)
    text = re.sub(r"([,;])\1+", r"\1", text)
    text = re.sub(r",\.", ".", text)
    text = re.sub(r"(?<![.\s])\.\.(?!\.)", ".", text)
    return text


def trim(paras):
    keep, n = [], 0
    for para in paras:
        w = len(para.split())
        if keep and (n >= 200 or n + w > MAXW):
            break
        keep.append(para)
        n += w
    return keep, n


def split_paras(extract):
    return [p.strip() for p in clean(extract).split("\n") if p.strip() and len(p.split()) > 3]


# ---------- answers and hidden words ----------
def display_title(title):
    return re.sub(r"\s*\([^)]*\)$", "", title).strip()


def bold_terms(intro_html):
    for p in re.findall(r"<p[^>]*>(.*?)</p>", intro_html, re.S):
        text = re.sub(r"<[^>]+>", "", p).strip()
        if not text:
            continue
        out = []
        for b in re.findall(r"<b>(.*?)</b>", p, re.S):
            b = html.unescape(re.sub(r"<[^>]+>", "", b)).strip()
            if b and len(b.split()) <= 6 and latin_only(b):
                out.append(b)
        return out
    return []


SUFFIXES = ("ization", "isation", "ation", "ology", "ism", "ist", "ity", "ian", "ese", "ics", "ical", "ic", "al", "y", "e", "s")


def stem(h):
    """Strip endings like -ism, -ian, -al (colonialism -> coloni, confucianism -> confuc)."""
    while True:
        for s in SUFFIXES:
            if h.endswith(s) and len(h) - len(s) >= 5:
                h = h[:-len(s)]
                break
        else:
            return h


def derived(h, vocab):
    """Words in the article that are forms of hidden word h (plurals, adjectives, compounds)."""
    out = set()
    if len(h) < 3 or h in STOP or ROMAN.match(h) or h.isdigit():
        return out
    vocab = [k for k in vocab if k not in STOP]
    pfx = len(h) if len(h) <= 4 else 4 if len(h) <= 7 else max(5, len(h) - 4)
    cap = len(h) + (5 if len(h) <= 4 else 6)
    st = stem(h)
    st = st[:max(5, len(st) - 1)] if len(st) < len(h) else None
    for k in vocab:
        if len(h) >= 4 and h in k:
            out.add(k)
        elif k.startswith(h[:pfx]) and len(k) <= cap:
            out.add(k)
        elif st and k.startswith(st) and len(k) <= cap:
            out.add(k)
        elif (len(k) >= 5 and k in h) or (len(k) >= 4 and h.startswith(k)):
            out.add(k)
    return out


def answers_and_hide(title, section, bolds, paras, df, overrides):
    disp = display_title(title)
    tw = [w for w in tokens(fold(disp)) if w not in STOP]
    accept = [norm_guess(disp), norm_guess(title)]
    base = set(w for w in tw if not ROMAN.match(w) or len(w) > 1)
    for b in bolds:
        nb = norm_guess(b)
        if nb and any(w not in STOP for w in nb.split()):
            accept.append(nb)
        for w in tokens(fold(b)):
            if w in STOP or len(w) < 2:
                continue
            if w in tw or df.get(w, 0) <= 0.25:  # skip very common words like "history" from long bold phrases
                base.add(w)
    if section == "People":
        words = disp.split()
        if " the " in f" {disp} ":
            accept.append(norm_guess(words[0]))
        elif len(words) > 1:
            last = [w for w in words if not ROMAN.match(fold(w).strip(".")) and fold(w).strip(".") not in ("jr", "sr")]
            if last and last[-1] != words[0]:
                accept.append(norm_guess(last[-1]))
            if last != words:
                accept.append(norm_guess(" ".join(last)))
    o = overrides.get(title, {})
    accept += [norm_guess(a) for a in o.get("accept", [])]
    base |= set(fold(w) for w in o.get("hide", []))
    for key, forms in overrides.get("_related", {}).items():
        if key in base:
            base |= set(forms)
    vocab = set(fold(w) for p in paras for w in tokens(p))
    hide = set(base)
    for h in base:
        hide |= derived(h, vocab)
    hide -= set(o.get("show", []))
    accept = list(dict.fromkeys(a for a in accept if a))
    return disp, accept, sorted(hide)


# ---------- images ----------
def image_of(info, file):
    if not info or not info.get("thumburl"):
        return None
    if not info.get("mime", "").startswith("image/"):
        return None
    meta = info.get("extmetadata", {})
    val = lambda k: (meta.get(k) or {}).get("value", "")
    artist = html.unescape(re.sub(r"<[^>]+>", " ", val("Artist")))
    artist = re.sub(r"\s+", " ", artist.split("\n")[0]).strip()
    artist = re.sub(r"^(Original author|Author|Photographer)\s*:\s*", "", artist, flags=re.I)
    if not artist:
        artist = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", val("Credit")))).strip() or "Unknown author"
    if len(artist) > 70:
        artist = artist[:67].rstrip(" ,;") + "…"
    lic = re.sub(r"\s+", " ", html.unescape(val("LicenseShortName"))).strip() or "see file page"
    return {"src": info["thumburl"].split("?")[0], "width": info.get("thumbwidth"), "height": info.get("thumbheight"),
            "artist": artist, "license": lic, "licenseUrl": val("LicenseUrl") or None, "page": info["descriptionurl"]}


# ---------- main ----------
def main():
    rebuild = "--rebuild" in sys.argv
    pages = json.load(open(os.path.join(ROOT, ".cache", "articles.json"), encoding="utf-8"))
    seed = json.load(open(os.path.join(ROOT, "tools", "seed.json"), encoding="utf-8"))
    overrides = json.load(open(os.path.join(ROOT, "tools", "overrides.json"), encoding="utf-8"))
    exclude = set(overrides.get("_exclude", []))

    texts = {t: trim(split_paras(p["extract"]))[0] for t, p in pages.items()}
    df = {}
    for paras in texts.values():
        for w in set(fold(w) for para in paras for w in tokens(para)):
            df[w] = df.get(w, 0) + 1
    df = {w: c / len(texts) for w, c in df.items()}

    puzzles, rejects = {}, []
    seed_titles = [s["title"] for s in seed]
    for s in seed:
        p = pages[s["title"]]
        paras = [clean(x) for x in s["paras"]]
        hide = sorted(set(s["hide"]) | set(overrides.get(s["title"], {}).get("hide", [])))
        puzzles[s["title"]] = {"title": s["title"], "url": s["url"], "accept": s["accept"], "hide": hide,
                               "paras": paras, "image": image_of(p["imageinfo"], p["image_file"]), "section": p["section"]}
    for t, p in sorted(pages.items()):
        if t in puzzles:
            continue
        why = None
        paras = texts[t]
        n = sum(len(x.split()) for x in paras)
        img = image_of(p["imageinfo"], p["image_file"])
        if t in exclude or p["listed_as"] in exclude:
            why = "excluded by hand"
        elif t.startswith(SKIP_PREFIX):
            why = "list-like title"
        elif not img:
            why = "no free lead image"
        elif not MINW <= n <= MAXW:
            why = f"{n} words"
        elif len([w for w in tokens(display_title(t)) if fold(w) not in STOP]) > 4:
            why = "title too long to guess"
        if why:
            rejects.append((t, why))
            continue
        disp, accept, hide = answers_and_hide(t, p["section"], bold_terms(p["html"]), paras, df, overrides)
        words = [fold(w) for para in paras for w in tokens(para)]
        share = sum(locked(w, hide) for w in words) / len(words)
        if share > MAX_LOCKED:
            rejects.append((t, f"{share:.0%} of words hidden for good"))
            continue
        puzzles[t] = {"title": disp, "url": p["url"], "accept": accept, "hide": hide, "paras": paras, "image": img,
                      "section": p["section"]}

    os.makedirs(OUT, exist_ok=True)
    existing = {}
    if rebuild:
        for f in os.listdir(OUT):
            os.remove(os.path.join(OUT, f))
    else:
        for f in os.listdir(OUT):
            if re.match(r"^\d+\.json$", f):
                existing[int(f[:-5])] = json.load(open(os.path.join(OUT, f), encoding="utf-8"))
    used = {e["url"] for e in existing.values()}
    order = [puzzles[t] for t in seed_titles if puzzles[t]["url"] not in used]
    rest = [p for t, p in sorted(puzzles.items()) if t not in seed_titles and p["url"] not in used]
    random.Random(f"wiki-blackout-{len(existing)}").shuffle(rest)
    last = existing[max(existing)]["section"] if existing else None
    while rest:  # avoid two puzzles from the same part of the list on consecutive days
        prev = order[-1]["section"] if order else last
        i = next((i for i, p in enumerate(rest) if p["section"] != prev), 0)
        order.append(rest.pop(i))

    n0 = max(existing, default=0)
    for i, p in enumerate(order, start=n0 + 1):
        p = dict(no=i, date=str(START + datetime.timedelta(days=i - 1)), **p)
        json.dump(p, open(os.path.join(OUT, f"{i}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        existing[i] = p
    count = max(existing, default=0)
    json.dump({"start": str(START), "count": count}, open(os.path.join(OUT, "meta.json"), "w"))

    with open(os.path.join(ROOT, ".cache", "report.txt"), "w", encoding="utf-8") as r:
        for i in sorted(existing):
            p = existing[i]
            words = [fold(w) for para in p["paras"] for w in tokens(para)]
            share = sum(locked(w, p["hide"]) for w in words) / len(words)
            r.write(f"#{i} {p['date']} {p['title']} [{p['section']}] {len(words)}w hidden={share:.0%}\n"
                    f"  accept: {p['accept']}\n  hide: {p['hide']}\n  img: {p['image']['artist']} | {p['image']['license']}\n"
                    f"  text: {' / '.join(p['paras'])[:400]}\n\n")
        r.write("\nREJECTED\n" + "\n".join(f"{t}: {w}" for t, w in rejects))
    print(f"{len(order)} new puzzles, {count} in total (last day {START + datetime.timedelta(days=count - 1)}); "
          f"{len(rejects)} candidates rejected")


if __name__ == "__main__":
    main()
