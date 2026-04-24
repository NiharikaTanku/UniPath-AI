# live_data.py  –  EduPath Live Data Engine

import warnings
warnings.filterwarnings("ignore", message=".*duckduckgo_search.*renamed.*ddgs.*", category=RuntimeWarning)

import os
import json
import time
import re
import hashlib
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional

try:
    from groq import Groq
    GROQ_LIB = True
except ImportError:
    GROQ_LIB = False

# ── DuckDuckGo: try new package name first, then legacy ──────────────────────
import json
import urllib.parse
from datetime import datetime
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

# ── Cache TTL settings ────────────────────────────────────────────────────────
CACHE_TTL_HOURS = {
    "universities": 24,
    "exams": 12,
    "scholarships": 24,
    "fees": 6,
    "deadlines": 3,
}

# ── Groq client ───────────────────────────────────────────────────────────────
def _get_groq_client():
    if not GROQ_LIB:
        return None
    key = None
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        pass
    if not key:
        key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    try:
        return Groq(api_key=key)
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def is_groq_key_valid() -> bool:
    """Cached Groq connectivity check (5-min TTL)."""
    client = _get_groq_client()
    if not client:
        return False
    try:
        client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1
        )
        return True
    except Exception as e:
        print(f"DEBUG: Groq Key Check Failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  DuckDuckGo SEARCH HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _is_english(text: str) -> bool:
    """Check if text is predominantly English (ASCII-based)."""
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return (ascii_chars / len(text)) > 0.7

def _ddg_search(query: str, max_results: int = 8) -> list:
    if not DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                max_results=max_results,
                region='wt-wt',
                safesearch='moderate'
            ))
        # For universities in non-English countries, we still want the results
        # We'll rely on the Groq extraction to translate/process them
        return [r for r in results if r.get('title') and r.get('body')]
    except Exception as e:
        if "Ratelimit" in str(e):
            st.warning("DuckDuckGo rate limit reached. Showing cached/static data.")
        return []


def _ddg_news(query: str, max_results: int = 8) -> list:
    if not DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, region='en-us', safesearch='moderate', max_results=max_results))
        return [r for r in results if _is_english(r.get('title', ''))]
    except Exception:
        return []


def _google_search(query: str, max_results: int = 10) -> list:
    """Optional Google CSE fallback."""
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        cse_id  = st.secrets.get("GOOGLE_CSE_ID")  or os.environ.get("GOOGLE_CSE_ID")
    except Exception:
        return []
    if not api_key or not cse_id:
        return []
    try:
        import requests
        url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cse_id}&q={query}&num={max_results}"
        resp = requests.get(url, timeout=5).json()
        return [{"title": i.get("title",""), "href": i.get("link",""), "body": i.get("snippet","")}
                for i in resp.get("items", [])]
    except Exception:
        return []


def _unified_search(query: str, max_results: int = 10) -> list:
    results = _google_search(query, max_results)
    if not results:
        results = _ddg_search(query, max_results)
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  GROQ EXTRACTION HELPER
# ─────────────────────────────────────────────────────────────────────────────
def _groq_extract(client, system: str, user: str, model: str = "llama-3.1-8b-instant") -> str:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=3000,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"ERROR: {e}"


def _safe_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("```").strip()
    try:
        return json.loads(text)
    except Exception:
        # Try to recover truncated JSON array
        try:
            last_brace = text.rfind("}")
            if last_brace != -1:
                fixed_text = text[:last_brace+1] + "\n]"
                return json.loads(fixed_text)
        except Exception:
            pass
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  REGEX FALLBACK EXTRACTOR  (works without Groq)
# ─────────────────────────────────────────────────────────────────────────────
# Keywords that indicate an actual educational institution
_EDU_KEYWORDS = [
    "university", "college", "institute", "school", "academy",
    "iit", "iim", "nit", "iiit", "bits", "mit", "caltech",
    "polytechnic", "conservatory", "faculty", "campus",
    "admission", "tuition", "undergraduate", "postgraduate",
    "bachelor", "master", "phd", "mba", "b.tech", "m.tech",
    ".edu", ".ac.", "ranking", "placement", "engineering",
    "community college", "vocational", "technical", "liberal arts",
    "medical college", "law school", "business school", "b-school",
    "higher education", "top colleges", "best colleges",
    "degree", "diploma", "certification", "curriculum",
    "enrollment", "semester", "programme", "program",
    "estudiar", "universidade", "universidad", "faculdade",
    "hochschule", "université", "università", "escuela",
    "instituto", "colegio", "pontificia", "nacional",
    "federal", "estadual", "católica", "autónoma",
]

def _is_university_result(title: str, url: str, body: str) -> bool:
    """Check if a search result is actually about a university/college."""
    combined = (title + " " + url + " " + body).lower()
    title_l = title.lower()
    # Only reject if the TITLE itself is a ranking aggregator site
    if any(kw in title_l for kw in ["qs world university ranking", "times higher education", "us news ranking", "topuniversities.com"]):
        return False
    return any(kw in combined for kw in _EDU_KEYWORDS)

def _regex_extract_unis(snippets: list, domain: str, country: str, max_unis: int = 20) -> list:
    """Build university cards from raw DDG snippets without Groq."""
    unis = []
    seen = set()
    for s in snippets[:max_unis * 3]:
        name_m = re.search(r"Title: (.*?)\n", s)
        url_m  = re.search(r"URL: (.*?)\n", s)
        body_m = re.search(r"Snippet: (.*)", s, re.S)
        if not name_m:
            continue
        raw_name = name_m.group(1)
        url = url_m.group(1).strip() if url_m else "#"
        body = body_m.group(1)[:200].strip() if body_m else "See website for details."

        # Skip if not a university result
        if not _is_university_result(raw_name, url, body):
            continue

        # Clean up name - take first part before separators
        name = re.split(r"[-|\u2013\u2014:]", raw_name)[0].strip()
        # Remove trailing junk like "... Top 10", "2026", etc.
        name = re.sub(r'\s*(\d{4}|Top \d+|Best|Ranking|Review|Admission).*$', '', name, flags=re.I).strip()
        if len(name) < 4 or len(name) > 100 or name.lower() in seen:
            continue
        seen.add(name.lower())

        # Basic type inference
        type_str = "Public"
        nl = name.lower() + " " + body.lower()
        if any(x in nl for x in ["private", "vit", "srm", "bits", "amity", "lpu", "manipal", "symbiosis"]):
            type_str = "Private"
        if any(x in nl for x in ["public", "state university", "government", "iit ", "iim ", "nit ", "university of"]):
            type_str = "Public"

        unis.append({
            "name": name,
            "city": "—",
            "country": country if country not in ("All", "Abroad") else "—",
            "type": type_str,
            "domain": domain if domain != "All" else "—",
            "rank": 999,
            "rating": 3.5,
            "degrees": ["Masters", "PhD", "Bachelors"],
            "fees_inr": "See website",
            "fees_usd": "—",
            "admission_status": "Open",
            "deadline": "Check website",
            "required_exams": [],
            "scholarships_available": "",
            "highlights": [body],
            "website": url,
            "apply_link": url,
            "source": "live_search",
        })
        if len(unis) >= max_unis:
            break
    return unis


# ─────────────────────────────────────────────────────────────────────────────
#  UNIVERSITIES  –  Live fetch (DDG-only mode + optional Groq extraction)
# ─────────────────────────────────────────────────────────────────────────────
UNIV_SYSTEM = """
You are a higher education data extractor. Given web search snippets,
extract ALL educational institutions mentioned — universities, colleges, institutes,
community colleges, polytechnics, business schools, medical colleges, and any other
educational institutions. Return ONLY a valid JSON array. ALL text MUST be in English.
Each element must have:
{
  "name": string (English name),
  "city": string,
  "country": string,
  "type": "Public" or "Private",
  "domain": string (e.g. "Engineering", "Computer Science", "Management", "Medical", etc.),
  "rank": integer,
  "rating": float,
  "degrees": [string],
  "fees_inr": string,
  "fees_usd": string,
  "admission_status": string,
  "deadline": string,
  "required_exams": [string],
  "scholarships_available": string,
  "highlights": [string],
  "website": string,
  "apply_link": string
}
Return ONLY the JSON array, no prose.
"""


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_universities_live(
    domain: str = "All",
    country: str = "All",
    degree_level: str = "All",
    query: str = "",
    max_unis: int = 80,
) -> list:
    """Fetch live university data. Works with DDG alone; Groq enhances extraction."""
    if not DDGS_AVAILABLE:
        return []

    parts = []
    if query:          parts.append(query)
    if domain != "All":   parts.append(domain)
    if country not in ("All","Abroad"): parts.append(country)
    if degree_level != "All": parts.append(degree_level)

    base = " ".join(parts) if parts else "top universities"
    ctry_q = country if country not in ('All','Abroad') else 'world'
    dom_q = domain if domain != 'All' else 'engineering computer science management'
    searches = [
        f"top universities colleges institutes {ctry_q} {dom_q} ranking 2025 2026",
        f"{base} college university tuition fees placement",
        f"affordable public private colleges universities {ctry_q} {dom_q}",
    ]

    snippets = []
    for sq in searches:
        results = _unified_search(sq, max_results=20)
        for r in results:
            title = r.get('title', '')
            body = r.get('body', '')
            # We removed the English-only restriction here to support global universities
            if title and body:
                snippets.append(f"Title: {title}\nURL: {r.get('href','')}\nSnippet: {body}")
        time.sleep(0.25)

    if not snippets:
        return []

    # Try Groq-enhanced extraction first
    client = _get_groq_client()
    if client:
        # Keep context smaller to stay under 6000 TPM limit for free tier
        context = "\n\n---\n\n".join(snippets[:30])
        user_prompt = (
            f"Extract as many real universities and colleges as possible from these web search results. "
            f"ONLY include actual educational institutions (universities, colleges, institutes) that a student can apply to. "
            f"Do NOT include university ranking websites (like QS World, Times Higher Education, US News). "
            f"Do NOT include news articles, blog posts, or aggregators. "
            f"If names are in another language (like Spanish/Portuguese), keep the original name but translate the rest of the data to English. "
            f"Focus on: domain={domain}, country={country}, degree={degree_level}. "
            f"Include BOTH Public and Private institutions. Include well-known, mid-tier, and affordable options. "
            f"Try to extract at least 15-20 institutions.\n\n"
            f"Search results:\n{context[:6000]}"
        )
        raw = _groq_extract(client, UNIV_SYSTEM, user_prompt)
        parsed = _safe_json(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed

    # DDG-only fallback: regex extraction
    return _regex_extract_unis(snippets, domain, country, max_unis)


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRANCE EXAMS  –  Live fetch
# ─────────────────────────────────────────────────────────────────────────────
EXAM_SYSTEM = """
You are an entrance exam data extractor. Given web search snippets, extract exam data
and return ONLY a valid JSON array. Each element:
{
  "name": string,
  "full_name": string,
  "domain": string,
  "body": string,
  "fee": string,
  "next_date": string,
  "mode": string,
  "validity": string,
  "accepted_by": [string],
  "register_link": string,
  "info_link": string,
  "is_international": boolean
}
Return ONLY the JSON array.
"""


def _regex_extract_exams(snippets: list, domain: str) -> list:
    """Build exam cards from raw DDG snippets without Groq."""
    known_exams = {
        "GATE": {"full_name": "Graduate Aptitude Test in Engineering", "domain": "Engineering", "fee": "₹1,800", "is_international": False},
        "CAT": {"full_name": "Common Admission Test", "domain": "Management", "fee": "₹2,400", "is_international": False},
        "NEET": {"full_name": "National Eligibility cum Entrance Test", "domain": "Medical & Health", "fee": "₹1,700", "is_international": False},
        "JEE": {"full_name": "Joint Entrance Examination", "domain": "Engineering", "fee": "₹1,000", "is_international": False},
        "CLAT": {"full_name": "Common Law Admission Test", "domain": "Law", "fee": "₹4,000", "is_international": False},
        "XAT": {"full_name": "Xavier Aptitude Test", "domain": "Management", "fee": "₹2,200", "is_international": False},
        "GRE": {"full_name": "Graduate Record Examination", "domain": "All", "fee": "₹21,450", "is_international": True},
        "GMAT": {"full_name": "Graduate Management Admission Test", "domain": "Management", "fee": "₹23,000", "is_international": True},
        "IELTS": {"full_name": "International English Language Testing System", "domain": "All", "fee": "₹17,000", "is_international": True},
        "TOEFL": {"full_name": "Test of English as a Foreign Language", "domain": "All", "fee": "₹18,500", "is_international": True},
        "SAT": {"full_name": "Scholastic Assessment Test", "domain": "All", "fee": "₹8,000", "is_international": True},
        "PTE": {"full_name": "Pearson Test of English", "domain": "All", "fee": "₹15,900", "is_international": True},
        "BITSAT": {"full_name": "BITS Admission Test", "domain": "Engineering", "fee": "₹3,400", "is_international": False},
        "SNAP": {"full_name": "Symbiosis National Aptitude Test", "domain": "Management", "fee": "₹1,950", "is_international": False},
        "JAM": {"full_name": "Joint Admission test to M.Sc.", "domain": "Sciences", "fee": "₹1,800", "is_international": False},
    }
    exams = []
    seen = set()
    combined_text = " ".join(snippets).lower()
    for name, info in known_exams.items():
        if name.lower() in combined_text and name not in seen:
            if domain != "All" and info["domain"] not in ("All", domain):
                continue
            seen.add(name)
            # Try to find dates from snippets
            date_str = "Check website"
            for s in snippets:
                if name.lower() in s.lower():
                    dm = re.search(r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s*\d{4})', s, re.I)
                    if dm:
                        date_str = dm.group(1)
                        break
            # Try to find URL
            url = "#"
            for s in snippets:
                if name.lower() in s.lower():
                    um = re.search(r'URL: (https?://\S+)', s)
                    if um:
                        url = um.group(1)
                        break
            exams.append({
                "name": name,
                "full_name": info["full_name"],
                "domain": info["domain"],
                "body": "",
                "fee": info["fee"],
                "next_date": date_str,
                "mode": "Online (CBT)",
                "validity": "1-3 years",
                "accepted_by": [],
                "register_link": url,
                "info_link": url,
                "is_international": info["is_international"],
            })
    return exams


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_exams_live(domain: str = "All", country_focus: str = "India") -> list:
    """Fetch live exam data. Works with DDG alone; Groq enhances extraction."""
    if not DDGS_AVAILABLE:
        return []

    dom_q = domain if domain != 'All' else 'engineering management medical law design'
    queries = [
        f"entrance exam 2025 2026 {dom_q} India registration date fee",
        "GATE CAT NEET CLAT GRE GMAT IELTS TOEFL SAT ACT exam date fee 2026",
        f"competitive exams India {dom_q} eligibility syllabus 2026",
        "international exams for study abroad GRE GMAT IELTS TOEFL PTE registration",
        f"{dom_q} entrance test India 2026 application form last date",
    ]
    snippets = []
    for q in queries:
        for r in _ddg_search(q, max_results=12):
            snippets.append(f"Title: {r.get('title','')}\nURL: {r.get('href','')}\n{r.get('body','')}")
        time.sleep(0.25)

    if not snippets:
        return []

    client = _get_groq_client()
    if client:
        raw = _groq_extract(
            client, EXAM_SYSTEM,
            f"Extract ALL entrance exams from these snippets. Be thorough, include every exam mentioned. Domain={domain}.\n\n"
            + "\n---\n".join(snippets[:20])[:5000]
        )
        parsed = _safe_json(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed

    # Regex fallback
    return _regex_extract_exams(snippets, domain)


# ─────────────────────────────────────────────────────────────────────────────
#  SCHOLARSHIPS  –  Live fetch
# ─────────────────────────────────────────────────────────────────────────────
SCHOL_SYSTEM = """
You are a scholarship data extractor for Indian students. Extract scholarship data from
web snippets and return ONLY a valid JSON array. Each element:
{
  "name": string,
  "body": string,
  "type": string,
  "amount_inr": string,
  "levels": [string],
  "countries": [string],
  "renewable": boolean,
  "deadline": string,
  "eligibility": string,
  "description": string,
  "covers": [string],
  "apply_link": string,
  "info_link": string
}
Return ONLY the JSON array.
"""


def _regex_extract_scholarships(snippets: list, country: str, level: str) -> list:
    """Build scholarship cards from raw DDG snippets without Groq."""
    known_schols = {
        "Fulbright": {"body": "US Government", "type": "Government", "amount_inr": "Full Funding", "countries": ["USA"]},
        "Chevening": {"body": "UK Government", "type": "Government", "amount_inr": "Full Funding", "countries": ["UK"]},
        "DAAD": {"body": "German Academic Exchange", "type": "Government", "amount_inr": "₹8-12 Lakhs/yr", "countries": ["Germany"]},
        "Commonwealth": {"body": "Commonwealth Secretariat", "type": "Government", "amount_inr": "Full Funding", "countries": ["UK"]},
        "Erasmus": {"body": "European Union", "type": "Government", "amount_inr": "Full Funding", "countries": ["EU"]},
        "Rhodes": {"body": "Rhodes Trust", "type": "Merit", "amount_inr": "Full Funding", "countries": ["UK"]},
        "Gates Cambridge": {"body": "Gates Foundation", "type": "Merit", "amount_inr": "Full Funding", "countries": ["UK"]},
        "MEXT": {"body": "Japanese Government", "type": "Government", "amount_inr": "Full Funding", "countries": ["Japan"]},
        "Australia Awards": {"body": "Australian Government", "type": "Government", "amount_inr": "Full Funding", "countries": ["Australia"]},
        "Vanier": {"body": "Canadian Government", "type": "Government", "amount_inr": "₹40L/yr", "countries": ["Canada"]},
        "INSPIRE": {"body": "DST India", "type": "Government", "amount_inr": "₹80,000/yr", "countries": ["India"]},
        "UGC NET": {"body": "UGC India", "type": "Government", "amount_inr": "₹31,000/month", "countries": ["India"]},
        "Aga Khan": {"body": "Aga Khan Foundation", "type": "Need-based", "amount_inr": "50-100% Tuition", "countries": ["Multiple"]},
        "Rotary": {"body": "Rotary Foundation", "type": "Merit", "amount_inr": "Up to $30,000", "countries": ["Multiple"]},
    }
    schols = []
    seen = set()
    combined_text = " ".join(snippets).lower()
    for name, info in known_schols.items():
        if name.lower() in combined_text and name not in seen:
            seen.add(name)
            url = "#"
            for s in snippets:
                if name.lower() in s.lower():
                    um = re.search(r'URL: (https?://\S+)', s)
                    if um:
                        url = um.group(1)
                        break
            schols.append({
                "name": f"{name} Scholarship",
                "body": info["body"],
                "type": info["type"],
                "amount_inr": info["amount_inr"],
                "levels": ["Masters", "PhD"],
                "countries": info["countries"],
                "renewable": True,
                "deadline": "Check website",
                "eligibility": "See official website",
                "description": "",
                "covers": ["Tuition", "Living Expenses"],
                "apply_link": url,
                "info_link": url,
            })
    return schols


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_scholarships_live(country: str = "All", level: str = "All") -> list:
    """Fetch live scholarship data for Indian students. Works with DDG alone; Groq enhances."""
    if not DDGS_AVAILABLE:
        return []

    ctry_str = country if country not in ("All","Abroad") else "USA UK Canada Australia Germany Singapore Japan"
    lvl_q = level if level != 'All' else 'bachelors masters PhD MBA'
    queries = [
        f"scholarship Indian students {ctry_str} 2025 2026 full funding apply",
        f"government scholarship India abroad {lvl_q} eligibility deadline",
        f"merit based scholarship {ctry_str} international students 2026",
        f"need based financial aid {ctry_str} tuition waiver stipend",
        f"Fulbright Chevening DAAD Commonwealth Erasmus Rhodes scholarship 2026 apply",
        f"private NGO corporate scholarship Indian students {lvl_q} 2026",
    ]
    snippets = []
    for q in queries:
        for r in _ddg_search(q, max_results=12):
            snippets.append(f"Title: {r.get('title','')}\nURL: {r.get('href','')}\n{r.get('body','')}")
        time.sleep(0.25)

    if not snippets:
        return []

    client = _get_groq_client()
    if client:
        raw = _groq_extract(
            client, SCHOL_SYSTEM,
            f"Extract ALL scholarships for Indian students. Be exhaustive. Country={country}, Level={level}.\n\n"
            + "\n---\n".join(snippets[:20])[:5000]
        )
        parsed = _safe_json(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed

    # Regex fallback
    return _regex_extract_scholarships(snippets, country, level)


# ─────────────────────────────────────────────────────────────────────────────
#  LIVE FEE & DEADLINE UPDATER
# ─────────────────────────────────────────────────────────────────────────────
FEE_SYSTEM = """
You are a fee and deadline extractor. Given search results about a specific university,
return ONLY a JSON object:
{
  "fees_inr": string,
  "fees_usd": string,
  "deadline": string,
  "admission_status": string,
  "type": "Public" or "Private",
  "scholarships_available": string
}
Return ONLY the JSON object.
"""


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_live_fees(university_name: str, country: str) -> dict:
    """Fetch live fee/deadline info for a specific university."""
    client = _get_groq_client()
    if not client or not DDGS_AVAILABLE:
        return {}

    results = _ddg_search(
        f"{university_name} {country} tuition fees 2025 2026 admission deadline",
        max_results=6,
    )
    if not results:
        return {}

    snippets = "\n---\n".join(f"Title: {r.get('title','')}\n{r.get('body','')}" for r in results)
    raw = _groq_extract(client, FEE_SYSTEM, f"Extract fees for {university_name}.\n\n{snippets[:2000]}")
    parsed = _safe_json(raw)
    return parsed if isinstance(parsed, dict) else {}


# ─────────────────────────────────────────────────────────────────────────────
#  LIVE NEWS / ALERTS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_edu_news(topic: str = "study abroad India 2026") -> list:
    """Fetch latest higher education news."""
    if not DDGS_AVAILABLE:
        return _static_news()
    results = _ddg_news(topic, max_results=20)
    if not results:
        results = _ddg_search(topic + " news 2026", max_results=15)
        if results:
            return [{"title": r.get("title",""), "url": r.get("href",""),
                     "date": "Recent", "source": "Web", "body": r.get("body","")}
                    for r in results]
        return _static_news()
    return [{"title": r.get("title",""), "url": r.get("url",""),
             "date": r.get("date",""), "source": r.get("source",""),
             "body": r.get("body","")} for r in results]


def _static_news() -> list:
    return [
        {"title": "IIT Bombay Ranked 118 in QS World Rankings 2026", "url": "https://www.topuniversities.com", "source": "QS Rankings", "date": "2026", "body": "IIT Bombay continues its upward trajectory in global rankings."},
        {"title": "New Post-Study Work Visa Rules for UK – 2 Years Extended", "url": "https://www.gov.uk/student-visa", "source": "UK Gov", "date": "2026", "body": "International students get 2 years post-study work rights in the UK."},
        {"title": "Canada Caps International Student Permits for 2026", "url": "https://www.canada.ca", "source": "IRCC Canada", "date": "2026", "body": "Canada has announced a cap on international student permits for 2026."},
        {"title": "Germany Announces Free Tuition for International Students", "url": "https://www.daad.de", "source": "DAAD", "date": "2026", "body": "Most German public universities remain tuition-free for international students."},
        {"title": "GATE 2026 Registration Opens – Check Dates & Fees", "url": "https://gate2026.iitr.ac.in", "source": "IIT Roorkee", "date": "2026", "body": "GATE 2026 registration is now open. Last date for application is September 2025."},
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  AI-POWERED SUGGESTIONS  –  Personalized recommendations
# ─────────────────────────────────────────────────────────────────────────────
def ai_suggest(section: str, profile: dict, context_data: list = None) -> str:
    """Get AI-powered suggestions for any section based on user profile."""
    client = _get_groq_client()
    if not client:
        return ""

    profile_str = ", ".join(f"{k}: {v}" for k, v in profile.items() if v)

    # Skip slow web search - use AI's built-in knowledge for instant response
    live_ctx = ""

    system = (
        f"You are EduPath AI recommendation engine. Based on the student profile, provide 3-5 specific, "
        f"actionable recommendations for the '{section}' section. "
        f"IMPORTANT: For universities and colleges, CLEARLY state if each institution is PUBLIC or PRIVATE. "
        f"Use LIVE WEB DATA if provided. Be specific with names, fees, deadlines. "
        f"Format as a concise bullet list. RESPOND IN ENGLISH ONLY.\n"
    )
    if live_ctx:
        system += f"\nLIVE WEB CONTEXT:\n{live_ctx[:2000]}\n"
    if context_data:
        ctx_str = str(context_data[:5])[:1000]
        system += f"\nAVAILABLE DATA:\n{ctx_str}\n"

    user = f"Student Profile: {profile_str}\nProvide personalized {section} recommendations."

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=450,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  GROQ AI COUNSELLOR  –  RAG-powered answer
# ─────────────────────────────────────────────────────────────────────────────
def counsellor_answer(question: str, chat_history: list, stream: bool = True):
    """Use DuckDuckGo to gather context, then Groq to answer."""
    client = _get_groq_client()
    if not client:
        return "⚠️ Groq API key not configured. Please add GROQ_API_KEY to `.streamlit/secrets.toml`."

    # Live web context – use more results for better answers
    live_snippets = ""
    if DDGS_AVAILABLE:
        results = _ddg_search(f"{question} study abroad 2026", max_results=2)
        if results:
            live_snippets = "\n\n".join(f"[{r.get('title','')}] {r.get('body','')}" for r in results)

    system = (
        "You are EduPath AI – an expert higher-education counsellor for Indian students. "
        "IMPORTANT: Prioritize the LIVE WEB CONTEXT provided below. Do not suggest old or hardcoded colleges "
        "if fresh ones are found in the search results. ALWAYS RESPOND IN ENGLISH. "
        "Give accurate, up-to-date answers with specific numbers (fees, deadlines, ranks). "
        "Include both Public and Private university options when relevant. "
        "Mention scholarship opportunities and visa requirements when applicable. "
        "Be concise, encouraging, and always cite deadlines and amounts.\n\n"
    )
    if live_snippets:
        system += f"LIVE WEB CONTEXT:\n{live_snippets[:3000]}\n\n"

    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in chat_history[-10:]]

    try:
        model_name = "llama-3.1-8b-instant"
        if stream:
            return client.chat.completions.create(model=model_name, messages=messages, max_tokens=1000, stream=True)
        else:
            resp = client.chat.completions.create(model=model_name, messages=messages, max_tokens=1000)
            return resp.choices[0].message.content
    except Exception as e:
        err = str(e)
        if "401" in err or "invalid_api_key" in err.lower():
            return "🔑 **Invalid Groq API Key.** Get a free key at [console.groq.com](https://console.groq.com)."
        try:
            resp = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, max_tokens=800)
            return resp.choices[0].message.content
        except Exception as e2:
            return f"⚠️ Assistant Error: {e}\n\nFallback also failed: {e2}"


# ─────────────────────────────────────────────────────────────────────────────
#  MERGE  –  Combine static fallback + live data
# ─────────────────────────────────────────────────────────────────────────────
def merge_with_live(static_list: list, live_list: list, key: str = "name") -> list:
    """Merge live data into static list. Live items update/extend static."""
    static_map = {item.get(key, "").lower(): item for item in static_list}
    for live_item in live_list:
        k = live_item.get(key, "").lower()
        if k in static_map:
            for field, val in live_item.items():
                if val and val not in ("Unknown", "—", ""):
                    static_map[k][field] = val
        else:
            static_map[k] = live_item
    return list(static_map.values())