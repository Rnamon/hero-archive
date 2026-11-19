#!/usr/bin/env python3
"""Download the raw data files from YGOPRODeck into raw/.

NOT TESTED by the author (the build environment had no access to the site).
Run it on your own computer or in GitHub Actions, then run build_data.py.

    python3 -I scripts/fetch_sources.py raw
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://db.ygoprodeck.com/api/v7/"
UA = "hero-archive-web/1.0 (personal collection tracker; GitHub Pages)"
# Same list as HERO_ARCHETYPES in build_data.py. The page's own file was a name search for "hero";
# these extra queries also bring HERO-archetype cards whose names do not contain the word.
ARCHETYPES = ["HERO", "Elemental HERO", "Destiny HERO", "Evil HERO", "Vision HERO",
              "Masked HERO", "Xtra HERO", "Contrast HERO", "Heroic"]
PAUSE = 1.5   # seconds between requests (the provider's limit is much higher)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return None          # the API answers 400 when a query matches nothing
        raise                    # 403/429 etc: stop, never hammer the server


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    sets = get(BASE + "cardsets.php")
    with open(os.path.join(outdir, "cardsets.json"), "w", encoding="utf-8") as f:
        json.dump(sets, f, ensure_ascii=False)
    print("sets:", len(sets))
    queries = [("fname", "hero")] + [("archetype", a) for a in ARCHETYPES]
    merged = {}
    for key, val in queries:
        time.sleep(PAUSE)
        res = get(BASE + "cardinfo.php?" + urllib.parse.urlencode({key: val}))
        rows = (res or {}).get("data", [])
        print(f"{key}={val}: {len(rows)} cards")
        for c in rows:
            merged[c["id"]] = c
    if not merged:
        sys.exit("No cards downloaded - keeping the old files.")
    root = os.path.dirname(os.path.abspath(outdir))
    fetch_extras(merged, os.path.join(root, "extra_cards.txt"), outdir)
    with open(os.path.join(outdir, "cardinfo.json"), "w", encoding="utf-8") as f:
        json.dump({"data": list(merged.values())}, f, ensure_ascii=False)
    print("total unique cards:", len(merged))
    cards_for_images = list(merged.values())
    cand = os.path.join(outdir, "candidates_cardinfo.json")
    if os.path.exists(cand):
        with open(cand, encoding="utf-8") as f:
            cards_for_images += json.load(f)["data"]
    download_images(cards_for_images, os.path.join(os.path.dirname(os.path.abspath(outdir)), "images"))


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def fetch_extras(merged, path, outdir):
    """Cards named in extra_cards.txt that the archetype queries did not return."""
    names = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "|" in line:
                    names.append(line.rsplit("|", 1)[0].strip())
    except OSError:
        return
    have = {_norm(c["name"]) for c in merged.values()}
    missing = []
    for name in names:
        if _norm(name) in have:
            continue
        time.sleep(PAUSE)
        res = get(BASE + "cardinfo.php?" + urllib.parse.urlencode({"fname": name}))
        hits = [c for c in (res or {}).get("data", []) if _norm(c["name"]) == _norm(name)]
        if hits:
            merged[hits[0]["id"]] = hits[0]
            have.add(_norm(name))
        else:
            missing.append(name)
    print(f"extra names: {len(names)} listed, {len(missing)} not found in the database")
    with open(os.path.join(outdir, "extra_not_found.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(missing))


def download_images(cards, imgdir):
    """Each image is downloaded ONCE and kept in images/ (the provider asks not to hotlink)."""
    for kind, field in (("small", "image_url_small"), ("large", "image_url")):
        os.makedirs(os.path.join(imgdir, kind), exist_ok=True)
    done = skipped = 0
    for c in cards:
        for im in c.get("card_images", []):
            for kind, field in (("small", "image_url_small"), ("large", "image_url")):
                dest = os.path.join(imgdir, kind, f"{im['id']}.jpg")
                if os.path.exists(dest) or not im.get(field):
                    skipped += 1
                    continue
                time.sleep(0.2)
                req = urllib.request.Request(im[field], headers={"User-Agent": UA})
                try:
                    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                        f.write(r.read())
                    done += 1
                except urllib.error.HTTPError as e:
                    if e.code in (403, 429):
                        sys.exit(f"Stopped: HTTP {e.code} while downloading images (never retried).")
                    print("image failed:", im[field], e.code)
    print(f"images: {done} downloaded, {skipped} already there")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "raw")
