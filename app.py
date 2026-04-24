# edupath_live.py - EduPath India with LIVE data
import os, re, time
import logging

# Set up activity logger
activity_logger = logging.getLogger("activity_logger")
activity_logger.setLevel(logging.INFO)
# Prevent duplicate logs if the module is reloaded
if not activity_logger.handlers:
    fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), "user_activity.log"))
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    activity_logger.addHandler(fh)

def log_activity(email, action):
    if email:
        activity_logger.info(f"User: {email} | Action: {action}")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from auth import init_db, create_user, verify_user
init_db()

# MUST BE FIRST COMMAND
st.set_page_config(
    page_title="UniPath AI – Live Navigator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

from live_data import (
    fetch_universities_live,
    fetch_exams_live,
    fetch_scholarships_live,
    fetch_live_fees,
    fetch_edu_news,
    counsellor_answer,
    merge_with_live,
    is_groq_key_valid,
    ai_suggest,
    DDGS_AVAILABLE,
)
from ml_engine import EduPathMLEngine


# --- Try to import static fallback data ---
try:
    from edupath_data import (
        STATIC_UNIVERSITIES,
        STATIC_ENTRANCE_EXAMS,
        STATIC_LANGUAGE_EXAMS,
        STATIC_SCHOLARSHIPS,
        ALL_DEGREES, ALL_DOMAINS, ALL_COUNTRIES, ABROAD_COUNTRIES,
        DEGREE_SHORT, ROI_PROFILES, LOAN_BANKS, VISA_DATA, SOP_STRUCTURE,
    )
    HAS_STATIC = True
except Exception:
    HAS_STATIC = False
    STATIC_UNIVERSITIES = []
    STATIC_ENTRANCE_EXAMS = []
    STATIC_LANGUAGE_EXAMS = []
    STATIC_SCHOLARSHIPS = []
    ALL_DEGREES = ["All", "Masters (M.Sc.)", "Masters (M.Tech/M.E.)", "MBA", "PhD", "Bachelors (B.Tech/B.E.)", "Bachelors (B.Sc.)"]
    ALL_DOMAINS = ["All", "Engineering", "Computer Science", "Data Science & AI", "Management", "Medical & Health", "Law", "Sciences", "Design & Architecture", "Finance & Accounting"]
    ALL_COUNTRIES = ["All", "India", "USA", "UK", "Canada", "Australia", "Germany", "Singapore", "Netherlands", "France", "Japan", "Argentina", "Brazil", "South Korea", "Italy", "Spain", "Ireland", "New Zealand", "Switzerland", "China", "Sweden", "Denmark", "Hong Kong", "Malaysia", "Norway", "Finland", "Austria", "Belgium", "Poland", "Portugal", "Czech Republic", "Mexico", "Chile", "Taiwan", "UAE", "Russia"]
    ABROAD_COUNTRIES = [c for c in ALL_COUNTRIES if c not in ("All", "India")]
    DEGREE_SHORT, ROI_PROFILES, LOAN_BANKS, VISA_DATA, SOP_STRUCTURE = {}, {}, {}, {}, {}
    EXAM_MAP, ALL_EXAM_NAMES = {}, []

def parse_fee_lakhs(s):
    try:
        m = re.search(r"[\d.]+", str(s).replace(",", ""))
        return float(m.group()) if m else 0.0
    except:
        return 0.0

def filter_universities(data, search_q="", dest="All", level="All", domain="All", status="All", uni_type="All", inst_category="All", fee_range=(0, 80), rank_max=None, sort_by="Rank"):
    filtered = list(data)
    # Country filter - use aliases for common abbreviations
    if dest != "All":
        if dest == "Abroad": 
            filtered = [u for u in filtered if u.get("country","").lower() not in ("india","")]
        else: 
            dest_lower = dest.lower()
            aliases = [dest_lower]
            if dest_lower == "uk": aliases += ["united kingdom", "britain", "england"]
            if dest_lower == "usa": aliases += ["united states", "us", "america"]
            filtered = [u for u in filtered if any(a in u.get("country", "").lower() for a in aliases) or u.get("country","").lower() == dest_lower]
    # Type filter (Public/Private)
    if uni_type != "All": filtered = [u for u in filtered if u.get("type") == uni_type]
    # Category filter
    if inst_category != "All":
        if inst_category == "University":
            filtered = [u for u in filtered if any(k in u.get("name", "").lower() for k in ["universit", "universidad", "université"])]
        elif inst_category == "College/Institute":
            filtered = [u for u in filtered if not any(k in u.get("name", "").lower() for k in ["universit", "universidad", "université"])]
    # Text search
    if search_q:
        q = search_q.lower()
        filtered = [u for u in filtered if q in u.get("name","").lower() or q in u.get("city","").lower() or q in u.get("country","").lower() or q in str(u.get("highlights","")).lower()]
    # Sort
    if sort_by == "Rank": filtered.sort(key=lambda x: x.get("rank", 999))
    elif sort_by == "Fees (Low→High)": filtered.sort(key=lambda x: parse_fee_lakhs(x.get("fees_inr","0")))
    elif sort_by == "Rating": filtered.sort(key=lambda x: x.get("rating", 0), reverse=True)
    elif sort_by == "Name": filtered.sort(key=lambda x: x.get("name", ""))
    return filtered



def filter_entrance_exams(exams, domain="All", mode="All", fee_max=None):
    filtered = list(exams)
    if domain != "All":
        filtered = [e for e in filtered if domain.lower() in e.get("domain", "").lower()]
    if mode != "All":
        filtered = [e for e in filtered if mode.lower() in e.get("mode", "").lower()]
    if fee_max:
        def clean_fee(f):
            try:
                num = re.sub(r'[^\d]', '', str(f))
                return int(num) if num else 0
            except: return 0
        filtered = [e for e in filtered if clean_fee(e.get("fee", 0)) <= fee_max]
    return filtered

def filter_language_exams(exams, country="All", fee_max_inr=None, format_filter="All"):
    filtered = list(exams)
    if country != "All":
        # Check if country name is in the accepted_in list (string match)
        filtered = [e for e in filtered if any(country.lower() in c.lower() for c in e.get("accepted_in", [])) or "Global" in e.get("accepted_in", []) or "Worldwide" in e.get("accepted_in", [])]
    if format_filter != "All":
        filtered = [e for e in filtered if format_filter.lower() in e.get("format", "").lower()]
    if fee_max_inr:
        def clean_fee(f):
            try:
                num = re.sub(r'[^\d]', '', str(f))
                return int(num) if num else 0
            except: return 0
        filtered = [e for e in filtered if clean_fee(e.get("fee_inr", 0)) <= fee_max_inr]
    return filtered


def render_uni_card(uni, profile=None):
    """Unified rich university card renderer."""
    m_score = 0
    if profile:
        m_score = ml_engine.match_model.predict(uni, profile)
    elif "user_profile" in st.session_state:
        m_score = ml_engine.match_model.predict(uni, st.session_state.user_profile)
    
    m_badge = f'<span class="badge badge-india">{m_score}% Match</span>' if m_score > 0 else ""
    utype = uni.get('type', 'Public')
    type_badge = f'<span class="badge badge-{"public" if utype=="Public" else "private"}">{"🏫" if utype=="Public" else "🏢"} {utype}</span>'
    
    country = uni.get("country", "India")
    abroad = country != "India"
    loc_badge_cls = "badge-abroad" if abroad else "badge-india"
    loc_label = ("🌐 " + country) if abroad else "🇮🇳 India"
    
    sc = "badge-open"
    si = "🟢"
    st_val = uni.get("admission_status", "Open").lower()
    if "close" in st_val or "soon" in st_val:
        sc = "badge-closing"; si = "🟠"
    elif "closed" in st_val:
        sc = "badge-closed"; si = "🔴"
        
    ws = uni.get('website','') or uni.get('apply_link','')
    ws_html = f'<a href="{ws}" target="_blank" class="apply-btn" style="margin-top:8px;text-decoration:none;">Apply →</a>' if ws and ws != '#' else ''
    
    degrees = ", ".join(uni.get("degrees", ["Bachelors", "Masters"]))
    domain = uni.get("domain", "General")
    
    highlights_html = "".join(['<span class="info-pill">✓ ' + h + '</span>' for h in uni.get("highlights",[])[:3]])
    
    html = (
        f'<div class="uni-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">'
        f'<div class="uni-name">{uni.get("name","—")}</div>'
        f'<div>{m_badge} {type_badge} <span class="badge {loc_badge_cls}">{loc_label}</span> '
        f'<span class="badge {sc}">{si} {uni.get("admission_status","—")}</span></div>'
        f'</div>'
        f'<div style="font-size:0.82rem;color:#888;margin-bottom:0.6rem;">'
        f'📍 {uni.get("city","—")} | 🏅 Rank #{uni.get("rank","—")} | 🎓 {domain}</div>'
        f'<div style="display:flex;gap:1.2rem;flex-wrap:wrap;margin-bottom:0.6rem;">'
        f'<div><span style="font-size:0.75rem;color:#888;">Annual Fee</span><br>'
        f'<span style="font-weight:700;color:#302b63;">₹{uni.get("fees_inr","—")}L</span></div>'
        f'<div><span style="font-size:0.75rem;color:#888;">Degrees</span><br>'
        f'<span style="font-size:0.85rem;">{degrees}</span></div>'
        f'<div><span style="font-size:0.75rem;color:#888;">Deadline</span><br>'
        f'<span>{uni.get("deadline","—")}</span></div>'
        f'</div>{highlights_html}<div style="text-align:right;">{ws_html}</div></div>'
    )
    return html

# --- Custom CSS ---
CSS = '<style>@import url("https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap");html,body,[class*="css"]{font-family:"DM Sans",sans-serif;}h1,h2,h3,.big-title{font-family:"Sora",sans-serif;}section[data-testid="stSidebar"]{background:linear-gradient(160deg,#0f0c29,#302b63,#24243e);}section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span:not([data-baseweb]),section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] .stMarkdown p,section[data-testid="stSidebar"] h1,section[data-testid="stSidebar"] h2,section[data-testid="stSidebar"] h3{color:white !important;}section[data-testid="stSidebar"] .stSelectbox>div>div[data-baseweb="select"]{background:rgba(255,255,255,0.13)!important;border:1px solid rgba(255,255,255,0.35)!important;border-radius:8px!important;}section[data-testid="stSidebar"] .stSelectbox [data-testid="stSelectboxSelectedOption"] p,section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"]>div span{color:white!important;}section[data-testid="stSidebar"] .stSelectbox svg{fill:white!important;}section[data-testid="stSidebar"] .stRadio label{opacity:1!important;cursor:pointer!important;pointer-events:auto!important;}section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label{opacity:1!important;cursor:pointer!important;}section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label:hover{background:rgba(255,255,255,0.1)!important;border-radius:8px;}.live-badge{display:inline-flex;align-items:center;gap:4px;background:#e8f5e9;color:#2e7d32;border-radius:20px;padding:3px 10px;font-size:0.72rem;font-weight:700;}.live-dot{width:7px;height:7px;border-radius:50%;background:#2e7d32;animation:pulse 1.5s infinite;}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}.stApp{background:#f4f2ff;}.hero-banner{background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#667eea 100%);border-radius:20px;padding:2.5rem 3rem;color:white;margin-bottom:2rem;position:relative;overflow:hidden;}.hero-title{font-family:"Sora",sans-serif;font-size:2.2rem;font-weight:800;margin:0 0 0.5rem;line-height:1.2;}.hero-sub{font-size:1.05rem;opacity:0.85;font-weight:300;margin:0;}.metric-card{background:white;border-radius:16px;padding:1.4rem 1.6rem;box-shadow:0 4px 20px rgba(48,43,99,.10);border-left:5px solid #667eea;margin-bottom:1rem;}.metric-card h3{font-family:"Sora",sans-serif;font-size:1.8rem;font-weight:800;color:#302b63;margin:0;}.metric-card p{color:#888;margin:.2rem 0 0;font-size:0.85rem;}.uni-card{background:white;border-radius:18px;padding:1.5rem;box-shadow:0 4px 24px rgba(48,43,99,.08);margin-bottom:1.2rem;border:1px solid #e8e4ff;}.uni-name{font-family:"Sora",sans-serif;font-size:1.15rem;font-weight:700;color:#302b63;margin:0 0 0.3rem;}.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:600;margin-right:5px;margin-bottom:5px;}.badge-india{background:#fff3e0;color:#e65100;}.badge-abroad{background:#e8f5e9;color:#2e7d32;}.badge-rank{background:#ede7f6;color:#4527a0;}.badge-open{background:#e3f2fd;color:#1565c0;}.badge-closed{background:#fce4ec;color:#880e4f;}.badge-live{background:#e8f5e9;color:#2e7d32;}.section-header{font-family:"Sora",sans-serif;font-size:1.5rem;font-weight:700;color:#302b63;border-bottom:3px solid #667eea;padding-bottom:.4rem;margin:1.5rem 0 1rem;}.exam-card{background:white;border-radius:16px;padding:1.4rem;box-shadow:0 4px 20px rgba(48,43,99,.08);margin-bottom:1rem;border-top:4px solid #667eea;}.exam-name{font-family:"Sora",sans-serif;font-size:1.1rem;font-weight:700;color:#302b63;}.exam-fee{font-size:1.4rem;font-weight:800;color:#667eea;font-family:"Sora",sans-serif;}.schol-card{background:linear-gradient(135deg,#fff 60%,#f0edff 100%);border-radius:16px;padding:1.4rem;box-shadow:0 4px 20px rgba(48,43,99,.08);margin-bottom:1rem;border:1px solid #e0d9ff;}.schol-amount{font-size:1.5rem;font-weight:800;color:#302b63;font-family:"Sora",sans-serif;}.apply-btn{display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:white!important;padding:8px 20px;border-radius:30px;font-size:0.85rem;font-weight:600;text-decoration:none;}.info-pill{background:#ede9ff;color:#302b63;padding:4px 12px;border-radius:20px;font-size:0.78rem;font-weight:600;display:inline-block;margin:2px;}.news-card{background:white;border-radius:12px;padding:1rem 1.2rem;border-left:4px solid #667eea;margin-bottom:0.7rem;box-shadow:0 2px 10px rgba(48,43,99,.06);}div.stButton>button{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;border-radius:25px;padding:.5rem 1.5rem;font-family:"Sora",sans-serif;font-weight:600;transition:all 0.3s ease;opacity:1!important;cursor:pointer!important;}div.stButton>button:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(102,126,234,0.4);opacity:1!important;}div.stButton>button:active{transform:translateY(0);}.stTabs [data-baseweb="tab-list"]{background:#ede9ff;border-radius:10px;padding:4px;}.stTabs [data-baseweb="tab"]{color:#302b63;font-family:"Sora",sans-serif;font-weight:600;}.stTabs [aria-selected="true"]{background:white!important;border-radius:8px!important;}</style>'
st.markdown(CSS, unsafe_allow_html=True)

# --- Global Status ---
GROQ_OK = is_groq_key_valid()
DDG_OK = DDGS_AVAILABLE

# ═══════════════════════════════════════════════════════════════════════════════
#  AUTHENTICATION GATE — Login / Register before accessing the app
# ═══════════════════════════════════════════════════════════════════════════════
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = ""

if "user_profile" not in st.session_state:
    st.session_state.user_profile = {
        "score_pct": 75.0, "gre": 0, "gmat": 0, "ielts": 0.0, "toefl": 0, "work_exp": 0,
        "desired_domain": "All", "desired_level": "All", "target_dest": ["India"],
        "budget_max": 40.0, "priorities": ["High Ranking"]
    }

if not st.session_state.authenticated:
    # Hide sidebar for login page
    st.markdown('<style>section[data-testid="stSidebar"]{display:none;}</style>', unsafe_allow_html=True)

    # Login page with same theme
    st.markdown("""
    <div style="max-width:480px;margin:2rem auto;">
        <div style="background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#667eea 100%);
                    border-radius:20px;padding:2.5rem 2rem;text-align:center;margin-bottom:2rem;">
            <div style="font-family:'Sora',sans-serif;font-size:2.2rem;font-weight:800;color:white;margin-bottom:0.5rem;">🎓 UniPath AI</div>
            <div style="font-size:1rem;color:#e0d9ff;font-weight:300;">Live Navigator · AI Counsellor · 35+ Countries</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    auth_col = st.columns([1, 2, 1])[1]
    with auth_col:
        login_tab, register_tab = st.tabs(["🔐 Login", "📝 Register"])

        with login_tab:
            st.markdown("##### Welcome Back!")
            login_email = st.text_input("📧 Email", placeholder="you@example.com", key="login_email")
            login_pass = st.text_input("🔑 Password", type="password", placeholder="Enter password", key="login_pass")
            if st.button("🚀 Login", width="stretch", key="login_btn"):
                if not login_email or not login_pass:
                    st.error("Please enter both email and password.")
                elif verify_user(login_email.strip(), login_pass):
                    st.session_state.authenticated = True
                    st.session_state.user_email = login_email.strip()
                    log_activity(st.session_state.user_email, "Logged in to the application")
                    st.rerun()
                else:
                    st.error("❌ Invalid email or password. Please try again.")

        with register_tab:
            st.markdown("##### Create Your Account")
            reg_email = st.text_input("📧 Email", placeholder="you@example.com", key="reg_email")
            reg_pass = st.text_input("🔑 Password", type="password", placeholder="Min 6 characters", key="reg_pass")
            reg_pass2 = st.text_input("🔑 Confirm Password", type="password", placeholder="Re-enter password", key="reg_pass2")
            if st.button("✨ Create Account", width="stretch", key="reg_btn"):
                if not reg_email or not reg_pass:
                    st.error("Please fill in all fields.")
                elif len(reg_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                elif reg_pass != reg_pass2:
                    st.error("Passwords do not match.")
                elif create_user(reg_email.strip(), reg_pass):
                    st.success("✅ Account created! Switch to the Login tab to sign in.")
                    log_activity(reg_email.strip(), "Created a new account")
                else:
                    st.error("❌ Email already registered. Try logging in.")

        st.markdown("---")
        st.caption("Your data is stored locally and securely.")

    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP (authenticated users only)
# ═══════════════════════════════════════════════════════════════════════════════
if "sidebar_nav" not in st.session_state:
    st.session_state["sidebar_nav"] = "🏠 Dashboard"

with st.sidebar:
    # --- Sidebar Header ---
    st.markdown("""
    <div style='padding: 1rem 0 1.5rem 0;'>
        <h1 style='color: white; font-size: 1.8rem; margin: 0; font-family: "Sora", sans-serif; letter-spacing: -1px;'>UniPath AI</h1>
    </div>
    """, unsafe_allow_html=True)

    # All options in one list for stability
    nav_options = [
        "🏠 Dashboard", "🏛️ Find Universities", "🎓 Scholarships", "📰 Live News",
        "📝 Entrance Exams", "📋 Apply Now", "🛂 Visa Guide", "💰 Compare Fees",
        "✍️ SOP / LOR Builder", "💬 Ask Assistant"
    ]

    # Handle navigation from dashboard buttons
    if st.session_state.get("nav_target"):
        target = st.session_state.pop("nav_target")
        if "Find Universities" in target: target = "🏛️ Find Universities"
        if target in nav_options:
            st.session_state["sidebar_nav"] = target

    if "sidebar_nav" not in st.session_state:
        st.session_state["sidebar_nav"] = nav_options[0]

    # Single radio for maximum stability
    nav = st.radio("Navigation", nav_options, key="sidebar_nav", label_visibility="collapsed")

    st.markdown("---")
    st.markdown(f'<div style="font-size:0.75rem;color:#94a3b8;margin-bottom:10px;">👤 {st.session_state.user_email}</div>', unsafe_allow_html=True)
    if st.button("🚪 Logout", key="logout_btn", width="stretch"):
        st.session_state.authenticated = False
        st.session_state.user_email = ""
        st.rerun()
    
    st.caption("v2.5.0-EDU · AI Enabled")

# Inject CSS to hide radio buttons, style as menu items, and INJECT HEADERS
st.markdown("""
<style>
    /* Dark Sidebar Base */
    [data-testid="stSidebar"] {
        background-color: #0c1427 !important;
        background-image: none !important;
    }
    
    /* HIDE ONLY THE RADIO CIRCLE */
    [data-testid="stSidebar"] div[role="radiogroup"] [data-testid="stWidgetSelectionControl"] {
        display: none !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 2px;
        padding-top: 10px;
    }
    
    /* Reset label layout to be safe */
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: transparent !important;
        padding: 8px 14px !important;
        border-radius: 4px !important;
        margin: 0px !important;
        border: none !important;
        min-height: 40px !important;
        transition: all 0.2s ease !important;
        position: relative;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: rgba(255,255,255,0.05) !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] label p {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        margin: 0 !important;
        padding-left: 0px !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-selected="true"] {
        background-color: #1e293b !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-selected="true"] p {
        color: white !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-selected="true"]::after {
        content: "";
        position: absolute;
        left: 0;
        top: 20%;
        height: 60%;
        width: 3px;
        background-color: #6366f1;
        border-radius: 0 4px 4px 0;
    }

    /* INJECT CATEGORY HEADERS - USE MARGINS ON THE ITEMS */
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(1) { margin-top: 25px !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(5) { margin-top: 40px !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(9) { margin-top: 40px !important; }

    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(1)::before,
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(5)::before,
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(9)::before {
        position: absolute;
        top: -24px;
        left: 14px;
        font-size: 0.65rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: #6366f1;
        white-space: nowrap;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(1)::before { content: "INTELLIGENCE"; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(5)::before { content: "ACADEMIC MODULES"; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:nth-child(9)::before { content: "AI & ASSISTANCE"; }

    /* Scrollbar */
    [data-testid="stSidebar"] ::-webkit-scrollbar { width: 4px; }
    [data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def get_ml_engine():
    from uni_db import get_country_universities
    from exam_db import ENTRANCE_EXAMS, LANGUAGE_EXAMS
    from schol_db import SCHOLARSHIPS
    
    engine = EduPathMLEngine()
    # Use global data or fetch it
    all_unis = get_country_universities("All")
    engine.initialize(all_unis, list(ENTRANCE_EXAMS), list(LANGUAGE_EXAMS), list(SCHOLARSHIPS))
    return engine

ml_engine = get_ml_engine()

from uni_db import get_country_universities

def get_universities(domain="All", country="All", degree="All", query="", live=True):
    # Always start with instant hardcoded database
    unis = get_country_universities(country)
    # Optionally enhance with live data
    if live and DDG_OK and not unis:
        live_unis = fetch_universities_live(domain, country, degree, query, max_unis=20)
        if live_unis: unis.extend(live_unis)
    return unis

def get_exams(domain="All", live=True):
    if live and DDG_OK:
        live_ex = fetch_exams_live(domain)
        if live_ex:
            intl = [e for e in live_ex if e.get("is_international")]
            dom = [e for e in live_ex if not e.get("is_international")]
            return dom, intl
    return list(STATIC_ENTRANCE_EXAMS), list(STATIC_LANGUAGE_EXAMS)

def get_scholarships(country="All", level="All", live=True):
    if live and DDG_OK:
        live_schols = fetch_scholarships_live(country, level)
        if live_schols: return live_schols
    return list(STATIC_SCHOLARSHIPS)

if nav == "🏠 Dashboard":
    hero_html = f'<div class="hero-banner"><p class="hero-title">🎓 UniPath AI– Live Navigator</p><p class="hero-sub">Real-time universities · Live fees · Fresh scholarships · AI Counsellor powered by web search</p></div>'
    st.markdown(hero_html, unsafe_allow_html=True)

    # --- Horizontal Metric Cards (pure HTML flexbox) ---
    all_unis = get_universities(); all_ent, all_lang = get_exams(); all_schols = get_scholarships()
    metrics = [
        (f"{len(all_unis)}+", "Universities", "🏛️"),
        (f"{len(ABROAD_COUNTRIES)}+", "Countries", "🌍"),
        (f"{len(all_schols)}+", "Scholarships", "🏅"),
        (f"{len(all_ent)+len(all_lang)}+", "Exams", "📝"),
    ]
    metrics_html = '<div style="display:flex;flex-direction:row;gap:16px;margin-bottom:1.5rem;flex-wrap:wrap;">'
    for val, label, icon in metrics:
        metrics_html += (
            f'<div style="flex:1;min-width:160px;background:white;border-radius:16px;padding:1.4rem 1.6rem;'
            f'box-shadow:0 4px 20px rgba(48,43,99,.10);border-left:5px solid #667eea;">'
            f'<div style="font-size:0.85rem;color:#888;margin-bottom:4px;">{icon} {label}</div>'
            f'<div style="font-family:Sora,sans-serif;font-size:1.8rem;font-weight:800;color:#302b63;">{val}</div>'
            f'</div>'
        )
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    st.markdown("---")

    # --- Quick Navigate Module Cards (horizontal, clickable) ---
    st.markdown('<p class="section-header">⚡ Quick Navigate</p>', unsafe_allow_html=True)
    nav_modules = [
        ("🏛️ Find Universities & Colleges", "🏛️", "Search & filter universities worldwide"),
        ("📝 Entrance Exams", "📝", "Indian & international exam info"),
        ("🏅 Scholarships", "🏅", "Find scholarships & grants"),
        ("💰 Compare Fees", "💰", "Side-by-side fee comparison"),
        ("📋 Apply Now", "📋", "Application tracker & matching"),
        ("📰 Live News", "📰", "Latest education headlines"),
        ("🛂 Visa Guide", "🛂", "Student visa requirements"),
        ("📈 ROI Calculator", "📈", "Return on investment analysis"),
        ("🏦 Loan Estimator", "🏦", "EMI & loan provider info"),
        ("✍️ SOP / LOR Builder", "✍️", "AI-powered SOP generator"),
        ("💬 Ask Assistant", "💬", "AI counsellor chat"),
    ]
    # Render in rows of 4
    for row_start in range(0, len(nav_modules), 4):
        row_cols = st.columns(4)
        for i, col in enumerate(row_cols):
            idx = row_start + i
            if idx < len(nav_modules):
                mod_nav, mod_icon, mod_desc = nav_modules[idx]
                with col:
                    if st.button(f"{mod_icon}\n{mod_nav.split(' ', 1)[-1] if ' ' in mod_nav else mod_nav}", key=f"nav_btn_{idx}", width="stretch"):
                        st.session_state["nav_target"] = mod_nav
                        st.rerun()
                    st.caption(mod_desc)

    st.markdown("---")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("**🔴 Live Data Sources**")
        st.markdown(f"- DuckDuckGo Search: {'✅ Active' if DDG_OK else '❌ Throttled'}")
        st.markdown(f"- Groq AI Extraction: {'✅ Active' if GROQ_OK else '❌ Disconnected'}")
    st.markdown("---")
    st.markdown('<p class="section-header">📰 Latest Higher Education News</p>', unsafe_allow_html=True)
    news = fetch_edu_news("study abroad India university admission 2026")
    if news:
        for item in news:
            url_link = f'<a href="{item.get("url","#")}" target="_blank" style="font-size:0.78rem;color:#667eea;">Read more →</a>' if item.get("url") else ''
            news_html = f'<div class="news-card"><div style="font-weight:700;color:#302b63;font-size:0.9rem;">{item["title"]}</div><div style="font-size:0.78rem;color:#888;margin:.3rem 0;">{item.get("source","")} · {item.get("date","")}</div><div style="font-size:0.82rem;color:#555;">{item.get("body","")[:300]}</div>{url_link}</div>'
            st.markdown(news_html, unsafe_allow_html=True)
    st.markdown("---")
    df_t = pd.DataFrame({"Country": ["USA","UK","Canada","Australia","Germany","India","Singapore","Ireland","Netherlands","Japan"], "Applications 2025 (K)": [210,185,160,140,95,320,70,45,40,35], "Avg Fees (₹ Lakhs/yr)": [35,30,28,25,5,3,32,25,20,8]})
    fig = px.bar(df_t, x="Country", y="Applications 2025 (K)", color="Avg Fees (₹ Lakhs/yr)", color_continuous_scale=["#c9b8ff","#302b63"], title="🔥 Top Study Destinations")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=300)
    st.plotly_chart(fig, width="stretch")

elif nav == "🏛️ Find Universities":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">🏛️ Find Universities – Live Search</h1>', unsafe_allow_html=True)
    with st.expander("🔎 Search & Filters", expanded=True):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        search_q = r1c1.text_input("🔍 Search", placeholder="e.g. AI research Europe...", key="uni_search")
        f_dest = r1c2.selectbox("📍 Destination", ["All","India","Abroad"]+ABROAD_COUNTRIES, key="uni_dest")
        f_level = r1c3.selectbox("🎓 Degree Level", ALL_DEGREES, key="uni_level")
        f_domain = r1c4.selectbox("📚 Domain", ALL_DOMAINS, key="uni_dom")
        r2c1, r2c2, r2c3, r2c4, r2c5, r2c6 = st.columns(6)
        f_status = r2c1.selectbox("📋 Status", ["All","Open","Closing Soon","Closed"], key="uni_stat")
        f_cat = r2c2.selectbox("🎓 Category", ["All", "University", "College/Institute"], key="uni_cat")
        f_type = r2c3.selectbox("🏫 Type", ["All","Public","Private"], key="uni_type")
        f_rank = r2c4.number_input("🏅 Max Rank", 1, 9999, 9999, key="uni_rank")
        f_fee = r2c5.slider("💰 Max Fee (₹L)", 0.0, 80.0, 80.0, 0.5, key="uni_fee")
        f_sort = r2c6.selectbox("↕️ Sort", ["Rank","Fees (Low→High)","Rating","Name"], key="uni_sort")
        use_live = st.checkbox("🔴 Fetch live data", value=True, key="uni_live")
        # AI Suggestion
        ai_uc1, ai_uc2 = st.columns([3, 1])
        ai_uni_goal = ai_uc1.text_input("🎯 Describe Your Profile (for AI recommendations)", placeholder="e.g. B.Tech CSE 8.0 CGPA, want affordable MS in AI abroad...", key="uni_ai_goal")
        if ai_uc2.button("🤖 Get AI Suggestions", key="uni_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI University Suggestions")
            if ai_uni_goal:
                with st.spinner("🤖 Finding best universities for you..."):
                    suggestion = ai_suggest("universities", {"profile": ai_uni_goal, "domain": f_domain, "country": f_dest, "degree": f_level, "category": f_cat, "type": f_type, "budget": f"{f_fee}L"})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;margin-bottom:1rem;color:#302b63;line-height:1.7;"><b>🤖 AI Recommendation:</b><br>{suggestion}</div>', unsafe_allow_html=True)
            else:
                st.warning("Please describe your profile to get AI recommendations.")
    # Auto-trigger search if filters change and live is enabled, or if search button is clicked
    current_search_state = (f_domain, f_dest, f_level, search_q)
    if st.button("🔍 Search Institutions", width="stretch") or (use_live and st.session_state.get("last_uni_search") != current_search_state):
        log_activity(st.session_state.user_email, f"Searched Universities (Q: '{search_q}', Dest: {f_dest}, Domain: {f_domain})")
        with st.spinner("Fetching live university data..."):
            all_unis = get_universities(f_domain, f_dest, f_level, search_q, live=use_live)
            st.session_state["uni_results"] = all_unis
            st.session_state["last_uni_search"] = current_search_state
    results = filter_universities(st.session_state.get("uni_results", list(STATIC_UNIVERSITIES)), search_q=search_q, dest=f_dest, level=f_level, domain=f_domain, status=f_status, uni_type=f_type, inst_category=f_cat, fee_range=(0.0, f_fee), rank_max=f_rank if f_rank < 9999 else None, sort_by=f_sort)
    pub_c = len([u for u in results if u.get('type')=='Public']); priv_c = len([u for u in results if u.get('type')=='Private'])
    st.markdown(f"**{len(results)} institutions found** (🏫 Public: {pub_c} | 🏢 Private: {priv_c})")
    for uni in results:
        st.markdown(render_uni_card(uni), unsafe_allow_html=True)

elif nav == "📝 Entrance Exams":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">📝 Entrance Exams – Comprehensive Guide</h1>', unsafe_allow_html=True)
    from exam_db import ENTRANCE_EXAMS, LANGUAGE_EXAMS
    with st.expander("🔎 Filters & AI Suggestions", expanded=True):
        ec1, ec2 = st.columns(2)
        exam_domain = ec1.selectbox("📚 Domain", ALL_DOMAINS, key="exam_dom_filter")
        exam_search = ec2.text_input("🔍 Search Exam", placeholder="e.g. GATE, GRE, IELTS...", key="exam_search")
        ai_c1, ai_c2 = st.columns([3, 1])
        ai_goal = ai_c1.text_input("🎯 Your Goal", placeholder="e.g. MS in CS in USA...", key="exam_ai_goal")
        suggestion = None
        if ai_c2.button("🤖 Get AI Suggestions", key="exam_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI Exam Suggestions")
            if ai_goal:
                with st.spinner("🤖 Recommending exams..."):
                    suggestion = ai_suggest("entrance exams", {"goal": ai_goal, "domain": exam_domain})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;margin-bottom:1rem;color:#302b63;line-height:1.7;"><b>🤖 AI Recommendation:</b><br>{suggestion}</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🇮🇳 Indian Entrance Exams", "🌐 International & Language Tests"])


    with tab1:
        st.markdown('<p class="section-header">Indian Entrance Examinations</p>', unsafe_allow_html=True)

        # Exam filters
        with st.expander("🔎 Filter Exams", expanded=True):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                e_domain = st.selectbox("📚 Domain", ["All","Engineering","Management","Medical","Law","Sciences","Design"], key="exam_dom")
            with ec2:
                e_mode = st.selectbox("💻 Mode", ["All","Online","Offline"], key="exam_mode")
            with ec3:
                e_fee_max = st.slider("💰 Max Fee (₹)", 500, 10000, 10000, 100, key="exam_fee")

        mode_map = {"All":"All","Online":"Online (CBT)","Offline":"Offline (OMR)"}

        # ── Live exam data enrichment ──────────────────────────────────
        _exam_pool = list(ENTRANCE_EXAMS)
        if GROQ_OK and DDG_OK:
            _ex_cache = f"live_exams_{e_domain}"
            if _ex_cache not in st.session_state:
                st.session_state[_ex_cache] = None
            if st.button("🔴 Fetch Live Exam Data from Web", key="btn_live_exams"):
                with st.spinner("🌐 Fetching live exam data..."):
                    try:
                        _live_ex = fetch_exams_live(domain=e_domain)
                        _dom_ex = [e for e in _live_ex if not e.get("is_international")]
                        st.session_state[_ex_cache] = _dom_ex if _dom_ex else []
                    except Exception:
                        st.session_state[_ex_cache] = []
            if st.session_state.get(_ex_cache):
                _exam_pool = merge_with_live(_exam_pool, st.session_state[_ex_cache])

        filtered_exams = filter_entrance_exams(
            _exam_pool,
            domain=e_domain,
            mode=mode_map[e_mode],
            fee_max=e_fee_max if e_fee_max < 10000 else None,
        )

        st.markdown(f"**{len(filtered_exams)} exams found**")
        cols = st.columns(2)
        for i, exam in enumerate(filtered_exams):
            with cols[i % 2]:
                st.markdown(f"""
                <div class="exam-card">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                        <div>
                            <div class="exam-name">{exam["name"]}</div>
                            <div style="font-size:0.8rem;color:#888;margin:3px 0 8px;">{exam["full_name"]}</div>
                        </div>
                        <span class="badge badge-rank">{exam["domain"]}</span>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
                        <div><span style="font-size:0.75rem;color:#888;">Conducting Body</span><br>
                             <span style="font-size:0.85rem;font-weight:600;color:#302b63;">{exam["body"]}</span></div>
                        <div><span style="font-size:0.75rem;color:#888;">Exam Fee</span><br>
                             <span class="exam-fee">{exam["fee"]}</span></div>
                        <div><span style="font-size:0.75rem;color:#888;">Next Date</span><br>
                             <span style="font-size:0.85rem;font-weight:600;color:#302b63;">{exam["next_date"]}</span></div>
                        <div><span style="font-size:0.75rem;color:#888;">Mode</span><br>
                             <span style="font-size:0.85rem;font-weight:600;color:#302b63;">{exam["mode"]}</span></div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-size:0.75rem;color:#888;">Accepted By:</span><br>
                        <span style="font-size:0.8rem;color:#302b63;">{", ".join(exam["accepted_by"][:4])}{" & more" if len(exam["accepted_by"])>4 else ""}</span>
                    </div>
                    <div style="margin-bottom:10px;">
                        <span style="font-size:0.75rem;color:#888;">Valid For:</span>
                        <span style="font-size:0.8rem;font-weight:600;color:#667eea;"> {exam["validity"]}</span>
                    </div>
                    <div style="display:flex;gap:8px;">
                        <a href="{exam["register_link"]}" target="_blank" class="apply-btn">📝 Register</a>
                        <a href="{exam["info_link"]}" target="_blank" class="apply-btn" style="background:linear-gradient(135deg,#434343,#000);">ℹ️ Info</a>
                    </div>
                </div>""", unsafe_allow_html=True)

    with tab2:
        st.markdown('<p class="section-header">International & Language Proficiency Tests</p>', unsafe_allow_html=True)

        # Language exam filters
        with st.expander("🔎 Filter Tests", expanded=True):
            lc1, lc2, lc3, lc4 = st.columns(4)
            with lc1:
                l_country = st.selectbox("🌍 Accepted In", ["All","USA","UK","Canada","Australia","Germany","Europe","Global"], key="lang_ctry")
            with lc2:
                l_format = st.selectbox("💻 Format", ["All","Online","Computer"], key="lang_fmt")
            with lc3:
                l_fee_max = st.slider("💰 Max Fee (₹)", 4000, 30000, 30000, 500, key="lang_fee")
            with lc4:
                l_validity = st.selectbox("⏳ Score Validity", ["All","2 Years","5 Years","Unlimited"], key="lang_valid")

        filtered_lang = filter_language_exams(
            LANGUAGE_EXAMS,
            country=l_country,
            fee_max_inr=l_fee_max if l_fee_max < 30000 else None,
            format_filter=l_format,
        )
        if l_validity != "All":
            filtered_lang = [e for e in filtered_lang if e.get("validity") == l_validity]

        st.markdown(f"**{len(filtered_lang)} tests found**")

        # Fee comparison mini-chart
        if filtered_lang:
            df_fees = pd.DataFrame([{"Test": e["name"], "Fee (₹)": int(e["fee_inr"].replace(",","")),
                                      "Accepted In": len(e["accepted_in"])} for e in filtered_lang])
            fig_lf = px.bar(df_fees, x="Test", y="Fee (₹)", color="Accepted In",
                            color_continuous_scale=["#c9b8ff","#302b63"],
                            title="Fee Comparison – Language Tests")
            fig_lf.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  font=dict(family="DM Sans"), margin=dict(t=30,b=0), height=220)
            st.plotly_chart(fig_lf, width="stretch")

        for exam in filtered_lang:
            st.markdown(f"""
            <div class="exam-card" style="border-top-color:#11998e;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">
                    <div>
                        <div class="exam-name" style="font-size:1.3rem;">{exam["name"]}</div>
                        <div style="font-size:0.82rem;color:#888;">{exam["full_name"]}</div>
                    </div>
                    <div style="text-align:right;">
                        <div class="exam-fee">₹{exam["fee_inr"]}</div>
                        <div style="font-size:0.75rem;color:#888;">(~${exam["fee_usd"]} USD)</div>
                    </div>
                </div>
                <div style="margin:10px 0;display:flex;flex-wrap:wrap;gap:4px;">
                    {"".join([f'<span class="info-pill">✓ {c}</span>' for c in exam["accepted_in"]])}
                </div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0;">
                    <div><span style="font-size:0.73rem;color:#888;">Format</span><br>
                         <span style="font-size:0.82rem;font-weight:600;color:#302b63;">{exam["format"]}</span></div>
                    <div><span style="font-size:0.73rem;color:#888;">Duration</span><br>
                         <span style="font-size:0.82rem;font-weight:600;color:#302b63;">{exam["duration"]}</span></div>
                    <div><span style="font-size:0.73rem;color:#888;">Score Valid</span><br>
                         <span style="font-size:0.82rem;font-weight:600;color:#302b63;">{exam["validity"]}</span></div>
                    <div><span style="font-size:0.73rem;color:#888;">Test Centers</span><br>
                         <span style="font-size:0.82rem;font-weight:600;color:#667eea;">{exam["centers_india"]} in India</span></div>
                </div>
                <div style="background:#f4f2ff;border-radius:10px;padding:10px;margin-bottom:10px;">
                    <span style="font-size:0.78rem;font-weight:600;color:#302b63;">Score Range & Requirement:</span>
                    <span style="font-size:0.78rem;color:#555;"> {exam["score_info"]}</span>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <a href="{exam["register_link"]}" target="_blank" class="apply-btn">📝 Book Test Slot</a>
                    <a href="{exam["prep_link"]}" target="_blank" class="apply-btn" style="background:linear-gradient(135deg,#f7971e,#ffd200);color:#302b63 !important;">📖 Free Prep</a>
                    <a href="{exam["center_link"]}" target="_blank" class="apply-btn" style="background:linear-gradient(135deg,#434343,#000);">📍 Find Center</a>
                </div>
            </div>""", unsafe_allow_html=True)

elif nav == "🎓 Scholarships":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">🏅 Scholarships – By Country</h1>', unsafe_allow_html=True)
    from schol_db import SCHOLARSHIPS, get_scholarships_by_country
    with st.expander("🔎 Filters & AI Suggestions", expanded=True):
        sc1, sc2, sc3 = st.columns(3)
        schol_country = sc1.selectbox("🌍 Country", ALL_COUNTRIES, key="schol_country")
        schol_type = sc2.selectbox("📋 Type", ["All","Government","University"], key="schol_type")
        schol_search = sc3.text_input("🔍 Search", placeholder="e.g. Fulbright, DAAD...", key="schol_search")
        ai_sc1, ai_sc2 = st.columns([3, 1])
        ai_profile = ai_sc1.text_input("🎯 Your Profile", placeholder="e.g. BE in CS, 8.5 CGPA, want to study in USA...", key="schol_ai_profile")
        if ai_sc2.button("🤖 Get AI Suggestions", key="schol_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI Scholarship Suggestions")
            if ai_profile:
                with st.spinner("🤖 Finding matching scholarships..."):
                    suggestion = ai_suggest("scholarships", {"profile": ai_profile, "country": schol_country})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;margin-bottom:1rem;color:#302b63;line-height:1.7;"><b>🤖 AI Recommendation:</b><br>{suggestion}</div>', unsafe_allow_html=True)
    all_schols = get_scholarships_by_country(schol_country)
    if schol_type != "All":
        all_schols = [s for s in all_schols if s.get("type","").lower() == schol_type.lower()]
    if schol_search:
        q = schol_search.lower()
        all_schols = [s for s in all_schols if q in s["name"].lower() or q in s.get("provider","").lower()]
    gov_c = len([s for s in all_schols if s.get("type")=="Government"])
    uni_c = len([s for s in all_schols if s.get("type")=="University"])
    st.markdown(f"**{len(all_schols)} scholarships found** (🏛️ Government: {gov_c} | 🎓 University: {uni_c})")
    for schol in all_schols:
        t = schol.get("type","")
        t_bg = "#e8f5e9" if t == "Government" else "#fff3e0"
        t_fg = "#2e7d32" if t == "Government" else "#e65100"
        t_icon = "🏛️" if t == "Government" else "🎓"
        st.markdown(f'<div class="schol-card"><div style="display:flex;justify-content:space-between;align-items:start;"><div><div class="uni-name">{schol["name"]}</div><div style="font-size:0.82rem;color:#888;">by <b>{schol.get("provider","")}</b> — {schol["country"]}</div></div><div><span class="badge" style="background:{t_bg};color:{t_fg};">{t_icon} {t}</span></div></div><div style="margin:10px 0;"><span class="schol-amount">{schol.get("amount","—")}</span></div><div style="font-size:0.82rem;color:#555;margin:6px 0;">📋 <b>Eligibility:</b> {schol.get("eligibility","See website")}</div><div style="font-size:0.82rem;color:#555;">📅 <b>Deadline:</b> {schol.get("deadline","Varies")}</div><div style="margin-top:10px;"><a href="{schol.get("website","#")}" target="_blank" class="apply-btn">🏅 Apply / Visit Website →</a></div></div>', unsafe_allow_html=True)

elif nav == "💬 Ask Assistant":
    from voice_assistant import render_assistant_page
    render_assistant_page(GROQ_OK)

elif nav == "💰 Compare Fees":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">💰 Compare Fees – Live</h1>', unsafe_allow_html=True)
    # AI Suggestion
    with st.expander("🤖 AI Fee Advisor", expanded=False):
        fee_ai_c1, fee_ai_c2 = st.columns([3, 1])
        fee_ai_q = fee_ai_c1.text_input("🎯 Your Budget & Goal", placeholder="e.g. Budget 15L/yr, want MS in CS abroad...", key="fee_ai_q")
        if fee_ai_c2.button("🤖 Get Advice", key="fee_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI Fee Advice")
            if fee_ai_q:
                with st.spinner("🤖 Analyzing affordable options..."):
                    suggestion = ai_suggest("fee comparison", {"query": fee_ai_q})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;color:#302b63;line-height:1.7;"><b>🤖 AI Fee Advice:</b><br>{suggestion}</div>', unsafe_allow_html=True)
    fc1, fc2 = st.columns(2)
    uni1 = fc1.text_input("University 1", "IIT Bombay", key="fee_u1")
    uni2 = fc2.text_input("University 2", "MIT", key="fee_u2")
    if st.button("🔍 Compare Fees", width="stretch"):
        log_activity(st.session_state.user_email, f"Compared fees between {uni1} and {uni2}")
        with st.spinner("Fetching live fees…"):
            f1 = fetch_live_fees(uni1, "India")
            f2 = fetch_live_fees(uni2, "USA")
        c1, c2 = st.columns(2)
        for col, name, data in [(c1,uni1,f1),(c2,uni2,f2)]:
            with col:
                st.markdown(f'<div class="metric-card"><h3>{name}</h3><p>Fee: {data.get("fees_inr","N/A")} | Deadline: {data.get("deadline","N/A")}</p><p>Status: {data.get("admission_status","N/A")}</p></div>', unsafe_allow_html=True)
    # Static comparison chart
    df_fees = pd.DataFrame({"University":["IIT Bombay","IIT Delhi","IIT Madras","MIT","Stanford","Oxford","Cambridge","TU Munich","ETH Zurich","NUS","UToronto","UNSW Sydney","Tokyo Univ","NTU Singapore","KAIST Korea"],"Fees (₹ Lakhs/yr)":[2.5,2.8,2.3,42,45,32,34,0.5,1.2,28,22,30,4,28,3]})
    fig = px.bar(df_fees, x="University", y="Fees (₹ Lakhs/yr)", color="Fees (₹ Lakhs/yr)", color_continuous_scale=["#c9b8ff","#302b63"], title="💰 Fee Comparison – Global Universities")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400)
    st.plotly_chart(fig, width="stretch")

elif nav == "📋 Apply Now":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">📋 Application Tracker</h1>', unsafe_allow_html=True)
    st.markdown('**Build your application profile and track deadlines**')
    
    # Update profile instantly
    with st.expander("👤 Edit Your Profile & Scores", expanded=True):
        ac1, ac2 = st.columns(2)
        u_name = ac1.text_input("Full Name", value=st.session_state.get("user_name", ""), key="apply_name")
        u_email = ac2.text_input("Email", value=st.session_state.user_email, key="apply_email")
        st.session_state["user_name"] = u_name

        ac3, ac4 = st.columns(2)
        degree = ac3.selectbox("Target Degree", ALL_DEGREES[1:], key="apply_deg")
        domain = ac4.selectbox("Target Domain", ALL_DOMAINS[1:], key="apply_dom")
        countries = st.multiselect("Target Countries", ABROAD_COUNTRIES + ["India"], default=st.session_state.user_profile["target_dest"], key="apply_countries")
        
        budget = st.slider("Annual Budget (₹ Lakhs)", 1.0, 80.0, float(st.session_state.user_profile["budget_max"]), key="apply_budget")
        
        ap1, ap2, ap3 = st.columns(3)
        ug_score = ap1.number_input("UG Score / CGPA (%)", 0.0, 100.0, float(st.session_state.user_profile["score_pct"]), key="apply_ug")
        gre_score = ap2.number_input("GRE Score", 0, 340, int(st.session_state.user_profile["gre"]), key="apply_gre")
        gmat_score = ap3.number_input("GMAT Score", 0, 805, int(st.session_state.user_profile["gmat"]), key="apply_gmat")
        
        ap4, ap5, ap6 = st.columns(3)
        ielts_score = ap4.number_input("IELTS Score", 0.0, 9.0, float(st.session_state.user_profile["ielts"]), 0.5, key="apply_ielts")
        toefl_score = ap5.number_input("TOEFL Score", 0, 120, int(st.session_state.user_profile["toefl"]), key="apply_toefl")
        work_exp = ap6.number_input("Work Experience (Years)", 0, 20, int(st.session_state.user_profile["work_exp"]), key="apply_work")

        priorities = st.multiselect("Priorities", ["High Ranking", "Low Fees", "Scholarships", "Research Focus", "Industry Connections"], default=st.session_state.user_profile["priorities"], key="apply_pri")
        
        # Update session state profile
        st.session_state.user_profile = {
            "score_pct": ug_score, "gre": gre_score, "gmat": gmat_score,
            "ielts": ielts_score, "toefl": toefl_score, "work_exp": work_exp,
            "desired_domain": domain, "desired_level": degree,
            "target_dest": countries if countries else ["India"],
            "budget_max": budget, "priorities": priorities
        }

    if st.button("🔍 Refresh & Find Matching Programs", width="stretch"):
        log_activity(st.session_state.user_email, "Refreshed matching programs in Apply Now")
        with st.spinner("Fetching latest programs..."):
            unis = get_universities(domain, countries[0] if countries else "All", degree, live=True)
            st.session_state["apply_unis"] = unis

    # Always show results if we have them, they will update instantly when profile changes
    if "apply_unis" in st.session_state:
        unis = st.session_state["apply_unis"]
        matches = ml_engine.match_model.get_ranked_matches(unis, st.session_state.user_profile)
        st.markdown(f"**Found {len(matches)} matching programs for {u_name}:**")
        for u, score in matches:
            st.markdown(render_uni_card(u, st.session_state.user_profile), unsafe_allow_html=True)

elif nav == "📰 Live News":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">📰 Live Education News</h1>', unsafe_allow_html=True)
    topic = st.text_input("Search news topic", "India study abroad university admission 2026", key="news_q")
    news = fetch_edu_news(topic)
    if news:
        for item in news:
            url_link = f'<a href="{item.get("url","#")}" target="_blank" style="color:#667eea;font-size:.82rem;">Read full article →</a>' if item.get("url") else ''
            st.markdown(f'<div class="news-card"><div style="font-weight:700;color:#302b63;font-size:.95rem;">{item["title"]}</div><div style="font-size:.78rem;color:#888;margin:.3rem 0;">{item.get("source","")} · {item.get("date","")}</div><div style="font-size:.84rem;color:#555;">{item.get("body","")[:300]}</div>{url_link}</div>', unsafe_allow_html=True)
    else:
        st.info("No news found. Try a different search topic.")

elif nav == "🛂 Visa Guide":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">🛂 Student Visa Guide</h1>', unsafe_allow_html=True)
    # AI Visa Advisor
    with st.expander("🤖 AI Visa Advisor", expanded=False):
        visa_ai_c1, visa_ai_c2 = st.columns([3, 1])
        visa_ai_q = visa_ai_c1.text_input("🎯 Your Visa Question", placeholder="e.g. Best visa strategy for MS in USA with part-time work...", key="visa_ai_q")
        if visa_ai_c2.button("🤖 Get Advice", key="visa_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI Visa Advice")
            if visa_ai_q:
                with st.spinner("🤖 Getting visa guidance..."):
                    suggestion = ai_suggest("student visa", {"query": visa_ai_q})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;color:#302b63;line-height:1.7;"><b>🤖 AI Visa Advice:</b><br>{suggestion}</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0f0c29,#302b63,#667eea);border-radius:20px;
                padding:1.8rem 2rem;margin-bottom:1.5rem;color:white;">
        <h1 style="font-family:'Sora',sans-serif;margin:0;font-size:1.8rem;">🛂 Student Visa Guide for Indian Students</h1>
        <p style="margin:0.5rem 0 0;opacity:0.85;">Country-wise visa types · Required docs · Processing timelines · Pro tips</p>
    </div>""", unsafe_allow_html=True)
 
    visa_country = st.selectbox("🌍 Select Destination Country", list(VISA_DATA.keys()), key="visa_ctry")
    
    if not visa_country or not VISA_DATA:
        st.info("🌐 Please select a country to view visa details. (Data Hub might be loading...)")
    else:
        vdata = VISA_DATA[visa_country]
     
        # Overview metrics
        v1, v2, v3, v4 = st.columns(4)
        v1.markdown(f'<div class="metric-card"><h3 style="font-size:1rem;">{vdata["visa_type"]}</h3><p>Visa Type</p></div>', unsafe_allow_html=True)
        v2.markdown(f'<div class="metric-card" style="border-color:#11998e;"><h3 style="font-size:1.1rem;">{vdata["fee_inr"]}</h3><p>Application Fee</p></div>', unsafe_allow_html=True)
        v3.markdown(f'<div class="metric-card" style="border-color:#f7971e;"><h3 style="font-size:1.1rem;">{vdata["processing_weeks"]}</h3><p>Processing Time</p></div>', unsafe_allow_html=True)
        v4.markdown(f'<div class="metric-card" style="border-color:#764ba2;"><h3 style="font-size:1rem;">{vdata["work_rights"][:35]}…</h3><p>Work Rights</p></div>', unsafe_allow_html=True)
     
        tab_docs, tab_timeline, tab_tips, tab_pr = st.tabs(["📄 Documents", "📅 Timeline", "💡 Tips", "🏠 PR Pathway"])
     
        with tab_docs:
            st.markdown('<p class="section-header">Required Documents</p>', unsafe_allow_html=True)
            doc_cols = st.columns(2)
            for i, doc in enumerate(vdata["documents"]):
                with doc_cols[i % 2]:
                    st.markdown(f"""
                    <div style="display:flex;gap:10px;align-items:flex-start;background:white;border-radius:10px;
                                padding:10px 14px;margin-bottom:8px;box-shadow:0 2px 8px rgba(48,43,99,0.06);border:1px solid #e8e4ff;">
                        <span style="color:#11998e;font-weight:700;font-size:1rem;">✓</span>
                        <span style="font-size:0.87rem;color:#302b63;">{doc}</span>
                    </div>""", unsafe_allow_html=True)
     
            st.markdown("---")
            st.markdown(f"""
            <div style="background:#fff3e0;border-radius:12px;padding:1rem 1.2rem;border-left:4px solid #f7971e;">
                <span style="font-weight:700;color:#e65100;">⚠️ Special Note:</span>
                <span style="font-size:0.87rem;color:#555;"> Application fee includes {vdata.get("sevis_fee","—")} additional charges (e.g., SEVIS, IHS, GIC). Budget accordingly.</span>
            </div>""", unsafe_allow_html=True)
     
        with tab_timeline:
            st.markdown('<p class="section-header">Application Timeline</p>', unsafe_allow_html=True)
            for step_idx, (step, timing) in enumerate(vdata["timeline"], 1):
                st.markdown(f"""
                <div style="display:flex;gap:16px;margin-bottom:14px;align-items:flex-start;">
                    <div style="min-width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#667eea,#764ba2);
                                display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:0.85rem;">{step_idx}</div>
                    <div style="flex:1;background:white;border-radius:10px;padding:10px 14px;
                                box-shadow:0 2px 8px rgba(48,43,99,0.06);border:1px solid #e8e4ff;">
                        <div style="font-weight:600;color:#302b63;font-size:0.9rem;">{step}</div>
                        <div style="font-size:0.8rem;color:#888;margin-top:3px;">{timing}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
     
        with tab_tips:
            st.markdown('<p class="section-header">Expert Tips for Indian Students</p>', unsafe_allow_html=True)
            for tip in vdata["tips"]:
                st.markdown(f"""
                <div style="background:white;border-radius:10px;padding:10px 14px;margin-bottom:8px;
                            border-left:3px solid #667eea;box-shadow:0 2px 8px rgba(48,43,99,0.05);">
                    <span style="font-size:0.87rem;color:#302b63;">💡 {tip}</span>
                </div>""", unsafe_allow_html=True)
     
        with tab_pr:
            st.markdown('<p class="section-header">🏠 Permanent Residency Pathway</p>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="uni-card" style="background:linear-gradient(135deg,white,#f4f2ff);">
                <div class="uni-name">🏠 {visa_country} PR Pathway for Indian Students</div>
                <p style="font-size:0.9rem;color:#555;line-height:1.7;margin-top:0.5rem;">{vdata["pr_path"]}</p>
            </div>""", unsafe_allow_html=True)
     
            pr_ease = {
                "Canada": 90, "Australia": 80, "Germany": 75, "Netherlands": 65,
                "UK": 55, "Singapore": 40, "USA": 35, "Japan": 30,
                "South Korea": 30, "UAE": 20, "Czech Republic": 60,
                "Mexico": 45, "Chile": 50, "Poland": 60, "Portugal": 70,
                "Malaysia": 25, "Norway": 65, "Finland": 70, "Hong Kong": 45
            }
            ease = pr_ease.get(visa_country, 50)
            st.markdown(f"""
            <div style="margin-top:1rem;">
                <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:6px;">
                    <span style="color:#888;">PR Ease Score for Indian Students</span>
                    <span style="font-weight:700;color:#302b63;">{ease}/100</span>
                </div>
                <div style="height:10px;background:#e8e4ff;border-radius:5px;">
                    <div style="height:10px;width:{ease}%;background:linear-gradient(90deg,{'#11998e,#38ef7d' if ease >= 70 else '#f7971e,#ffd200' if ease >= 50 else '#667eea,#764ba2'});border-radius:5px;"></div>
                </div>
                <div style="font-size:0.78rem;color:#888;margin-top:4px;">{"🟢 Excellent" if ease >= 70 else "🟡 Moderate" if ease >= 50 else "🔵 Competitive"} — based on processing times, investment required, and historical approval rates</div>
            </div>""", unsafe_allow_html=True)
     
        # Embassy quick links
        st.markdown("---")
        st.markdown(f'<a href="{vdata["embassy_link"]}" target="_blank" class="apply-btn">🌐 Official {visa_country} Embassy / Immigration Portal</a>', unsafe_allow_html=True)
 
 

elif nav == "📈 ROI Calculator":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">📈 ROI Calculator</h1>', unsafe_allow_html=True)
    # AI Career ROI Advisor
    with st.expander("🤖 AI Career & ROI Advisor", expanded=False):
        roi_ai_c1, roi_ai_c2 = st.columns([3, 1])
        roi_ai_q = roi_ai_c1.text_input("🎯 Your Career Goal", placeholder="e.g. Is MS in Data Science in USA worth 50L investment?", key="roi_ai_q")
        if roi_ai_c2.button("🤖 Analyze ROI", key="roi_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI ROI Analysis")
            if roi_ai_q:
                with st.spinner("🤖 Analyzing ROI..."):
                    suggestion = ai_suggest("ROI and career prospects", {"query": roi_ai_q})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;color:#302b63;line-height:1.7;"><b>🤖 AI ROI Analysis:</b><br>{suggestion}</div>', unsafe_allow_html=True)
    rc1, rc2, rc3 = st.columns(3)
    total_cost = rc1.number_input("Total Program Cost (₹ Lakhs)", 1.0, 200.0, 25.0, key="roi_cost")
    expected_salary = rc2.number_input("Expected Annual Salary After (₹ Lakhs)", 1.0, 100.0, 12.0, key="roi_sal")
    years = rc3.number_input("Years to Calculate", 1, 20, 5, key="roi_yrs")
    roi = ((expected_salary * years - total_cost) / total_cost) * 100
    st.markdown(f'<div class="metric-card"><h3>{roi:.0f}% ROI</h3><p>Over {years} years with ₹{expected_salary}L/yr salary</p></div>', unsafe_allow_html=True)
    df_roi = pd.DataFrame({"Year": list(range(1, years+1)), "Cumulative Earnings (₹L)": [expected_salary*y for y in range(1,years+1)], "Break Even (₹L)": [total_cost]*years})
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_roi["Year"], y=df_roi["Cumulative Earnings (₹L)"], name="Earnings", fill="tozeroy", line=dict(color="#667eea")))
    fig.add_trace(go.Scatter(x=df_roi["Year"], y=df_roi["Break Even (₹L)"], name="Investment", line=dict(color="#e65100", dash="dash")))
    fig.update_layout(title="📈 ROI Projection", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=350)
    st.plotly_chart(fig, width="stretch")

elif nav == "🏦 Loan Estimator":
    st.markdown('<h1 style="font-family:Sora,sans-serif;color:#302b63;">🏦 Education Loan Estimator</h1>', unsafe_allow_html=True)
    # AI Loan Advisor
    with st.expander("🤖 AI Loan Advisor", expanded=False):
        loan_ai_c1, loan_ai_c2 = st.columns([3, 1])
        loan_ai_q = loan_ai_c1.text_input("🎯 Your Loan Query", placeholder="e.g. Best loan for 30L to study in Canada, no collateral...", key="loan_ai_q")
        if loan_ai_c2.button("🤖 Get Advice", key="loan_ai_btn", width="stretch"):
            log_activity(st.session_state.user_email, "Requested AI Loan Advice")
            if loan_ai_q:
                with st.spinner("🤖 Finding best loan options..."):
                    suggestion = ai_suggest("education loans", {"query": loan_ai_q})
                if suggestion:
                    st.markdown(f'<div style="background:#f0edff;border:1px solid #e0d9ff;border-radius:16px;padding:1.2rem;color:#302b63;line-height:1.7;"><b>🤖 AI Loan Advice:</b><br>{suggestion}</div>', unsafe_allow_html=True)
    lc1, lc2, lc3 = st.columns(3)
    loan_amt = lc1.number_input("Loan Amount (₹ Lakhs)", 1.0, 100.0, 20.0, key="loan_amt")
    rate = lc2.number_input("Interest Rate (%)", 1.0, 20.0, 8.5, 0.1, key="loan_rate")
    tenure = lc3.number_input("Tenure (Years)", 1, 20, 7, key="loan_ten")
    r_monthly = (rate/100)/12
    n_months = tenure*12
    if r_monthly > 0:
        emi = loan_amt*100000 * r_monthly * (1+r_monthly)**n_months / ((1+r_monthly)**n_months - 1)
    else:
        emi = loan_amt*100000 / n_months
    total_pay = emi * n_months
    total_interest = total_pay - loan_amt*100000
    ec1,ec2,ec3 = st.columns(3)
    ec1.markdown(f'<div class="metric-card"><h3>₹{emi:,.0f}</h3><p>Monthly EMI</p></div>', unsafe_allow_html=True)
    ec2.markdown(f'<div class="metric-card"><h3>₹{total_pay/100000:,.1f}L</h3><p>Total Payment</p></div>', unsafe_allow_html=True)
    ec3.markdown(f'<div class="metric-card"><h3>₹{total_interest/100000:,.1f}L</h3><p>Total Interest</p></div>', unsafe_allow_html=True)
    banks = [{"name":"SBI Education Loan","rate":"7.25-8.65%","max":"₹1.5 Cr","link":"https://sbi.co.in"},{"name":"HDFC Credila","rate":"9.5-13%","max":"₹45L","link":"https://hdfc.com"},{"name":"Prodigy Finance","rate":"Variable","max":"$100K","link":"https://prodigyfinance.com"},{"name":"MPOWER Financing","rate":"7.5-14%","max":"$100K","link":"https://mpowerfinancing.com"},{"name":"Bank of Baroda","rate":"7.70-9.85%","max":"₹80L","link":"https://bankofbaroda.in"},{"name":"Axis Bank","rate":"9.0-13.5%","max":"₹75L","link":"https://axisbank.com"},{"name":"Punjab National Bank","rate":"7.95-9.45%","max":"₹1 Cr","link":"https://pnbindia.in"},{"name":"ICICI Bank","rate":"9.85-11%","max":"₹1 Cr","link":"https://icicibank.com"},{"name":"Union Bank of India","rate":"8.05-10.05%","max":"₹40L","link":"https://unionbankofindia.co.in"},{"name":"Canara Bank","rate":"8.15-9.65%","max":"₹40L","link":"https://canarabank.com"},{"name":"Auxilo Finserve","rate":"10-12%","max":"₹50L","link":"https://auxilo.com"},{"name":"Avanse Financial","rate":"10.25-14%","max":"₹75L","link":"https://avanse.com"}]
    st.markdown('<p class="section-header">🏦 Top Education Loan Providers</p>', unsafe_allow_html=True)
    for bank in banks:
        st.markdown(f'<div class="uni-card"><div class="uni-name">{bank["name"]}</div><div style="font-size:.85rem;color:#888;">Rate: {bank["rate"]} | Max: {bank["max"]}</div><a href="{bank["link"]}" target="_blank" class="apply-btn">Apply →</a></div>', unsafe_allow_html=True)

elif nav == "✍️ SOP / LOR Builder":
    from groq import Groq
    import os
 
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0f0c29,#302b63,#667eea);border-radius:20px;
                padding:1.8rem 2rem;margin-bottom:1.5rem;color:white;">
        <h1 style="font-family:'Sora',sans-serif;margin:0;font-size:1.8rem;">✍️ SOP / LOR Builder</h1>
        <p style="margin:0.5rem 0 0;opacity:0.85;">AI-powered drafts for Statement of Purpose, Letters of Recommendation, Personal Statements & Research Proposals</p>
    </div>""", unsafe_allow_html=True)
 
    groq_key = None
    try:
        groq_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    except Exception:
        groq_key = os.environ.get("GROQ_API_KEY")
 
    if not groq_key:
        st.warning("⚠️ Add `GROQ_API_KEY` to `.streamlit/secrets.toml` to enable AI drafting.")
 
    doc_type = st.selectbox("📄 Document Type", list(SOP_STRUCTURE.keys()), key="sop_type")
    
    if not doc_type or not SOP_STRUCTURE:
        st.info("📄 Please select a document type. (Data Hub might be loading...)")
    else:
        info = SOP_STRUCTURE[doc_type]
 
        st.markdown(f"""
        <div style="background:white;border-radius:14px;padding:1rem 1.4rem;margin-bottom:1rem;
                    border:1px solid #e8e4ff;box-shadow:0 2px 10px rgba(48,43,99,0.06);">
            <div style="font-family:'Sora',sans-serif;font-weight:700;color:#302b63;margin-bottom:6px;">
                📋 Structure for {doc_type} <span style="font-size:0.8rem;font-weight:400;color:#888;">({info["word_limit"]})</span>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;">
                {"".join([f'<span class="info-pill">{i+1}. {s[0]}</span>' for i, s in enumerate(info["sections"])])}
            </div>
        </div>""", unsafe_allow_html=True)
 
        with st.expander("👤 Your Details", expanded=True):
            i1, i2 = st.columns(2)
            with i1:
                applicant_name = st.text_input("Your Full Name", placeholder="Priya Sharma", key="sop_name")
                target_program = st.text_input("Target Program", placeholder="MS in Computer Science", key="sop_prog")
                target_university = st.text_input("University Name", placeholder="Carnegie Mellon University", key="sop_uni")
            with i2:
                if doc_type == "Letter of Recommendation (LOR)":
                    referee_name = st.text_input("Referee's Name", placeholder="Dr. Anand Kumar", key="sop_ref_name")
                    referee_role = st.text_input("Referee's Role", placeholder="Associate Professor", key="sop_ref_role")
                    referee_inst = st.text_input("Referee's Institution", placeholder="IIT Bombay", key="sop_ref_inst")
                    referee_vars = {"referee_name": referee_name, "referee_role": referee_role, "referee_institution": referee_inst}
                else:
                    cgpa = st.text_input("CGPA / Percentage", placeholder="9.1 / 10", key="sop_cgpa")
                    work_exp_sop = st.text_input("Work Experience", placeholder="2 years at Infosys", key="sop_work")
                    referee_vars = {}
 
        background = st.text_area("📝 Key Background Points", placeholder="• Published paper\n• 9.1 CGPA\n• Built ML pipeline", height=140, key="sop_bg")
        tone = st.selectbox("🎨 Tone", ["Professional & confident", "Warm & personal", "Academic & precise", "Bold & visionary"], key="sop_tone")
        word_count = st.slider("📏 Target Word Count", 400, 1500, 900, 50, key="sop_wc")
 
        dd_col1, dd_col2 = st.columns(2)
        with dd_col1:
            st.markdown('<p class="section-header">✅ Do\'s</p>', unsafe_allow_html=True)
            for d in info["dos"]:
                st.markdown(f"<div style='font-size:0.82rem;color:#302b63;padding:3px 0;'>✅ {d}</div>", unsafe_allow_html=True)
        with dd_col2:
            st.markdown('<p class="section-header">❌ Don\'ts</p>', unsafe_allow_html=True)
            for d in info["donts"]:
                st.markdown(f"<div style='font-size:0.82rem;color:#e65100;padding:3px 0;'>❌ {d}</div>", unsafe_allow_html=True)
 
        if st.button("🤖 Generate Draft with Groq AI", width="stretch", key="sop_gen"):
            log_activity(st.session_state.user_email, f"Generated AI Draft for {doc_type}")
            if not groq_key:
                st.error("Please add GROQ_API_KEY to generate drafts.")
            elif not background.strip():
                st.warning("Please fill in your key background points.")
            else:
                template = info["prompt_template"]
                prompt_vars = {
                    "program": target_program or "MS in Computer Science",
                    "university": target_university or "a top-ranked university",
                    "background": background,
                    "applicant_name": applicant_name or "the applicant",
                }
                prompt_vars.update(referee_vars)
                # Filter variables actually in template
                safe_vars = {k: v for k, v in prompt_vars.items() if f"{{{k}}}" in template}
                prompt = template.format(**safe_vars)
                prompt += f"\n\nTone: {tone}. Target word count: {word_count} words."
                
                with st.spinner("✍️ AI is drafting…"):
                    try:
                        client = Groq(api_key=groq_key)
                        api_messages = [
                            {"role": "system", "content": "You are an expert academic writing coach for Indian students applying to top global universities."},
                            {"role": "user", "content": prompt}
                        ]
                        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=api_messages)
                        st.session_state["sop_draft"] = response.choices[0].message.content
                        st.session_state["sop_target"] = f"{doc_type} for {target_program} at {target_university}"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
 
    if "sop_draft" in st.session_state:
        st.markdown("---")
        st.markdown(f'<p class="section-header">✍️ AI Draft: {st.session_state.get("sop_target","")}</p>', unsafe_allow_html=True)
        wc = len(st.session_state["sop_draft"].split())
        st.markdown(f'<span class="info-pill">📏 {wc} words</span>', unsafe_allow_html=True)
        draft_text = st.text_area("Your Draft (editable)", st.session_state["sop_draft"], height=500, key="sop_edit")
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        with col_dl1:
            st.download_button("⬇️ Download .txt", draft_text, file_name="sop_draft.txt", mime="text/plain", width="stretch")
        with col_dl2:
            if st.button("🔄 Improve Draft", width="stretch", key="sop_improve"):
                if groq_key:
                    with st.spinner("Improving…"):
                        try:
                            client = Groq(api_key=groq_key)
                            response = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": f"Improve this {doc_type if 'doc_type' in locals() else 'document'} draft:\n\n{draft_text}"}])
                            st.session_state["sop_draft"] = response.choices[0].message.content
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        with col_dl3:
            if st.button("🗑️ Clear Draft", width="stretch", key="sop_clear"):
                del st.session_state["sop_draft"]
                st.rerun()


