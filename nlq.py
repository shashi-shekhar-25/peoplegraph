"""Natural-language query box.

A local Ollama model turns a question into an intent + slots. If Ollama is
not running, or answers with nonsense, a keyword router takes over — the
five templated questions always work either way. Only localhost is touched.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
# Small models first: they run on an ordinary 8 GB laptop. gemma3:4b writes Indian
# languages better if the laptop has 16 GB.
PREFERRED_MODELS = ["gemma3:4b", "qwen2.5:3b-instruct", "qwen2.5:1.5b", "llama3.2:3b", "llama3.1:8b"]
RECOMMENDED_PULL = "ollama pull qwen2.5:1.5b"
OLLAMA_DOWNLOAD = "https://ollama.com/download"
LANGUAGES = ["English", "हिन्दी (Hindi)", "मराठी (Marathi)", "தமிழ் (Tamil)", "తెలుగు (Telugu)",
             "ಕನ್ನಡ (Kannada)", "বাংলা (Bengali)", "ગુજરાતી (Gujarati)", "മലയാളം (Malayalam)"]

INTENTS = {
    "successors": "who could take over a named role or person",
    "flight_risks": "who is at risk of leaving, optionally in one division",
    "single_points_of_failure": "which critical roles have no ready-now successor",
    "data_quality": "what was wrong with the uploaded sheet",
    "headcount": "how many people match a skill, location or division",
}

TEMPLATES = [
    ("Who can replace the Head of QA, and is anyone a flight risk?",
     {"intent": "successors", "target": "Head of QA"}),
    ("Which critical roles have no ready-now successor?",
     {"intent": "single_points_of_failure"}),
    ("Who is a flight risk in Quality?",
     {"intent": "flight_risks", "division": "Quality"}),
    ("What did the ingestion fix in this sheet?",
     {"intent": "data_quality"}),
    ("How many people have HPLC in Hyderabad?",
     {"intent": "headcount", "skill": "HPLC", "location": "Hyderabad"}),
]

SYSTEM = """You convert an HR question into JSON. Reply with JSON only.
Schema: {"intent": one of %s, "target": string or null, "division": string or null,
"location": string or null, "skill": string or null}
intent meanings: %s

Examples:
Question: Who could step into the Plant Head job in Pune?
JSON: {"intent": "successors", "target": "Plant Head", "division": null, "location": "Pune", "skill": null}
Question: Which critical roles have no ready-now successor?
JSON: {"intent": "single_points_of_failure", "target": null, "division": null, "location": null, "skill": null}
Question: How many people have HPLC in Hyderabad?
JSON: {"intent": "headcount", "target": null, "division": null, "location": "Hyderabad", "skill": "HPLC"}
""" % (list(INTENTS), "; ".join(f"{k}: {v}" for k, v in INTENTS.items()))


def available_model() -> str | None:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=1.5) as r:
            names = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return None
    for p in PREFERRED_MODELS:
        for n in names:
            if n.startswith(p.split(":")[0]) and p.split(":")[1] in n:
                return n
    return names[0] if names else None


def ask_model(question: str, model: str, timeout: float = 25.0) -> dict | None:
    body = json.dumps({
        "model": model,
        "prompt": f"{SYSTEM}\n\nQuestion: {question}\nJSON:",
        "format": "json", "stream": False,
        "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", body,
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.load(r).get("response", "")
        parsed = json.loads(out)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError, ValueError):
        return None
    if not isinstance(parsed, dict) or parsed.get("intent") not in INTENTS:
        return None
    return {k: (v or None) for k, v in parsed.items()}


def _numbers(text: str) -> list[str]:
    """Every number in a text, with Indian-script digits read as 0-9."""
    import unicodedata
    ascii_ = "".join(str(unicodedata.digit(ch)) if ch.isdigit() else ch for ch in text)
    return re.findall(r"\d+(?:\.\d+)?", ascii_.replace(",", ""))


def explain(summary: str, language: str, model: str | None, timeout: float = 90.0) -> tuple[str, str]:
    """Put a summary PeopleGraph has already written into the reader's language.

    The summary is plain English with every figure worked out by the toolkit, never by
    the model. The model on 127.0.0.1 only translates it; if any number comes back
    changed, the translation is thrown away and the English is shown. Returns
    (text, how) where how says which of the two the reader is looking at.
    """
    if language.startswith("English") or not model:
        return summary, "written by PeopleGraph from the figures"
    prompt = (f"Translate the text below into simple {language} for the head of HR of an Indian company. "
              "Keep every number exactly as written, using the digits 0-9. Do not add, remove or explain "
              "anything. Reply with the translation only.\n\n" + summary)
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/generate", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = json.load(r).get("response", "").strip()
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError, ValueError):
        return summary, "the local model did not answer, so this is the English"
    if not text or sorted(_numbers(text)) != sorted(_numbers(summary)):
        return summary, "the local model changed a number, so this is the English it was given"
    return text, f"translated by {model} on this machine; every number checked against the English"


DIVISIONS = ["Quality", "Manufacturing", "R&D", "Regulatory", "Clinical",
             "Supply Chain", "Commercial", "Corporate"]


def keyword_route(question: str) -> dict:
    q = question.lower()
    slots: dict = {"intent": "data_quality"}
    if re.search(r"replace|successor|succeed|take over|bench", q):
        slots["intent"] = "successors"
        m = re.search(r"(?:for|replace|of)\s+(?:the\s+)?([a-z0-9 ,&/-]{3,45})", q)
        slots["target"] = m.group(1).strip(" ?.") if m else None
    elif re.search(r"flight risk|at risk|leaving|attrition|resign", q):
        slots["intent"] = "flight_risks"
    elif re.search(r"single point|no ready|no successor|exposed|bus factor", q):
        slots["intent"] = "single_points_of_failure"
    elif re.search(r"how many|count|headcount|people with|who has", q):
        slots["intent"] = "headcount"
    elif re.search(r"quality of the (data|sheet)|duplicate|dirty|ingest|clean", q):
        slots["intent"] = "data_quality"
    for d in DIVISIONS:
        if d.lower() in q:
            slots["division"] = d
    return slots


def route(question: str, model: str | None) -> tuple[dict, str]:
    """Returns (slots, how) where how is 'local model' or 'keyword fallback'."""
    if model:
        slots = ask_model(question, model)
        if slots:
            kw = keyword_route(question)
            slots["division"] = slots.get("division") or kw.get("division")
            # Two phrasings the small model keeps mis-filing; the regex is sure.
            if kw["intent"] == "single_points_of_failure":
                slots["intent"] = kw["intent"]
            if slots["intent"] == "headcount" and not slots.get("skill"):
                slots["skill"] = slots.get("target")
            return slots, f"local model ({model})"
    return keyword_route(question), "keyword fallback"


# --------------------------------------------------------------------------
# executing a routed question against the graph

def resolve_target(co, text: str | None):
    """Find the person whose role the question is about."""
    from rapidfuzz import fuzz as _f
    if not text:
        return None
    q = text.strip().lower()
    pool = co.people[co.people["status"] != "Exited"]
    # A title that literally contains the phrase beats any fuzzy match;
    # "Head of QA" must not drift to "Head of Market Access".
    exact = [r for _, r in pool.iterrows()
             if q in str(r["title"]).lower() or q in str(r["name"]).lower()]
    if exact:
        return sorted(exact, key=lambda r: (int(r["level"]), len(str(r["title"]))))[0]["emp_code"]
    best, score = None, 0
    for _, r in pool.iterrows():
        sc = max(_f.WRatio(q, str(r["title"]).lower()), _f.WRatio(q, str(r["name"]).lower()))
        if sc > score:
            best, score = r["emp_code"], sc
    return best if score >= 88 else None


NEEDS_TOOLKIT = ("That question needs the succession engine, which ships with the PeopleGraph "
                 "Succession Toolkit rather than the open-source build. The data-quality and "
                 "headcount questions work here.")


def answer(co, slots: dict, fmt=lambda n, code="": n):
    """Returns (headline, table_or_none, extra_dict). fmt masks names on the way out."""
    intent = slots.get("intent")
    try:
        import succession as sx
    except ImportError:
        sx = None
    if sx is None and intent in ("successors", "flight_risks", "single_points_of_failure"):
        return NEEDS_TOOLKIT, None, {}

    if intent == "successors":
        code = resolve_target(co, slots.get("target"))
        if not code:
            return "I could not match that role in this sheet.", None, {}
        b = sx.bench(co, code)
        t = b["target"]
        risky = ", ".join(fmt(c["name"], c["emp_code"]) for c in b["ready_now_at_risk"])
        head = (f"{t['title']} — {fmt(t['name'], t['emp_code'])}: {b['ready_now']} ready now"
                + (f". Flight risk on {risky}." if risky else ". No flight risk on the ready-now bench."))
        if b["single_point_of_failure"]:
            head += " Single point of failure."
        return head, b, {"bench": True}

    if intent == "flight_risks":
        div = slots.get("division")
        df = sx.flight_risks(co, div)
        n_high = int((df["risk"] == "High").sum()) if not df.empty else 0
        return (f"{len(df)} people flagged{' in ' + div if div else ''}, {n_high} high risk.",
                df, {})

    if intent == "single_points_of_failure":
        df = sx.spof_report(co)
        thin = df[df["ready_now"] <= 1]
        return (f"{len(thin)} critical roles have one ready-now successor or none.",
                thin if not thin.empty else df, {})

    if intent == "headcount":
        # Slot values come from free text, so they are bound, never spliced into SQL.
        where, params, label = [], [], []
        if slots.get("division"):
            where.append("lower(division) = lower(?)")
            params.append(str(slots["division"]))
            label.append(slots["division"])
        if slots.get("location"):
            where.append("lower(location) = lower(?)")
            params.append(str(slots["location"]))
            label.append(slots["location"])
        if slots.get("skill"):
            where.append("lower(skills) like lower(?)")
            params.append(f"%{slots['skill']}%")
            label.append(slots["skill"])
        clause = " and ".join(where) or "1=1"
        df = co.sql(f"select name, title, division, location, band, skills from people "
                    f"where status <> 'Exited' and {clause} order by band, name", params)
        return f"{len(df)} people match {' / '.join(label) or 'the whole company'}.", df, {}

    # data_quality
    c = co.counts()
    head = (f"{co.raw_rows} rows in, {len(co.people)} people out. "
            + ", ".join(f"{v} {k}" for k, v in sorted(c.items(), key=lambda kv: -kv[1])) + ".")
    import pandas as pd
    df = pd.DataFrame([{"issue": i.kind, "detail": i.detail} for i in co.issues])
    return head, df, {}
