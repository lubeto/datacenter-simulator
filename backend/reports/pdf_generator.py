"""
DC Monitoring Simulator - Generador de Reportes PDF
Usa ReportLab para generar reportes profesionales
"""
import os
from datetime import datetime
from typing import List, Dict, Any
from ..utils_time import iso_utc

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False


# Colores del tema
COLOR_PRIMARY   = colors.HexColor("#1d4ed8")
COLOR_DARK      = colors.HexColor("#0f172a")
COLOR_GRAY      = colors.HexColor("#64748b")
COLOR_RED       = colors.HexColor("#dc2626")
COLOR_YELLOW    = colors.HexColor("#ca8a04")
COLOR_GREEN     = colors.HexColor("#16a34a")
COLOR_BG        = colors.HexColor("#f8fafc")
COLOR_WHITE     = colors.white


ATTACK_LABELS = {
    "ddos":"DDoS","dos":"DoS","brute_force":"Fuerza Bruta","port_scan":"Escaneo de Puertos",
    "memory_leak":"Memory Leak","disk_failure":"Disk Failure","thermal":"Falla Termica",
    "unauthorized_access":"Acceso No Autorizado","ssl_expiring":"SSL por Vencer",
    "ssl_expired":"SSL Expirado","ssl_tls_downgrade":"TLS Downgrade",
}

def generate_pdf_report(report_type: str, title: str,
                         data: List[Dict[str, Any]],
                         output_path: str) -> bool:
    """Genera un PDF y lo guarda en output_path. Retorna True si tuvo éxito."""
    if not REPORTLAB_OK:
        # Fallback: generar un TXT simple si ReportLab no está disponible
        return _generate_txt_fallback(title, data, output_path.replace(".pdf", ".txt"))

    try:
        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )
        styles = getSampleStyleSheet()
        story = []

        # ── Encabezado ──────────────────────────────────────
        story.append(_header(title, report_type))
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARY))
        story.append(Spacer(1, 0.3*cm))

        # Metadata
        meta_data = [
            ["Tipo de Reporte", report_type.upper().replace("_", " ")],
            ["Generado",        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
            ["Total Registros", str(len(data))],
            ["Sistema",         "DC Monitoring Simulator v1.0"],
        ]
        story.append(_info_table(meta_data))
        story.append(Spacer(1, 0.5*cm))

        # ── Contenido según tipo ─────────────────────────────
        if report_type == "incident":
            story.extend(_build_incident_section(data))
        elif report_type == "health":
            story.extend(_build_health_section(data))
        elif report_type == "ssl":
            story.extend(_build_ssl_section(data))
        elif report_type == "sst":
            story.extend(_build_sst_section(data))
        elif report_type == "student_shift":
            story.extend(_build_student_section(data))
        elif report_type == "full_summary":
            story.extend(_build_full_summary_section(data))
        else:
            story.extend(_build_generic_section(data))

        # ── Pie de página ────────────────────────────────────
        story.append(Spacer(1, 1*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=COLOR_GRAY))
        story.append(Spacer(1, 0.2*cm))
        footer_style = ParagraphStyle("footer", fontSize=8, textColor=COLOR_GRAY, alignment=TA_CENTER)
        story.append(Paragraph(
            "DC Monitoring Simulator · Reporte generado automáticamente · Confidencial",
            footer_style
        ))

        doc.build(story)
        return True

    except Exception as e:
        print(f"Error generando PDF: {e}")
        return _generate_txt_fallback(title, data, output_path.replace(".pdf", ".txt"))


def _header(title: str, rtype: str) -> Table:
    TYPE_ICONS = {
        "incident":     "🚨 REPORTE DE INCIDENTES",
        "health":       "📊 REPORTE DE SALUD DEL DC",
        "ssl":          "🔐 REPORTE SSL/TLS",
        "sst":          "🌡️ REPORTE SST",
        "student_shift":"🎓 EVALUACIÓN DE TURNO",
    }
    label = TYPE_ICONS.get(rtype, f"📋 {rtype.upper()}")
    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle("t1", fontSize=18, fontName="Helvetica-Bold",
                                   textColor=COLOR_WHITE, spaceAfter=4)
    label_style  = ParagraphStyle("t2", fontSize=10, fontName="Helvetica",
                                   textColor=colors.HexColor("#bfdbfe"))
    tbl = Table([[
        Paragraph(title, title_style),
        Paragraph(label, label_style),
    ]], colWidths=["65%", "35%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARY),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING",(0,0), (-1,-1), 14),
        ("TOPPADDING",  (0,0), (-1,-1), 14),
        ("BOTTOMPADDING",(0,0),(-1,-1), 14),
        ("ROUNDEDCORNERS", [6]),
    ]))
    return tbl


def _info_table(rows: List[List[str]]) -> Table:
    styles = getSampleStyleSheet()
    k_style = ParagraphStyle("k", fontSize=9, fontName="Helvetica-Bold", textColor=COLOR_GRAY)
    v_style = ParagraphStyle("v", fontSize=9, fontName="Helvetica", textColor=COLOR_DARK)
    table_data = [[Paragraph(r[0], k_style), Paragraph(r[1], v_style)] for r in rows]
    tbl = Table(table_data, colWidths=["30%", "70%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), COLOR_BG),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING",(0,0),(-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("TOPPADDING", (0,0),(-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1), 5),
    ]))
    return tbl


def _section_title(text: str):
    style = ParagraphStyle("sec", fontSize=12, fontName="Helvetica-Bold",
                            textColor=COLOR_PRIMARY, spaceBefore=12, spaceAfter=6)
    return Paragraph(text, style)


def _severity_color(severity: str):
    return {"critical": COLOR_RED, "warning": COLOR_YELLOW,
            "info": COLOR_GREEN, "normal": COLOR_GREEN}.get(severity, COLOR_GRAY)


def _build_incident_section(data: List[Dict]) -> list:
    story = [_section_title("📋 Registro de Incidentes")]
    if not data:
        story.append(Paragraph("No hay incidentes registrados.", getSampleStyleSheet()["Normal"]))
        return story

    headers = ["ID", "Tipo", "Nodo", "Severidad", "Inicio", "MTTD (s)", "MTTR (s)", "Estado"]
    rows = [headers]
    for d in data:
        rows.append([
            str(d.get("id", "")),
            str(d.get("type", ""))[:20],
            str(d.get("node", "")),
            str(d.get("severity", "")).upper(),
            str(d.get("started", ""))[:16],
            f"{d.get('mttd_sec') or 0:.1f}",
            f"{d.get('mttr_sec') or 0:.1f}",
            str(d.get("status", "")),
        ])

    tbl = Table(rows, repeatRows=1,
                colWidths=["5%","18%","12%","10%","18%","10%","10%","10%"])
    style = [
        ("BACKGROUND",  (0,0), (-1,0), COLOR_PRIMARY),
        ("TEXTCOLOR",   (0,0), (-1,0), COLOR_WHITE),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [COLOR_WHITE, COLOR_BG]),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING",(0,0), (-1,-1), 4),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]
    for i, d in enumerate(data, 1):
        sev = d.get("severity", "")
        if sev == "critical":
            style.append(("TEXTCOLOR", (3, i), (3, i), COLOR_RED))
            style.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))
        elif sev == "warning":
            style.append(("TEXTCOLOR", (3, i), (3, i), COLOR_YELLOW))

    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    return story


def _build_health_section(data: List[Dict]) -> list:
    story = [_section_title("🖥️ Estado de Salud de Nodos")]
    if not data:
        return story

    headers = ["Nodo", "Tipo", "CPU %", "RAM %", "Latencia (ms)", "Pkt Loss %", "Estado"]
    rows = [headers]
    for d in data:
        status = "🟢 Online" if d.get("online") else "🔴 Offline"
        rows.append([
            d.get("node", ""), d.get("type", ""),
            f"{d.get('cpu_pct', 0):.1f}",
            f"{d.get('ram_pct', 0):.1f}",
            f"{d.get('latency_ms', 0):.1f}",
            f"{d.get('packet_loss', 0):.3f}",
            status,
        ])

    tbl = Table(rows, repeatRows=1, colWidths=["18%","15%","10%","10%","15%","13%","19%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), COLOR_PRIMARY),
        ("TEXTCOLOR",   (0,0), (-1,0), COLOR_WHITE),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [COLOR_WHITE, COLOR_BG]),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",  (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(tbl)
    return story


def _build_ssl_section(data: List[Dict]) -> list:
    story = [_section_title("🔐 Estado de Certificados SSL/TLS")]
    if not data:
        return story

    headers = ["Nodo", "Dominio", "Días para vencer", "Versión TLS", "Válido", "Alerta"]
    rows = [headers]
    for d in data:
        rows.append([
            d.get("node", ""), d.get("domain", ""),
            str(d.get("days_to_expire", 0)),
            d.get("tls_version", ""),
            "✅ Sí" if d.get("is_valid") else "❌ No",
            d.get("alert_message", "-") or "-",
        ])

    tbl = Table(rows, repeatRows=1, colWidths=["12%","25%","15%","13%","10%","25%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), COLOR_PRIMARY),
        ("TEXTCOLOR",   (0,0), (-1,0), COLOR_WHITE),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [COLOR_WHITE, COLOR_BG]),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",  (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(tbl)
    return story


def _build_sst_section(data: List[Dict]) -> list:
    story = [_section_title("🌡️ Lecturas de Sensores SST")]
    if not data:
        return story

    headers = ["Sensor", "Zona", "Tipo", "Valor", "Unidad", "Nivel de Alerta"]
    rows = [headers]
    for d in data:
        val = (d.get("temperature_c") or d.get("humidity_pct") or
               d.get("smoke_ppm") or d.get("ups_battery_pct") or
               d.get("power_kw") or "-")
        rows.append([
            d.get("sensor", ""), d.get("zone", ""),
            d.get("type", ""), str(val),
            d.get("unit", ""),
            (d.get("alert_level") or "normal").upper(),
        ])

    tbl = Table(rows, repeatRows=1, colWidths=["20%","15%","15%","12%","10%","28%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), COLOR_PRIMARY),
        ("TEXTCOLOR",   (0,0), (-1,0), COLOR_WHITE),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [COLOR_WHITE, COLOR_BG]),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
        ("TOPPADDING",  (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(tbl)
    return story


def _build_student_section(data: List[Dict]) -> list:
    story = [_section_title("🎓 Evaluación de Desempeño del Estudiante")]
    if not data:
        return story
    d = data[0]
    rows = [
        ["Estudiante",              d.get("student", "")],
        ["Total Sesiones",          str(d.get("sessions", 0))],
        ["MTTD Promedio",           f"{d.get('avg_mttd', 0):.1f} segundos"],
        ["MTTR Promedio",           f"{d.get('avg_mttr', 0):.1f} segundos"],
        ["Score Promedio",          f"{d.get('avg_score', 0):.1f} / 100"],
        ["Incidentes Revisados",    str(d.get("incidents_total", 0))],
    ]
    story.append(_info_table(rows))
    return story


def _build_generic_section(data: List[Dict]) -> list:
    story = [_section_title("📋 Datos del Reporte")]
    style = getSampleStyleSheet()["Normal"]
    for item in data[:50]:
        story.append(Paragraph(str(item), style))
        story.append(Spacer(1, 0.2*cm))
    return story



def _build_full_summary_section(data: List[Dict]) -> list:
    """Reporte completo del aprendiz."""
    story = []
    bold9  = ParagraphStyle("fs_bold",   fontSize=9, leading=13, textColor=COLOR_DARK, fontName="Helvetica-Bold")
    normal = ParagraphStyle("fs_normal", fontSize=8, leading=12, textColor=COLOR_DARK)

    # Verificar que los datos tienen el formato nuevo (con "section")
    has_sections = any(d.get("section") for d in data)
    if not has_sections:
        story.append(_section_title("Sin datos disponibles"))
        style = getSampleStyleSheet()["Normal"]
        story.append(Paragraph("No se encontraron actividades registradas para este aprendiz. Completa al menos un diagnostico guiado y una bitacora para generar el informe completo.", style))
        return story

    # 1. Perfil del aprendiz
    hdr = [d for d in data if d.get("section") == "student_header"]
    if hdr:
        s = hdr[0]
        story.append(_section_title("Perfil del Aprendiz"))
        story.append(_info_table([
            ["Nombre",                  s.get("name","—")],
            ["Correo",                  s.get("email","—")],
            ["Total sesiones",          str(s.get("sessions",0))],
            ["Diagnosticos guiados",    str(s.get("guided_count",0))],
            ["Protocolos SST",          str(s.get("sst_count",0))],
            ["Labs completados",        str(s.get("lab_count",0))],
            ["Bitacoras redactadas",    str(s.get("bitacora_count",0))],
            ["Incidentes gestionados",  str(s.get("incidents",0))],
            ["MTTD promedio",           f"{s.get('avg_mttd',0)} s"],
            ["Score promedio",          f"{s.get('avg_score',0)} / 100"],
        ]))
        story.append(Spacer(1, 0.4*cm))

    # 2. Diagnosticos guiados
    guided = [d for d in data if d.get("section") == "eval_session"]
    if guided:
        story.append(PageBreak())
        story.append(_section_title(f"Diagnosticos Guiados ({len(guided)} registros)"))
        rows = [["Fecha", "Ataque", "Nodo", "Score", "Correctas", "Pistas", "Duracion"]]
        for g in guided:
            atk = ATTACK_LABELS.get(g.get("attack",""), g.get("attack","—"))
            rows.append([
                g.get("started","—")[:16], atk, g.get("node","—"),
                f"{g.get('score',0)}/100", f"{g.get('correct',0)}/{g.get('total',4)}",
                str(g.get("hints",0)), f"{g.get('duration',0)}s",
            ])
        tbl = Table(rows, repeatRows=1, colWidths=["18%","22%","10%","11%","12%","9%","10%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),COLOR_PRIMARY),("TEXTCOLOR",(0,0),(-1,0),COLOR_WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[COLOR_WHITE,COLOR_BG]),
            ("LEFTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))

    # 3. Protocolos SST
    sst = [d for d in data if d.get("section") == "sst_session"]
    if sst:
        story.append(_section_title(f"Protocolos SST ({len(sst)} registros)"))
        rows = [["Fecha","Protocolo","Sensor","Valor","Score","Correctas"]]
        for s in sst:
            rows.append([
                s.get("date","—")[:16], s.get("protocol","—")[:30],
                s.get("sensor","—"), s.get("value","—"),
                f"{s.get('score',0)}/100", f"{s.get('correct',0)}/{s.get('total',4)}",
            ])
        tbl = Table(rows, repeatRows=1, colWidths=["15%","28%","17%","12%","14%","14%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#ea580c")),("TEXTCOLOR",(0,0),(-1,0),COLOR_WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[COLOR_WHITE,COLOR_BG]),
            ("LEFTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))

    # 4. Labs
    labs = [d for d in data if d.get("section") == "lab_session"]
    if labs:
        story.append(_section_title(f"Labs de Mitigacion ({len(labs)} registros)"))
        rows = [["Fecha","Escenario","Score","Pasos","Duracion"]]
        for l in labs:
            rows.append([
                l.get("date","—")[:16], l.get("scenario","—")[:35],
                f"{l.get('score',0)}/100", f"{l.get('steps',0)}/{l.get('total_steps',0)}",
                f"{l.get('duration',0)}s",
            ])
        tbl = Table(rows, repeatRows=1, colWidths=["18%","40%","14%","14%","14%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#7c3aed")),("TEXTCOLOR",(0,0),(-1,0),COLOR_WHITE),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[COLOR_WHITE,COLOR_BG]),
            ("LEFTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))

    # 5. Bitacoras con texto completo
    bms = [d for d in data if d.get("section") == "bitacora"]
    if bms:
        story.append(PageBreak())
        story.append(_section_title(f"Bitacoras de Incidentes ({len(bms)} registros)"))
        for i, b in enumerate(bms, 1):
            atk = ATTACK_LABELS.get(b.get("attack",""), b.get("attack","—"))
            story.append(Paragraph(
                f"<b>#{i} — {atk} | Nodo: {b.get('node','—')} | {b.get('date','—')[:16]} | "
                f"Score: {b.get('score',0)}/100 | {b.get('correct',0)}/4 | {b.get('hints',0)} pistas | {b.get('duration',0)}s</b>",
                bold9
            ))
            story.append(Spacer(1, 0.1*cm))
            for label, key in [
                ("Sintomas observados:", "sintomas"),
                ("Analisis de causa raiz:", "causa"),
                ("Acciones tomadas:", "acciones"),
                ("Lecciones aprendidas:", "lecciones"),
            ]:
                txt = b.get(key,"")
                if txt:
                    story.append(Paragraph(f"<b>{label}</b>", bold9))
                    story.append(Paragraph(txt, normal))
                    story.append(Spacer(1, 0.08*cm))
            if i < len(bms):
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
            story.append(Spacer(1, 0.25*cm))

    # 6. Incidentes del DC
    incidents = [d for d in data if d.get("section") == "incident"]
    if incidents:
        story.append(PageBreak())
        story.append(_section_title(f"Incidentes del Datacenter ({len(incidents)})"))
        story.extend(_build_incident_section(incidents))

    # 7. Salud del DC
    health = [d for d in data if d.get("section") == "health"]
    if health:
        story.append(_section_title("Estado Actual del Datacenter"))
        story.extend(_build_health_section(health))

    # 8. SSL
    ssl_certs = [d for d in data if d.get("section") == "ssl"]
    if ssl_certs:
        story.append(_section_title("Certificados SSL/TLS"))
        story.extend(_build_ssl_section(ssl_certs))

    return story

def _generate_txt_fallback(title: str, data: List[Dict], path: str) -> bool:
    """Genera un archivo TXT si ReportLab no está disponible."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{'='*60}\n{title}\n{'='*60}\n")
            f.write(f"Generado: {iso_utc(datetime.utcnow())}\n\n")
            for i, item in enumerate(data, 1):
                f.write(f"[{i}] {item}\n")
        return True
    except Exception:
        return False
