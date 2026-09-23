"""Synthetic pharma HRIS export, traps included.

Produces data/employees_messy.csv: ~500 people plus last year's leavers, eight divisions, with the
mess a real export carries (duplicate rehires, a reorg cycle, exited
managers, five spellings of one skill, two grading systems, blank divisions),
plus last year's leavers so the attrition model has history to learn from.

All names and structures are Faker output. Nothing from any employer.
"""
import csv
import math
import random
from datetime import date, timedelta

from faker import Faker

SEED = 20260922
fake = Faker("en_IN")
Faker.seed(SEED)
rng = random.Random(SEED)

TODAY = date(2026, 9, 22)

LOCATIONS = [
    "Bengaluru", "Hyderabad", "Ahmedabad", "Mumbai",
    "Visakhapatnam", "Baddi", "Pune", "Princeton, US",
]

# division -> (departments, canonical skills, title stems by level 2..5)
DIVISIONS = {
    "Quality": (
        ["QA Compliance", "QC Analytical", "Quality Systems", "Validation"],
        ["GMP Auditing", "Deviation Management", "HPLC", "CAPA", "Batch Record Review",
         "Computer System Validation", "Stability Studies", "Method Validation"],
        ["Head of QA", "Head of QC", "Head of Quality Systems", "Qualified Person"],
    ),
    "Manufacturing": (
        ["OSD Production", "Sterile Fill-Finish", "Engineering", "Packaging"],
        ["Tech Transfer", "Aseptic Processing", "Lean Manufacturing", "Equipment Qualification",
         "Granulation", "Shop Floor Scheduling", "GMP Auditing"],
        ["Plant Head", "Head of Production", "Head of Engineering", "Site Operations Lead"],
    ),
    "R&D": (
        ["Formulation Development", "Analytical R&D", "Process Chemistry", "IP & Patents"],
        ["Formulation Development", "HPLC", "Process Chemistry", "Design of Experiments",
         "Patent Drafting", "Scale-up", "Method Validation"],
        ["Head of Formulation", "Head of Analytical R&D", "Head of Process Chemistry"],
    ),
    "Regulatory": (
        ["Regulatory CMC", "Regulatory Operations", "Labelling"],
        ["ANDA Filings", "eCTD Publishing", "US FDA Liaison", "EU MDR", "Labelling Compliance",
         "Regulatory Strategy"],
        ["Head of Regulatory Affairs", "Head of Regulatory CMC", "Regulatory Operations Lead"],
    ),
    "Clinical": (
        ["Clinical Operations", "Pharmacovigilance", "Medical Affairs"],
        ["Clinical Trial Management", "Pharmacovigilance", "GCP Auditing", "Signal Detection",
         "Protocol Design", "Medical Writing"],
        ["Head of Clinical Operations", "Head of Pharmacovigilance", "Medical Affairs Lead"],
    ),
    "Supply Chain": (
        ["Procurement", "Planning", "Warehouse & Distribution"],
        ["Demand Planning", "Cold Chain Logistics", "Vendor Qualification", "SAP MM",
         "Serialisation", "Inventory Optimisation"],
        ["Head of Supply Chain", "Head of Procurement", "Head of Planning"],
    ),
    "Commercial": (
        ["Sales", "Marketing", "Market Access"],
        ["Key Account Management", "Brand Strategy", "Tender Management", "Pricing Strategy",
         "Market Access", "CRM Analytics"],
        ["Head of Sales", "Head of Marketing", "Head of Market Access"],
    ),
    "Corporate": (
        ["Human Resources", "Finance", "IT", "Legal"],
        ["Talent Management", "Financial Planning & Analysis", "SAP FICO", "Contract Law",
         "IT Infrastructure", "Data Privacy"],
        ["Head of HR", "Head of Finance", "Head of IT", "Head of Legal"],
    ),
}

IC_STEMS = {
    2: "Associate Director, {dept}",
    3: "Manager, {dept}",
    4: "Senior Executive, {dept}",
    5: "Executive, {dept}",
}

# Two grading systems live in the sheet: the current one and one inherited
# from an acquisition. Same level, different label.
BANDS = {0: "M6", 1: "M5", 2: "M4", 3: "M3", 4: "E2", 5: "E1"}
LEGACY_BANDS = {0: "Director-I", 1: "Director-II", 2: "Manager-I",
                3: "Manager-II", 4: "Executive-I", 5: "Executive-II"}

# Skill strings as people actually type them.
SKILL_VARIANTS = {
    "HPLC": ["HPLC", "H.P.L.C.", "High Performance Liquid Chromatography",
             "hplc analysis", "HPLC method dev"],
    "GMP Auditing": ["GMP Auditing", "cGMP audit", "GMP audits", "Good Manufacturing Practice auditing"],
    "CAPA": ["CAPA", "C.A.P.A", "Corrective and Preventive Action", "capa closure"],
    "Pharmacovigilance": ["Pharmacovigilance", "PV", "Pharmaco-vigilance", "pharmacovigilence"],
    "ANDA Filings": ["ANDA Filings", "ANDA filing", "Abbreviated New Drug Application"],
    "Computer System Validation": ["Computer System Validation", "CSV", "CSV (21 CFR Part 11)"],
    "Demand Planning": ["Demand Planning", "demand planning", "S&OP / demand planning"],
}

RATINGS = ["1 - Below", "2 - Partially Meets", "3 - Meets", "4 - Exceeds", "5 - Outstanding"]
# Potential is captured at the talent council, and two review cycles used two
# different vocabularies before anyone standardised them.
POTENTIAL = ["Well placed", "Growth", "Ready for more"]
POTENTIAL_LEGACY = ["P1", "P2", "P3"]


def d(day: date, fmt: int) -> str:
    """Dates arrive in whatever format the source system used."""
    return [day.isoformat(), day.strftime("%d-%m-%Y"), day.strftime("%d/%m/%Y"),
            day.strftime("%d-%b-%Y")][fmt]


def messy_skill(canonical: str) -> str:
    return rng.choice(SKILL_VARIANTS.get(canonical, [canonical]))


def make_row(code, name, dob, level, division, dept, title, location, manager_code, skills):
    joined = TODAY - timedelta(days=rng.randint(180, 5200))
    in_role = TODAY - timedelta(days=rng.randint(90, min(2600, (TODAY - joined).days or 90)))
    promoted = in_role if rng.random() < 0.7 else joined
    legacy = rng.random() < 0.18
    return {
        "Employee Code": code,
        "Employee Name": name,
        "Date of Birth": d(dob, rng.randint(0, 3)),
        "Division": division,
        "Department": dept,
        "Job Title": title,
        "Band": (LEGACY_BANDS if legacy else BANDS)[level],
        "Location": location,
        "Date of Joining": d(joined, rng.randint(0, 3)),
        "Date In Current Role": d(in_role, rng.randint(0, 3)),
        "Last Promotion Date": d(promoted, rng.randint(0, 3)),
        "Manager Employee Code": manager_code or "",
        "Employment Status": "Active",
        "Exit Date": "",
        "Last Rating": rng.choices(RATINGS, weights=[2, 8, 45, 32, 13])[0],
        "Potential": (POTENTIAL_LEGACY if rng.random() < 0.22 else POTENTIAL)[
            rng.choices([0, 1, 2], weights=[52, 34, 14])[0]],
        "Skills": " | ".join(messy_skill(s) for s in skills),
        "Email": "",
    }


def build():
    rows = []
    code_n = 10000

    def next_code():
        nonlocal code_n
        code_n += rng.randint(1, 4)
        return f"EMP{code_n}"

    dob = lambda lo, hi: TODAY - timedelta(days=rng.randint(lo * 365, hi * 365))

    ceo_code = next_code()
    rows.append(make_row(ceo_code, fake.name(), dob(50, 60), 0, "Corporate", "Executive Office",
                         "Chief Executive Officer", "Mumbai", "", ["Talent Management"]))

    # Target headcount per division, tapering down the pyramid.
    plan = {"Quality": 105, "Manufacturing": 95, "R&D": 70, "Regulatory": 45,
            "Clinical": 45, "Supply Chain": 45, "Commercial": 55, "Corporate": 39}

    for division, headcount in plan.items():
        depts, skills, head_titles = DIVISIONS[division]
        div_loc = rng.choice(LOCATIONS[:7])
        head_code = next_code()
        rows.append(make_row(head_code, fake.name(), dob(44, 56), 1, division, depts[0],
                             f"Head of {division}", div_loc, ceo_code,
                             rng.sample(skills, 3)))

        # Level 2: the named critical roles, one per department where possible.
        l2 = []
        for i, dept in enumerate(depts):
            title = head_titles[i] if i < len(head_titles) else IC_STEMS[2].format(dept=dept)
            c = next_code()
            # The demo names Head of QA, Bengaluru; pin it so the script holds.
            loc = "Bengaluru" if title == "Head of QA" else rng.choice(LOCATIONS[:7])
            rows.append(make_row(c, fake.name(), dob(38, 52), 2, division, dept,
                                 f"{title}, {loc}" if title.startswith("Head") else title,
                                 loc, head_code, rng.sample(skills, 4)))
            l2.append((c, dept, loc))

        remaining = headcount - 1 - len(l2)
        # Split the rest across L3/L4/L5 as a pyramid. Teams are handed out
        # round-robin rather than at random: real sites have even-ish spans,
        # not a crowd of managers with one report each.
        counts = {3: int(remaining * 0.10), 4: int(remaining * 0.25)}
        counts[5] = remaining - counts[3] - counts[4]
        parents = {3: l2}
        for level in (3, 4, 5):
            made = []
            pool = parents[level]
            for i in range(max(counts[level], 0)):
                pcode, dept, loc = pool[i % len(pool)]
                c = next_code()
                loc2 = loc if rng.random() < 0.8 else rng.choice(LOCATIONS[:7])
                rows.append(make_row(c, fake.name(), dob(24 + level * 3, 34 + level * 3), level,
                                     division, dept, IC_STEMS[level].format(dept=dept),
                                     loc2, pcode, rng.sample(skills, rng.randint(2, 4))))
                made.append((c, dept, loc2))
            parents[level + 1] = made or parents[level]

    by_code = {r["Employee Code"]: r for r in rows}

    # ---- traps ----------------------------------------------------------
    traps = []

    # 1. A rehire recorded twice: same DOB, two codes, name written both ways.
    victim = next(r for r in rows if r["Band"] in ("M3", "Manager-II"))
    victim["Employee Name"] = "Priya Nair"
    dup = dict(victim)
    dup["Employee Code"] = next_code()
    dup["Employee Name"] = "Nair Priya R."
    dup["Email"] = "priya.nair@example-pharma.test"
    dup["Date of Joining"] = d(TODAY - timedelta(days=400), 1)
    rows.append(dup)
    traps.append("duplicate person: Priya Nair / Nair Priya R.")

    # Two more duplicates, less obvious: initials and a married surname.
    for original, variant in [("{first} {last}", "{first_initial}. {last}"),
                              ("{first} {last}", "{first} {last} (Contract)")]:
        src = rng.choice([r for r in rows if r["Band"] in ("E1", "E2", "Executive-I", "Executive-II")])
        parts = src["Employee Name"].split()
        dup = dict(src)
        dup["Employee Code"] = next_code()
        dup["Employee Name"] = variant.format(first=parts[0], last=parts[-1],
                                              first_initial=parts[0][0])
        rows.append(dup)
        traps.append(f"duplicate person: {src['Employee Name']} / {dup['Employee Name']}")

    # 2. A reorg left a two-person loop.
    a, b = rng.sample([r for r in rows if r["Band"] in ("M4", "Manager-I")], 2)
    a["Manager Employee Code"] = b["Employee Code"]
    b["Manager Employee Code"] = a["Employee Code"]
    traps.append(f"circular reporting: {a['Employee Code']} <-> {b['Employee Code']}")

    # 3. Managers who have already exited, still on the org chart.
    managers = [r for r in rows if any(x["Manager Employee Code"] == r["Employee Code"] for x in rows)]
    for leaver in rng.sample(managers, 3):
        leaver["Employment Status"] = "Exited"
        leaver["Exit Date"] = d(TODAY - timedelta(days=rng.randint(60, 300)), 0)
        traps.append(f"exited manager still has reports: {leaver['Employee Code']}")

    # 4. A manager code that never existed (typo at data entry).
    orphan = rng.choice([r for r in rows if r["Band"] in ("E1", "Executive-II")])
    orphan["Manager Employee Code"] = "EMP99999"
    traps.append(f"manager code not on roster: {orphan['Employee Code']} -> EMP99999")

    # 5. Contract-to-permanent conversions came across without a division.
    batch = rng.sample([r for r in rows if r["Band"] in ("E1", "E2", "Executive-I", "Executive-II")], 14)
    for r in batch:
        r["Division"] = ""
    traps.append(f"blank division for {len(batch)} contract-to-permanent conversions")

    # 6. People on notice, including one strong successor on the QA bench —
    #    a bench that quietly drops leavers is how councils get surprised.
    strong = rng.choice([r for r in rows if "QA Compliance" in r["Department"]
                         and r["Band"] in ("M3", "M4", "Manager-I", "Manager-II")
                         and "Nair" not in r["Employee Name"]])
    # Give them a genuine QA bench profile, so the bench has to deal with them.
    qa_head = next(r for r in rows if r["Job Title"].startswith("Head of QA"))
    strong["Skills"] = qa_head["Skills"]
    strong["Last Rating"] = "4 - Exceeds"
    strong["Employment Status"] = "Notice"
    traps.append(f"strong QA successor on notice: {strong['Employee Code']}")
    for r in rng.sample([x for x in rows if x["Employment Status"] == "Active"], 8):
        r["Employment Status"] = "Notice"
    traps.append("9 people serving notice")

    # 7. Someone reporting to themselves.
    selfie = rng.choice([r for r in rows if r["Band"] == "E2"])
    selfie["Manager Employee Code"] = selfie["Employee Code"]
    traps.append(f"self-reporting: {selfie['Employee Code']}")

    # Cosmetic mess: stray whitespace and casing, as exports have.
    for r in rows:
        if rng.random() < 0.08:
            r["Employee Name"] = f"  {r['Employee Name'].upper()} "
        if rng.random() < 0.06:
            r["Location"] = r["Location"].lower()
        if not r["Email"]:
            n = "".join(ch for ch in r["Employee Name"].lower() if ch.isalpha() or ch == " ")
            r["Email"] = ".".join(n.split()[:2]) + "@example-pharma.test"

    rng.shuffle(rows)
    return rows, traps


def add_leavers(rows, n=72):
    """People who left in the last twelve months, as an HRIS exports them: status
    Exited with an exit date.

    The pattern is seeded on purpose, and the guides say so: no promotion for three
    years, "Well placed" potential, the first two years in the company and a sales
    role each raise the odds of leaving. (Nobody in their first two years can have
    gone three without a promotion, so that condition carries the larger weight.)
    Everything else is drawn the way make_row
    draws the people who stayed, counted back from the exit date, so the only
    difference a model can find is the one planted here.

    Its own random stream: every row build() makes stays exactly as it was.
    """
    lr = random.Random(SEED + 1)
    lf = Faker("en_IN")
    lf.seed_instance(SEED + 1)
    # Copy only clean rows, so the planted faults stay the ones build() planted.
    gone = {r["Employee Code"] for r in rows if r["Employment Status"] == "Exited"}
    pool = [r for r in rows if r["Employment Status"] == "Active" and r["Division"]
            and r["Manager Employee Code"] not in gone and r["Band"] in
            ("M3", "E2", "E1", "Manager-II", "Executive-I", "Executive-II")
            and not r["Job Title"].startswith(("Head of", "Plant Head", "Qualified Person", "Chief"))
            and not r["Job Title"].endswith("Lead")]
    out = []
    while len(out) < n:
        like = lr.choice(pool)
        left = TODAY - timedelta(days=lr.randint(5, 360))
        joined = left - timedelta(days=lr.randint(180, 5200))
        in_role = left - timedelta(days=lr.randint(90, min(2600, (left - joined).days or 90)))
        promoted = in_role if lr.random() < 0.7 else joined
        potential = POTENTIAL[lr.choices([0, 1, 2], weights=[52, 34, 14])[0]]
        z = (-6.0 + 3.0 * ((left - promoted).days > 3 * 365) + 2.2 * (potential == "Well placed")
             + 4.2 * ((left - joined).days < 2 * 365) + 2.0 * (like["Division"] == "Commercial"))
        if lr.random() > 1 / (1 + math.exp(-z)):
            continue
        name = lf.name()
        out.append({**like,
                    "Employee Code": f"EMP3{len(out):04d}",
                    "Employee Name": name,
                    "Date of Birth": d(left - timedelta(days=lr.randint(24 * 365, 50 * 365)), lr.randint(0, 3)),
                    "Date of Joining": d(joined, lr.randint(0, 3)),
                    "Date In Current Role": d(in_role, lr.randint(0, 3)),
                    "Last Promotion Date": d(promoted, lr.randint(0, 3)),
                    "Employment Status": "Exited",
                    "Exit Date": d(left, 0),
                    "Last Rating": lr.choices(RATINGS, weights=[2, 8, 45, 32, 13])[0],
                    "Potential": potential,
                    "Email": ".".join(name.lower().split()[:2]) + "@example-pharma.test"})
    return out


def main():
    rows, traps = build()
    leavers = add_leavers(rows)
    rows += leavers
    traps.append(f"{len(leavers)} leavers in the last twelve months (seeded attrition pattern)")
    path = "data/employees_messy.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {path}")
    for t in traps:
        print(f"  trap: {t}")


if __name__ == "__main__":
    main()
