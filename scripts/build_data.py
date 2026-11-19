#!/usr/bin/env python3
"""Build data/hero-data.json from raw YGOPRODeck files.

Usage (run with -I so Python ignores stray modules in the current folder):
    python3 -I scripts/build_data.py --cards raw/cardinfo.json [--cards more.json ...] \
        --sets raw/cardsets.json --out data/hero-data.json [--html index.html]

Nothing is typed in by hand: every card, set and date comes from the input files.
Dates are the set-level `tcg_date` joined to each printing by set name.
"""
import argparse
import datetime
import json
import os
import re
import sys

RULE_VERSION = "2026.11.17-r1"
HERO_ARCHETYPES = ["HERO", "Elemental HERO", "Destiny HERO", "Evil HERO",
                   "Vision HERO", "Masked HERO", "Xtra HERO", "Contrast HERO"]
HEROIC_ARCHETYPES = ["Heroic"]

TOKEN_HERO = re.compile(r"\bHERO\b")                  # capital letters only
WORD_HERO = re.compile(r"\bheroe?s?\b", re.I)          # Hero / hero / Heroes
QUOTED_HERO = re.compile(r'"[^"]*\bHERO\b[^"]*"')      # effect mentions a HERO card/archetype
EN_SUFFIX = re.compile(r"^(?:EN[A-Z]*|E)?\d+$")        # IOC-104, LON-E059, BP02-EN179, SGX1-ENB04
DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def load_extras(path):
    """extra_cards.txt -> {normalised name: 'support' | 'related'}"""
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "|" not in line:
                    continue
                name, group = [x.strip() for x in line.rsplit("|", 1)]
                if group in ("support", "related"):
                    out[norm(name)] = group
    except OSError:
        pass
    return out


def load_cards(paths):
    merged = {}
    for p in paths:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        rows = raw["data"] if isinstance(raw, dict) else raw
        for c in rows:
            merged[c["id"]] = c          # same id twice -> keep the later file's copy
    return list(merged.values())


def classify(c, extras=None):
    name, arch, desc = c["name"], c.get("archetype"), c.get("desc", "")
    cat, why = classify_rules(name, arch, desc)
    g = (extras or {}).get(norm(name))
    if g and cat != "hero":      # a real HERO archetype card stays "hero"
        return g, "on your list (wiki): HERO " + ("support" if g == "support" else "related card")
    return cat, why


def classify_rules(name, arch, desc):
    if TOKEN_HERO.search(name):
        return "hero", 'name has the word HERO'
    if arch in HERO_ARCHETYPES:
        return "hero", f'archetype "{arch}"'
    if arch in HEROIC_ARCHETYPES:
        return "heroic", f'archetype "{arch}" (a different family from HERO)'
    if WORD_HERO.search(name):
        return "review", 'name has the word "Hero" but no HERO archetype'
    if QUOTED_HERO.search(desc):
        return "review", 'effect text mentions a HERO card or archetype'
    return "noise", 'no HERO word in the name and no HERO archetype'


def build(card_paths, sets_path, extras=None, candidates_path=None):
    cards = load_cards(card_paths)
    cand_ids = set()
    if candidates_path and os.path.exists(candidates_path):
        extra_cards = load_cards([candidates_path])
        cand_ids = {c["id"] for c in extra_cards}
        have = {c["id"] for c in cards}
        cards += [c for c in extra_cards if c["id"] not in have]
    with open(sets_path, encoding="utf-8") as f:
        sets_raw = json.load(f)
    set_by_name = {}
    for s in sets_raw:
        set_by_name.setdefault(s["set_name"], s)

    out_cards, used_sets, warnings = [], {}, []
    for c in sorted(cards, key=lambda x: x["name"].lower()):
        if c.get("archetype") in HEROIC_ARCHETYPES:
            continue    # "Heroic" is a different family; the owner removed it from the app
        cat, why = classify(c, extras)
        if c["id"] in cand_ids and cat in ("noise", "review"):
            cat = "mention"
            why = ('companion archetype "%s" (not a HERO archetype)' % c.get("archetype")
                   if c.get("archetype") in ("Neo-Spacian", "Neos") else 'effect text mentions HERO')
        printings = []
        for p in c.get("card_sets", []):
            sname, code = p["set_name"], p["set_code"]
            s = set_by_name.get(sname)
            if s is None:
                warnings.append(f'set not in cardsets file: {sname}')
                date = None
            else:
                d = s.get("tcg_date")
                date = d if d and DATE_FULL.match(d) else None
                used_sets[sname] = {"code": s["set_code"], "date": date, "n": s.get("num_of_cards")}
            suffix = code.split("-")[-1] if "-" in code else ""
            printings.append({
                "set": sname, "code": code, "rar": p.get("set_rarity", ""),
                "rc": p.get("set_rarity_code", ""),
                "en": bool(EN_SUFFIX.match(suffix)),
                "sd": sname.startswith("Speed Duel"),
            })
        # same (set, code, rarity) twice in the source -> keep both, tell the app by index
        seen = {}
        for pr in printings:
            k = (pr["set"], pr["code"], pr["rar"])
            seen[k] = seen.get(k, 0) + 1
            pr["k"] = f'{pr["set"]}|{pr["code"]}|{pr["rar"]}' + (f'#{seen[k]}' if seen[k] > 1 else "")
        arts = [im["id"] for im in c.get("card_images", []) if im.get("id")]   # file names: images/small/<id>.jpg, images/large/<id>.jpg
        out_cards.append({
            "id": c["id"], "name": c["name"], "type": c["type"], "kind": c["humanReadableCardType"],
            "frame": c["frameType"], "race": c.get("race"), "arch": c.get("archetype"),
            "attr": c.get("attribute"), "lvl": c.get("level"), "atk": c.get("atk"), "def": c.get("def"),
            "link": c.get("linkval"), "desc": c.get("desc", "").replace("\r", ""),
            "url": c.get("ygoprodeck_url"), "arts": arts,
            "cat": cat, "why": why, "p": printings,
        })
    return out_cards, used_sets, warnings, len(sets_raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", action="append", required=True)
    ap.add_argument("--sets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--extras", default="extra_cards.txt")
    ap.add_argument("--candidates", default="raw/candidates_cardinfo.json")
    ap.add_argument("--html", help="index.html whose embedded snapshot should be refreshed")
    a = ap.parse_args()

    cards, used_sets, warnings, n_sets_file = build(a.cards, a.sets, load_extras(a.extras), a.candidates)
    data = {
        "schema": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule_version": RULE_VERSION,
        "source": {"cards_in_file": len(cards), "sets_in_file": n_sets_file,
                   "provider": "YGOPRODeck API v7 (cardinfo.php, cardsets.php)"},
        "rules": {"hero_archetypes": HERO_ARCHETYPES, "heroic_archetypes": HEROIC_ARCHETYPES},
        "sets": used_sets,
        "cards": cards,
    }
    # Do not touch the files when only the build timestamp would change
    try:
        with open(a.out, encoding="utf-8") as f:
            old = json.load(f)
        if {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in data.items() if k != "generated_at"}:
            print("No real change in cards or sets - files left as they are.")
            return
    except (OSError, ValueError):
        pass
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    if a.html:
        with open(a.html, encoding="utf-8") as f:
            html = f.read()
        blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        pat = re.compile(r"(<!--SEED-START-->).*?(<!--SEED-END-->)", re.S)
        if not pat.search(html):
            sys.exit("index.html has no SEED markers")
        html = pat.sub(lambda m: m.group(1) + '<script id="seed-data" type="application/json">' + blob + "</script>" + m.group(2), html)
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(html)

    cats = {}
    for c in cards:
        cats[c["cat"]] = cats.get(c["cat"], 0) + 1
    print("cards:", len(cards), cats)
    print("printings:", sum(len(c["p"]) for c in cards), "| sets used:", len(used_sets))
    for w in sorted(set(warnings)):
        print("WARNING:", w)


if __name__ == "__main__":
    main()
