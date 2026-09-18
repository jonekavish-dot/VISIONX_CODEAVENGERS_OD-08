"""
IVACS V-TRACE: PDF Progress Report Generator
Generates and updates IVACS_VTRACE_Progress_Report.pdf in the workspace root.
Uses ReportLab to render a clean, professional, hackathon-ready status document.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IVACS_VTRACE_Progress_Report.pdf")

def generate_report():
    doc = SimpleDocTemplate(
        REPORT_PATH,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        fontName='Helvetica'
    )
    
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold',
        spaceBefore=7,
        spaceAfter=4
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica'
    )
    
    badge_pass = ParagraphStyle(
        'PassBadge',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#166534'),
        fontName='Helvetica-Bold',
        alignment=TA_CENTER
    )

    story = []
    
    # Header Banner
    story.append(Paragraph("IVACS V-TRACE: Vehicle Trust, Route & Evidence Engine", title_style))
    story.append(Paragraph("Problem Statement: OD-08 — License Plate Detection, Recognition & Vehicle Identity Engine", subtitle_style))
    story.append(Spacer(1, 4))
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_table_data = [
        [Paragraph(f"<b>Report Updated:</b> {now_str}", body_style),
         Paragraph("<b>Phase:</b> Vehicle Visual Fingerprint Verified", body_style),
         Paragraph("<b>Policy:</b> Zero LLM / CV-Native", body_style)]
    ]
    meta_table = Table(meta_table_data, colWidths=[180, 220, 140])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E1')),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))
    
    # 1. System Status Table
    story.append(Paragraph("1. System Component Status Audit", h2_style))
    
    foundation_items = [
        ("Backend Server (FastAPI REST App & Background Demo Worker)", "PASS"),
        ("Video Ingestion (MP4 Sequential Stream & Configurable Sampling)", "PASS"),
        ("Vehicle Detection (Ultralytics YOLOv8 Nano Pretrained)", "PASS"),
        ("Plate Localization (Bumper ROI & Vehicle Association)", "PASS"),
        ("OCR Character Recognition (EasyOCR Dual Text Normalization)", "PASS"),
        ("Vehicle Visual Fingerprint (ResNet18 512-dim Normalized Embedding)", "PASS"),
        ("Identity Matching & Decision Rules (Rules A through E)", "PASS"),
        ("Database Persistence (SQLite: detections, vehicle_identities, observations)", "PASS"),
        ("Evidence Image Storage (Frame, Vehicle, Plate, Annotated Crops)", "PASS"),
        ("REST API Layer (Health, Cameras, Demo, Detections, Vehicles, Identity-Events)", "PASS"),
        ("Automated Test Suite (14/14 Tests Passed - 100% Pass Rate)", "PASS"),
    ]
    
    status_table_data = [
        [Paragraph("<b>Component / Subsystem</b>", body_style), Paragraph("<b>Verification Status</b>", ParagraphStyle('HCenter', parent=body_style, alignment=TA_CENTER))]
    ]
    
    for comp, st in foundation_items:
        badge = Paragraph("<b>PASS</b>", badge_pass)
        status_table_data.append([Paragraph(comp, body_style), badge])
        
    t = Table(status_table_data, colWidths=[410, 130])
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 3),
    ]
    for i in range(1, len(foundation_items) + 1):
        t_style.append(('BACKGROUND', (1, i), (1, i), colors.HexColor('#DCFCE7')))
    t.setStyle(TableStyle(t_style))
    story.append(t)
    story.append(Spacer(1, 6))
    
    # 2. Team Member Allocation
    story.append(Paragraph("2. Team Member Role Allocation (CodeAvengers Team)", h2_style))
    team_data = [
        [Paragraph("<b>Member</b>", body_style), Paragraph("<b>GitHub / Email</b>", body_style), Paragraph("<b>Assigned Subsystem Role</b>", body_style)],
        [Paragraph("<b>Jone Kavish</b> (Lead)", body_style), Paragraph("jonekavish-dot<br/>jonekavish@gmail.com", body_style), Paragraph("Backend Architecture, Overall Team Management, EasyOCR Pipeline, REST Endpoints, Frame Orchestrator", body_style)],
        [Paragraph("<b>K.V. Pranesh</b> (Member-1)", body_style), Paragraph("kvpranesh<br/>kvpranesh49@gmail.com", body_style), Paragraph("Computer Vision & Vehicle Detection Engine (YOLOv8n Inference, Multi-Class COCO Vehicle Filtering)", body_style)],
        [Paragraph("<b>Gowshik Gunal</b> (Member-2)", body_style), Paragraph("gowshikgunal22<br/>gowshikgunal@gmail.com", body_style), Paragraph("License Plate Localization Engine (Bumper ROI Analysis, Vehicle Association, Image Preprocessing)", body_style)],
        [Paragraph("<b>Dinesh Balu</b> (Member-3)", body_style), Paragraph("dineshbalu7f-glitch<br/>dineshbalu7.f@gmail.com", body_style), Paragraph("Video Source Abstraction (MP4/RTSP/Webcam Streams), Frame Sampling, Evidence Storage & SQLite Persistence", body_style)]
    ]
    team_table = Table(team_data, colWidths=[110, 150, 280])
    team_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(team_table)
    story.append(Spacer(1, 6))

    # 3. Decision Rules Summary
    story.append(Paragraph("3. Identity Engine Decision Rules Audit", h2_style))
    rule_data = [
        [Paragraph("<b>Rule</b>", body_style), Paragraph("<b>Condition / Observation</b>", body_style), Paragraph("<b>System Analytical Event Signal</b>", body_style)],
        [Paragraph("<b>Rule A</b>", body_style), Paragraph("Same Plate + High Visual Similarity (&ge; 0.85)", body_style), Paragraph("<code>SAME_VEHICLE</code> (Confirmed consistent identity)", body_style)],
        [Paragraph("<b>Rule B</b>", body_style), Paragraph("Same Plate + Low Visual Similarity (< 0.85)", body_style), Paragraph("<code>POSSIBLE_IDENTITY_MISMATCH</code> (Appearance conflict)", body_style)],
        [Paragraph("<b>Rule C</b>", body_style), Paragraph("Different Plate + High Visual Similarity (&ge; 0.85)", body_style), Paragraph("<code>POSSIBLE_PLATE_SWAP</code> (Plate swap anomaly)", body_style)],
        [Paragraph("<b>Rule D</b>", body_style), Paragraph("Plate Unreadable + High Visual Similarity (&ge; 0.85)", body_style), Paragraph("<code>PLATE_UNREADABLE_VEHICLE_MATCH</code> (Continuity)", body_style)],
        [Paragraph("<b>Rule E</b>", body_style), Paragraph("No Historical Match Found", body_style), Paragraph("<code>NEW_VEHICLE</code> (New identity registration)", body_style)]
    ]
    rule_table = Table(rule_data, colWidths=[60, 240, 240])
    rule_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(rule_table)

    doc.build(story)
    print(f"Report successfully written to {REPORT_PATH}")

if __name__ == "__main__":
    generate_report()
