"""Goalytical API test: fetches upcoming fixtures from football-data.org and
checks that team names can be matched to the names in our results files."""
import difflib, io, os, re
import pandas as pd, requests
import backtest as bt

API = "https://api.football-data.org/v4/competitions/{c}/matches"
COMPS = {"E0": "PL", "E1": "ELC", "D1": "BL1"}
DROP = {"fc", "afc", "cf", "sc", "fk", "sv", "vfl", "vfb", "tsg", "fsv", "bsc", "ssv", "sg", "1", "04", "05", "09", "96", "98", "ac", "as", "us", "ss", "rc", "ud", "cd"}
ALIASES = {"manchester united": "man united", "manchester city": "man city", "newcastle united": "newcastle",
           "wolverhampton wanderers": "wolves", "tottenham hotspur": "tottenham",
           "nottingham forest": "nott'm forest", "west ham united": "west ham", "leeds united": "leeds",
           "brighton and hove albion": "brighton", "bayern munchen": "bayern munich",
           "borussia monchengladbach": "m'gladbach", "eintracht frankfurt": "ein frankfurt"}


def norm(s):
    s = s.lower().replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("é", "e")
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    s = " ".join(t for t in s.split() if t not in DROP)
    return ALIASES.get(s, s)


def csv_teams(lg):
    df = pd.read_csv(io.StringIO(bt.fetch(lg, "2627")), on_bad_lines="skip")
    return sorted(set(df.HomeTeam.dropna()) | set(df.AwayTeam.dropna()))


def match_name(team, csv_names):
    cands = [team["name"], team.get("shortName") or "", team.get("tla") or ""]
    by_norm = {norm(c): c for c in csv_names}
    for c in cands:
        if norm(c) in by_norm:
            return by_norm[norm(c)], "exact"
    for c in cands:
        n = norm(c)
        if len(n) >= 4:
            for k, v in by_norm.items():
                if k and (k in n or n in k):
                    return v, "contains"
    best = difflib.get_close_matches(norm(team["name"]), list(by_norm), n=1, cutoff=0.6)
    if best:
        return by_norm[best[0]], "fuzzy"
    return None, "NO MATCH"


def main():
    token = os.environ.get("TOKEN", "")
    lines = ["# Goalytical API test\n"]
    now = pd.Timestamp.now(tz="UTC")
    for lg, code in COMPS.items():
        r = requests.get(API.format(c=code), headers={"X-Auth-Token": token}, timeout=60)
        lines.append(f"## {bt.LEAGUES[lg]} ({code}): HTTP {r.status_code}\n")
        if r.status_code != 200:
            lines.append(f"Problem: {r.text[:300]}\n")
            continue
        ms = r.json().get("matches", [])
        up = [m for m in ms if m["status"] in ("SCHEDULED", "TIMED")]
        up.sort(key=lambda m: m["utcDate"])
        nxt = [m for m in up if pd.Timestamp(m["utcDate"]) <= now + pd.Timedelta(days=14)]
        names = csv_teams(lg)
        lines.append(f"Fixtures in season: {len(ms)}. Upcoming: {len(up)}. In next 14 days: {len(nxt)}. Teams in results file: {len(names)}.\n")
        lines.append("| kick-off (UTC) | matchday | API home | API away | matched home | matched away |\n|---|---|---|---|---|---|")
        seen = {}
        for m in nxt[:20]:
            h, hm = match_name(m["homeTeam"], names)
            a, am = match_name(m["awayTeam"], names)
            seen[m["homeTeam"]["name"]] = (h, hm)
            seen[m["awayTeam"]["name"]] = (a, am)
            lines.append(f"| {m['utcDate']} | {m.get('matchday')} | {m['homeTeam']['name']} | {m['awayTeam']['name']} | {h} ({hm}) | {a} ({am}) |")
        allteams = {}
        for m in ms:
            for t in (m["homeTeam"], m["awayTeam"]):
                if t.get("name"):
                    allteams[t["name"]] = t
        lines.append("\n### Name matching for every team in the season\n")
        lines.append("| API name | results-file name | how |\n|---|---|---|")
        bad = 0
        for nm, t in sorted(allteams.items()):
            c, how = match_name(t, names)
            bad += c is None
            lines.append(f"| {nm} | {c} | {how} |")
        lines.append(f"\nUnmatched teams: {bad}\n")
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(text)


if __name__ == "__main__":
    main()
