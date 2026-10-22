"""Goalytical backtest: tests our goals model on past seasons.
Uses only match results (no odds). Each prediction uses only matches played before it."""
import io, itertools, math, os, time
import numpy as np, pandas as pd, requests
from scipy.optimize import minimize
from scipy.special import gammaln

LEAGUES = {"E0": "Premier League", "E1": "Championship", "D1": "Bundesliga"}
SEASONS = ["1819", "1920", "2021", "2122", "2223", "2324", "2425", "2526"]
TEST_SEASONS = ["2324", "2425", "2526"]
UA = "GoalyticalBot/1.0 (football statistics research)"
BASE = "https://www.football-data.co.uk/mmz4281/{s}/{l}.csv"
XIS, REGS, RHOS = [0.0, 0.002, 0.004], [1.0, 3.0], [0.0, -0.05, -0.10]
WINDOW_DAYS, BLOCK, MIN_TRAIN, MAXG = 1100, 10, 150, 10


def fetch(league, season):
    r = requests.get(BASE.format(s=season, l=league), headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    return r.content.decode("latin-1")


def load():
    frames = []
    for lg in LEAGUES:
        for s in SEASONS:
            try:
                df = pd.read_csv(io.StringIO(fetch(lg, s)), on_bad_lines="skip")
                df = df[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]].dropna()
            except Exception as e:
                print("skipped", lg, s, e)
                continue
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Date"])
            df["League"], df["Season"] = lg, s
            frames.append(df)
            time.sleep(1.0)
    d = pd.concat(frames, ignore_index=True)
    d[["FTHG", "FTAG"]] = d[["FTHG", "FTAG"]].astype(int)
    return d.sort_values("Date").reset_index(drop=True)


def fit(df, ref, xi, reg):
    teams = sorted(set(df.HomeTeam) | set(df.AwayTeam))
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    hi, ai = df.HomeTeam.map(ix).values, df.AwayTeam.map(ix).values
    hg, ag = df.FTHG.values, df.FTAG.values
    w = np.exp(-xi * (ref - df.Date).dt.days.values)

    def f(p):
        mu, h, a, d = p[0], p[1], p[2:2 + n], p[2 + n:]
        lh, la = mu + h + a[hi] - d[ai], mu + a[ai] - d[hi]
        eh, ea = np.exp(lh), np.exp(la)
        ll = (w * (hg * lh - eh + ag * la - ea)).sum()
        rh, ra = w * (hg - eh), w * (ag - ea)
        g = np.zeros_like(p)
        g[0], g[1] = -(rh.sum() + ra.sum()), -rh.sum()
        g[2:2 + n] = -(np.bincount(hi, rh, n) + np.bincount(ai, ra, n)) + 2 * reg * a
        g[2 + n:] = np.bincount(ai, rh, n) + np.bincount(hi, ra, n) + 2 * reg * d
        return -ll + reg * (a @ a + d @ d), g

    x0 = np.zeros(2 + 2 * n)
    x0[0] = math.log(max((hg.mean() + ag.mean()) / 2, 0.5))
    res = minimize(f, x0, jac=True, method="L-BFGS-B")
    return {"p": res.x, "n": n, "ix": ix}


def probs(m, home, away, rho):
    p, n, ix = m["p"], m["n"], m["ix"]
    ah = p[2 + ix[home]] if home in ix else 0.0
    dh = p[2 + n + ix[home]] if home in ix else 0.0
    aa = p[2 + ix[away]] if away in ix else 0.0
    da = p[2 + n + ix[away]] if away in ix else 0.0
    lh, la = math.exp(p[0] + p[1] + ah - da), math.exp(p[0] + aa - dh)
    k = np.arange(MAXG + 1)
    M = np.outer(np.exp(k * math.log(lh) - lh - gammaln(k + 1)),
                 np.exp(k * math.log(la) - la - gammaln(k + 1)))
    M[0, 0] *= 1 - lh * la * rho
    M[0, 1] *= 1 + lh * rho
    M[1, 0] *= 1 + la * rho
    M[1, 1] *= 1 - rho
    M /= M.sum()
    return np.array([np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()])


def metrics(P, y):
    O = np.eye(3)[y]
    brier = ((P - O) ** 2).sum(1)
    rps = ((np.cumsum(P, 1)[:, :2] - np.cumsum(O, 1)[:, :2]) ** 2).sum(1) / 2
    ll = -np.log(np.clip(P[np.arange(len(y)), y], 1e-9, 1))
    return {"acc": (P.argmax(1) == y).mean() * 100, "brier": brier.mean(), "rps": rps.mean(), "ll": ll.mean()}


def run(d=None):
    d = load() if d is None else d
    rec = []
    for lg in LEAGUES:
        L = d[d.League == lg]
        idxs = list(L[L.Season.isin(TEST_SEASONS)].index)
        for s in range(0, len(idxs), BLOCK):
            blk = L.loc[idxs[s:s + BLOCK]]
            ref = blk.Date.min()
            tr = L[(L.Date < ref) & (L.Date >= ref - pd.Timedelta(days=WINDOW_DAYS))]
            if len(tr) < MIN_TRAIN:
                continue
            hd = (tr.FTHG > tr.FTAG).mean()
            dr = (tr.FTHG == tr.FTAG).mean()
            base = np.array([hd, dr, 1 - hd - dr])
            for xi, reg in itertools.product(XIS, REGS):
                m = fit(tr, ref, xi, reg)
                for r in blk.itertuples():
                    y = 0 if r.FTHG > r.FTAG else (1 if r.FTHG == r.FTAG else 2)
                    for rho in RHOS:
                        rec.append((lg, xi, reg, rho, probs(m, r.HomeTeam, r.AwayTeam, rho), y, base))
        print("done", lg, flush=True)
    df = pd.DataFrame(rec, columns=["lg", "xi", "reg", "rho", "P", "y", "B"])
    out = []
    out.append("# Goalytical model backtest\n")
    out.append(f"Matches tested per setting: {len(df[(df.xi == XIS[0]) & (df.reg == REGS[0]) & (df.rho == RHOS[0])])}. "
               "Each prediction used only earlier matches. No odds used.\n")
    rows = []
    for (xi, reg, rho), g in df.groupby(["xi", "reg", "rho"]):
        mt = metrics(np.vstack(g.P), g.y.values)
        rows.append((xi, reg, rho, mt))
    rows.sort(key=lambda r: r[3]["brier"])
    one = df[(df.xi == XIS[0]) & (df.reg == REGS[0]) & (df.rho == RHOS[0])]
    yb = one.y.values
    mb = metrics(np.vstack(one.B), yb)
    mu = metrics(np.full((len(yb), 3), 1 / 3), yb)
    out.append("## Settings compared (best first)\n")
    out.append("| decay | ridge | rho | correct % | Brier | RPS | log loss |\n|---|---|---|---|---|---|---|")
    for xi, reg, rho, mt in rows:
        out.append(f"| {xi} | {reg} | {rho} | {mt['acc']:.1f} | {mt['brier']:.4f} | {mt['rps']:.4f} | {mt['ll']:.4f} |")
    out.append(f"| baseline: past home/draw/away rates | | | {mb['acc']:.1f} | {mb['brier']:.4f} | {mb['rps']:.4f} | {mb['ll']:.4f} |")
    out.append(f"| baseline: equal chances | | | n/a | {mu['brier']:.4f} | {mu['rps']:.4f} | {mu['ll']:.4f} |\n")
    bx, br, bho, _ = rows[0]
    best = df[(df.xi == bx) & (df.reg == br) & (df.rho == bho)]
    out.append(f"## Best setting: decay {bx}, ridge {br}, rho {bho}\n")
    out.append("| league | matches | correct % | Brier | baseline Brier |\n|---|---|---|---|---|")
    for lg, g in best.groupby("lg"):
        mt, bt = metrics(np.vstack(g.P), g.y.values), metrics(np.vstack(g.B), g.y.values)
        out.append(f"| {LEAGUES[lg]} | {len(g)} | {mt['acc']:.1f} | {mt['brier']:.4f} | {bt['brier']:.4f} |")
    P, Y = np.vstack(best.P).ravel(), np.eye(3)[best.y.values].ravel()
    out.append("\n## Calibration (all three outcomes pooled)\n")
    out.append("| said | cases | average said | happened |\n|---|---|---|---|")
    for lo in np.arange(0, 1, 0.1):
        s = (P >= lo) & (P < lo + 0.1 + (1e-9 if lo > 0.85 else 0))
        if s.sum() >= 30:
            out.append(f"| {lo:.1f}-{lo + 0.1:.1f} | {s.sum()} | {P[s].mean():.3f} | {Y[s].mean():.3f} |")
    text = "\n".join(out)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(text)


if __name__ == "__main__":
    run()
