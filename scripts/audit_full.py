#!/usr/bin/env python3
"""Coverage audit: compare data/hero-data.json with the FULL YGOPRODeck card database.

NOT TESTED by the author (the build environment cannot reach the site) - run it in GitHub Actions.
Writes:
  docs/COVERAGE_AUDIT.md          human-readable report
  raw/candidates_cardinfo.json    cards NOT in the app whose English-printed text mentions HERO,
                                  or that belong to companion archetypes (Neo-Spacian, Neos)
It never says "complete": it lists exactly what was checked and what was found.
"""
import datetime
import json
import os
import re
import sys
import urllib.request

URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
UA = "hero-archive-web/1.0 (personal collection tracker; GitHub Pages)"
HERO_ARCH = {"HERO", "Elemental HERO", "Destiny HERO", "Evil HERO", "Vision HERO", "Masked HERO",
             "Xtra HERO", "Contrast HERO"}
COMPANION = {"Neo-Spacian", "Neos"}
TOKEN = re.compile(r"\bHERO\b")
EN = re.compile(r"^(?:EN[A-Z]*|E)?\d+$")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def has_english(c):
    return any(EN.match(p["set_code"].split("-")[-1]) for p in c.get("card_sets", []) if "-" in p["set_code"])


def main():
    root = os.getcwd()
    with open(os.path.join(root, "data", "hero-data.json"), encoding="utf-8") as f:
        ours = json.load(f)
    our_ids = {c["id"] for c in ours["cards"]}
    scope = [c for c in ours["cards"] if c["cat"] in ("hero", "support", "related")]

    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as r:
        full = json.load(r)["data"]
    by_id = {c["id"]: c for c in full}
    if len(full) < 5000:
        sys.exit(f"Only {len(full)} cards came back - this does not look like the full database. Stopping.")

    # A. things that MUST be zero: rule matches in the full DB that the app does not have
    rule_missing = [c for c in full if c["id"] not in our_ids and
                    (TOKEN.search(c["name"]) or c.get("archetype") in HERO_ARCH)]
    # B. candidates: not in the app, has English print, text says HERO or companion archetype
    cands, kinds = [], {}
    for c in full:
        if c["id"] in our_ids or not has_english(c):
            continue
        if c.get("archetype") in COMPANION:
            cands.append(c); kinds[c["id"]] = "companion archetype"
        elif TOKEN.search(c.get("desc", "")):
            cands.append(c); kinds[c["id"]] = "text mentions HERO"
    cands = [c for c in cands if c not in rule_missing]
    # C. our cards that disappeared / changed id in the full DB
    gone = [c["name"] for c in ours["cards"] if c["id"] not in by_id]
    # D. in-scope cards with no English printing
    no_en = [c["name"] for c in scope if not any(p["en"] for p in c["p"])]
    # E. in-scope cards: does the full DB list more printings than we have?
    more = []
    for c in scope:
        f = by_id.get(c["id"])
        if f and len(f.get("card_sets", [])) != len(c["p"]):
            more.append((c["name"], len(c["p"]), len(f.get("card_sets", []))))

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    L = [f"# Coverage audit ({today})", "",
         "Compares the app's data with the full YGOPRODeck database. **This is not a proof of completeness.** "
         "'HERO' is defined by the provider's archetype field, the name, and card text; other sources may disagree.", "",
         f"- Cards in the full database: **{len(full)}**",
         f"- Cards in the app: **{len(ours['cards'])}** (in your scope: {len(scope)})",
         f"- **Rule matches missing from the app** (archetype in a HERO family, or the word HERO in the name): **{len(rule_missing)}**"]
    for c in rule_missing[:100]:
        L.append(f"  - {c['name']} ({c.get('archetype')})")
    L += [f"- Candidates added for your review (English print, not in the app): **{len(cands)}** "
          f"({sum(1 for k in kinds.values() if k == 'text mentions HERO')} mention HERO in text, "
          f"{sum(1 for k in kinds.values() if k == 'companion archetype')} Neo-Spacian/Neos)",
          f"- App cards missing from the full database now (renamed or removed): {len(gone)} {gone[:20]}",
          f"- In-scope cards with no English-looking printing: {len(no_en)} {no_en[:30]}",
          f"- In-scope cards where the printing count differs from the full database: {len(more)} {more[:20]}", "",
          "## Candidates", ""]
    for c in sorted(cands, key=lambda x: x["name"]):
        L.append(f"- {c['name']} - {kinds[c['id']]} - {c.get('archetype') or 'no archetype'}")
    os.makedirs(os.path.join(root, "docs"), exist_ok=True)
    with open(os.path.join(root, "docs", "COVERAGE_AUDIT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(root, "raw", "candidates_cardinfo.json"), "w", encoding="utf-8") as f:
        json.dump({"data": cands}, f, ensure_ascii=False)
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
