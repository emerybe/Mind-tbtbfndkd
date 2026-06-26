#!/usr/bin/env python3
"""
Hotfix a Pocket GM 3 2016 roster JSON:
- Removes/keeps out modern players from the playable 2016 base/free-agent pool.
- Forces future players into draft-class-only records.
- Rebuilds development curves so star/fast/normal dev are clear and not severe regression.
- Recalibrates low in-game OVR cases by giving position-relevant attributes a sane floor.
- Specifically fixes Joe Schobert so he should not display as a 55.

Usage:
  python fix_pgm3_2016_roster.py input.json output.json
"""
import json, sys, re
from pathlib import Path

MODERN_NAMES = {
    # Known contaminants that should never be in 2016 free agency/base roster
    ("quenton", "nelson"), ("quentin", "nelson"), ("denzel", "ward"),
    ("derwin", "james"), ("vita", "vea"), ("baker", "mayfield"),
    ("saquon", "barkley"), ("josh", "allen"), ("lamar", "jackson"),
    ("fred", "warner"), ("roquan", "smith"), ("minkah", "fitzpatrick"),
    ("bradley", "chubb"), ("tremaine", "edmunds"), ("jessie", "bates"),
    ("nick", "bosa"), ("kyler", "murray"), ("deebo", "samuel"),
    ("dk", "metcalf"), ("aj", "brown"), ("a.j.", "brown"),
    ("joe", "burrow"), ("justin", "herbert"), ("justin", "jefferson"),
    ("ceedee", "lamb"), ("micah", "parsons"), ("trevor", "lawrence"),
    ("ja'marr", "chase"), ("jamar", "chase"), ("penei", "sewell"),
    ("patrick", "surtain"), ("jalen", "waddle"), ("drake", "maye"),
    ("brock", "bowers"), ("aidan", "hutchinson"), ("will", "anderson"),
    ("trenton", "mcduffie"), ("trent", "mcduffie"),
}

ATTRS = ["vision","burst","ballSecurity","zoneCover","tackle","ballStrip","sPassAcc","mPassAcc","dPassAcc","rushBlock","routeRun","trucking","discipline","speed","intelligence","blockShedding","catching","decisions","agility","throwOnRun","jumping","passBlock","elusiveness","releaseLine","power","kickAccuracy","skillMove","manCover","stamina"]
POS_ATTRS = {
    "QB": ["vision","sPassAcc","mPassAcc","dPassAcc","throwOnRun","decisions","intelligence","discipline","power","speed","burst","agility","stamina"],
    "RB": ["vision","burst","ballSecurity","trucking","speed","agility","elusiveness","power","skillMove","catching","routeRun","decisions","stamina"],
    "WR": ["catching","routeRun","releaseLine","speed","burst","agility","jumping","ballSecurity","elusiveness","vision","decisions","stamina"],
    "TE": ["catching","routeRun","releaseLine","rushBlock","passBlock","power","speed","burst","ballSecurity","trucking","stamina"],
    "OT": ["passBlock","rushBlock","power","releaseLine","intelligence","decisions","discipline","stamina","burst","agility"],
    "OG": ["passBlock","rushBlock","power","releaseLine","intelligence","decisions","discipline","stamina","burst","agility"],
    "C":  ["passBlock","rushBlock","power","releaseLine","intelligence","decisions","discipline","stamina","burst","agility"],
    "DE": ["tackle","blockShedding","skillMove","power","burst","speed","agility","releaseLine","ballStrip","discipline","stamina"],
    "DT": ["tackle","blockShedding","power","releaseLine","ballStrip","burst","strength","skillMove","discipline","stamina"],
    "OLB":["tackle","blockShedding","skillMove","power","burst","speed","agility","zoneCover","manCover","ballStrip","discipline","intelligence","decisions","stamina"],
    "MLB":["tackle","blockShedding","zoneCover","manCover","speed","burst","power","ballStrip","discipline","intelligence","decisions","stamina"],
    "CB": ["manCover","zoneCover","speed","burst","agility","jumping","tackle","ballStrip","catching","discipline","decisions","stamina"],
    "S":  ["zoneCover","manCover","tackle","speed","burst","agility","jumping","ballStrip","catching","power","discipline","decisions","stamina"],
    "K":  ["kickAccuracy","power","discipline","stamina"],
    "P":  ["kickAccuracy","power","discipline","stamina"],
}

def norm(s):
    return re.sub(r"[^a-z0-9']", "", str(s).strip().lower())

def fullname(p):
    return (norm(p.get('forename','')), norm(p.get('surname','')))

def dev_curve(dev, age):
    # 31-value safe Pocket GM curve: no brutal -500/-1000 regression values.
    if dev == "star":
        base = [260,240,220,190,165,140,115,90,70,50,35,20,10,0,0,-5,-10,-20,-30,-45,-60,-75,-90,-105,-120,-135,-150,-165,-180,-195,-210]
    elif dev == "fast":
        base = [170,150,130,110,90,70,50,35,20,10,0,0,0,-5,-10,-20,-35,-50,-65,-80,-95,-110,-125,-140,-155,-170,-185,-200,-215,-225,-225]
    else:
        base = [90,80,65,50,35,25,15,5,0,0,0,0,0,-5,-10,-20,-35,-50,-65,-80,-95,-110,-125,-140,-155,-170,-185,-200,-215,-225,-225]
    if age >= 30:
        base = [min(x, 25) if i < 8 else min(x, -5) for i, x in enumerate(base)]
        base[-10:] = [-180,-195,-210,-225,-240,-250,-250,-250,-250,-250]
    return base[:31]

def infer_dev(p):
    rating = int(p.get('rating', 60) or 60); pot = int(p.get('potential', rating) or rating)
    age = int(p.get('age', 25) or 25); pick = int(p.get('draftNum', 999) or 999)
    ds = int(p.get('draftSeason', 0) or 0)
    if rating >= 88 or pot >= 92 or (ds >= 2017 and (pick <= 10 or pot >= 92)):
        return "star"
    if rating >= 78 or pot >= 84 or (ds >= 2017 and pick <= 64) or (age <= 24 and pot >= 80):
        return "fast"
    return "normal"

def calibrate_attributes(p):
    pos = str(p.get('position','')).upper()
    rating = int(p.get('rating', 60) or 60)
    pot = int(p.get('potential', rating) or rating)
    keys = POS_ATTRS.get(pos, [])
    # Set relevant attributes near/above rating; leave irrelevant at 0 unless already meaningful.
    floor = max(58, rating)
    for k in ATTRS:
        if k not in p:
            p[k] = 0
    for k in keys:
        if k in p:
            cur = int(p.get(k) or 0)
            p[k] = max(cur, min(99, floor))
    for k in ["discipline","intelligence","decisions","stamina"]:
        p[k] = max(int(p.get(k) or 0), min(99, max(60, rating)))
    # Specific Schobert correction: Madden-style 65 OVR but Pocket GM attribute formula should not drag him to 55.
    if fullname(p) == ("joe", "schobert"):
        p["position"] = "OLB"
        p["teamID"] = "CLE"
        p["age"] = 22
        p["rating"] = 65
        p["potential"] = max(int(p.get('potential', 0) or 0), 72)
        for k in ["tackle","blockShedding","skillMove","power","burst","speed","agility","zoneCover","manCover","ballStrip","discipline","intelligence","decisions","stamina","releaseLine"]:
            p[k] = max(int(p.get(k) or 0), 66)
        p["growthType"] = dev_curve("fast", 22)
    return p

def fix_roster(data):
    # Most PGM imports are a list; if wrapped, find the largest list of player dicts.
    container_key = None
    players = data
    if isinstance(data, dict):
        list_keys = [(k, v) for k,v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict) and 'forename' in v[0]]
        if list_keys:
            container_key, players = max(list_keys, key=lambda kv: len(kv[1]))
        else:
            raise ValueError('Could not find players array in JSON')
    if not isinstance(players, list):
        raise ValueError('Input JSON is not a player list or recognized roster object')

    fixed=[]; removed_modern_base=0; moved_future=0
    seen=set()
    for p in players:
        if not isinstance(p, dict):
            continue
        first,last = fullname(p)
        ds = int(p.get('draftSeason', 0) or 0)
        team = str(p.get('teamID',''))
        is_future = ds > 2016 or (first,last) in MODERN_NAMES
        if is_future:
            # Future players should exist only as future draft class records, never base/free agents.
            # Keep them only if draftSeason is 2017-2021; otherwise drop.
            if ds < 2017:
                # Known modern contaminant with wrong historical draftSeason: remove entirely.
                removed_modern_base += 1
                continue
            p['teamID'] = 'Rookie'
            p['teamNum'] = 0
            p['salary'] = 0; p['guarantee'] = 0; p['length'] = 0
            p['eSalary'] = 0; p['eGuarantee'] = 0; p['eLength'] = 0
            moved_future += 1
        p = calibrate_attributes(p)
        dev = infer_dev(p)
        p['growthType'] = dev_curve(dev, int(p.get('age',25) or 25))
        # Required sanity keys
        for k in ['iden','forename','surname','position','age','teamID','teamNum','rating','potential','salary','guarantee','length','eSalary','eGuarantee','eLength','draftSeason','draftNum','loyalty','greed','ambition','injuryProne','growthType','appearance']:
            if k not in p:
                if k == 'appearance': p[k] = ["Head1a","Eyes1a","Hair1a","Beard1a","Eyebrows1a","Nose1a","Mouth1a","Glasses1e","Clothes1"]
                elif k == 'iden': p[k] = f"FIXED-{len(fixed):06d}"
                elif k in ['forename','surname','position','teamID']: p[k] = ''
                elif k == 'growthType': p[k] = dev_curve('normal',25)
                else: p[k] = 0
        identity = (norm(p.get('forename')), norm(p.get('surname')), str(p.get('position')), int(p.get('draftSeason') or 0), int(p.get('draftNum') or 0), str(p.get('teamID')))
        if identity in seen:
            continue
        seen.add(identity)
        fixed.append(p)
    if container_key:
        data[container_key] = fixed
        out = data
    else:
        out = fixed
    return out, {'players_out': len(fixed), 'future_moved_to_rookie': moved_future, 'modern_wrong_year_removed': removed_modern_base}

def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    inp, outp = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(inp.read_text(encoding='utf-8-sig'))
    fixed, report = fix_roster(data)
    outp.write_text(json.dumps(fixed, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    report_path = outp.with_suffix('.report.json')
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
