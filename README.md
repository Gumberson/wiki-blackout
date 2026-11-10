# Wiki Blackout

A daily guessing game. Everyone gets the same blacked-out Wikipedia article each day; uncover more of it (and sharpen its picture) step by step, and name it as early as you can.

The website is the plain static folder `site/`. There is no build step: `site/index.html` is the whole game, and it downloads only today's puzzle from `site/puzzles/<n>.json`. Every push to `main` republishes the site through `.github/workflows/pages.yml`.

## Folders

- `site/` – the website (game page plus one small JSON file per day).
- `tools/` – Python scripts that make the puzzles. They use only the standard library.
- `prototype/` – the original claude.ai prototype, kept for reference.

## Try it on your computer

```
python -m http.server 8000 --directory site
```

Then open http://localhost:8000.

## How puzzles are made

1. `python tools/fetch_wiki.py` downloads Wikipedia's Level 3 "Vital articles" (about 1,000 topics), plus the 12 starting puzzles in `tools/seed.json` and any titles listed in `tools/extra_titles.txt`. It asks for 20 intros per request, about one request per second, and keeps only lead images with a free licence. Everything is cached in `.cache/` (not committed).
2. `python tools/build_puzzles.py` cleans each intro (removes pronunciations and other-script spellings), keeps articles with 150–380 words and a free image, works out which guesses count as right and which words stay hidden until the end, and writes one file per day. It also writes `.cache/report.txt` so you can read every puzzle by eye.

Puzzle No. 1 is 10 November 2026. There are currently 804 puzzles, enough until January 2029. If they ever run out, the site starts again from No. 1.

## Adding more puzzles

1. Put the article titles you want, one per line, in `tools/extra_titles.txt`.
2. Run `python tools/fetch_wiki.py`, then `python tools/build_puzzles.py`.
3. Commit and push.

New puzzles are added after the last existing day. Existing days are never changed, because people may already have played them. (`--rebuild` starts the whole schedule from scratch; only use it before anyone is playing.)

## Fixing a puzzle by hand

`tools/overrides.json` holds manual fixes: titles to skip (`_exclude`), related words to hide alongside a title word (`_related`, e.g. sun → solar), and per-article `accept`, `hide` or `show` lists. After editing it, rebuild. Days that already exist keep their files, so to fix one of those, edit its `site/puzzles/<n>.json` directly.

## Credits

Article text comes from Wikipedia under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); images come from Wikimedia Commons under their own free licences. Both are credited on the page once a puzzle is over. Wiki Blackout is fan-made and is not part of Wikipedia or the Wikimedia Foundation.

Answers are in the puzzle files, so anyone who digs into the site's files can find them. That's fine for a game among friends.
