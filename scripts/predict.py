"""Goalytical predict test: fits the model on recent seasons and prints
win probabilities for the upcoming fixtures. Uses results only (no odds)."""
import io, math, os, time
import numpy as np, pandas as pd, requests
import backtest as bt

SEASONS = ["2324", "2425", "2526", "2627"]
XI, REG, RHO = 0.002, 3.0, -0.05
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"


def results(lg):
    frames = []
    for s in SEASONS:
        try:
            df = pd.read_csv(io.StringIO(bt.fetch(lg, s)), on_bad_lines="skip")
            df = df[["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]].dropna()
        except Exception as e:
            print("skipped", lg, s, e)
            continue
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
        frames.append(df.dropna(subset=["Date"]))
        time.sleep(1.0)
    d = pd.concat(frames, ignore_index=True)
    d[["FTHG", "FTAG"]] = d[["FTHG", "FTAG"]].astype(int)
    return d.sort_values("Date").reset_index(drop=True)


def score_matrix(m, home, away):
    p, n, ix = m["p"], m["n"], m["ix"]
    g = lambda name, off: p[2 + off + ix[name]] if name in ix else 0.0
    lh = math.exp(p[0] + p[1] + g(home, 0) - g(away, n))
    la = math.exp(p[0] + g(away, 0) - g(home, n))
    k = np.arange(bt.MAXG + 1)
    M = np.outer(np.exp(k * math.log(lh) - lh - bt.gammaln(k + 1)),
                 np.exp(k * math.log(la) - la - bt.gammaln(k + 1)))
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
    return out


def main():
    r = requests.get(FIXTURES_URL, headers={"User-Agent": bt.UA}, timeout=60)
    r.raise_for_status()
    try:
        txt = r.content.decode("utf-8-sig")
    except UnicodeDecodeError:
        txt = r.content.decode("latin-1").lstrip("\ufeff")
    fx = pd.read_csv(io.StringIO(txt), on_bad_lines="skip")
    fx.columns = [str(c).strip().lstrip("\ufeff") for c in fx.columns]
    if "Div" not in fx.columns:
        print("Unexpected fixtures file. Columns:", list(fx.columns))
        print(txt[:300])
        raise SystemExit(1)
    fx = fx[fx.Div.isin(bt.LEAGUES)].copy()
    lines = ["# Goalytical predictions test\n",
             "Times are UK time as given by the data source. Projected goals come from our model.\n"]
    for lg, name in bt.LEAGUES.items():
        d = results(lg)
        ref = d.Date.max() + pd.Timedelta(days=1)
        m = bt.fit(d[d.Date >= ref - pd.Timedelta(days=bt.WINDOW_DAYS)], ref, XI, REG)
        f = fx[fx.Div == lg]
        lines.append(f"## {name} ({m['n']} teams, {len(d)} matches used, {len(f)} fixtures)\n")
        if f.empty:
            lines.append("No fixtures in the file for this league.\n")
            continue
        lines.append("| date | match | home % | draw % | away % | projected goals | likeliest score | note |\n|---|---|---|---|---|---|---|---|")
        for row in f.itertuples():
            M, lh, la = score_matrix(m, row.HomeTeam, row.AwayTeam)
            P = [np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()]
            h, dr, a = pct3(P)
            i, j = np.unravel_index(M[:6, :6].argmax(), (6, 6))
            miss = [t for t in (row.HomeTeam, row.AwayTeam) if t not in m["ix"]]
            note = "no history: " + ", ".join(miss) if miss else ""
            lines.append(f"| {row.Date} {row.Time} | {row.HomeTeam} v {row.AwayTeam} | {h} | {dr} | {a} | {lh:.2f} - {la:.2f} | {i}-{j} ({M[i, j] * 100:.0f}%) | {note} |")
        lines.append("")
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(text)


if __name__ == "__main__":
    main()
