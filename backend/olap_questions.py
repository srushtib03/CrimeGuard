"""Question-driven OLAP engine for CrimeGuard.
Every question is a Roll-up, Drill-down, Slice, Dice or Pivot over the existing star schema
(fact_crime + dim_crime + dim_location). The warehouse is opened READ-ONLY; nothing is modified."""
import json, sqlite3
from functools import lru_cache
from pathlib import Path
import pandas as pd

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
QUARTERS = {1: "Q1 (Jan–Mar)", 2: "Q2 (Apr–Jun)", 3: "Q3 (Jul–Sep)", 4: "Q4 (Oct–Dec)"}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PERIODS = ["Morning", "Afternoon", "Evening", "Night"]

OPERATIONS = {
    "rollup":    {"title": "Roll-up",    "tagline": "Zoom out: summarise detailed data into bigger groups",   "example": "Month → Quarter → Year"},
    "drilldown": {"title": "Drill-down", "tagline": "Zoom in: break a group into finer detail",               "example": "Quarter → Month → Day"},
    "slice":     {"title": "Slice",      "tagline": "Fix ONE dimension and look at what remains",              "example": "Only District 8"},
    "dice":      {"title": "Dice",       "tagline": "Fix SEVERAL dimensions together to get a small sub-cube", "example": "District 8 + Theft + Q3"},
    "pivot":     {"title": "Pivot",      "tagline": "Rotate the cube: put one dimension on rows, another on columns", "example": "Districts × Crime types"},
}

_DB_PATH = None


def init(db_path):
    global _DB_PATH
    _DB_PATH = Path(db_path)


@lru_cache(maxsize=1)
def cube() -> pd.DataFrame:
    uri = _DB_PATH.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as c:
        df = pd.read_sql_query(
            'SELECT f.date_key, f.hour, f.case_count AS n, f.arrest_flag AS arrest, cr."Primary Type" AS crime_type, '
            'cr.Description AS description, l.District AS district, l."Community Area" AS community, '
            'l."Location Description" AS location_desc '
            "FROM fact_crime f JOIN dim_crime cr ON cr.crime_key=f.crime_key JOIN dim_location l ON l.location_key=f.location_key", c)
    dk = df["date_key"].astype(int)
    df["month"] = (dk // 100) % 100
    df["day"] = dk % 100
    df["quarter"] = (df["month"] - 1) // 3 + 1
    df["date"] = pd.to_datetime(dk.astype(str), format="%Y%m%d")
    df["dow"] = df["date"].dt.dayofweek
    df["weekend"] = df["dow"] >= 5
    df["period"] = pd.cut(df["hour"], [-1, 5, 11, 17, 23], labels=["Night", "Morning", "Afternoon", "Evening"]).astype(str)
    df["district"] = df["district"].astype(str)
    def _area(v):
        try:
            return f"Area {int(float(v))}"
        except (TypeError, ValueError):
            return "Unknown"
    def _dist(v):
        try:
            return str(int(float(v)))
        except (TypeError, ValueError):
            return str(v)
    df["community"] = df["community"].map(_area)
    df["district"] = df["district"].map(_dist)
    return df


# ---------- option lists for the dropdowns ----------
def _district_sort(v):
    return (0, int(v)) if str(v).isdigit() else (1, str(v))


def option_lists():
    d = cube()
    districts = sorted(d["district"].unique(), key=_district_sort)
    crimes = d.groupby("crime_type")["n"].sum().sort_values(ascending=False).index.tolist()
    return {
        "district": [{"value": x, "label": f"District {x}"} for x in districts],
        "crime_type": [{"value": x, "label": x.title()} for x in crimes],
        "quarter": [{"value": str(k), "label": v} for k, v in QUARTERS.items()],
        "month": [{"value": str(i + 1), "label": m} for i, m in enumerate(MONTHS)],
        "hour": [{"value": str(h), "label": f"{h:02d}:00 – {h:02d}:59"} for h in range(24)],
        "period": [{"value": p, "label": f"{p} ({ {'Morning':'6am–12pm','Afternoon':'12pm–6pm','Evening':'6pm–12am','Night':'12am–6am'}[p] })"} for p in PERIODS],
        "dow": [{"value": str(i), "label": x} for i, x in enumerate(DAYS)],
    }


# ---------- registry ----------
REG = {}


def question(qid, op, text, params=(), hierarchy=""):
    def deco(fn):
        REG[qid] = {"id": qid, "operation": op, "question": text, "params": list(params), "hierarchy": hierarchy, "fn": fn}
        return fn
    return deco


def catalog():
    opts = option_lists()
    out = []
    for q in REG.values():
        ps = []
        for i, (name, label, src) in enumerate(q["params"]):
            o = opts[src]
            default = o[1]["value"] if name.endswith("_b") and len(o) > 1 else o[0]["value"]
            ps.append({"name": name, "label": label, "options": o, "default": default})
        out.append({"id": q["id"], "operation": q["operation"], "question": q["question"], "hierarchy": q["hierarchy"], "params": ps})
    return {"operations": OPERATIONS, "questions": out}


def label_of(src, value):
    return next((o["label"] for o in option_lists()[src] if o["value"] == str(value)), str(value))


def ask(qid, params):
    q = REG[qid]
    p = {}
    opts = option_lists()
    for name, label, src in q["params"]:
        val = params.get(name)
        if val is None or val not in [o["value"] for o in opts[src]]:
            val = next(c for c in catalog()["questions"] if c["id"] == qid)["params"][[x[0] for x in q["params"]].index(name)]["default"]
        p[name] = val
    rows, chart, summary = q["fn"](cube(), p)
    return {"id": qid, "operation": q["operation"], "question": q["question"], "hierarchy": q["hierarchy"], "params": p,
            "summary": summary, "chart": chart, "rows": json.loads(pd.DataFrame(rows).to_json(orient="records"))}


# ---------- helpers ----------
def tally(d, col):
    g = d.groupby(col, observed=True).agg(crimes=("n", "sum"), arrests=("arrest", "sum")).reset_index().rename(columns={col: "label"})
    g["arrest_rate"] = (g["arrests"] / g["crimes"] * 100).round(1)
    return g


def fmt(n):
    return f"{int(n):,}"


def peak_low(g, key="crimes", label="label", noun="value"):
    hi, lo = g.loc[g[key].idxmax()], g.loc[g[key].idxmin()]
    return hi, lo


def bar(series, horizontal=False, kind="bar"):
    return {"kind": kind, "x": "label", "series": series, "horizontal": horizontal}


CR = [{"key": "crimes", "name": "Crimes"}]
CRAR = [{"key": "crimes", "name": "Crimes"}, {"key": "arrests", "name": "Arrests"}]


# ================= ROLL-UP =================
@question("ru_year", "rollup", "What was the total number of crimes and arrests for the whole year?", hierarchy="Month → Quarter → Year")
def _(d, p):
    g = tally(d.assign(y=d["date"].dt.year.astype(str)), "y")
    r = g.iloc[0]
    return g, bar(CRAR), f"In {r['label']} there were {fmt(r['crimes'])} recorded crimes and {fmt(r['arrests'])} arrests ({r['arrest_rate']}% of cases)."


@question("ru_quarter", "rollup", "How many crimes happened in each quarter?", hierarchy="Month → Quarter")
def _(d, p):
    g = tally(d, "quarter"); g["label"] = g["label"].map(QUARTERS)
    hi, lo = peak_low(g)
    return g, bar(CRAR), f"{hi['label']} was the busiest quarter with {fmt(hi['crimes'])} crimes; {lo['label']} was the quietest with {fmt(lo['crimes'])}."


@question("ru_month", "rollup", "How many crimes happened in each month?", hierarchy="Day → Month")
def _(d, p):
    g = tally(d, "month").sort_values("label"); g["label"] = g["label"].map(lambda m: MONTHS[m - 1])
    hi, lo = peak_low(g)
    return g, bar(CRAR, kind="line"), f"{hi['label']} had the most crimes ({fmt(hi['crimes'])}) and {lo['label']} the fewest ({fmt(lo['crimes'])})."


@question("ru_district", "rollup", "Which districts have the most crimes?", hierarchy="Location → Community area → District")
def _(d, p):
    g = tally(d, "district").sort_values("crimes", ascending=False).head(10); g["label"] = "District " + g["label"]
    return g, bar(CRAR, horizontal=True), f"{g.iloc[0]['label']} leads with {fmt(g.iloc[0]['crimes'])} crimes, followed by {g.iloc[1]['label']} ({fmt(g.iloc[1]['crimes'])})."


@question("ru_crime", "rollup", "Which crime categories happen the most?", hierarchy="Description → Primary crime type")
def _(d, p):
    g = tally(d, "crime_type").sort_values("crimes", ascending=False).head(10); g["label"] = g["label"].str.title()
    share = g.iloc[0]["crimes"] / len(d) * 100
    return g, bar(CRAR, horizontal=True), f"{g.iloc[0]['label']} is the most common category ({fmt(g.iloc[0]['crimes'])} cases, {share:.1f}% of all crime)."


@question("ru_period", "rollup", "Is crime higher in the morning, afternoon, evening or at night?", hierarchy="Hour → Time of day")
def _(d, p):
    g = tally(d, "period").set_index("label").loc[PERIODS].reset_index()
    hi, lo = peak_low(g)
    return g, bar(CRAR), f"{hi['label']} sees the most crime ({fmt(hi['crimes'])}); {lo['label']} the least ({fmt(lo['crimes'])})."


# ================= DRILL-DOWN =================
@question("dd_quarter_month", "drilldown", "Drill into a quarter: which months made it up?", [("quarter", "Quarter", "quarter")], "Quarter → Month")
def _(d, p):
    q = int(p["quarter"]); g = tally(d[d["quarter"] == q], "month").sort_values("label"); g["label"] = g["label"].map(lambda m: MONTHS[m - 1])
    hi, _lo = peak_low(g)
    return g, bar(CRAR), f"{QUARTERS[q]} had {fmt(g['crimes'].sum())} crimes in total; {hi['label']} contributed the most ({fmt(hi['crimes'])})."


@question("dd_month_day", "drilldown", "Drill into a month: how did crime change day by day?", [("month", "Month", "month")], "Month → Day")
def _(d, p):
    m = int(p["month"]); g = tally(d[d["month"] == m], "day").sort_values("label"); g["label"] = g["label"].astype(str)
    hi, lo = peak_low(g)
    return g, bar(CR, kind="line"), f"In {MONTHS[m-1]}, day {hi['label']} was the peak ({fmt(hi['crimes'])} crimes) and day {lo['label']} the lowest ({fmt(lo['crimes'])})."


@question("dd_crime_desc", "drilldown", "Drill into a crime type: what are its specific kinds?", [("crime_type", "Crime type", "crime_type")], "Primary type → Description")
def _(d, p):
    s = d[d["crime_type"] == p["crime_type"]]; g = tally(s, "description").sort_values("crimes", ascending=False).head(10); g["label"] = g["label"].str.title()
    return g, bar(CRAR, horizontal=True), f"{p['crime_type'].title()} has {s['description'].nunique()} sub-types; the most frequent is “{g.iloc[0]['label']}” ({fmt(g.iloc[0]['crimes'])} cases)."


@question("dd_district_area", "drilldown", "Drill into a district: which community areas drive its crime?", [("district", "District", "district")], "District → Community area")
def _(d, p):
    s = d[d["district"] == p["district"]]; g = tally(s, "community").sort_values("crimes", ascending=False).head(10)
    return g, bar(CRAR, horizontal=True), f"District {p['district']} covers {s['community'].nunique()} community areas; {g.iloc[0]['label']} accounts for {fmt(g.iloc[0]['crimes'])} of its {fmt(len(s))} crimes."


@question("dd_dow_hour", "drilldown", "Drill into a weekday: which hours are the busiest?", [("dow", "Day of week", "dow")], "Day of week → Hour")
def _(d, p):
    k = int(p["dow"]); g = tally(d[d["dow"] == k], "hour").sort_values("label"); g["label"] = g["label"].map(lambda h: f"{h:02d}h")
    hi, _lo = peak_low(g)
    return g, bar(CR, kind="line"), f"On {DAYS[k]}s, crime peaks at {hi['label']} ({fmt(hi['crimes'])} cases across the year)."


# ================= SLICE =================
@question("sl_district", "slice", "Show only one district: what crimes happen there?", [("district", "District", "district")], "Fix District")
def _(d, p):
    s = d[d["district"] == p["district"]]; g = tally(s, "crime_type").sort_values("crimes", ascending=False).head(10); g["label"] = g["label"].str.title()
    return g, bar(CRAR, horizontal=True), f"District {p['district']} recorded {fmt(len(s))} crimes. The top category is {g.iloc[0]['label']} ({fmt(g.iloc[0]['crimes'])})."


@question("sl_month", "slice", "Show only one month: which crimes were most common?", [("month", "Month", "month")], "Fix Month")
def _(d, p):
    m = int(p["month"]); s = d[d["month"] == m]; g = tally(s, "crime_type").sort_values("crimes", ascending=False).head(10); g["label"] = g["label"].str.title()
    return g, bar(CRAR, horizontal=True), f"{MONTHS[m-1]} had {fmt(len(s))} crimes; {g.iloc[0]['label']} was the most common ({fmt(g.iloc[0]['crimes'])})."


@question("sl_hour", "slice", "Show only one hour of the day: what happens then?", [("hour", "Hour", "hour")], "Fix Hour")
def _(d, p):
    h = int(p["hour"]); s = d[d["hour"] == h]; g = tally(s, "crime_type").sort_values("crimes", ascending=False).head(10); g["label"] = g["label"].str.title()
    return g, bar(CRAR, horizontal=True), f"Between {h:02d}:00 and {h:02d}:59 there were {fmt(len(s))} crimes; the most common is {g.iloc[0]['label']} ({fmt(g.iloc[0]['crimes'])})."


@question("sl_crime_district", "slice", "Show only one crime type: where does it happen most?", [("crime_type", "Crime type", "crime_type")], "Fix Crime type")
def _(d, p):
    s = d[d["crime_type"] == p["crime_type"]]; g = tally(s, "district").sort_values("crimes", ascending=False).head(10); g["label"] = "District " + g["label"]
    return g, bar(CRAR, horizontal=True), f"{p['crime_type'].title()} has {fmt(len(s))} cases; {g.iloc[0]['label']} is the hotspot with {fmt(g.iloc[0]['crimes'])}."


# ================= DICE =================
@question("dc_compare", "dice", "Compare two districts for one crime type across the quarters", [("district_a", "District A", "district"), ("district_b", "District B", "district"), ("crime_type", "Crime type", "crime_type")], "District ∈ {A, B} · Crime type · Quarter")
def _(d, p):
    s = d[d["crime_type"] == p["crime_type"]]
    rows = []
    for q in range(1, 5):
        rows.append({"label": QUARTERS[q], "a": int(((s["district"] == p["district_a"]) & (s["quarter"] == q)).sum()), "b": int(((s["district"] == p["district_b"]) & (s["quarter"] == q)).sum())})
    ta, tb = sum(r["a"] for r in rows), sum(r["b"] for r in rows)
    na, nb = f"District {p['district_a']}", f"District {p['district_b']}"
    win = na if ta > tb else nb if tb > ta else "Both districts"
    return rows, bar([{"key": "a", "name": na}, {"key": "b", "name": nb}]), f"For {p['crime_type'].title()}: {na} recorded {fmt(ta)} and {nb} recorded {fmt(tb)}. {win} {'is higher' if win != 'Both districts' else 'are level'} overall."


@question("dc_crime_quarter_period", "dice", "How many cases of a crime type happened in a quarter, during a time of day?", [("crime_type", "Crime type", "crime_type"), ("quarter", "Quarter", "quarter"), ("period", "Time of day", "period")], "Crime type · Quarter · Time of day")
def _(d, p):
    q = int(p["quarter"]); base = d[(d["crime_type"] == p["crime_type"]) & (d["quarter"] == q)]; s = base[base["period"] == p["period"]]
    g = tally(s, "month").sort_values("label"); g["label"] = g["label"].map(lambda m: MONTHS[m - 1])
    share = len(s) / len(base) * 100 if len(base) else 0
    return g, bar(CRAR), f"{fmt(len(s))} {p['crime_type'].title()} cases happened in {QUARTERS[q]} during the {p['period'].lower()} — {share:.0f}% of that crime's cases in the quarter."


@question("dc_district_quarter", "dice", "In one district and quarter, which crimes were most common?", [("district", "District", "district"), ("quarter", "Quarter", "quarter")], "District · Quarter · Crime type")
def _(d, p):
    q = int(p["quarter"]); s = d[(d["district"] == p["district"]) & (d["quarter"] == q)]; g = tally(s, "crime_type").sort_values("crimes", ascending=False).head(8); g["label"] = g["label"].str.title()
    return g, bar(CRAR, horizontal=True), f"District {p['district']} in {QUARTERS[q]}: {fmt(len(s))} crimes, led by {g.iloc[0]['label']} ({fmt(g.iloc[0]['crimes'])})."


@question("dc_weekend", "dice", "For one crime type, how do arrests compare on weekdays vs weekends?", [("crime_type", "Crime type", "crime_type")], "Crime type · Weekday/Weekend · Arrest outcome")
def _(d, p):
    s = d[d["crime_type"] == p["crime_type"]]; rows = []
    for name, flag in (("Weekdays", False), ("Weekends", True)):
        x = s[s["weekend"] == flag]; rows.append({"label": name, "arrests": int(x["arrest"].sum()), "no_arrest": int(len(x) - x["arrest"].sum()), "arrest_rate": round(x["arrest"].mean() * 100, 1) if len(x) else 0})
    return rows, bar([{"key": "arrests", "name": "Arrest"}, {"key": "no_arrest", "name": "No arrest"}]), f"{p['crime_type'].title()} arrest rate: {rows[0]['arrest_rate']}% on weekdays vs {rows[1]['arrest_rate']}% on weekends."


# ================= PIVOT =================
def matrix(rows, columns, title_col, total=True, sort=False):
    if total:
        for r in rows:
            r["Total"] = int(sum(r[c] for c in columns))
        columns = columns + ["Total"]
    if sort:
        rows = sorted(rows, key=lambda r: r["Total"], reverse=True)
    return rows, {"kind": "matrix", "x": "label", "columns": columns, "rowHeader": title_col}


@question("pv_district_crime", "pivot", "Pivot: districts (rows) against the top crime types (columns)", hierarchy="District × Crime type")
def _(d, p):
    top_c = d["crime_type"].value_counts().head(6).index.tolist(); top_d = d["district"].value_counts().head(8).index.tolist()
    ct = pd.crosstab(d[d["district"].isin(top_d)]["district"], d["crime_type"]).reindex(index=top_d, columns=top_c).fillna(0).astype(int)
    rows = [{"label": f"District {i}", **{c.title(): int(ct.loc[i, c]) for c in top_c}} for i in ct.index]
    r, ch = matrix(rows, [c.title() for c in top_c], "District", sort=True)
    return r, ch, f"Rows are the 8 busiest districts, columns the 6 most common crimes. Darker cells = more cases. {r[0]['label']} has the highest total in this table ({fmt(r[0]['Total'])})."


@question("pv_month_crime", "pivot", "Pivot: months (rows) against the top crime types (columns)", hierarchy="Month × Crime type")
def _(d, p):
    top_c = d["crime_type"].value_counts().head(5).index.tolist()
    ct = pd.crosstab(d["month"], d["crime_type"]).reindex(columns=top_c).fillna(0).astype(int)
    rows = [{"label": MONTHS[m - 1], **{c.title(): int(ct.loc[m, c]) for c in top_c}} for m in ct.index]
    r, ch = matrix(rows, [c.title() for c in top_c], "Month")
    return r, ch, "Each row is a month and each column a crime type — scan down a column to see its seasonal pattern."


@question("pv_dow_period", "pivot", "Pivot: day of week (rows) against time of day (columns)", hierarchy="Day of week × Time of day")
def _(d, p):
    ct = pd.crosstab(d["dow"], d["period"]).reindex(columns=PERIODS).fillna(0).astype(int)
    rows = [{"label": DAYS[k], **{c: int(ct.loc[k, c]) for c in PERIODS}} for k in ct.index]
    r, ch = matrix(rows, PERIODS, "Day")
    flat = ct.stack(); (k, per) = flat.idxmax()
    return r, ch, f"The single busiest slot is {DAYS[k]} {per.lower()} ({fmt(flat.max())} cases)."


@question("pv_quarter_arrest", "pivot", "Pivot: quarters (rows) against arrest outcome (columns)", hierarchy="Quarter × Arrest outcome")
def _(d, p):
    rows = []
    for q in range(1, 5):
        x = d[d["quarter"] == q]; rows.append({"label": QUARTERS[q], "Arrest": int(x["arrest"].sum()), "No arrest": int(len(x) - x["arrest"].sum())})
    r, ch = matrix(rows, ["Arrest", "No arrest"], "Quarter")
    best = max(rows, key=lambda z: z["Arrest"] / z["Total"])
    return r, ch, f"{best['label']} has the highest arrest rate ({best['Arrest']/best['Total']*100:.1f}%)."


@question("pv_district_quarter", "pivot", "Pivot: districts (rows) against quarters (columns)", hierarchy="District × Quarter")
def _(d, p):
    top_d = d["district"].value_counts().head(8).index.tolist()
    ct = pd.crosstab(d["district"], d["quarter"]).reindex(index=top_d).fillna(0).astype(int)
    rows = [{"label": f"District {i}", **{QUARTERS[q]: int(ct.loc[i, q]) for q in range(1, 5)}} for i in ct.index]
    r, ch = matrix(rows, [QUARTERS[q] for q in range(1, 5)], "District", sort=True)
    return r, ch, "Compare how each busy district behaves across the year — a row that shifts colour shows a seasonal district."
