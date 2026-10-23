"""Goalytical page builder: turns data/site.json and data/log.json into the website in public/.
Run from the repository root:  python scripts/render.py"""
import datetime as dt, hashlib, html, json, os, re, shutil

# ---------- settings you will change at launch ----------
SITE_URL = ""          # e.g. "https://goalytical.com" once your domain is connected (no trailing slash)
INDEXABLE = False      # set to True when you are ready for Google to list the site
ADS = False            # set to True after your ad account is approved
CONTACT_EMAIL = ""     # your public contact email address
# --------------------------------------------------------
NAME, TAGLINE, OUT = "Goalytical", "Football stats and match analysis", "public"
D = json.load(open("data/site.json", encoding="utf-8"))
LOG = json.load(open("data/log.json", encoding="utf-8")) if os.path.exists("data/log.json") else {}
NOW = dt.datetime.now(dt.timezone.utc)
D.setdefault("record", {"all": None, "leagues": {}, "pending": 0})
D.setdefault("played", [])
LEAGUES = D["leagues"]
CLS = {"E0": "a", "E1": "b", "D1": "c"}
LGCOL = {"a": ("#7B61FF", "#fff"), "b": ("#0FA3A3", "#fff"), "c": ("#E0A100", "#0B1B2B")}
TEAMS, TEAM_LG, PAGES = {}, {}, []
for _lg, _L in LEAGUES.items():
    for _t in _L["table"]:
        TEAMS[_t["slug"]], TEAM_LG[_t["slug"]] = _t, _lg


def e(s):
    return html.escape(str(s), quote=True)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("ü", "u").replace("ö", "o")).strip("-")


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def when(utc):
    return dt.datetime.fromisoformat(utc.replace("Z", "+00:00"))


def ko(utc, full=False):
    d = when(utc)
    if full:
        return f'<time class="ko" data-full datetime="{utc}">{d.strftime("%a %d %b, %H:%M")} UTC</time>'
    return f'<time class="ko" datetime="{utc}">{d.strftime("%a %d")}<br>{d.strftime("%H:%M")}</time>'


def fm(s):
    return "".join(f'<i class="f f{c}">{c}</i>' for c in s)


def team_of(sl, name):
    return TEAMS.get(sl) or {"team": name, "slug": sl, "P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0, "CS": 0,
                             "FTS": 0, "H": [0] * 6, "A": [0] * 6, "form": [], "last": [], "GD": 0, "ppg": 0, "gf_pm": 0,
                             "ga_pm": 0, "shots_pm": None, "pos": None}


def posx(t):
    return ordinal(t["pos"]) if t.get("pos") else "-"


def ad(kind="rect"):
    if not ADS:
        return ""
    box = {"rect": "300 x 250", "lb": "320 x 100", "tall": "300 x 600"}[kind]
    cls = {"rect": "ad", "lb": "ad lb", "tall": "ad tall"}[kind]
    return f'<div class="{cls}"><small>Advertisement</small><div data-ad-slot="{kind}">{box}</div></div>'


ICON_MENU = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
ICON_SRCH = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@700&family=Onest:wght@400;600&display=swap">')
CSSV = hashlib.md5(open("static/style.css", "rb").read()).hexdigest()[:8]
APP_JS = """(function(){
var esc=function(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})};
document.querySelectorAll('time.ko').forEach(function(t){var d=new Date(t.getAttribute('datetime'));if(isNaN(d))return;
if(t.hasAttribute('data-full')){t.textContent=d.toLocaleString(undefined,{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});}
else{t.innerHTML=d.toLocaleDateString(undefined,{weekday:'short',day:'numeric'})+'<br>'+d.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'});}});
var q=document.getElementById('q');
if(q){var out=document.getElementById('res'),idx=[];
function show(v){v=v.trim().toLowerCase();var r=idx.filter(function(x){return !v||x.t.toLowerCase().indexOf(v)>-1}).slice(0,40);
out.innerHTML=r.map(function(x){return '<a class="ro" href="'+esc(x.u)+'"><span>'+esc(x.t)+'</span><span class="mu">'+esc(x.k)+'</span></a>'}).join('')||'<p class="mu">Nothing found.</p>';}
fetch('/search.json').then(function(r){return r.json()}).then(function(j){idx=j;show(q.value)});
q.addEventListener('input',function(){show(q.value)});}
})();"""


def nav(active):
    items = [("Home", "/"), ("Leagues", "/leagues/"), ("Previews", "/previews/"), ("Record", "/record/"), ("Method", "/method/")]
    leagues = "".join(f'<a href="/leagues/{L["slug"]}/"><i class="cr" style="background:{LGCOL[CLS[lg]][0]};color:{LGCOL[CLS[lg]][1]}">{e(L["name"][0])}</i>{e(L["name"])}</a>'
                      for lg, L in LEAGUES.items())
    desk = ""
    for n, h in items:
        on = ' class="on"' if n == active else ""
        if n == "Leagues":
            desk += (f'<div class="nvi"><a{on} href="{h}">Leagues &#9662;</a><div class="mega"><div><h3>Leagues</h3>{leagues}</div>'
                     f'<div><h3>Quick links</h3><a href="/previews/">All previews</a><a href="/record/">Our record</a><a href="/method/">How it works</a></div></div></div>')
        else:
            desk += f'<div class="nvi"><a{on} href="{h}">{n}</a></div>'
    mob = "".join(f'<a href="{h}">{n}</a>' for n, h in items)
    mob += "<h4>Leagues</h4>" + "".join(f'<a href="/leagues/{L["slug"]}/">{e(L["name"])}</a>' for L in LEAGUES.values())
    return desk, mob


def footer():
    lg = "".join(f'<a href="/leagues/{L["slug"]}/">{e(L["name"])}</a>' for L in LEAGUES.values())
    return (f'<div class="ft"><a class="lgo" href="/"><img src="/logo-white.svg" width="129" height="24" alt="{NAME}"></a><p>{TAGLINE}.</p>'
            f'<div class="fg"><div><h3>Leagues</h3>{lg}</div><div><h3>{NAME}</h3><a href="/previews/">Previews</a><a href="/record/">Record</a><a href="/method/">Method</a><a href="/search/">Search</a></div>'
            f'<div><h3>Company</h3><a href="/about/">About</a><a href="/contact/">Contact</a></div><div><h3>Legal</h3><a href="/disclaimer/">Disclaimer</a></div></div>'
            f'<p>Projections are statistical estimates, not guarantees or betting advice. 18+. Match results: football-data.co.uk. Fixtures: football-data.org. Data updated {e(D.get("generated_at", ""))}.</p></div>')


def layout(title, desc, path, body, active="", ld=None, kind="website"):
    ft = title if title.endswith(NAME) else f"{title} | {NAME}"
    desk, mob = nav(active)
    robots = "" if INDEXABLE else '<meta name="robots" content="noindex,nofollow">'
    canon = f'<link rel="canonical" href="{SITE_URL}{path}">' if SITE_URL else ""
    ldj = json.dumps(ld).replace("</", "<\\/") if ld else ""
    ldt = f'<script type="application/ld+json">{ldj}</script>' if ld else ""
    head = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(ft)}</title><meta name="description" content="{e(desc)}">{robots}{canon}<meta name="color-scheme" content="light dark">'
            f'<meta property="og:title" content="{e(ft)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="{kind}"><meta property="og:site_name" content="{NAME}">'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml">{FONTS}<link rel="stylesheet" href="/style.css?v={CSSV}">{ldt}</head>')
    header = (f'<a class="skip" href="#main">Skip to content</a><div class="ut"><span>{TAGLINE}</span><span>Times shown in your local time</span></div>'
              f'<div class="hd"><details class="mb"><summary aria-label="Menu">{ICON_MENU}</summary><div class="drawer">{mob}</div></details>'
              f'<a class="lgo" href="/"><img src="/logo-white.svg" width="129" height="24" alt="{NAME}"></a><nav class="nvd">{desk}</nav>'
              f'<div class="hr"><a class="sf" href="/search/">{ICON_SRCH}<span>Search teams and leagues</span></a></div>'
              f'<a class="ms" href="/search/" aria-label="Search">{ICON_SRCH}</a></div>')
    return f'{head}<body><div class="pg">{header}<main id="main">{body}</main>{footer()}</div><script src="/app.js?v={CSSV}" defer></script></body></html>'


def emit(path, content, sitemap=True):
    fp = os.path.join(OUT, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.strip("/"))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, "w", encoding="utf-8").write(content)
    if sitemap and path.endswith("/"):
        PAGES.append(path)


def crumb(*items):
    parts = [f'<a href="{h}">{e(t)}</a>' if h else f"<b>{e(t)}</b>" for t, h in items]
    return f'<div class="crumb">{" &rsaquo; ".join(parts)}</div>'


def sh(title, text=None, href=None):
    return f'<div class="sh"><h2>{e(title)}</h2>' + (f'<a href="{href}">{e(text)}</a>' if text else "") + "</div>"


def sec(id_, title, inner, text=None, href=None):
    return f'<div class="sec" id="{id_}">{sh(title, text, href)}{inner}</div>'


def probs(p, nt=""):
    return (f'<div class="np"><div><small>Home win</small><b class="u">{p[0]}%</b></div><div><small>Draw</small><b class="u">{p[1]}%</b></div>'
            f'<div><small>Away win</small><b class="u">{p[2]}%</b></div></div><div class="sb"><i style="flex:{p[0]}"></i><i style="flex:{p[1]}"></i><i style="flex:{p[2]}"></i></div>{nt}')


def fx_row(f):
    p = f["pct"]
    return (f'<a class="fx" href="/match/{f["id"]}/"><span class="t">{ko(f["utc"])}</span><div><b>{e(f["home"])}</b><b>{e(f["away"])}</b></div>'
            f'<div class="p"><i>{p[0]}</i><i>{p[1]}</i><i>{p[2]}</i></div></a>')


def fx_group(lg, fixtures, limit=None):
    L = LEAGUES[lg]
    rows = "".join(fx_row(f) for f in (fixtures[:limit] if limit else fixtures))
    return (f'<div class="card p0" style="margin-bottom:12px"><div class="lh lg{CLS[lg]}"><span>{e(L["name"])}</span>'
            f'<span><i>H</i><i>D</i><i>A</i></span></div>{rows or "<p class=nt style=padding:14px>No upcoming matches in the data right now.</p>"}</div>')


def table_html(rows, me=()):
    o = ('<div class="tw"><table><tr><th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th><th>Form</th></tr>')
    prev = None
    for t in rows:
        if prev is not None and t["pos"] != prev + 1:
            o += '<tr><td colspan="9" style="text-align:center;color:var(--mu)">...</td></tr>'
        prev = t["pos"]
        o += (f'<tr class="{"me" if t["slug"] in me else ""}"><td>{t["pos"]}</td><td><a href="/team/{t["slug"]}/">{e(t["team"])}</a></td><td>{t["P"]}</td>'
              f'<td>{t["W"]}</td><td>{t["D"]}</td><td>{t["L"]}</td><td>{t["GD"]:+d}</td><td><b>{t["Pts"]}</b></td><td>{fm("".join(t["form"]))}</td></tr>')
    return o + "</table></div>"


def window(lg, slugs, span=2):
    rows = LEAGUES[lg]["table"]
    pos = {t["pos"] for t in rows if t["slug"] in slugs}
    keep = set()
    for p in pos:
        keep.update(range(max(1, p - span), min(len(rows), p + span) + 1))
    return [t for t in rows if t["pos"] in keep]


def upcoming(lg):
    return [f for f in LEAGUES[lg]["fixtures"] if when(f["utc"]) > NOW]


def cmp(label, va, vb, fmt="{}"):
    return (f'<div class="cmp"><div class="l"><b>{fmt.format(va)}</b><em>{label}</em><b>{fmt.format(vb)}</b></div>'
            f'<div class="b"><i style="flex:{max(va, 0.01):.3f}"></i><i style="flex:{max(vb, 0.01):.3f}"></i></div></div>')


def last_rows(t):
    if not t["last"]:
        return '<p class="nt">No matches played yet this season.</p>'
    return "".join(f'<div class="ro"><span>{e(x["opp"])} ({x["venue"]})<br><small class="mu">{x["date"]}</small></span><span><b>{x["gf"]}-{x["ga"]}</b> {fm(x["res"])}</span></div>' for x in t["last"])


def plural(n, w):
    return f"{n} {w}" + ("" if n == 1 else "s")


def notes(f, th, ta, L):
    h, a, out = f["home"], f["away"], []
    if th["P"] and ta["P"]:
        out.append(f'{h} are {ordinal(th["pos"])} in the {L["name"]} with {th["Pts"]} points from {th["P"]} matches. {a} are {ordinal(ta["pos"])} with {ta["Pts"]} from {ta["P"]}.')
        out.append(f'{h} score {th["gf_pm"]} and concede {th["ga_pm"]} goals per match this season. {a} score {ta["gf_pm"]} and concede {ta["ga_pm"]}.')
        if th["H"][0] and ta["A"][0]:
            out.append(f'At home, {h} have won {th["H"][1]} of {th["H"][0]}. Away from home, {a} have won {ta["A"][1]} of {ta["A"][0]}.')
        fh, fa = "".join(th["form"]), "".join(ta["form"])
        out.append(f'In their last {len(fh)} matches {h} have {plural(fh.count("W"), "win")}, {plural(fh.count("D"), "draw")} and {plural(fh.count("L"), "defeat")}. {a} have {plural(fa.count("W"), "win")}, {plural(fa.count("D"), "draw")} and {plural(fa.count("L"), "defeat")}.')
    p = f["pct"]
    fav = h if p[0] >= p[2] else a
    top = max(p)
    if top < 40:
        out.append(f'No outcome is above 40%, so our model sees this as an open match: {h} {p[0]}%, draw {p[1]}%, {a} {p[2]}%.')
    else:
        out.append(f'Our model makes {fav} the likelier winner at {max(p[0], p[2])}%, with the draw at {p[1]}%.')
    i, j, pr = f["top"][0]
    out.append(f'Projected goals are {f["proj"][0]} for {h} and {f["proj"][1]} for {a}. The single likeliest score is {i}-{j} at {pr}%, which shows how many different results are possible in one match.')
    if f["h2h"]:
        w = {h: 0, a: 0, "d": 0}
        for m in f["h2h"]:
            if m["hg"] == m["ag"]:
                w["d"] += 1
            else:
                w[m["home"] if m["hg"] > m["ag"] else m["away"]] += 1
        out.append(f'In their last {len(f["h2h"])} meetings in this league since 2023/24, {h} won {w[h]}, {a} won {w[a]} and {w["d"]} were drawn.')
    return out


def analysis_text(mid):
    fp = os.path.join("analysis", mid + ".txt")
    if not os.path.exists(fp):
        return ""
    paras = [p.strip() for p in open(fp, encoding="utf-8").read().split("\n\n") if p.strip()]
    return "".join(f"<p>{e(p)}</p>" for p in paras)


def crest(name, cls=""):
    return f'<div class="cr {cls}">{e(name[0])}</div>'


def match_page(lg, f):
    L = LEAGUES[lg]
    th, ta = team_of(f["home_slug"], f["home"]), team_of(f["away_slug"], f["away"])
    h, a, p = f["home"], f["away"], f["pct"]
    path = f'/match/{f["id"]}/'
    warn = ""
    limited = f.get("limited", [])
    if limited:
        warn = f'<p class="warn">Limited data: {e(", ".join(limited))} {"has" if len(limited) == 1 else "have"} played few matches in this league recently, so the model leans on league averages for {"them" if len(limited) > 1 else "this team"}. Treat these numbers with extra care.</p>'
    fav = h if p[0] >= p[2] else a
    view = "Model view: " + e(fav) + " win most likely." if max(p) >= 40 else "Model view: an open match."
    nt = f'<p class="nt" style="margin-bottom:0">{view} Projected goals {f["proj"][0]} to {f["proj"][1]}. <a class="lk" href="/method/">How this is calculated</a></p>{warn}'
    header = (f'<div class="mh"><div class="top"><span>{e(L["name"])} &middot; Matchday {f.get("matchday") or "-"}</span><span class="tag">Pre-match</span></div>'
              f'<div class="tm"><a href="/team/{th["slug"]}/">{crest(h)}<b>{e(h)}</b><small>{posx(th)} &middot; {th["Pts"]} pts</small></a>'
              f'<div><b class="u" style="font-size:15px">{ko(f["utc"], True)}</b></div>'
              f'<a href="/team/{ta["slug"]}/">{crest(a, "a")}<b>{e(a)}</b><small>{posx(ta)} &middot; {ta["Pts"]} pts</small></a></div>'
              f'<p class="nt" style="text-align:center;margin-bottom:0">Kick-off is shown in your local time.</p></div>')
    stk = f'<div class="stkw"><div class="stk"><span>{e(h)}</span><span class="u">{p[0]}% &middot; {p[1]}% &middot; {p[2]}%</span><span>{e(a)}</span></div></div>'
    pills = '<div class="pills"><a href="#probabilities">Probabilities</a><a href="#scores">Scores</a><a href="#numbers">Numbers</a><a href="#form">Form</a><a href="#notes">Notes</a><a href="#meetings">Meetings</a></div>'
    scores = "".join(f'<div class="sl"><b class="u">{i}-{j}</b><span><i style="width:{int(pr / f["top"][0][2] * 100)}%"></i></span><span>{pr}%</span></div>' for i, j, pr in f["top"])
    mx = max(max(r) for r in f["grid"]) or 1
    grid = '<div class="tw"><table class="gt"><tr><th></th>' + "".join(f"<th>{j}</th>" for j in range(5)) + "</tr>"
    for i, r in enumerate(f["grid"]):
        grid += f"<tr><th>{i}</th>" + "".join(f'<td class="{"hi" if v / mx > .45 else ""}" style="background:rgba(var(--hfrgb),{0.08 + 0.85 * v / mx:.2f})">{v}</td>' for v in r) + "</tr>"
    grid += f'</table></div><p class="nt">Rows are {e(h)} goals, columns are {e(a)} goals. Each cell is the chance of that exact score, in %.</p>'
    numbers = cmp("Points per match", th["ppg"], ta["ppg"]) + cmp("Goals scored per match", th["gf_pm"], ta["gf_pm"]) + cmp("Goals conceded per match", th["ga_pm"], ta["ga_pm"])
    numbers += cmp("Clean sheets", th["CS"], ta["CS"])
    if th.get("shots_pm") and ta.get("shots_pm"):
        numbers += cmp("Shots per match", th["shots_pm"], ta["shots_pm"])
    formc = (f'<div class="card"><h3>{e(h)}</h3>{last_rows(th)}</div><div style="height:12px"></div><div class="card"><h3>{e(a)}</h3>{last_rows(ta)}</div>')
    ns = "".join(f"<p>{e(x)}</p>" for x in notes(f, th, ta, L))
    own = analysis_text(f["id"])
    h2 = "".join(f'<div class="ro"><span>{m["date"]}<br><b>{e(m["home"])} v {e(m["away"])}</b></span><b class="u" style="font-size:14px">{m["hg"]}-{m["ag"]}</b></div>' for m in f["h2h"])
    h2 = h2 or '<p class="nt">These teams have not met in this league in our data since 2023/24.</p>'
    tbl = f'<div class="card p0">{table_html(window(lg, {f["home_slug"], f["away_slug"]}), {f["home_slug"], f["away_slug"]})}</div>'
    nxt = ""
    for sl, nm in ((f["home_slug"], h), (f["away_slug"], a)):
        more = [x for x in upcoming(lg) if x["id"] != f["id"] and sl in (x["home_slug"], x["away_slug"])][:2]
        if more:
            nxt += f'<div class="card p0" style="margin-bottom:12px"><div class="lh lg{CLS[lg]}"><span>Next for {e(nm)}</span><span></span></div>{"".join(fx_row(x) for x in more)}</div>'
    faq = ('<div class="card"><details open><summary>How is this projection made?</summary><p>From each team\'s scoring and conceding record, adjusted for home advantage and weighted towards recent matches. '
           '<a class="lk" href="/method/">Read the full method</a>.</p></details><details><summary>How accurate are these projections?</summary><p>We publish a backtest and a live record, with a baseline to compare against. '
           '<a class="lk" href="/record/">See our record</a>.</p></details></div>')
    main = (f'<div class="sec"><h1>{e(h)} vs {e(a)}: preview and win probabilities</h1></div>'
            + sec("probabilities", "Win probabilities", f'<div class="card">{probs(p, nt)}</div>') + sec("scores", "Most likely scores", f'<div class="card">{scores}</div><div class="card" style="margin-top:12px">{grid}</div>')
            + ad() + sec("numbers", "Season numbers", f'<div class="card">{numbers}</div>') + sec("form", "Recent form", formc)
            + sec("notes", "Match notes", f'<div class="card">{own}{ns}<p class="nt" style="margin:0">Notes are generated from the data above.{" Includes written analysis." if own else ""}</p></div>')
            + sec("meetings", "Last meetings", f'<div class="card">{h2}</div>') + sec("faq", "Questions", faq))
    side = sec("table", "League table", tbl, "Full table", f'/leagues/{L["slug"]}/') + nxt + ad("tall")
    body = crumb(("Home", "/"), (L["name"], f'/leagues/{L["slug"]}/'), ("Previews", "/previews/"), (f"{h} v {a}", None)) + header + stk + pills + f'<div class="cols"><div>{main}</div><div>{side}</div></div>' + ad("lb")
    d = when(f["utc"]).strftime("%d %b %Y")
    desc = f"{h} vs {a} ({L['name']}, {d}): our model gives {h} {p[0]}%, draw {p[1]}%, {a} {p[2]}%. Form, head to head and score probabilities."
    ld = {"@context": "https://schema.org", "@type": "SportsEvent", "name": f"{h} vs {a}", "startDate": f["utc"], "eventStatus": "https://schema.org/EventScheduled",
          "sport": "Association football", "homeTeam": {"@type": "SportsTeam", "name": h}, "awayTeam": {"@type": "SportsTeam", "name": a}, "url": f"{SITE_URL}{path}"}
    emit(path, layout(f"{h} vs {a} preview: win probabilities and stats", desc, path, body, "Previews", ld))


def played_page(en):
    lg, res = en["lg"], en.get("result") or {}
    L = LEAGUES[lg]
    h, a, p = en["home"], en["away"], en["pct"]
    th, ta = team_of(slug(h), h), team_of(slug(a), a)
    done = "hg" in res
    path = f'/match/{en["id"]}/'
    score = f'{res["hg"]}-{res["ag"]}' if done else "v"
    y = 0 if done and res["hg"] > res["ag"] else (1 if done and res["hg"] == res["ag"] else 2)
    verdict = ""
    if done:
        ok = p.index(max(p)) == y
        verdict = f'<div class="ro"><span>Result called?</span><span class="vd {"vy" if ok else "vn"}">{"Called" if ok else "Missed"}: {["home win", "draw", "away win"][y]}</span></div>'
    else:
        verdict = '<div class="ro"><span>Status</span><span class="tag">Awaiting final result</span></div>'
    header = (f'<div class="mh"><div class="top"><span>{e(L["name"])}</span><span class="tag n">{"Full time" if done else "Result pending"}</span></div>'
              f'<div class="tm"><a href="/team/{slug(h)}/">{crest(h)}<b>{e(h)}</b></a><div><b class="score">{score}</b><br><small>{ko(en["utc"], True)}</small></div>'
              f'<a href="/team/{slug(a)}/">{crest(a, "a")}<b>{e(a)}</b></a></div></div>')
    proj = f'<div class="ro"><span>Projected goals</span><span>{en["proj"][0]} to {en["proj"][1]}</span></div>'
    main = (f'<div class="sec"><h1>{e(h)} {score} {e(a)}: result and our projection</h1></div>'
            + sec("projection", "What we projected", f'<div class="card">{probs(p)}{verdict}{proj}<p class="nt" style="margin-bottom:0">Frozen before kick-off. <a class="lk" href="/record/">See our record</a></p></div>'))
    after = "".join(f'<div class="card p0" style="margin-bottom:12px">{table_html(window(lg, {t["slug"]}, 1), {t["slug"]})}</div>' for t in (th, ta) if t["pos"])
    body = crumb(("Home", "/"), (L["name"], f'/leagues/{L["slug"]}/'), ("Results", None), (f"{h} v {a}", None)) + header + f'<div class="cols"><div>{main}{ad()}</div><div>{sec("table", "League table", after)}{ad("tall")}</div></div>'
    desc = (f"{h} {score} {a}: full-time result and how our projection did ({p[0]}% / {p[1]}% / {p[2]}%)." if done else f"{h} v {a}: our pre-match projection was {p[0]}% / {p[1]}% / {p[2]}%. Result pending.")
    emit(path, layout(f"{h} {score} {a}: result and projection", desc, path, body, "Record"))


def team_page(lg, t):
    L = LEAGUES[lg]
    path = f'/team/{t["slug"]}/'
    ups = [f for f in upcoming(lg) if t["slug"] in (f["home_slug"], f["away_slug"])][:3]
    nxt = sec("next", "Next matches", fx_group(lg, ups) if ups else '<p class="nt">No upcoming matches in the data right now.</p>')
    sp = ["P", "W", "D", "L", "GF", "GA"]
    rows = "".join(f'<tr><td>{n}</td>' + "".join(f"<td>{v}</td>" for v in vals) + "</tr>" for n, vals in
                   (("Overall", [t["P"], t["W"], t["D"], t["L"], t["GF"], t["GA"]]), ("Home", t["H"][:1] + t["H"][1:4] + t["H"][4:]), ("Away", t["A"][:1] + t["A"][1:4] + t["A"][4:])))
    summ = '<div class="card p0"><div class="tw"><table><tr><th></th>' + "".join(f"<th>{s}</th>" for s in sp) + f"</tr>{rows}</table></div></div>"
    kv = (f'<div class="kv"><div><b class="u">{t["ppg"]}</b><small>Points per match</small></div><div><b class="u">{t["gf_pm"]}</b><small>Goals for per match</small></div>'
          f'<div><b class="u">{t["ga_pm"]}</b><small>Goals against per match</small></div></div><div class="kv" style="margin-top:10px"><div><b class="u">{t["CS"]}</b><small>Clean sheets</small></div>'
          f'<div><b class="u">{t["FTS"]}</b><small>Failed to score</small></div><div><b class="u">{t["shots_pm"] if t.get("shots_pm") else "-"}</b><small>Shots per match</small></div></div>')
    head = (f'<div class="mh"><div style="display:flex;gap:14px;align-items:center">{crest(t["team"])}<div><h1>{e(t["team"])}</h1>'
            f'<span class="mu sm">{e(L["name"])} &middot; {posx(t)} &middot; {t["Pts"]} pts</span></div></div><div class="fb" style="margin-top:14px">{fm("".join(t["form"]))}</div></div>')
    main = (nxt + sec("summary", "Season summary", summ) + ad() + sec("numbers", "Season numbers", kv) + sec("results", "Recent results", f'<div class="card">{last_rows(t)}</div>'))
    side = sec("table", "League table", f'<div class="card p0">{table_html(window(lg, {t["slug"]}), {t["slug"]})}</div>', "Full table", f'/leagues/{L["slug"]}/') + ad("tall")
    body = crumb(("Home", "/"), (L["name"], f'/leagues/{L["slug"]}/'), (t["team"], None)) + head + f'<div class="cols"><div>{main}</div><div>{side}</div></div>' + ad("lb")
    desc = f'{t["team"]} form, results and next match win probabilities. {posx(t)} in the {L["name"]} with {t["Pts"]} points from {t["P"]} matches.'
    emit(path, layout(f'{t["team"]} form, results and next match prediction', desc, path, body, "Leagues"))


def league_page(lg):
    L = LEAGUES[lg]
    path = f'/leagues/{L["slug"]}/'
    av = L["averages"]
    chips = '<div class="chips">' + "".join(f'<a href="/leagues/{x["slug"]}/"{" class=on" if k == lg else ""}><i class="ld lg{CLS[k]}"></i>{e(x["name"])}</a>' for k, x in LEAGUES.items()) + "</div>"
    pills = '<div class="pills"><a href="#table">Table</a><a href="#fixtures">Fixtures</a><a href="#averages">Averages</a></div>'
    kv = (f'<div class="kv"><div><b class="u">{av["goals_pm"]}</b><small>Goals per match</small></div><div><b class="u">{av["home_win"]}%</b><small>Home wins</small></div>'
          f'<div><b class="u">{av["draw"]}%</b><small>Draws</small></div></div><p class="nt">Based on {av["matches"]} matches this season. Away wins: {av["away_win"]}%.</p>')
    main = (sec("table", "League table", f'<div class="card p0">{table_html(L["table"])}</div><p class="nt">Ordered by points, then goal difference, then goals scored. Form shows the last five results, newest on the right.</p>')
            + ad() + sec("fixtures", "Upcoming matches", fx_group(lg, upcoming(lg))))
    side = sec("averages", "League averages", kv) + ad("tall")
    body = (chips + crumb(("Home", "/"), ("Leagues", "/leagues/"), (L["name"], None)) + f'<div class="sec lg{CLS[lg]}"><i class="lgbar"></i><h1>{e(L["name"])}</h1>'
            f'<p class="mu sm" style="margin-top:4px">Season {D["season"]} &middot; {len(L["table"])} teams</p></div>' + pills + f'<div class="cols"><div>{main}</div><div>{side}</div></div>' + ad("lb"))
    emit(path, layout(f'{L["name"]} table, fixtures and win probabilities', f'{L["name"]} table, form and statistical previews with win probabilities for every upcoming match.', path, body, "Leagues"))
    for t in L["table"]:
        team_page(lg, t)


def simple(path, title, desc, inner, active="", crumbs=None):
    cr = crumb(("Home", "/"), (title, None)) if crumbs is None else crumbs
    emit(path, layout(title, desc, path, cr + inner, active))


def record_page():
    B, R = D["backtest"], D["record"]
    rows = lambda items: "".join(f'<div class="ro"><span>{a}</span><b>{b}</b></div>' for a, b in items)
    if R["all"]:
        A = R["all"]
        early = '<p class="warn">Early days: fewer than 30 matches are scored so far, so these figures can swing a lot. The backtest below is a better guide for now.</p>' if A["matches"] < 30 else ""
        live = (early + f'<div class="kv"><div><b class="u">{A["matches"]}</b><small>Matches scored</small></div><div><b class="u">{A["correct"]}%</b><small>Result called</small></div><div><b class="u">{A["brier"]}</b><small>Brier score</small></div></div>'
                f'<div class="card" style="margin-top:12px">{rows([("Our Brier score (lower is better)", A["brier"]), ("Baseline: past home/draw/away rates", A["base_brier"]), ("Guessing equal chances", "0.6667")])}</div>')
        rec = "".join(f'<div class="ro"><span>{e(x["home"])} {x["hg"]}-{x["ag"]} {e(x["away"])}<br><small class="mu">{x["pct"][0]} &middot; {x["pct"][1]} &middot; {x["pct"][2]}</small></span><span class="vd {"vy" if x["called"] else "vn"}">{"Called" if x["called"] else "Missed"}</span></div>' for x in D["played"][:10])
        live += f'<div class="sec" style="padding:20px 0 0">{sh("Latest scored matches")}<div class="card">{rec}</div></div>'
    else:
        live = f'<div class="card"><p style="margin:0">Our live record begins with our first scored match. {R["pending"]} predictions are logged and waiting for results. Each one is saved before kick-off.</p></div>'
    bl = "".join(f'<tr><td>{e(x["name"])}</td><td>{x["matches"]}</td><td>{x["correct"]}</td><td>{x["brier"]}</td><td>{x["base_brier"]}</td></tr>' for x in B["leagues"])
    cal = "".join(f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td><b>{r[3]}</b></td></tr>' for r in B["calibration"])
    m, b0, q = B["model"], B["base_rates"], B["equal"]
    row_list = [("Result called: our model", str(m["correct"]) + "%"), ("Result called: always pick the likeliest from past rates", str(b0["correct"]) + "%"),
                ("Brier score: our model (lower is better)", m["brier"]), ("Brier score: past home/draw/away rates", b0["brier"]), ("Brier score: equal chances", q["brier"])]
    back = (f'<div class="kv"><div><b class="u">{B["matches"]:,}</b><small>Matches tested</small></div><div><b class="u">{m["correct"]}%</b><small>Result called</small></div><div><b class="u">{m["brier"]}</b><small>Brier score</small></div></div>'
            f'<div class="card" style="margin-top:12px">{rows(row_list)}</div>'
            f'<p class="nt">Backtest of {B["period"]}. Each prediction used only matches played before it. Settings: {e(B["settings"])}. This is a test on past seasons, not a live record.</p>')
    body = (crumb(("Home", "/"), ("Record", None)) + '<div class="sec"><h1>How accurate are our projections?</h1><p class="lead" style="margin-top:8px">Every projection is saved before kick-off and scored after full time. We show a baseline next to every number, because a score means little without one.</p></div>'
            + '<div class="cols"><div>' + sec("live", "Live record", live) + ad() + sec("backtest", "Backtest on past seasons", back)
            + sec("leagues", "By league", f'<div class="card p0"><div class="tw"><table><tr><th>League</th><th>Matches</th><th>Called %</th><th>Brier</th><th>Baseline</th></tr>{bl}</table></div></div><p class="nt">The Championship is the hardest to predict: results are closer to the baseline there.</p>')
            + sec("calibration", "Calibration", f'<div class="card p0"><div class="tw"><table><tr><th>We said</th><th>Cases</th><th>Average said</th><th>Happened</th></tr>{cal}</table></div></div><p class="nt">When we say about 60%, the outcome should happen about 60% of the time. Pooled across home, draw and away.</p>')
            + '</div><div>' + sec("read", "How to read this", '<div class="card"><p><b>Result called</b> counts a match when the outcome we rated likeliest happened. About half is normal in football.</p><p><b>Brier score</b> measures the quality of the probabilities. Lower is better, and 0.6667 is what guessing equal chances scores.</p><p style="margin:0"><b>Calibration</b> checks whether our percentages mean what they say.</p></div>') + ad("tall") + "</div></div>" + ad("lb"))
    emit("/record/", layout("How accurate are our football projections?", "Our public record: every projection is saved before kick-off and scored against the result, with a baseline, Brier score and calibration table.", "/record/", body, "Record"))


def method_page():
    steps = [("Collect results", "Past scores for each league, from football-data.co.uk."), ("Rate every team", "An attack rating, a defence rating, and one home advantage for the league."),
             ("Weight recent matches", "Older games count for less than recent ones, with a half-life of about a year."), ("Work out scores", "The chance of every scoreline, from 0-0 upward, using a Poisson goals model with a small correction for low-scoring draws."),
             ("Add up outcomes", "Home win, draw and away win chances come from adding those scorelines.")]
    st = "".join(f'<div class="ro" style="align-items:flex-start"><b class="u" style="color:var(--ot)">{i}</b><span style="flex:1"><b>{e(t)}</b><br><span class="mu">{e(x)}</span></span></div>' for i, (t, x) in enumerate(steps, 1))
    use = [("Match results and scores", "Used", "vy"), ("Shots and corners", "Shown only", "vy"), ("Expected goals (xG)", "Not used", "vn"), ("Bookmaker odds", "Not used", "vn"), ("Injuries and lineups", "Not yet", "vn")]
    us = "".join(f'<div class="ro"><span>{a}</span><span class="vd {c}">{b}</span></div>' for a, b, c in use)
    body = (crumb(("Home", "/"), ("Method", None)) + '<div class="sec"><h1>How our projections work</h1><p class="lead" style="margin-top:8px">A results-based goals model. Every number comes from our own calculation: we never copy tips from anyone.</p></div>'
            + '<div class="cols"><div>' + sec("steps", "Five steps", f'<div class="card">{st}</div>') + ad()
            + sec("limits", "Limits", '<div class="card"><p>Football has luck in it. A 60% projection still fails four times in ten. The model does not know about injuries, suspensions, lineups or tactics, and it knows little about teams that have just joined a league.</p><p style="margin:0">When a team has little recent data in a league, we say so on the match page.</p></div>')
            + sec("data", "Data and updates", '<div class="card"><p>Match results: football-data.co.uk. Fixtures and kick-off times: football-data.org. Projections refresh every six hours and are frozen at kick-off.</p><p style="margin:0">We do not use or publish betting odds, and we do not offer betting tips.</p></div>')
            + '</div><div>' + sec("used", "What we use", f'<div class="card">{us}</div>') + sec("test", "Checking ourselves", '<div class="card"><p style="margin:0">We publish a backtest and a live record with a baseline. <a class="lk" href="/record/">See the record</a>.</p></div>') + ad("tall") + "</div></div>" + ad("lb"))
    emit("/method/", layout("How our football projections work", "How Goalytical calculates win probabilities: a results-based Poisson goals model, what data we use, what we leave out, and how we check ourselves.", "/method/", body, "Record"))


def build():
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree("static", OUT)
    open(os.path.join(OUT, "app.js"), "w", encoding="utf-8").write(APP_JS)
    ups = {}
    for lg in LEAGUES:
        league_page(lg)
        for f in upcoming(lg):
            ups[f["id"]] = (lg, f)
    for lg, f in ups.values():
        match_page(lg, f)
    n_played = 0
    for en in LOG.values():
        res = en.get("result") or {}
        if en["id"] in ups or res.get("void") or en["lg"] not in LEAGUES:
            continue
        age = (NOW - when(en["utc"])).days
        if when(en["utc"]) <= NOW and age <= 45:
            played_page(en)
            n_played += 1
    allup = sorted(((lg, f) for lg in LEAGUES for f in upcoming(lg)), key=lambda x: x[1]["utc"])
    # home
    soon = [(lg, f) for lg, f in allup if when(f["utc"]) < NOW + dt.timedelta(days=7)] or allup
    feat = ""
    if soon:
        lg, f = max(soon, key=lambda x: team_of(x[1]["home_slug"], "")["ppg"] + team_of(x[1]["away_slug"], "")["ppg"])
        note = '<p class="nt" style="text-align:center;margin-bottom:0">' + e(LEAGUES[lg]["name"]) + " &middot; read the preview</p>"
        feat = (f'<a class="card" href="/match/{f["id"]}/"><div class="tm"><div>{crest(f["home"])}<b>{e(f["home"])}</b></div><div><small>{ko(f["utc"])}</small></div><div>{crest(f["away"], "a")}<b>{e(f["away"])}</b></div></div>'
                + probs(f["pct"], note) + "</a>")
    groups = "".join(fx_group(lg, upcoming(lg), 5) for lg in LEAGUES)
    first = next(iter(LEAGUES))
    R, B = D["record"], D["backtest"]
    if R["all"] and R["all"]["matches"] >= 30:
        kv = f'<div class="kv"><div><b class="u">{R["all"]["correct"]}%</b><small>Called</small></div><div><b class="u">{R["all"]["brier"]}</b><small>Brier</small></div><div><b class="u">{R["all"]["matches"]}</b><small>Matches</small></div></div><p class="nt">Live record. Baseline Brier: {R["all"]["base_brier"]}.</p>'
    else:
        kv = f'<div class="kv"><div><b class="u">{B["model"]["correct"]}%</b><small>Called</small></div><div><b class="u">{B["model"]["brier"]}</b><small>Brier</small></div><div><b class="u">{B["matches"]:,}</b><small>Matches</small></div></div><p class="nt">Backtest {B["period"]}. Baseline Brier: {B["base_rates"]["brier"]}. Live record starts with our first scored match.</p>'
    main = (f'<div class="sec"><h1>{TAGLINE}</h1><p class="lead" style="margin-top:8px">Win probabilities for every upcoming match in the {", ".join(x["name"] for x in LEAGUES.values())}, from our own model and checked against the results.</p></div>'
            + (sec("featured", "Featured preview", feat) if feat else "") + ad() + sec("next", "Next matches", groups, "All previews", "/previews/"))
    side = (sec("record", "Our record", kv, "Details", "/record/") + sec("table", f'{LEAGUES[first]["name"]} table', f'<div class="card p0">{table_html(LEAGUES[first]["table"][:6])}</div>', "Full table", f'/leagues/{LEAGUES[first]["slug"]}/') + ad("tall"))
    chips = '<div class="chips">' + "".join(f'<a href="/leagues/{x["slug"]}/"><i class="ld lg{CLS[k]}"></i>{e(x["name"])}</a>' for k, x in LEAGUES.items()) + "</div>"
    emit("/", layout(f"{NAME}: {TAGLINE}", "Win probabilities, form and statistical previews for the Premier League, Championship and Bundesliga, from our own model with a public accuracy record.", "/", chips + f'<div class="cols"><div>{main}</div><div>{side}</div></div>' + ad("lb"), "Home"))
    # previews
    chips2 = '<div class="chips">' + "".join(f'<a href="#{x["slug"]}">{e(x["name"])}</a>' for x in LEAGUES.values()) + "</div>"
    body = chips2 + crumb(("Home", "/"), ("Previews", None)) + '<div class="sec"><h1>Match previews</h1><p class="nt">Win probabilities for every upcoming match. H, D and A are the home, draw and away chances in %. Times are shown in your local time.</p></div><div class="pad">'
    for k, x in LEAGUES.items():
        body += f'<div id="{x["slug"]}" class="sec" style="padding:20px 0 0">{fx_group(k, upcoming(k))}</div>{ad()}'
    emit("/previews/", layout("Football match previews and win probabilities", "Upcoming Premier League, Championship and Bundesliga matches with win probabilities, projected goals and likeliest scores from our own model.", "/previews/", body + "</div>", "Previews"))
    # leagues index
    cards = "".join(f'<a class="card" href="/leagues/{x["slug"]}/" style="margin-bottom:12px"><div class="sec lg{CLS[k]}" style="padding:0"><i class="lgbar"></i><h2>{e(x["name"])}</h2><p class="mu sm" style="margin:6px 0 0">{len(x["table"])} teams &middot; {x["averages"]["goals_pm"]} goals per match &middot; {len(upcoming(k))} upcoming matches</p></div></a>' for k, x in LEAGUES.items())
    emit("/leagues/", layout("Football leagues: tables, fixtures and projections", "All leagues covered by Goalytical, with tables, fixtures and win probabilities.", "/leagues/", crumb(("Home", "/"), ("Leagues", None)) + f'<div class="sec"><h1>Leagues</h1></div><div class="sec">{cards}</div>', "Leagues"))
    record_page()
    method_page()
    simple("/about/", "About Goalytical", "About Goalytical: football statistics and match analysis from our own results-based model, with a public accuracy record.",
           '<div class="sec"><h1>About Goalytical</h1><p class="lead" style="margin-top:8px">We explain football matches with numbers.</p></div><div class="sec"><div class="card"><p>Every win probability on this site comes from our own model, built on match results. We do not copy or import tips from other websites, and we do not publish betting odds or betting tips.</p><p>Projections are estimates, never guarantees. We save every projection before kick-off and score it afterwards, so you can judge us on the <a class="lk" href="/record/">record</a>.</p><p style="margin:0">Read <a class="lk" href="/method/">how the model works</a>. Goalytical is independent and is not affiliated with any league or club.</p></div></div>', "")
    contact = (f'<a class="lk" href="mailto:{e(CONTACT_EMAIL)}">{e(CONTACT_EMAIL)}</a>' if CONTACT_EMAIL else "Contact details will be published here before launch.")
    simple("/contact/", "Contact Goalytical", "How to contact the Goalytical team.", f'<div class="sec"><h1>Contact</h1></div><div class="sec"><div class="card"><p style="margin:0">{contact}</p></div></div>')
    simple("/disclaimer/", "Disclaimer", "Goalytical disclaimer: projections are statistical estimates, not guarantees or betting advice.",
           '<div class="sec"><h1>Disclaimer</h1></div><div class="sec"><div class="card"><p>Goalytical publishes statistical estimates of football results. They are not guarantees, predictions of certain outcomes, or betting advice.</p><p>Football results involve luck. Past accuracy does not promise future accuracy. You are responsible for any decision you make using this information. This site is intended for adults aged 18 and over.</p><p style="margin:0">Team and league names are used only to identify matches. Goalytical is not affiliated with, or endorsed by, any league, club or data provider.</p></div></div>')
    sf = '<div class="sec"><h1>Search</h1><p class="nt">Find a team, league or upcoming match.</p><input id="q" type="search" placeholder="Search teams and leagues" aria-label="Search" autocomplete="off"><div id="res" class="card"></div></div>'
    emit("/search/", layout("Search", "Search teams, leagues and upcoming matches on Goalytical.", "/search/", crumb(("Home", "/"), ("Search", None)) + sf), sitemap=False)
    idx = [{"t": x["name"], "u": f'/leagues/{x["slug"]}/', "k": "League"} for x in LEAGUES.values()]
    idx += [{"t": t["team"], "u": f'/team/{t["slug"]}/', "k": LEAGUES[TEAM_LG[t["slug"]]]["name"]} for t in TEAMS.values()]
    idx += [{"t": f'{f["home"]} v {f["away"]}', "u": f'/match/{f["id"]}/', "k": "Match"} for _, f in allup]
    open(os.path.join(OUT, "search.json"), "w", encoding="utf-8").write(json.dumps(idx, ensure_ascii=False))
    emit("/404.html", layout("Page not found", "This page does not exist.", "/404.html", '<div class="sec"><h1>Page not found</h1><p class="mu">Try search, or go back to the <a class="lk" href="/">home page</a>.</p></div>'), sitemap=False)
    open(os.path.join(OUT, "robots.txt"), "w").write(("User-agent: *\nAllow: /\n" + (f"Sitemap: {SITE_URL}/sitemap.xml\n" if SITE_URL else "")) if INDEXABLE else "User-agent: *\nDisallow: /\n")
    if SITE_URL and INDEXABLE:
        urls = "".join(f"<url><loc>{SITE_URL}{p}</loc></url>" for p in sorted(set(PAGES)))
        open(os.path.join(OUT, "sitemap.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    return len(ups), n_played


def check_links():
    bad, pages = set(), 0
    for root, _, files in os.walk(OUT):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            pages += 1
            src = open(os.path.join(root, fn), encoding="utf-8").read()
            for m in re.findall(r'(?:href|src)="(/[^"#?]*)', src):
                fp = os.path.join(OUT, m.strip("/"), "index.html") if m.endswith("/") else os.path.join(OUT, m.strip("/"))
                if m != "/" and not os.path.exists(fp):
                    bad.add(m)
                if m == "/" and not os.path.exists(os.path.join(OUT, "index.html")):
                    bad.add(m)
    return pages, sorted(bad)


if __name__ == "__main__":
    n_up, n_pl = build()
    pages, bad = check_links()
    lines = ["# Goalytical page builder\n", f"Pages written: {pages}. Upcoming match pages: {n_up}. Played match pages: {n_pl}. Teams: {len(TEAMS)}.\n",
             f"Search engines: {'allowed' if INDEXABLE else 'blocked (staging)'}. Ads: {'on' if ADS else 'off'}.\n"]
    lines.append("Broken internal links: none.\n" if not bad else "Broken internal links:\n" + "\n".join(f"- {b}" for b in bad[:30]) + "\n")
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(text)
