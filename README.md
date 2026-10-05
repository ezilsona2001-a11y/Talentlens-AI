# TalentLens AI

Green-themed AI recruitment intelligence platform built with Streamlit.

## Features

- Recruiter and Candidate access modes
- PDF/DOCX resume parsing
- Explainable resume/JD matching
- ATS analysis
- Candidate ranking
- PDF recruiter reports
- Resume creator
- Resume PDF/DOCX export
- Interview questions and suggested answers
- Analysis history
- Resume optimization
- Skill gap view
- Hugging Face LLM with fallback mode

## Windows setup

```powershell
cd TalentLens_AI
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` from `.env.example` and add your Hugging Face token.

Run:

```powershell
streamlit run app.py
```

If PowerShell blocks activation, use:

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m streamlit run app.py
```

For Streamlit Cloud, put `HF_TOKEN` and `HF_MODEL` in App Settings > Secrets.

The app is advisory only. Final employment decisions must be made by a human recruiter.
