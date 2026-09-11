import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_monthly_pdf_report(month_str: str, station_stats: list, judge_score_avg: float = None):
    """
    Generate a PDF report for the given month.
    station_stats: list of dicts with keys:
        'station_name', 'total_measurements', 'anomaly_count', 'anomaly_rate'
    judge_score_avg: float or None
    Returns: PDF bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)

    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']

    elements = []

    # 1. Header
    elements.append(Paragraph("Su-AI Monthly Anomaly Report", title_style))
    elements.append(Paragraph(f"Report Period: {month_str}", normal_style))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated At: {generated_at}", normal_style))
    elements.append(Spacer(1, 20))

    # 2. Station Summary Table
    elements.append(Paragraph("Station Summary", subtitle_style))

    table_data = [["Station Name", "Total Measurements", "Anomaly Count", "Anomaly Rate (%)"]]
    for stat in station_stats:
        table_data.append([
            stat['station_name'],
            str(stat['total_measurements']),
            str(stat['anomaly_count']),
            f"{stat['anomaly_rate']:.1f}%"
        ])

    if len(table_data) > 1:
        t = Table(table_data, colWidths=[150, 120, 100, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No measurements found for this period.", normal_style))
    elements.append(Spacer(1, 20))

    # 3. Worst Performing Stations (Top 5 by anomaly rate)
    elements.append(Paragraph("Worst Performing Stations (Top 5)", subtitle_style))
    sorted_stats = sorted([s for s in station_stats if s['anomaly_rate'] > 0], key=lambda x: x['anomaly_rate'], reverse=True)[:5]
    if sorted_stats:
        worst_data = [["Station Name", "Anomaly Rate (%)"]]
        for stat in sorted_stats:
            worst_data.append([stat['station_name'], f"{stat['anomaly_rate']:.1f}%"])

        t2 = Table(worst_data, colWidths=[150, 120])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkred),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        elements.append(t2)
    else:
        elements.append(Paragraph("No anomalies detected for this period.", normal_style))
    elements.append(Spacer(1, 20))

    # 4. LLM Judge Score Trend
    elements.append(Paragraph("LLM Judge Score Trend", subtitle_style))
    if judge_score_avg is not None:
        elements.append(Paragraph(f"Average LLM Judge Score for {month_str}: {judge_score_avg:.1f} / 100", normal_style))
    else:
        elements.append(Paragraph("No judge scores recorded for this period. (Pending judge-score tracking)", normal_style))

    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
