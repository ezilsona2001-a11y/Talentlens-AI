import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

GREEN = colors.HexColor("#16a34a")
DARK = colors.HexColor("#0b1710")
LIGHT = colors.HexColor("#ecfdf5")

def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="TitleGreen", parent=s["Title"], textColor=GREEN, fontSize=24, leading=28))
    s.add(ParagraphStyle(name="HeadingGreen", parent=s["Heading2"], textColor=GREEN, fontSize=15, spaceBefore=12, spaceAfter=7))
    s.add(ParagraphStyle(name="BodySmall", parent=s["BodyText"], fontSize=9, leading=13))
    return s

def safe(x):
    return str(x or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def build_analysis_pdf(item):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
    s=styles()
    story=[
        Paragraph("TalentLens AI",s["TitleGreen"]),
        Paragraph("AI Resume Intelligence Report",s["HeadingGreen"]),
        Paragraph(safe(item.get("candidate","Candidate")),s["Title"]),
        Spacer(1,8),
    ]
    score_data=[
        ["Metric","Score"],
        ["Match Score",f'{item.get("match_score",0)}%'],
        ["Skills",f'{item.get("skills_score",0)}%'],
        ["Experience",f'{item.get("experience_score",0)}%'],
        ["Education",f'{item.get("education_score",0)}%'],
        ["JD Coverage",f'{item.get("jd_coverage_score",0)}%'],
        ["ATS",f'{item.get("ats_score",0)}%'],
    ]
    t=Table(score_data,colWidths=[260,100])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GREEN),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BACKGROUND",(0,1),(-1,-1),LIGHT),
        ("GRID",(0,0),(-1,-1),.4,colors.grey),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("PADDING",(0,0),(-1,-1),7),
    ]))
    story += [t,Spacer(1,14),Paragraph("Executive Summary",s["HeadingGreen"]),Paragraph(safe(item.get("summary","")),s["BodyText"])]
    story += [Paragraph("Strengths",s["HeadingGreen"])]
    for x in item.get("strengths",[]): story.append(Paragraph("• "+safe(x),s["BodySmall"]))
    story += [Paragraph("Gaps / Review Areas",s["HeadingGreen"])]
    for x in item.get("gaps",[]): story.append(Paragraph("• "+safe(x),s["BodySmall"]))
    story += [Paragraph("Requirements",s["HeadingGreen"])]
    reqs=[["Requirement","Status","Evidence"]]
    for r in item.get("requirements",[]):
        reqs.append([safe(r.get("requirement")),safe(r.get("status")),safe(r.get("evidence"))])
    if len(reqs)>1:
        rt=Table(reqs,colWidths=[150,100,210],repeatRows=1)
        rt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),GREEN),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),.35,colors.grey),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("FONTSIZE",(0,0),(-1,-1),8),
            ("PADDING",(0,0),(-1,-1),5),
        ]))
        story += [rt]
    story += [Spacer(1,12),Paragraph("Recommendation",s["HeadingGreen"]),Paragraph(safe(item.get("recommendation","")),s["BodyText"])]
    story += [Spacer(1,18),Paragraph("AI-generated recommendation only. Final hiring decisions must be made by a human recruiter.",s["BodySmall"])]
    doc.build(story)
    return buffer.getvalue()

def build_ranking_pdf(items):
    buffer=io.BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=30,leftMargin=30,topMargin=30,bottomMargin=30)
    s=styles()
    data=[["Rank","Candidate","Match","ATS","Classification"]]
    for i,x in enumerate(sorted(items,key=lambda a:int(a.get("match_score",0)),reverse=True),1):
        data.append([i,safe(x.get("candidate")),f'{x.get("match_score",0)}%',f'{x.get("ats_score",0)}%',safe(x.get("classification"))])
    t=Table(data,colWidths=[45,170,65,55,140],repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),GREEN),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),.35,colors.grey),
        ("PADDING",(0,0),(-1,-1),6),
        ("FONTSIZE",(0,0),(-1,-1),8),
    ]))
    doc.build([Paragraph("TalentLens AI — Candidate Ranking",s["TitleGreen"]),Spacer(1,12),t])
    return buffer.getvalue()
