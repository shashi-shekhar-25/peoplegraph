"""PeopleGraph engine: ingest -> resolve -> graph -> org design and skills supply.

Everything runs in-process on this machine: pandas + DuckDB for tables,
NetworkX for the org graph, rapidfuzz for string variants. No network calls.
Succession scoring is not in this module; it ships with the Succession Toolkit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import duckdb
import networkx as nx
import pandas as pd
from rapidfuzz import fuzz

TODAY = date(2026, 9, 22)

COLUMN_ALIASES = {
    "employee code": "emp_code", "employee id": "emp_code", "emp code": "emp_code",
    "employee name": "name", "full name": "name", "name": "name",
    "date of birth": "dob", "dob": "dob",
    "division": "division", "business unit": "division",
    "department": "department", "function": "department",
    "job title": "title", "designation": "title", "role": "title",
    "band": "band", "grade": "band",
    "location": "location", "site": "location",
    "date of joining": "doj", "doj": "doj",
    "date in current role": "date_in_role", "time in role": "date_in_role",
    "last promotion date": "last_promotion",
    "manager employee code": "manager_code", "manager id": "manager_code",
    "employment status": "status", "exit date": "exit_date",
    "last rating": "rating", "potential": "potential",
    "skills": "skills", "email": "email",
}

# Canonical skill -> the spellings seen in the wild. Anything unmatched falls
# through to fuzzy matching against the canonical list.
SKILL_ALIASES = {
    "HPLC": ["h.p.l.c.", "high performance liquid chromatography", "hplc analysis",
             "hplc method dev", "hplc method development"],
    "GMP Auditing": ["cgmp audit", "gmp audits", "good manufacturing practice auditing",
                     "gmp audit"],
    "CAPA": ["c.a.p.a", "corrective and preventive action", "capa closure"],
    "Pharmacovigilance": ["pv", "pharmaco-vigilance", "pharmacovigilence"],
    "ANDA Filings": ["anda filing", "abbreviated new drug application"],
    "Computer System Validation": ["csv", "csv (21 cfr part 11)"],
    "Demand Planning": ["s&op / demand planning"],
    # Common outside pharma: cloud, software, office and CRM names people abbreviate.
    "AWS": ["amazon web services", "aws cloud"],
    "Microsoft Azure": ["azure", "ms azure"],
    "Google Cloud": ["gcp", "google cloud platform"],
    "Kubernetes": ["k8s"],
    "React": ["reactjs", "react.js", "react js"],
    "Node.js": ["nodejs", "node js"],
    "JavaScript": ["js", "java script"],
    "Microsoft Excel": ["excel", "ms excel", "advanced excel"],
    "Power BI": ["powerbi", "power-bi"],
    "Salesforce": ["sfdc", "salesforce crm"],
}

# Two grading systems in one sheet. Level 0 is the top of the house.
BAND_LEVELS = {
    "M6": 0, "DIRECTOR-I": 0,
    "M5": 1, "DIRECTOR-II": 1,
    "M4": 2, "MANAGER-I": 2,
    "M3": 3, "MANAGER-II": 3,
    "E2": 4, "EXECUTIVE-I": 4,
    "E1": 5, "EXECUTIVE-II": 5,
}
CANONICAL_BAND = {0: "M6", 1: "M5", 2: "M4", 3: "M3", 4: "E2", 5: "E1"}

# Roles the business cannot run without. Regulatory-critical ones make a
# vacancy a compliance exposure, not just a headcount gap.
CRITICAL_PATTERNS = [r"^head of", r"^plant head", r"^qualified person",
                     r"^chief ", r"lead$", r"^associate director"]
REGULATORY_PATTERNS = [r"qualified person", r"\bqa\b", r"quality", r"regulatory",
                       r"pharmacovigilance", r"gmp"]

DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y"]

# Potential as two review cycles recorded it.
POTENTIAL_LEVELS = {"well placed": 1.0, "p1": 1.0, "growth": 2.0, "p2": 2.0,
                    "ready for more": 3.0, "p3": 3.0, "hipo": 3.0}


def parse_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    s = str(v).strip()
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None


def months_since(d):
    if d is None:
        return None
    return round((TODAY - d).days / 30.44, 1)


def normalise_name(n: str) -> str:
    n = re.sub(r"\(.*?\)", " ", str(n))            # "(Contract)"
    n = re.sub(r"[^A-Za-z ]", " ", n)              # initials' dots, punctuation
    return " ".join(sorted(w.lower() for w in n.split() if len(w) > 1))


SHORT_CASING: dict[str, str] = {}  # first casing seen of each skill of three characters or fewer


def canonical_skill(raw: str, canon_list: list[str]) -> str:
    s = str(raw).strip()
    if not s:
        return ""
    low = s.lower()
    for canon, aliases in SKILL_ALIASES.items():
        if low == canon.lower() or low in aliases:
            return canon
    # Short names (AWS, Aws, aws) never reach the fuzzy list: merge them on case alone.
    if len(s) <= 3:
        return SHORT_CASING.setdefault(low, s)
    best, score = None, 0
    for canon in canon_list:
        sc = fuzz.token_set_ratio(low, canon.lower())
        if sc > score:
            best, score = canon, sc
    if score >= 88:
        return best
    # Keep acronyms as people typed them; only tidy all-lowercase entries.
    return s if any(ch.isupper() for ch in s) else s.title()


def matches(title: str, patterns) -> bool:
    t = str(title).lower()
    return any(re.search(p, t) for p in patterns)


@dataclass
class Issue:
    kind: str
    detail: str
    codes: list[str] = field(default_factory=list)


@dataclass
class Company:
    people: pd.DataFrame
    graph: nx.DiGraph
    issues: list[Issue]
    con: duckdb.DuckDBPyConnection
    raw_rows: int
    skill_variants_collapsed: int
    merged: list[tuple[str, str]]
    _benches: dict | None = None     # bench cache for the Succession Toolkit

    def counts(self) -> dict:
        by_kind: dict[str, int] = {}
        for i in self.issues:
            by_kind[i.kind] = by_kind.get(i.kind, 0) + 1
        return by_kind

    def sql(self, q: str, params: list | None = None) -> pd.DataFrame:
        return self.con.execute(q, params or []).df()


# --------------------------------------------------------------------------
# ingest + resolve


def load(path_or_buffer) -> Company:
    SHORT_CASING.clear()  # each file keeps its own first casing
    raw = pd.read_csv(path_or_buffer, dtype=str).fillna("")
    raw_rows = len(raw)
    raw.columns = [COLUMN_ALIASES.get(c.strip().lower(), c.strip().lower())
                   for c in raw.columns]

    df = raw.copy()
    for c in ("emp_code", "name", "division", "department", "title", "band",
              "location", "status", "manager_code", "rating", "potential",
              "skills", "email"):
        if c not in df:
            df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df["name"] = df["name"].str.title().str.replace(r"\s+", " ", regex=True)
    df["location"] = df["location"].str.title().str.replace("Us", "US")

    for c in ("dob", "doj", "date_in_role", "last_promotion", "exit_date"):
        df[c] = df[c].map(parse_date) if c in df else None

    issues: list[Issue] = []

    # Bands across two grading systems -> one level.
    df["level"] = df["band"].str.upper().map(BAND_LEVELS)
    legacy = df["band"].str.upper().isin(["DIRECTOR-I", "DIRECTOR-II", "MANAGER-I",
                                          "MANAGER-II", "EXECUTIVE-I", "EXECUTIVE-II"])
    if legacy.any():
        issues.append(Issue("band system mismatch",
                            f"{int(legacy.sum())} rows use the legacy grading system "
                            f"(Manager-II etc.); mapped onto the current bands",
                            df.loc[legacy, "emp_code"].tolist()))
    legacy_pot = df["potential"].str.upper().isin(["P1", "P2", "P3"])
    if legacy_pot.any():
        issues.append(Issue("potential scale mismatch",
                            f"{int(legacy_pot.sum())} rows carry the old P1/P2/P3 potential "
                            f"scale from an earlier review cycle; mapped onto the current one",
                            df.loc[legacy_pot, "emp_code"].tolist()))

    unknown = df["level"].isna()
    if unknown.any():
        issues.append(Issue("unrecognised band", f"{int(unknown.sum())} rows",
                            df.loc[unknown, "emp_code"].tolist()))
    df["level"] = df["level"].fillna(5).astype(int)
    df["band"] = df["level"].map(CANONICAL_BAND)

    # Skills -> canonical vocabulary.
    # Build the vocabulary from the spellings in the file, first casing wins, so
    # SAP MM and eCTD Publishing survive instead of becoming Sap Mm.
    alias_strings = {a for al in SKILL_ALIASES.values() for a in al}
    seen_casing: dict[str, str] = {}
    for row in df["skills"]:
        for raw in str(row).split("|"):
            raw = raw.strip()
            if len(raw) > 3 and raw.lower() not in alias_strings:
                seen_casing.setdefault(raw.lower(), raw)
    canon_list = sorted(set(SKILL_ALIASES) | set(seen_casing.values()))
    collapsed = 0
    skills_col, variant_map = [], {}
    for row in df["skills"]:
        out = []
        for s in str(row).split("|"):
            s = s.strip()
            if not s:
                continue
            c = canonical_skill(s, canon_list)
            if c.lower() != s.lower():
                collapsed += 1
                variant_map.setdefault(c, set()).add(s)
            out.append(c)
        skills_col.append(sorted(set(out)))
    df["skills_list"] = skills_col
    if variant_map:
        worst = max(variant_map.items(), key=lambda kv: len(kv[1]))
        issues.append(Issue("skill variants collapsed",
                            f"{collapsed} skill strings mapped to canonical skills; "
                            f"'{worst[0]}' alone appeared as {len(worst[1]) + 1} spellings",
                            []))

    # Duplicate people: same DOB + fuzzy name, or same email.
    merged: list[tuple[str, str]] = []
    df["nname"] = df["name"].map(normalise_name)
    drop_idx = set()
    for _, group in df.groupby(df["dob"].astype(str)):
        if len(group) < 2 or str(group["dob"].iloc[0]) == "None":
            continue
        rows = list(group.itertuples())
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a.Index in drop_idx or b.Index in drop_idx:
                    continue
                na, nb = df.at[a.Index, "nname"], df.at[b.Index, "nname"]
                score = max(fuzz.token_sort_ratio(na, nb), fuzz.partial_ratio(na, nb))
                if score >= 80:
                    keep, dupe = (a, b) if (a.doj or TODAY) >= (b.doj or TODAY) else (b, a)
                    drop_idx.add(dupe.Index)
                    merged.append((df.at[keep.Index, "emp_code"], df.at[dupe.Index, "emp_code"]))
                    df.at[keep.Index, "skills_list"] = sorted(
                        set(df.at[keep.Index, "skills_list"]) | set(df.at[dupe.Index, "skills_list"]))
                    issues.append(Issue(
                        "duplicate person",
                        f"{df.at[keep.Index,'name']} ({df.at[keep.Index,'emp_code']}) and "
                        f"{df.at[dupe.Index,'name']} ({df.at[dupe.Index,'emp_code']}) "
                        f"share a date of birth — merged, rehire record kept",
                        [df.at[keep.Index, "emp_code"], df.at[dupe.Index, "emp_code"]]))
    alias_of = {dupe: keep for keep, dupe in merged}
    df = df.drop(index=list(drop_idx)).reset_index(drop=True)
    df["manager_code"] = df["manager_code"].map(lambda c: alias_of.get(c, c))

    codes = set(df["emp_code"])

    # Reporting lines: self, missing, exited manager.
    self_rep = df["manager_code"] == df["emp_code"]
    for c in df.loc[self_rep, "emp_code"]:
        issues.append(Issue("self-reporting", f"{c} is recorded as their own manager", [c]))
    df.loc[self_rep, "manager_code"] = ""

    orphan = (~df["manager_code"].isin(codes)) & (df["manager_code"] != "")
    for _, r in df[orphan].iterrows():
        issues.append(Issue("manager not on roster",
                            f"{r['name']} ({r['emp_code']}) reports to {r['manager_code']}, "
                            f"who is not in this file", [r["emp_code"]]))
    df.loc[orphan, "manager_code"] = ""

    status_by_code = dict(zip(df["emp_code"], df["status"]))
    name_by_code = dict(zip(df["emp_code"], df["name"]))
    exit_by_code = dict(zip(df["emp_code"], df["exit_date"]))
    for _, r in df.iterrows():
        m = r["manager_code"]
        if m and status_by_code.get(m) == "Exited":
            issues.append(Issue("manager has exited",
                                f"{r['name']} ({r['emp_code']}) reports to "
                                f"{name_by_code[m]}, who exited "
                                f"{exit_by_code.get(m) or 'earlier this year'}", [r["emp_code"], m]))

    # Blank division: inherit from the manager rather than guess.
    blank = df["division"] == ""
    div_by_code = dict(zip(df["emp_code"], df["division"]))
    for i in df.index[blank]:
        m = df.at[i, "manager_code"]
        inferred = div_by_code.get(m, "")
        df.at[i, "division"] = inferred or "Unassigned"
        issues.append(Issue("division missing",
                            f"{df.at[i,'name']} ({df.at[i,'emp_code']}) had no division; "
                            f"inferred '{df.at[i,'division']}' from reporting line",
                            [df.at[i, "emp_code"]]))

    # Derived fields the rest of the app reads.
    df["months_in_role"] = df["date_in_role"].map(months_since)
    df["months_since_promotion"] = df["last_promotion"].map(months_since)
    df["tenure_months"] = df["doj"].map(months_since)
    df["rating_score"] = df["rating"].str.extract(r"^(\d)").astype(float).fillna(3.0)
    df["potential_score"] = df["potential"].str.lower().map(POTENTIAL_LEVELS).fillna(1.0)
    df["potential"] = df["potential_score"].map({1.0: "Well placed", 2.0: "Growth",
                                                 3.0: "Ready for more"})
    df["is_critical"] = df["title"].map(lambda t: matches(t, CRITICAL_PATTERNS))
    df["is_regulatory"] = df.apply(
        lambda r: bool(r["is_critical"]) and matches(f"{r['title']} {r['division']}",
                                                     REGULATORY_PATTERNS), axis=1)
    df["role_key"] = df["title"].str.strip()

    graph = build_graph(df)

    # Circular reporting lines, found on the graph.
    reports = nx.DiGraph()
    for _, r in df.iterrows():
        if r["manager_code"]:
            reports.add_edge(r["emp_code"], r["manager_code"])
    for cycle in sorted(nx.simple_cycles(reports), key=min):
        # simple_cycles starts wherever set iteration lands, which moves with the
        # hash seed; start at the lowest code so the same line is broken every run.
        k = cycle.index(min(cycle))
        cycle = cycle[k:] + cycle[:k]
        names = " -> ".join(name_by_code.get(c, c) for c in cycle + [cycle[0]])
        issues.append(Issue("circular reporting line",
                            f"{names} — left behind by a reorg", cycle))
        df.loc[df["emp_code"] == cycle[0], "manager_code"] = ""

    con = duckdb.connect(":memory:")
    flat = df.drop(columns=["skills_list", "nname"]).copy()
    flat["skills"] = df["skills_list"].map(lambda s: " | ".join(s))
    con.register("people", flat)

    return Company(people=df, graph=graph, issues=issues, con=con, raw_rows=raw_rows,
                   skill_variants_collapsed=collapsed, merged=merged)


def build_graph(df: pd.DataFrame) -> nx.DiGraph:
    g = nx.DiGraph()
    for _, r in df.iterrows():
        pid = f"person:{r['emp_code']}"
        g.add_node(pid, kind="person", **{k: r[k] for k in
                   ("emp_code", "name", "title", "division", "department", "band",
                    "level", "location", "status", "rating_score", "months_in_role")})
        role = f"role:{r['role_key']}"
        g.add_node(role, kind="role", title=r["role_key"])
        g.add_edge(pid, role, kind="holds_role")
        loc = f"location:{r['location']}"
        g.add_node(loc, kind="location", name=r["location"])
        g.add_edge(pid, loc, kind="based_at")
        for s in r["skills_list"]:
            sid = f"skill:{s}"
            g.add_node(sid, kind="skill", name=s)
            g.add_edge(pid, sid, kind="has_skill")
    for _, r in df.iterrows():
        if r["manager_code"]:
            g.add_edge(f"person:{r['emp_code']}", f"person:{r['manager_code']}",
                       kind="reports_to")
    return g


def chain(co: Company, emp_code: str) -> list[str]:
    """Reporting chain upward, cycle-safe."""
    out, seen, cur = [], set(), emp_code
    by_code = co.people.set_index("emp_code")
    while cur and cur not in seen and cur in by_code.index:
        seen.add(cur)
        out.append(cur)
        cur = by_code.at[cur, "manager_code"]
    return out


def critical_roles(co: Company) -> pd.DataFrame:
    df = co.people
    out = df[df["is_critical"] & (df["status"] != "Exited")].copy()
    return out.sort_values(["level", "division", "title"])[
        ["emp_code", "name", "title", "division", "location", "band", "status", "is_regulatory"]]


def mask_name(name: str) -> str:
    return " ".join(w[0] + "•" * max(len(w) - 1, 1) for w in str(name).split())


# --------------------------------------------------------------------------
# modules that read the same graph

def skills_report(co: Company) -> pd.DataFrame:
    """Supply and demand per skill: who holds it, where, and who needs it."""
    df = co.people[co.people["status"] != "Exited"]
    critical = df[df["is_critical"]]
    demand: dict[str, int] = {}
    for _, r in critical.iterrows():
        for s in r["skills_list"]:
            demand[s] = demand.get(s, 0) + 1

    rows = []
    for skill in sorted({s for lst in df["skills_list"] for s in lst}):
        holders = df[df["skills_list"].map(lambda l: skill in l)]
        leaving = int((holders["status"] == "Notice").sum())
        # Cover for a critical role has to come from someone senior enough to
        # hold it. A hundred junior holders are not a bench.
        # Backup depth: senior enough to hold a critical role, staying, and not
        # already sitting in one of the roles that depends on the skill.
        senior = holders[(holders["level"] <= 3) & (holders["status"] != "Notice")
                         & (~holders["is_critical"])]
        rows.append({
            "skill": skill,
            "holders": len(holders),
            "staying": len(holders) - leaving,
            "leaving": leaving,
            "senior_cover": len(senior),
            "sites": holders["location"].nunique(),
            "senior_sites": int(senior["location"].nunique()),
            "divisions": holders["division"].nunique(),
            "critical_roles_needing_it": demand.get(skill, 0),
        })
    out = pd.DataFrame(rows)
    out["exposure"] = out.apply(
        lambda r: "" if not r["critical_roles_needing_it"]
        else "Single expert" if r["senior_cover"] <= 1
        # Fewer people deep enough to cover it than roles that depend on it.
        else "Thin" if r["senior_cover"] < r["critical_roles_needing_it"]
        else "One site" if r["senior_sites"] == 1
        else "", axis=1)
    return out.sort_values(["critical_roles_needing_it", "senior_cover"],
                           ascending=[False, True])


def org_design(co: Company) -> dict:
    """Span, layers and duplicated roles, read off the reporting edges."""
    df = co.people[co.people["status"] != "Exited"].copy()
    spans = df["manager_code"].value_counts()
    df["direct_reports"] = df["emp_code"].map(spans).fillna(0).astype(int)
    df["layer"] = [len(chain(co, c)) for c in df["emp_code"]]

    managers = df[df["direct_reports"] > 0]
    dupes = (df.groupby(df["title"].str.replace(r",.*$", "", regex=True).str.strip())
               .agg(holders=("emp_code", "size"), divisions=("division", "nunique"),
                    sites=("location", "nunique"))
               .query("holders > 1 and divisions > 1")
               .sort_values(["divisions", "holders"], ascending=False))

    return {
        "layers": df.groupby("layer").agg(people=("emp_code", "size")).reset_index(),
        "widest": managers.nlargest(10, "direct_reports")[
            ["name", "title", "division", "location", "direct_reports", "layer"]],
        "thin_spans": managers[managers["direct_reports"] == 1][
            ["name", "title", "division", "location", "layer"]],
        "duplicated_titles": dupes.reset_index().rename(columns={"title": "role"}),
        "median_span": float(managers["direct_reports"].median()) if len(managers) else 0.0,
        "deepest": int(df["layer"].max()),
        "people": df,
    }


NINE_BOX = {(3, 3): "Ready for more, delivering", (3, 2): "Growth, delivering",
            (3, 1): "Well placed, delivering", (2, 3): "Ready for more, meeting",
            (2, 2): "Growth, meeting", (2, 1): "Well placed, meeting",
            (1, 3): "Ready for more, below", (1, 2): "Growth, below",
            (1, 1): "Well placed, below"}


def nine_box(co: Company, division: str | None = None) -> pd.DataFrame:
    """Calibrated rating against recorded potential. Both come from the sheet."""
    df = co.people[co.people["status"] != "Exited"]
    if division:
        df = df[df["division"] == division]
    perf = df["rating_score"].map(lambda r: 3 if r >= 4 else 2 if r >= 3 else 1)
    pot = df["potential_score"].astype(int)
    grid = pd.DataFrame({"performance": perf, "potential": pot, "emp_code": df["emp_code"],
                         "name": df["name"], "title": df["title"],
                         "division": df["division"]})
    grid["box"] = [NINE_BOX[(p, q)] for p, q in zip(grid["performance"], grid["potential"])]
    return grid
