import io
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==========================================================
# CLARIÔ — BRAND DESIGN SYSTEM (PALETA OFICIAL)
# ==========================================================
CLARIO_ORANGE = "#FF6B35"
CLARIO_DARK = "#0F172A"
CLARIO_GREEN = "#10B981"
CLARIO_GREEN_BG = "#ECFDF5"
CLARIO_ORANGE_BG = "#FFF7ED"

LIGHT_BG = "#F8FAFC"
BORDER = "#E2E8F0"
BORDER_SUBTLE = "#F1F5F9"
MUTED = "#64748B"
TEXT = "#334155"


def fmt_money(val):
    """Formata valores numéricos para moeda BRL (R$ 1.234,56)."""
    try:
        return f"R$ {float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def fmt_int(val):
    """Formata inteiros no padrão pt-BR (1.234)."""
    try:
        return f"{int(round(float(val))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def get_clario_styles():
    """Gera o mapa de estilos tipográficos no padrão Clariô."""
    styles = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=styles["Normal"], fontName="Helvetica-Bold",
            fontSize=16, leading=18, textColor=colors.HexColor(CLARIO_DARK)
        ),
        "title": ParagraphStyle(
            "title", parent=styles["Heading1"], fontName="Helvetica-Bold",
            fontSize=18, leading=22, textColor=colors.HexColor(CLARIO_DARK), spaceAfter=4
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=styles["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor=colors.HexColor(MUTED)
        ),
        "section": ParagraphStyle(
            "section", parent=styles["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, textColor=colors.HexColor(CLARIO_DARK), spaceBefore=14, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "body", parent=styles["Normal"], fontName="Helvetica",
            fontSize=8.5, leading=12, textColor=colors.HexColor(TEXT)
        ),
        "kpi_val": ParagraphStyle("kpi_val", alignment=1, fontName="Helvetica-Bold")
    }


def clario_footer(canvas, doc):
    """Gera o rodapé do documento com a marca Clariô."""
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(colors.HexColor(CLARIO_DARK))
    canvas.drawString(36, 20, "clari")
    canvas.setFillColor(colors.HexColor(CLARIO_ORANGE))
    canvas.drawString(55, 20, "ô")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(63, 20, "• Pricing Engine — Diagnóstico Executivo")
    canvas.drawRightString(576, 20, f"Página {doc.page}")
    canvas.restoreState()


def generate_clario_pdf(res: dict, selected_sku: str, p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu) -> bytes:
    """
    Gera o relatório PDF executivo com a identidade visual oficial da Clariô.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )

    story = []
    st = get_clario_styles()

    # 1. CABEÇALHO COM BRANDING CLARIÔ
    story.append(Paragraph('clari<font color="#FF6B35">ô</font> <font color="#64748B" size="9">| PRICING ENGINE</font>', st["brand"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Diagnóstico Executivo: {selected_sku}", st["title"]))
    story.append(Paragraph("Relatório consolidado de otimização de preço, elasticidade da demanda e lucratividade.", st["subtitle"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER)))
    story.append(Spacer(1, 12))

    # 2. CARDS DE KPIS HERO
    def make_kpi_card(label, val, color_hex):
        content = (
            f'<font size="7" color="#64748B"><b>{label.upper()}</b></font><br/>'
            f'<font size="14" color="{color_hex}"><b>{val}</b></font>'
        )
        return Paragraph(content, st["kpi_val"])

    cards = [
        make_kpi_card("Preço Ideal (P*)", fmt_money(res.get("p_ideal", 0)), CLARIO_DARK),
        make_kpi_card("Lucro Líquido Diário", fmt_money(res.get("lucro_ideal", 0)), CLARIO_GREEN),
        make_kpi_card("Incremento Diário", f"+{fmt_money(res.get('incremento_diario', 0))}", CLARIO_ORANGE)
    ]
    kpi_table = Table([cards], colWidths=[180, 180, 180])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(LIGHT_BG)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(BORDER)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10)
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # 3. DETALHAMENTO TÉCNICO DOS PARÂMETROS
    story.append(Paragraph("1. Detalhamento Técnico & Parâmetros da Curva", st["section"]))

    p_params = [
        [
            Paragraph("<b>Elasticidade (ε):</b>", st["body"]), Paragraph(f"{res.get('elasticidade_estimada', 0):.4f}", st["body"]),
            Paragraph("<b>Margem Contrib. (R$):</b>", st["body"]), Paragraph(fmt_money(res.get("margem_contrib_unit", 0)), st["body"])
        ],
        [
            Paragraph("<b>Margem Contrib. (%):</b>", st["body"]), Paragraph(f"{res.get('margem_contrib_perc', 0):.1f}%", st["body"]),
            Paragraph("<b>Break-even (Unidades):</b>", st["body"]), Paragraph(f"{fmt_int(res.get('ponto_equilibrio_unidades', 0))} un.", st["body"])
        ],
        [
            Paragraph("<b>Preço Mínimo Histórico:</b>", st["body"]), Paragraph(f"{fmt_money(p_min)} ({fmt_int(q_pmin)} un/dia)", st["body"]),
            Paragraph("<b>Preço Máximo Histórico:</b>", st["body"]), Paragraph(f"{fmt_money(p_max)} ({fmt_int(q_pmax)} un/dia)", st["body"])
        ],
        [
            Paragraph("<b>Custo Variável Unit. (CVU):</b>", st["body"]), Paragraph(fmt_money(cvu), st["body"]),
            Paragraph("<b>Custo Fixo Absorvido:</b>", st["body"]), Paragraph(fmt_money(custos_fixos), st["body"])
        ]
    ]

    param_table = Table(p_params, colWidths=[130, 140, 140, 130])
    param_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_SUBTLE)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6)
    ]))
    story.append(param_table)
    story.append(Spacer(1, 14))

    # 4. TABELA COMPARATIVA DE ESTRATÉGIAS
    story.append(Paragraph("2. Comparativo de Estratégias de Precificação", st["section"]))

    table_raw = [["Estratégia", "Preço", "Volume", "Faturamento", "Custos Totais", "Lucro Líquido"]]
    for row in res.get("table_data", []):
        table_raw.append([
            row["Estratégia"], row["Preço"], row["Volume"],
            row["Faturamento"], row["Custos Totais"], row["Lucro Líquido"]
        ])

    table_comp = Table(table_raw, colWidths=[140, 75, 65, 85, 85, 90])
    table_comp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(MUTED)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER)),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        # Linha de destaque para a Estratégia Recomendada
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor(CLARIO_GREEN_BG)),
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.HexColor("#065F46")),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
    ]))

    story.append(KeepTogether(table_comp))

    # CONSTRUÇÃO DO PDF
    doc.build(story, onFirstPage=clario_footer, onLaterPages=clario_footer)
    buffer.seek(0)
    return buffer.getvalue()