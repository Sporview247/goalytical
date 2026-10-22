"""Goalytical data engine.
Downloads results (football-data.co.uk) and fixtures (football-data.org), builds league
tables and form, runs our goals model on every upcoming match, and writes data/site.json.
No odds are read or stored."""
import datetime as dt, io, json, math, os, re, time
import numpy as np, pandas as pd, requests
from scipy.optimize import minimize
from scipy.special import gammaln

UA = "GoalyticalBot/1.0 (football statistics research)"
CSV_URL = "https://www.football-data.co.uk/mmz4281/{s}/{l}.csv"
API_URL = "https://api.football-data.org/v4/competitions/{c}/matches"
HISTORY = ["2324", "2425", "2526", "2627"]
LEAGUES = {
    "E0": {"name": "Premier League", "slug": "premier-league", "api": "PL"},
    "E1": {"name": "Championship", "slug": "championship", "api": "ELC"},
    "D1": {"name": "Bundesliga", "slug": "bundesliga", "api": "BL1"},
}
XI, REG, RHO, WINDOW_DAYS, MAXG, FIXTURE_DAYS = 0.002, 3.0, -0.05, 1100, 10, 21

BACKTEST = {
    "period": "2023/24 to 2025/26", "matches": 3714,
    "settings": "decay 0.002, ridge 3.0, rho -0.05",
    "model": {"correct": 49.5, "brier": 0.6057, "rps": 0.2085, "logloss": 1.0119},
    "base_rates": {"correct": 43.3, "brier": 0.6510, "rps": 0.2307, "logloss": 1.0754},
    "equal": {"brier": 0.6667, "rps": 0.2355, "logloss": 1.0986},
    "leagues": [
        {"name": "Premier League", "matches": 1140, "correct": 52.8, "brier": 0.5839, "base_brier": 0.6503},
        {"name": "Bundesliga", "matches": 918, "correct": 51.5, "brier": 0.5918, "base_brier": 0.6547},
        {"name": "Championship", "matches": 1656, "correct": 46.0, "brier": 0.6284, "base_brier": 0.6494},
    ],
    "calibration": [
        ["0.0-0.1", 175, 0.076, 0.063], ["0.1-0.2", 1120, 0.162, 0.151], ["0.2-0.3", 4734, 0.255, 0.262],
        ["0.3-0.4", 2076, 0.345, 0.345], ["0.4-0.5", 1515, 0.447, 0.432], ["0.5-0.6", 852, 0.543, 0.526],
        ["0.6-0.7", 450, 0.642, 0.676], ["0.7-0.8", 168, 0.743, 0.774], ["0.8-0.9", 47, 0.836, 0.851],
    ],
}

TEAM_MAP = {
    "AFC Bournemouth": "Bournemouth", "Arsenal FC": "Arsenal", "Aston Villa FC": "Aston Villa",
    "Brentford FC": "Brentford", "Brighton & Hove Albion FC": "Brighton", "Chelsea FC": "Chelsea",
    "Coventry City FC": "Coventry", "Crystal Palace FC": "Crystal Palace", "Everton FC": "Everton",
    "Fulham FC": "Fulham", "Hull City AFC": "Hull", "Ipswich Town FC": "Ipswich", "Leeds United FC": "Leeds",
    "Liverpool FC": "Liverpool", "Manchester City FC": "Man City", "Manchester United FC": "Man United",
    "Newcastle United FC": "Newcastle", "Nottingham Forest FC": "Nott'm Forest", "Sunderland AFC": "Sunderland",
    "Tottenham Hotspur FC": "Tottenham",
    "Birmingham City FC": "Birmingham", "Blackburn Rovers FC": "Blackburn", "Bolton Wanderers FC": "Bolton",
    "Bristol City FC": "Bristol City", "Burnley FC": "Burnley", "Cardiff City FC": "Cardiff",
    "Charlton Athletic FC": "Charlton", "Derby County FC": "Derby", "Lincoln City FC": "Lincoln",
    "Middlesbrough FC": "Middlesbrough", "Millwall FC": "Millwall", "Norwich City FC": "Norwich",
    "Portsmouth FC": "Portsmouth", "Preston North End FC": "Preston", "Queens Park Rangers FC": "QPR",
    "Sheffield United FC": "Sheffield United", "Southampton FC": "Southampton", "Stoke City FC": "Stoke",
    "Swansea City AFC": "Swansea", "Watford FC": "Watford", "West Bromwich Albion FC": "West Brom",
    "West Ham United FC": "West Ham", "Wolverhampton Wanderers FC": "Wolves", "Wrexham AFC": "Wrexham",
    "1. FC Köln": "FC Koln", "1. FC Union Berlin": "Union Berlin", "1. FSV Mainz 05": "Mainz",
    "Bayer 04 Leverkusen": "Leverkusen", "Borussia Dortmund": "Dortmund", "Borussia Mönchengladbach": "M'gladbach",
    "Eintracht Frankfurt": "Ein Frankfurt", "FC Augsburg": "Augsburg", "FC Bayern München": "Bayern Munich",
    "FC Schalke 04": "Schalke 04", "Hamburger SV": "Hamburg", "RB Leipzig": "RB Leipzig", "SC Freiburg": "Freiburg",
    "SC Paderborn 07": "Paderborn", "SV 07 Elversberg": "Elversberg", "SV Werder Bremen": "Werder Bremen",
    "TSG 1899 Hoffenheim": "Hoffenheim", "VfB Stuttgart": "Stuttgart",
}
DROP = {"fc", "afc", "cf", "sc", "fk", "sv", "vfl", "vfb", "tsg", "fsv", "bsc", "ssv", "sg", "ac", "as", "us", "ss", "rc", "ud", "cd"}
WARNINGS = {}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("ü", "u").replace("ö", "o")).strip("-")


def norm(s):
    s = s.lower().replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("é", "e")
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    return " ".join(t for t in s.split() if t not in DROP)


def csv_name(team, known):
    if team["name"] in TEAM_MAP:
        return TEAM_MAP[team["name"]]
    by = {norm(k): k for k in known}
    for c in (team["name"], team.get("shortName") or ""):
        if norm(c) in by:
            WARNINGS[team["name"]] = f"Auto-matched {team['name']} -> {by[norm(c)]} (add to TEAM_MAP)"
            return by[norm(c)]
    raise SystemExit(f"Cannot match team name: {team['name']}. Add it to TEAM_MAP in scripts/pipeline.py")


def decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1").lstrip("\ufeff")


def load_results(lg):
    frames = []
    opt = ["HS", "AS", "HST", "AST", "HC", "AC"]
    for s in HISTORY:
        r = requests.get(CSV_URL.format(s=s, l=lg), headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(decode(r.content)), on_bad_lines="skip")
        df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
        base = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
        df = df[base + [c for c in opt if c in df.columns]].dropna(subset=base).copy()
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["Date"])
        df["Season"] = s
        frames.append(df)
        time.sleep(1.0)
    d = pd.concat(frames, ignore_index=True)
    d[["FTHG", "FTAG"]] = d[["FTHG", "FTAG"]].astype(int)
    for c in opt:
        d[c] = pd.to_numeric(d[c], errors="coerce") if c in d.columns else np.nan
    return d.sort_values("Date").reset_index(drop=True)


def fit(df, ref):
    teams = sorted(set(df.HomeTeam) | set(df.AwayTeam))
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    hi, ai = df.HomeTeam.map(ix).values, df.AwayTeam.map(ix).values
    hg, ag = df.FTHG.values, df.FTAG.values
    w = np.exp(-XI * (ref - df.Date).dt.days.values)

    def f(p):
        mu, h, a, d = p[0], p[1], p[2:2 + n], p[2 + n:]
        lh, la = mu + h + a[hi] - d[ai], mu + a[ai] - d[hi]
        eh, ea = np.exp(lh), np.exp(la)
        ll = (w * (hg * lh - eh + ag * la - ea)).sum()
        rh, ra = w * (hg - eh), w * (ag - ea)
        g = np.zeros_like(p)
        g[0], g[1] = -(rh.sum() + ra.sum()), -rh.sum()
        g[2:2 + n] = -(np.bincount(hi, rh, n) + np.bincount(ai, ra, n)) + 2 * REG * a
        g[2 + n:] = np.bincount(ai, rh, n) + np.bincount(hi, ra, n) + 2 * REG * d
        return -ll + REG * (a @ a + d @ d), g

    x0 = np.zeros(2 + 2 * n)
    x0[0] = math.log(max((hg.mean() + ag.mean()) / 2, 0.5))
    return {"p": minimize(f, x0, jac=True, method="L-BFGS-B").x, "n": n, "ix": ix}


def score_matrix(m, home, away):
    p, n, ix = m["p"], m["n"], m["ix"]
    g = lambda name, off: p[2 + off + ix[name]] if name in ix else 0.0
    lh, la = math.exp(p[0] + p[1] + g(home, 0) - g(away, n)), math.exp(p[0] + g(away, 0) - g(home, n))
    k = np.arange(MAXG + 1)
    M = np.outer(np.exp(k * math.log(lh) - lh - gammaln(k + 1)), np.exp(k * math.log(la) - la - gammaln(k + 1)))
    M[0, 0] *= 1 - lh * la * RHO
    M[0, 1] *= 1 + lh * RHO
    M[1, 0] *= 1 + la * RHO
    M[1, 1] *= 1 - RHO
    return M / M.sum(), lh, la


def pct3(P):
    raw = np.array(P) * 100
    out = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - out))[: 100 - out.sum()]:
        out[i] += 1
    return [int(x) for x in out]


def build_table(cur):
    T = {}
    for r in cur.sort_values("Date").itertuples():
        for team, opp, gf, ga, home, sh, sha, sot, cor in (
            (r.HomeTeam, r.AwayTeam, r.FTHG, r.FTAG, True, r.HS, r.AS, r.HST, r.HC),
            (r.AwayTeam, r.HomeTeam, r.FTAG, r.FTHG, False, r.AS, r.HS, r.AST, r.AC),
        ):
            t = T.setdefault(team, {"team": team, "slug": slug(team), "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0,
                                    "Pts": 0, "CS": 0, "FTS": 0, "H": [0, 0, 0, 0, 0, 0], "A": [0, 0, 0, 0, 0, 0],
                                    "shots": 0.0, "shots_n": 0, "sot": 0.0, "corners": 0.0, "form": [], "last": []})
            res = "W" if gf > ga else ("D" if gf == ga else "L")
            t["P"] += 1
            t[res] += 1
            t["GF"] += gf
            t["GA"] += ga
            t["Pts"] += 3 if res == "W" else (1 if res == "D" else 0)
            t["CS"] += ga == 0
            t["FTS"] += gf == 0
            s = t["H" if home else "A"]
            s[0] += 1
            s[1 + "WDL".index(res)] += 1
            s[4] += gf
            s[5] += ga
            if not math.isnan(sh):
                t["shots"] += sh
                t["shots_n"] += 1
                t["sot"] += 0 if math.isnan(sot) else sot
                t["corners"] += 0 if math.isnan(cor) else cor
            t["form"].append(res)
            t["last"].append({"date": r.Date.strftime("%Y-%m-%d"), "opp": opp, "venue": "H" if home else "A", "gf": int(gf), "ga": int(ga), "res": res})
    rows = []
    for t in T.values():
        n = max(t["P"], 1)
        t["GD"] = t["GF"] - t["GA"]
        t["ppg"] = round(t["Pts"] / n, 2)
        t["gf_pm"], t["ga_pm"] = round(t["GF"] / n, 2), round(t["GA"] / n, 2)
        t["shots_pm"] = round(t["shots"] / t["shots_n"], 1) if t["shots_n"] else None
        t["form"], t["last"] = t["form"][-5:], t["last"][-5:][::-1]
        t["CS"], t["FTS"] = int(t["CS"]), int(t["FTS"])
        for k in ("shots", "shots_n", "sot", "corners"):
            t.pop(k)
        rows.append(t)
    rows.sort(key=lambda t: (-t["Pts"], -t["GD"], -t["GF"], t["team"]))
    for i, t in enumerate(rows, 1):
        t["pos"] = i
    return rows


def h2h(d, a, b):
    m = d[((d.HomeTeam == a) & (d.AwayTeam == b)) | ((d.HomeTeam == b) & (d.AwayTeam == a))].tail(5)
    return [{"date": r.Date.strftime("%Y-%m-%d"), "home": r.HomeTeam, "away": r.AwayTeam, "hg": int(r.FTHG), "ag": int(r.FTAG)} for r in m.itertuples()][::-1]


LOG_PATH = "data/log.json"


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def update_log(log, lg, fixtures, cur, base, now):
    """Freeze our latest pre-kick-off prediction for each match, then attach results."""
    for f in fixtures:
        if pd.Timestamp(f["utc"]) <= now:
            continue
        e = log.get(f["id"])
        if e is None or (e.get("result") is None and e["pct"] != f["pct"]):
            log[f["id"]] = {"id": f["id"], "lg": lg, "home": f["home"], "away": f["away"], "utc": f["utc"],
                            "pct": f["pct"], "proj": f["proj"], "base": base,
                            "logged": now.strftime("%Y-%m-%d %H:%M"), "result": None}
    for e in log.values():
        if e["lg"] != lg or e.get("result") is not None:
            continue
        ko = pd.Timestamp(e["utc"]).tz_convert(None)
        m = cur[(cur.HomeTeam == e["home"]) & (cur.AwayTeam == e["away"]) &
                ((cur.Date - ko.normalize()).abs() <= pd.Timedelta(days=2))]
        if len(m):
            r = m.iloc[-1]
            e["result"] = {"hg": int(r.FTHG), "ag": int(r.FTAG)}
        elif ko < now.tz_convert(None) - pd.Timedelta(days=30):
            e["result"] = {"void": True}


def record_summary(log):
    rows = [e for e in log.values() if e.get("result") and "hg" in e["result"]]

    def stats(rs):
        if not rs:
            return None
        br, bb, hit = [], [], 0
        for e in rs:
            hg, ag = e["result"]["hg"], e["result"]["ag"]
            y = 0 if hg > ag else (1 if hg == ag else 2)
            P, O, b = np.array(e["pct"]) / 100, np.eye(3)[y], np.array(e["base"])
            br.append(((P - O) ** 2).sum())
            bb.append(((b - O) ** 2).sum())
            hit += int(P.argmax() == y)
        return {"matches": len(rs), "correct": round(100 * hit / len(rs), 1),
                "brier": round(float(np.mean(br)), 4), "base_brier": round(float(np.mean(bb)), 4)}

    rec = sorted(rows, key=lambda e: e["utc"], reverse=True)
    played = []
    for e in rec:
        hg, ag = e["result"]["hg"], e["result"]["ag"]
        y = 0 if hg > ag else (1 if hg == ag else 2)
        played.append({"id": e["id"], "lg": e["lg"], "home": e["home"], "away": e["away"], "utc": e["utc"],
                       "pct": e["pct"], "proj": e["proj"], "hg": hg, "ag": ag, "called": bool(np.argmax(e["pct"]) == y)})
    return {"all": stats(rows), "leagues": {k: stats([e for e in rows if e["lg"] == k]) for k in LEAGUES},
            "pending": sum(1 for e in log.values() if e.get("result") is None)}, played[:60]


def main():
    token = os.environ.get("TOKEN", "")
    now = pd.Timestamp.now(tz="UTC")
    today = now.normalize()
    log = load_json(LOG_PATH, {})
    old_log = json.dumps(log, sort_keys=True)
    out = {"season": "2026/27", "leagues": {}, "backtest": BACKTEST}
    lines = ["# Goalytical data engine\n"]
    for lg, info in LEAGUES.items():
        d = load_results(lg)
        cur = d[d.Season == HISTORY[-1]]
        ref = d.Date.max() + pd.Timedelta(days=1)
        win = d[d.Date >= ref - pd.Timedelta(days=WINDOW_DAYS)]
        m = fit(win, ref)
        games = pd.concat([win.HomeTeam, win.AwayTeam]).value_counts().to_dict()
        hd, dr = float((win.FTHG > win.FTAG).mean()), float((win.FTHG == win.FTAG).mean())
        base = [round(hd, 3), round(dr, 3), round(1 - hd - dr, 3)]
        table = build_table(cur)
        known = set(d.HomeTeam) | set(d.AwayTeam)
        r = requests.get(API_URL.format(c=info["api"]), headers={"X-Auth-Token": token},
                         params={"dateFrom": today.strftime("%Y-%m-%d"), "dateTo": (today + pd.Timedelta(days=FIXTURE_DAYS)).strftime("%Y-%m-%d")}, timeout=60)
        r.raise_for_status()
        fixtures = []
        for x in sorted(r.json().get("matches", []), key=lambda x: x["utcDate"]):
            if x["status"] not in ("SCHEDULED", "TIMED"):
                continue
            h, a = csv_name(x["homeTeam"], known), csv_name(x["awayTeam"], known)
            M, lh, la = score_matrix(m, h, a)
            P = [np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()]
            top = sorted([(M[i, j], i, j) for i in range(5) for j in range(5)], reverse=True)[:5]
            day = x["utcDate"][:10].replace("-", "")
            fixtures.append({
                "id": f"{slug(h)}-vs-{slug(a)}-{day}", "utc": x["utcDate"], "matchday": x.get("matchday"),
                "home": h, "away": a, "home_slug": slug(h), "away_slug": slug(a), "pct": pct3(P),
                "proj": [round(lh, 2), round(la, 2)], "top": [[int(i), int(j), round(float(p) * 100, 1)] for p, i, j in top],
                "grid": [[round(float(M[i, j]) * 100, 1) for j in range(5)] for i in range(5)],
                "new": [t for t in (h, a) if t not in m["ix"]], "h2h": h2h(d, h, a),
                "games": [int(games.get(h, 0)), int(games.get(a, 0))],
                "limited": [t for t in (h, a) if games.get(t, 0) < 20],
            })
        update_log(log, lg, fixtures, cur, base, now)
        n = len(cur)
        avg = {"matches": n, "goals_pm": round((cur.FTHG.sum() + cur.FTAG.sum()) / max(n, 1), 2),
               "home_win": round(100 * (cur.FTHG > cur.FTAG).mean()) if n else 0,
               "draw": round(100 * (cur.FTHG == cur.FTAG).mean()) if n else 0}
        avg["away_win"] = 100 - avg["home_win"] - avg["draw"] if n else 0
        out["leagues"][lg] = {"code": lg, "name": info["name"], "slug": info["slug"], "table": table, "fixtures": fixtures, "averages": avg}
        lines.append(f"## {info['name']}\n")
        lines.append(f"Results used: {len(d)} (this season: {n}). Teams in table: {len(table)}. Upcoming fixtures stored: {len(fixtures)}.\n")
        lines.append("| # | team | P | GD | Pts | form |\n|---|---|---|---|---|---|")
        for t in table[:5]:
            lines.append(f"| {t['pos']} | {t['team']} | {t['P']} | {t['GD']:+d} | {t['Pts']} | {''.join(t['form'])} |")
        lines.append("\n| kick-off (UTC) | match | H | D | A | proj goals | top score | limited data | last meetings |\n|---|---|---|---|---|---|---|---|---|")
        for f in fixtures[:4]:
            lines.append(f"| {f['utc']} | {f['home']} v {f['away']} | {f['pct'][0]} | {f['pct'][1]} | {f['pct'][2]} | {f['proj'][0]}-{f['proj'][1]} | {f['top'][0][0]}-{f['top'][0][1]} ({f['top'][0][2]}%) | {', '.join(f['limited'])} | {len(f['h2h'])} |")
        lines.append("")
    record, played = record_summary(log)
    out["record"], out["played"] = record, played
    lines.append(f"## Prediction log\n\nEntries: {len(log)}. Scored so far: {record['all']['matches'] if record['all'] else 0}. Waiting for results: {record['pending']}.\n")
    if WARNINGS:
        lines.append("## Warnings\n")
        lines += [f"- {w}" for w in WARNINGS.values()]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(text)
    os.makedirs("data", exist_ok=True)
    if json.dumps(log, sort_keys=True) != old_log:
        json.dump(log, open(LOG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("data/log.json updated")
    path = "data/site.json"
    old = None
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
            old.pop("generated_at", None)
        except Exception:
            old = None
    if old != out:
        out["generated_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("data/site.json updated")
    else:
        print("No data changes")


if __name__ == "__main__":
    main()
