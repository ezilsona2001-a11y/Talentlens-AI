import io
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from parsers.pdf_parser import extract_pdf_text
from parsers.docx_parser import extract_docx_text
from utils.llm import ask_llm, llm_available
from utils.history import load_history, save_analysis, delete_analysis
from reports.pdf_report import build_analysis_pdf, build_ranking_pdf
from reports.resume_export import build_resume_docx, build_resume_pdf

load_dotenv()

APP_DIR = Path(__file__).parent
HISTORY_FILE = APP_DIR / "data" / "history.json"
HISTORY_FILE.parent.mkdir(exist_ok=True)

st.set_page_config(
    page_title="TalentLens AI",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# THEME
# -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg:#07100c;
    --panel:#0d1812;
    --panel2:#101f17;
    --border:rgba(74,222,128,.16);
    --green:#22c55e;
    --green2:#86efac;
    --mint:#34d399;
    --text:#f1f8f3;
    --muted:#91a49a;
    --danger:#fb7185;
    --yellow:#facc15;
}

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 15% 10%, rgba(34,197,94,.12), transparent 28%),
        radial-gradient(circle at 85% 20%, rgba(16,185,129,.08), transparent 25%),
        linear-gradient(135deg,#050b08 0%,#07110c 45%,#08150f 100%);
    color:var(--text);
}

[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#07100c,#09150f);
    border-right:1px solid var(--border);
}

[data-testid="stSidebar"] * {
    color:var(--text);
}

.block-container {
    max-width:1450px;
    padding-top:2rem;
    padding-bottom:4rem;
}

h1,h2,h3,h4 {
    color:var(--text)!important;
}

.hero {
    padding:30px;
    border:1px solid var(--border);
    border-radius:24px;
    background:linear-gradient(135deg,rgba(18,45,29,.82),rgba(9,23,15,.72));
    box-shadow:0 20px 70px rgba(0,0,0,.25);
    margin-bottom:22px;
}

.hero-title {
    font-size:42px;
    font-weight:800;
    letter-spacing:-1.8px;
    margin:0;
}

.hero-title span {
    color:var(--green2);
}

.hero-sub {
    color:var(--muted);
    margin-top:8px;
    font-size:15px;
}

.card {
    padding:22px;
    border-radius:18px;
    background:rgba(14,29,20,.78);
    border:1px solid var(--border);
    box-shadow:0 12px 40px rgba(0,0,0,.16);
    margin-bottom:16px;
}

.metric {
    padding:20px;
    border-radius:18px;
    background:linear-gradient(145deg,rgba(18,43,28,.9),rgba(9,22,15,.85));
    border:1px solid var(--border);
    min-height:125px;
}

.metric-label {
    color:var(--muted);
    font-size:12px;
    text-transform:uppercase;
    letter-spacing:1px;
}

.metric-value {
    color:var(--green2);
    font-size:32px;
    font-weight:800;
    margin-top:8px;
}

.badge {
    display:inline-block;
    padding:6px 10px;
    border-radius:999px;
    background:rgba(34,197,94,.11);
    border:1px solid rgba(34,197,94,.25);
    color:#86efac;
    font-size:11px;
    font-weight:700;
}

.small {
    color:var(--muted);
    font-size:12px;
}

.green {
    color:var(--green2);
}

.stButton > button {
    border-radius:12px!important;
    border:1px solid rgba(74,222,128,.25)!important;
    background:linear-gradient(135deg,#15803d,#16a34a)!important;
    color:white!important;
    font-weight:700!important;
    min-height:42px;
    transition:.2s ease;
}

.stButton > button:hover {
    transform:translateY(-1px);
    box-shadow:0 8px 28px rgba(34,197,94,.22);
}

.stTextInput input, .stTextArea textarea {
    background:#09150f!important;
    color:#eefaf2!important;
    border:1px solid rgba(74,222,128,.18)!important;
    border-radius:12px!important;
}

[data-testid="stFileUploader"] {
    background:#09150f;
    border:1px dashed rgba(74,222,128,.25);
    border-radius:14px;
    padding:10px;
}

div[data-baseweb="select"] > div {
    background:#09150f!important;
    border-color:rgba(74,222,128,.18)!important;
}

hr {
    border-color:rgba(74,222,128,.12)!important;
}

div[data-testid="stMetric"] {
    background:rgba(14,29,20,.78);
    border:1px solid var(--border);
    border-radius:16px;
    padding:14px;
}

table {
    color:#eefaf2!important;
}

.notice {
    padding:12px 15px;
    border-radius:12px;
    background:rgba(250,204,21,.08);
    border:1px solid rgba(250,204,21,.18);
    color:#fde68a;
    font-size:12px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# CONFIG / LLM
# -----------------------------
def secret(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, default)

HF_TOKEN = secret("HF_TOKEN")
HF_MODEL = secret("HF_MODEL", "deepseek-ai/DeepSeek-V3-0324")

# -----------------------------
# SESSION
# -----------------------------
if "role" not in st.session_state:
    st.session_state.role = "Candidate"
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "analyses" not in st.session_state:
    st.session_state.analyses = load_history(HISTORY_FILE)
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None
if "resume_data" not in st.session_state:
    st.session_state.resume_data = {}

# -----------------------------
# HELPERS
# -----------------------------
def page(title, subtitle=""):
    st.markdown(f"""
    <div class="hero">
        <div class="hero-title">{title}</div>
        <div class="hero-sub">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def metric(label, value, note=""):
    st.markdown(f"""
    <div class="metric">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="small">{note}</div>
    </div>
    """, unsafe_allow_html=True)

def score_class(score):
    if score >= 80:
        return "Strong Match"
    if score >= 65:
        return "Good Match"
    if score >= 50:
        return "Partial Match"
    return "Low Match"

def clean_json(text):
    if not text:
        return {}
    text = re.sub(r"```json|```", "", text, flags=re.I).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
    return {}

def fallback_resume(text):
    email = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    phone = re.search(r'(\+?\d[\d\s().-]{8,}\d)', text)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    name = lines[0][:80] if lines else "Unknown Candidate"
    skill_words = [
        "python","sql","java","javascript","react","streamlit","machine learning",
        "deep learning","artificial intelligence","generative ai","agentic ai",
        "n8n","pandas","numpy","power bi","excel","aws","azure","docker",
        "tensorflow","pytorch","scikit-learn","langchain","rag","prompt engineering"
    ]
    lower = text.lower()
    skills = [s.title() for s in skill_words if s in lower]
    return {
        "name": name,
        "email": email.group(0) if email else "",
        "phone": phone.group(0) if phone else "",
        "location": "",
        "skills": skills,
        "education": [],
        "certifications": [],
        "experience": [],
        "projects": [],
        "tools": skills,
        "summary": ""
    }

def extract_resume(uploaded):
    suffix = Path(uploaded.name).suffix.lower()
    data = uploaded.getvalue()
    if suffix == ".pdf":
        text = extract_pdf_text(io.BytesIO(data))
    elif suffix == ".docx":
        text = extract_docx_text(io.BytesIO(data))
    else:
        raise ValueError("Only PDF and DOCX files are supported.")
    if len(text.strip()) < 30:
        raise ValueError("The uploaded resume is empty or too short.")
    prompt = f"""
Extract structured resume information from the text below.
Return ONLY valid JSON with keys:
name,email,phone,location,skills,education,certifications,experience,projects,tools,summary.
Do not invent facts. If evidence is unavailable use empty strings/lists.

RESUME:
{text[:30000]}
"""
    result = clean_json(ask_llm(prompt, token=HF_TOKEN, model=HF_MODEL))
    if not result:
        result = fallback_resume(text)
    result["file_name"] = uploaded.name
    result["raw_text"] = text[:30000]
    return result

def analyze_candidate(resume, jd):
    prompt = f"""
You are an explainable resume screening assistant.
Compare the resume against the job description.
Never claim a skill is missing merely because it is not mentioned.
Use "Insufficient Evidence" when evidence is unclear.
Do not invent candidate facts.

Return ONLY JSON:
{{
 "match_score": 0,
 "skills_score": 0,
 "experience_score": 0,
 "education_score": 0,
 "jd_coverage_score": 0,
 "ats_score": 0,
 "classification": "Strong Match",
 "summary": "",
 "strengths": [],
 "gaps": [],
 "requirements": [
   {{"requirement":"","status":"Match|Gap|Insufficient Evidence","evidence":"","explanation":""}}
 ],
 "ats_issues": [],
 "ats_fixes": [],
 "keywords_to_add": [],
 "optimization": [
   {{"issue":"","exact_improvement":"","reason":""}}
 ],
 "recommendation": ""
}}

JOB DESCRIPTION:
{jd[:25000]}

RESUME:
{resume.get("raw_text","")[:30000]}
"""
    result = clean_json(ask_llm(prompt, token=HF_TOKEN, model=HF_MODEL))
    if result:
        return result

    jd_lower = jd.lower()
    skills = resume.get("skills", [])
    matched = [s for s in skills if s.lower() in jd_lower]
    score = min(95, 45 + len(matched) * 8)
    return {
        "match_score": score,
        "skills_score": min(100, 40 + len(matched)*10),
        "experience_score": 60,
        "education_score": 60,
        "jd_coverage_score": score,
        "ats_score": 65,
        "classification": score_class(score),
        "summary": "Heuristic analysis used because the configured LLM did not return structured JSON.",
        "strengths": matched[:8],
        "gaps": [],
        "requirements": [],
        "ats_issues": ["AI analysis fallback was used."],
        "ats_fixes": ["Configure a working Hugging Face model/API key for richer analysis."],
        "keywords_to_add": [],
        "optimization": [],
        "recommendation": "Human recruiter review required.",
    }

def interview_questions(resume, jd):
    prompt = f"""
Create interview preparation from ONLY the candidate resume and job description.
Return JSON:
{{
 "technical":[{{"question":"","answer":"","why":""}}],
 "project":[{{"question":"","answer":"","why":""}}],
 "hr":[{{"question":"","answer":"","why":""}}],
 "jd_specific":[{{"question":"","answer":"","why":""}}]
}}
Generate 5 questions per category. Never invent experience.
RESUME:
{resume.get("raw_text","")[:25000]}
JD:
{jd[:20000]}
"""
    result = clean_json(ask_llm(prompt, token=HF_TOKEN, model=HF_MODEL))
    if result:
        return result
    return {
        "technical":[{"question":"Explain your strongest technical skill.","answer":"Use a real example from your resume and explain the result.","why":"Tests technical depth."}],
        "project":[{"question":"Explain one project from your resume.","answer":"Describe the problem, your role, technology, implementation and result.","why":"Tests ownership."}],
        "hr":[{"question":"Tell me about yourself.","answer":"Give a concise summary of your education, skills, projects and career goal.","why":"Tests communication."}],
        "jd_specific":[{"question":"Why are you a good fit for this role?","answer":"Connect only your documented skills and experience to the JD.","why":"Tests role alignment."}],
    }

def save_current(item):
    st.session_state.current_analysis = item
    st.session_state.analyses = save_analysis(HISTORY_FILE, item)

def render_download_pdf(item, label="Download PDF Report"):
    pdf = build_analysis_pdf(item)
    st.download_button(
        label,
        data=pdf,
        file_name=f"TalentLens_{item.get('candidate', 'Candidate')}_Report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:12px 4px 22px">
        <div style="font-size:32px;color:#4ade80">◈</div>
        <div style="font-size:22px;font-weight:800">TalentLens AI</div>
        <div class="small" style="letter-spacing:2px">AI RECRUITMENT INTELLIGENCE</div>
    </div>
    """, unsafe_allow_html=True)

    role = st.radio("ACCESS", ["Candidate", "Recruiter"], index=0 if st.session_state.role=="Candidate" else 1)
    if role != st.session_state.role:
        st.session_state.role = role
        st.session_state.page = "Dashboard"
        st.rerun()

    candidate_pages = [
        "Dashboard","Resume Creator","Resume Analyzer","Resume Optimization",
        "Interview Q&A","Skill Gap","My Resumes","Analysis History","Settings"
    ]
    recruiter_pages = [
        "Dashboard","Analyze Resumes","Candidates","Candidate Ranking",
        "ATS Analysis","Reports","Analysis History","Settings"
    ]
    pages = candidate_pages if role == "Candidate" else recruiter_pages

    st.markdown("### PAGES")
    for p in pages:
        if st.button(p, key=f"nav_{role}_{p}", use_container_width=True):
            st.session_state.page = p
            st.rerun()

    st.markdown("---")
    connected = bool(HF_TOKEN)
    st.markdown(
        f'<span class="badge">{"● Hugging Face Connected" if connected else "● Local Fallback Mode"}</span>'
        f'<div class="small" style="margin-top:10px">MODEL<br>{HF_MODEL}</div>',
        unsafe_allow_html=True
    )

# -----------------------------
# DASHBOARD
# -----------------------------
def dashboard():
    page("AI Recruitment <span>Command Center</span>", "Explainable resume intelligence for recruiters and candidates.")
    hist = st.session_state.analyses
    total = len(hist)
    scores = [int(x.get("match_score",0)) for x in hist if str(x.get("match_score","")).isdigit()]
    avg = round(sum(scores)/len(scores)) if scores else 0
    strong = sum(1 for s in scores if s >= 80)

    c1,c2,c3,c4 = st.columns(4)
    with c1: metric("Analyses", total, "Saved in history")
    with c2: metric("Average Match", f"{avg}%", "Across saved analyses")
    with c3: metric("Strong Matches", strong, "80%+ match")
    with c4: metric("Access", role, "Current workspace")

    st.markdown("### Recent Activity")
    if not hist:
        st.markdown('<div class="card"><b>No analyses yet.</b><br><span class="small">Start from Resume Analyzer or Analyze Resumes.</span></div>', unsafe_allow_html=True)
    else:
        rows = []
        for x in hist[:8]:
            rows.append({
                "Candidate": x.get("candidate","Unknown"),
                "Match": f'{x.get("match_score",0)}%',
                "ATS": f'{x.get("ats_score",0)}%',
                "Classification": x.get("classification",""),
                "Date": x.get("date",""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# -----------------------------
# RESUME CREATOR
# -----------------------------
def resume_creator():
    page("Resume <span>Creator</span>", "Build a professional ATS-friendly resume and export it as PDF or DOCX.")
    with st.form("resume_creator_form"):
        c1,c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            location = st.text_input("Location")
            headline = st.text_input("Professional Headline")
        with c2:
            skills = st.text_area("Skills", placeholder="Python, AI, Machine Learning, SQL...")
            education = st.text_area("Education")
            experience = st.text_area("Experience")
            projects = st.text_area("Projects")
            certifications = st.text_area("Certifications")
        summary = st.text_area("Professional Summary")
        submitted = st.form_submit_button("Create Resume", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Please enter your name.")
            return
        resume = {
            "name":name,"email":email,"phone":phone,"location":location,
            "headline":headline,"skills":[x.strip() for x in skills.split(",") if x.strip()],
            "education":education,"experience":experience,"projects":projects,
            "certifications":certifications,"summary":summary
        }
        st.session_state.resume_data = resume
        st.success("Resume created successfully.")

    if st.session_state.resume_data:
        r = st.session_state.resume_data
        st.markdown("### Preview")
        st.markdown(f"""
        <div class="card">
        <h2>{r.get("name","")}</h2>
        <div class="green">{r.get("headline","")}</div>
        <div class="small">{r.get("email","")} · {r.get("phone","")} · {r.get("location","")}</div>
        <hr>
        <b>SUMMARY</b><p>{r.get("summary","")}</p>
        <b>SKILLS</b><p>{", ".join(r.get("skills",[]))}</p>
        <b>EDUCATION</b><p>{r.get("education","")}</p>
        <b>EXPERIENCE</b><p>{r.get("experience","")}</p>
        <b>PROJECTS</b><p>{r.get("projects","")}</p>
        <b>CERTIFICATIONS</b><p>{r.get("certifications","")}</p>
        </div>
        """, unsafe_allow_html=True)
        a,b = st.columns(2)
        with a:
            st.download_button("Download DOCX", build_resume_docx(r), f"{r['name']}_Resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        with b:
            st.download_button("Download PDF", build_resume_pdf(r), f"{r['name']}_Resume.pdf", "application/pdf", use_container_width=True)

# -----------------------------
# CANDIDATE ANALYZER
# -----------------------------
def candidate_analyzer(recruiter=False):
    title = "Analyze <span>Resumes</span>" if recruiter else "Resume <span>Analyzer</span>"
    subtitle = "Upload PDF/DOCX resumes and compare them against a job description."
    page(title, subtitle)

    uploads = st.file_uploader(
        "Upload Resume(s)",
        type=["pdf","docx"],
        accept_multiple_files=recruiter,
        key="resume_uploads"
    )
    jd = st.text_area("Job Description", height=220, placeholder="Paste the job description here...")

    if st.button("Analyze Resume" if not recruiter else "Analyze Candidates", use_container_width=True):
        if not uploads:
            st.error("Please upload at least one resume.")
            return
        if not jd.strip():
            st.error("Please enter a job description.")
            return

        uploads = uploads if isinstance(uploads,list) else [uploads]
        progress = st.progress(0)
        results = []
        for i, up in enumerate(uploads):
            try:
                resume = extract_resume(up)
                analysis = analyze_candidate(resume, jd)
                item = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                    "candidate": resume.get("name") or Path(up.name).stem,
                    "file_name": up.name,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "jd": jd,
                    "resume": resume,
                    **analysis,
                }
                results.append(item)
            except Exception as e:
                st.error(f"{up.name}: {e}")
            progress.progress((i+1)/len(uploads))

        if results:
            for item in results:
                save_current(item)
            st.session_state.current_analysis = results[0]
            st.success(f"Completed {len(results)} analysis/analyses.")
            st.rerun()

# -----------------------------
# ANALYSIS VIEW
# -----------------------------
def analysis_view(item):
    if not item:
        st.info("No analysis selected.")
        return
    page(f'{item.get("candidate","Candidate")} <span>Analysis</span>', "Explainable AI analysis with human-review safeguards.")

    scores = [
        ("Match",item.get("match_score",0)),
        ("Skills",item.get("skills_score",0)),
        ("Experience",item.get("experience_score",0)),
        ("Education",item.get("education_score",0)),
        ("JD Coverage",item.get("jd_coverage_score",0)),
        ("ATS",item.get("ats_score",0)),
    ]
    cols = st.columns(6)
    for col,(label,val) in zip(cols,scores):
        with col: metric(label,f"{val}%")
    st.markdown(f'<span class="badge">{item.get("classification","")}</span>', unsafe_allow_html=True)
    st.markdown("### Executive Summary")
    st.markdown(f'<div class="card">{item.get("summary","")}</div>', unsafe_allow_html=True)

    a,b = st.columns(2)
    with a:
        st.markdown("### Strengths")
        for x in item.get("strengths",[]): st.success(x)
    with b:
        st.markdown("### Gaps / Review Areas")
        for x in item.get("gaps",[]): st.warning(x)

    st.markdown("### Requirement-by-Requirement Evidence")
    reqs = item.get("requirements",[])
    if reqs:
        rows = []
        for r in reqs:
            rows.append({
                "Requirement":r.get("requirement",""),
                "Status":r.get("status",""),
                "Evidence":r.get("evidence",""),
                "Explanation":r.get("explanation","")
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No structured requirement list returned.")

    st.markdown("### ATS Issues & Fixes")
    for x in item.get("ats_issues",[]): st.warning(x)
    for x in item.get("ats_fixes",[]): st.success(x)

    st.markdown("### Optimization Suggestions")
    for x in item.get("optimization",[]):
        st.markdown(f"""
        <div class="card">
        <b>Issue:</b> {x.get("issue","")}<br>
        <b class="green">Exact Improvement:</b> {x.get("exact_improvement","")}<br>
        <b>Reason:</b> {x.get("reason","")}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Recommendation")
    st.markdown(f'<div class="card"><b>{item.get("recommendation","")}</b></div>', unsafe_allow_html=True)
    st.markdown('<div class="notice">AI-generated recommendation only. Final hiring decisions must be made by a human recruiter.</div>', unsafe_allow_html=True)
    render_download_pdf(item)

# -----------------------------
# RECRUITER PAGES
# -----------------------------
def candidates_page():
    page("Candidate <span>Pool</span>", "Review and compare analyzed candidates.")
    hist = st.session_state.analyses
    if not hist:
        st.info("No candidates analyzed yet.")
        return
    rows = [{
        "Candidate":x.get("candidate"),
        "Match":x.get("match_score",0),
        "ATS":x.get("ats_score",0),
        "Classification":x.get("classification"),
        "Date":x.get("date")
    } for x in hist]
    df = pd.DataFrame(rows).sort_values("Match",ascending=False)
    st.dataframe(df,use_container_width=True,hide_index=True)
    for x in hist[:10]:
        with st.expander(f'{x.get("candidate")} — {x.get("match_score",0)}%'):
            if st.button("Open Analysis", key=f"open_{x.get('id')}"):
                st.session_state.current_analysis = x
                st.session_state.page = "Analysis Detail"
                st.rerun()

def ranking_page():
    page("Candidate <span>Ranking</span>", "Rank candidates by explainable match score.")
    hist = sorted(st.session_state.analyses,key=lambda x:int(x.get("match_score",0)),reverse=True)
    if not hist:
        st.info("Analyze multiple resumes first.")
        return
    rows=[]
    for i,x in enumerate(hist,1):
        rows.append({"Rank":i,"Candidate":x.get("candidate"),"Match":x.get("match_score",0),"ATS":x.get("ats_score",0),"Recommendation":x.get("classification")})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    pdf = build_ranking_pdf(hist)
    st.download_button("Download Ranking PDF",pdf,"TalentLens_Candidate_Ranking.pdf","application/pdf",use_container_width=True)

def reports_page():
    page("Recruiter <span>Reports</span>", "Download professional PDF reports.")
    hist=st.session_state.analyses
    if not hist:
        st.info("No reports available.")
        return
    for x in hist[:10]:
        c1,c2=st.columns([4,1])
        with c1:
            st.markdown(f"**{x.get('candidate')}** — {x.get('match_score',0)}% — {x.get('date')}")
        with c2:
            render_download_pdf(x,f"PDF · {x.get('candidate')}")

def ats_page():
    page("ATS <span>Analysis</span>", "Review ATS readiness across saved resumes.")
    hist=st.session_state.analyses
    if not hist:
        st.info("No ATS analyses yet.")
        return
    rows=[{"Candidate":x.get("candidate"),"ATS Score":x.get("ats_score",0),"Issues":"; ".join(x.get("ats_issues",[])[:3])} for x in hist]
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    selected=st.selectbox("Select candidate",[x.get("candidate") for x in hist])
    item=next(x for x in hist if x.get("candidate")==selected)
    metric("ATS Score",f'{item.get("ats_score",0)}%',"Resume quality and keyword readiness")
    for issue in item.get("ats_issues",[]): st.warning(issue)
    for fix in item.get("ats_fixes",[]): st.success(fix)

# -----------------------------
# CANDIDATE FEATURES
# -----------------------------
def optimization_page():
    item=st.session_state.current_analysis
    page("Resume <span>Optimization</span>","Improve the resume without fabricating experience.")
    if not item:
        st.info("Analyze a resume first.")
        return
    for x in item.get("optimization",[]):
        st.markdown(f"""
        <div class="card">
        <b>Issue</b><br>{x.get("issue","")}<br><br>
        <b class="green">Exact Improvement</b><br>{x.get("exact_improvement","")}<br><br>
        <b>Reason</b><br>{x.get("reason","")}
        </div>
        """,unsafe_allow_html=True)
    st.markdown("### Keywords to Consider")
    st.write(", ".join(item.get("keywords_to_add",[])) or "No additional keywords returned.")

def interview_page():
    item=st.session_state.current_analysis
    page("Interview <span>Q&A</span>","Practice questions generated from your resume and target role.")
    if not item:
        st.info("Analyze a resume first.")
        return
    if st.button("Generate Interview Questions",use_container_width=True):
        with st.spinner("Generating interview preparation..."):
            data=interview_questions(item.get("resume",{}),item.get("jd",""))
        st.session_state["interview_data"]=data
    data=st.session_state.get("interview_data")
    if not data: return
    tabs=st.tabs(["Technical","Projects","HR","JD Specific"])
    for tab,key in zip(tabs,["technical","project","hr","jd_specific"]):
        with tab:
            for q in data.get(key,[]):
                st.markdown(f"""
                <div class="card">
                <b>{q.get("question","")}</b><br><br>
                <span class="green">Suggested Answer</span><br>{q.get("answer","")}<br><br>
                <span class="small">Why asked: {q.get("why","")}</span>
                </div>
                """,unsafe_allow_html=True)

def skill_gap_page():
    item=st.session_state.current_analysis
    page("Skill <span>Gap Roadmap</span>","Prioritize genuine skill gaps based on evidence.")
    if not item:
        st.info("Analyze a resume first.")
        return
    gaps=item.get("gaps",[])
    if not gaps:
        st.success("No explicit skill gaps were returned.")
    for i,g in enumerate(gaps,1):
        st.markdown(f'<div class="card"><b>{i}. {g}</b><br><span class="small">Validate this gap against the JD before acting.</span></div>',unsafe_allow_html=True)

def history_page():
    page("Analysis <span>History</span>","Review, reopen, download or delete previous analyses.")
    hist=st.session_state.analyses
    if not hist:
        st.info("History is empty.")
        return
    for x in hist:
        c1,c2,c3=st.columns([5,1,1])
        with c1:
            st.markdown(f"**{x.get('candidate')}** · {x.get('match_score',0)}% · {x.get('date')}")
        with c2:
            if st.button("Open",key=f"hopen{x.get('id')}"):
                st.session_state.current_analysis=x
                st.session_state.page="Analysis Detail"
                st.rerun()
        with c3:
            if st.button("Delete",key=f"hdel{x.get('id')}"):
                st.session_state.analyses=delete_analysis(HISTORY_FILE,x.get("id"))
                st.rerun()

def my_resumes():
    page("My <span>Resumes</span>","Create and manage your resume workspace.")
    r=st.session_state.resume_data
    if r:
        st.success(f"Current resume: {r.get('name')}")
        if st.button("Open Resume Creator"):
            st.session_state.page="Resume Creator"; st.rerun()
    else:
        st.info("No resume created in this session.")
        if st.button("Create Resume"):
            st.session_state.page="Resume Creator"; st.rerun()

def settings_page():
    page("Workspace <span>Settings</span>","Configuration and safety information.")
    metric("Role",role,"Current access mode")
    metric("Model",HF_MODEL,"Configured model")
    st.markdown("### AI Policy")
    st.markdown('<div class="notice">TalentLens AI provides advisory analysis. It does not make autonomous hiring decisions and must not be used as the sole basis for employment decisions.</div>',unsafe_allow_html=True)

# -----------------------------
# ROUTER
# -----------------------------
p=st.session_state.page

if p=="Dashboard":
    dashboard()
elif p=="Resume Creator":
    resume_creator()
elif p=="Resume Analyzer":
    candidate_analyzer(False)
elif p=="Analyze Resumes":
    candidate_analyzer(True)
elif p=="Candidates":
    candidates_page()
elif p=="Candidate Ranking":
    ranking_page()
elif p=="ATS Analysis":
    ats_page()
elif p=="Reports":
    reports_page()
elif p=="Resume Optimization":
    optimization_page()
elif p=="Interview Q&A":
    interview_page()
elif p=="Skill Gap":
    skill_gap_page()
elif p=="Analysis History":
    history_page()
elif p=="My Resumes":
    my_resumes()
elif p=="Analysis Detail":
    analysis_view(st.session_state.current_analysis)
elif p=="Settings":
    settings_page()
else:
    dashboard()
