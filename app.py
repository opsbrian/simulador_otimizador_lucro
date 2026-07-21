import io
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# Módulo de PDF Executivo Clariô
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


# ==============================================================================
# 1. CORE MATEMÁTICO (CLARIÓ FRAMEWORK)
# ==============================================================================

class ClarioOptimizationEngine:
    """Motor analítico de otimização de lucro líquido com base no memorial Clariô."""

    def __init__(self, p_curr: float, q_curr: float, p_test: float, q_test: float, cf: float, cvu: float):
        self.p_curr = float(p_curr)
        self.q_curr = float(q_curr)
        self.p_test = float(p_test)
        self.q_test = float(q_test)
        self.cf = float(cf)
        self.cvu = float(cvu)

        if abs(self.p_curr - self.p_test) < 1e-6:
            raise ValueError("O Preço de Teste deve ser diferente do Preço Atual.")

        # Coeficiente b (Inclinação da demanda)
        self.b = (self.q_curr - self.q_test) / (self.p_test - self.p_curr)
        # Coeficiente a (Mercado potencial)
        self.a = self.q_curr + (self.b * self.p_curr)

    def predict_volume(self, price: float) -> float:
        return max(0.0, self.a - (self.b * price))

    def calculate_financials(self, price: float) -> dict:
        q = self.predict_volume(price)
        faturamento = price * q
        custo_total = self.cf + (self.cvu * q)
        lucro_liquido = faturamento - custo_total
        margem_contrib = price - self.cvu
        margem_liquida_pct = (lucro_liquido / faturamento * 100) if faturamento > 0 else 0.0

        return {
            "price": price,
            "volume": q,
            "faturamento": faturamento,
            "custo_total": custo_total,
            "lucro_liquido": lucro_liquido,
            "margem_contrib": margem_contrib,
            "margem_liquida_pct": margem_liquida_pct
        }

    def get_max_revenue_price(self) -> float:
        return self.a / (2 * self.b) if self.b > 0 else self.p_curr

    def get_max_profit_price(self) -> float:
        if self.b <= 0:
            return self.p_curr
        return (self.a / (2 * self.b)) + (self.cvu / 2)

    def generate_benchmark_data(self) -> list:
        p_opt_profit = self.get_max_profit_price()
        p_opt_rev = self.get_max_revenue_price()

        scenarios = [
            {"estratégia": "Volume Alto (Desconto)", "preco": self.p_curr * 0.8},
            {"estratégia": "Faturamento Máximo", "preco": p_opt_rev},
            {"estratégia": "Lucro Máximo (Clariô)", "preco": p_opt_profit},
            {"estratégia": "Preço Alto sem Amparo", "preco": self.p_test},
        ]

        data = []
        for sc in scenarios:
            fin = self.calculate_financials(sc["preco"])
            data.append({
                "Estratégia": sc["estratégia"],
                "Preço": fin["price"],
                "Volume": fin["volume"],
                "Faturamento": fin["faturamento"],
                "Custos Totais": fin["custo_total"],
                "Lucro Líquido": fin["lucro_liquido"]
            })
        return data


# ==============================================================================
# 2. GERADOR DE PDF EXECUTIVO (CLARIÓ STYLE)
# ==============================================================================

def generate_clario_pdf(engine: ClarioOptimizationEngine) -> bytes:
    """Gera um PDF corporativo no padrão Clariô Corporate Intelligence."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []

    # Estilos
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ClarioTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'ClarioSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#007AFF'),
        spaceAfter=15,
        textTransform='uppercase'
    )
    section_heading = ParagraphStyle(
        'ClarioSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'ClarioBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    p_opt = engine.get_max_profit_price()
    fin_opt = engine.calculate_financials(p_opt)
    fin_curr = engine.calculate_financials(engine.p_curr)
    delta_profit = fin_opt["lucro_liquido"] - fin_curr["lucro_liquido"]

    # 1. Header do Relatório
    story.append(Paragraph("CLARIÔ CORPORATE INTELLIGENCE", subtitle_style))
    story.append(Paragraph("Relatório Executivo de Otimização de Margem", title_style))
    story.append(Paragraph("Data-Driven Strategy Playbook — Diagnóstico e Governança Financeira", body_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceAfter=15))

    # 2. Resumo Executivo (KPIs)
    kpi_data = [
        [
            Paragraph(f"<b>Preço Ideal (Clariô):</b><br/><font size=14 color='#007AFF'><b>R$ {p_opt:,.2f}</b></font>",
                      body_style),
            Paragraph(
                f"<b>Lucro Líquido Diário:</b><br/><font size=14 color='#34C759'><b>R$ {fin_opt['lucro_liquido']:,.2f}</b></font>",
                body_style),
            Paragraph(
                f"<b>Ganho Adicionado:</b><br/><font size=14 color='#FF9500'><b>+R$ {delta_profit:,.2f}/dia</b></font>",
                body_style)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[180, 180, 180])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))

    # 3. Memorial de Cálculo Aritmético
    story.append(Paragraph("1. Memorial de Cálculo da Demanda", section_heading))
    memorial_text = (
        f"A partir dos testes de indução com Preço Atual de <b>R$ {engine.p_curr:,.2f}</b> (Volume: {engine.q_curr:.0f} un.) "
        f"e Preço Ajustado de <b>R$ {engine.p_test:,.2f}</b> (Volume: {engine.q_test:.0f} un.), isolou-se a sensibilidade do mercado:<br/>"
        f"• <b>Coeficiente b (Sensibilidade):</b> {engine.b:.4f} clientes perdidos a cada R$ 1,00 reajustado.<br/>"
        f"• <b>Coeficiente a (Capacidade Absoluta):</b> {engine.a:.2f} unidades de teto teórico de demanda.<br/>"
        f"• <b>Estrutura Operacional:</b> Custo Fixo de R$ {engine.cf:,.2f}/dia e Custo Variável Unitário (CVU) de R$ {engine.cvu:,.2f}."
    )
    story.append(Paragraph(memorial_text, body_style))
    story.append(Spacer(1, 10))

    # 4. Matriz Comparativa de Estratégias
    story.append(Paragraph("2. Matriz Comparativa de Estratégias", section_heading))
    bench_data = engine.generate_benchmark_data()
    table_content = [["Estratégia", "Preço (R$)", "Vol./Dia", "Faturamento", "Custos Totais", "Lucro Líquido"]]

    for row in bench_data:
        table_content.append([
            row["Estratégia"],
            f"R$ {row['Preço']:,.2f}",
            f"{row['Volume']:,.0f} un.",
            f"R$ {row['Faturamento']:,.2f}",
            f"R$ {row['Custos Totais']:,.2f}",
            f"R$ {row['Lucro Líquido']:,.2f}"
        ])

    matrix_table = Table(table_content, colWidths=[130, 75, 70, 85, 85, 95])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#DCFCE7')),  # Destaque Lucro Máximo Clariô
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 15))

    # 5. Governança em 3 Níveis
    story.append(Paragraph("3. Desdobramento de Metas & Governança Executiva", section_heading))
    gov_text = (
        f"<b>Nível 1 (Macro/C-Level):</b> Foco na Margem Líquida Geral. O objetivo de faturamento estabiliza-se no topo da curva quadrática de eficiência (R$ {fin_opt['lucro_liquido']:,.2f}/dia).<br/>"
        f"<b>Nível 2 (Tático/Marketing):</b> Fixação do preço de tabela em R$ {p_opt:,.2f}, blindando a margem de contribuição unitária em R$ {fin_opt['margem_contrib']:,.2f}.<br/>"
        f"<b>Nível 3 (Operacional/Estoque):</b> Dimensionamento da capacidade técnica para processar exatamente {fin_opt['volume']:,.0f} unidades com qualidade total, evitando desperdício de capital parado."
    )
    story.append(Paragraph(gov_text, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==============================================================================
# 3. INTERFACE DASHBOARD (APPLE HIG + GLASSMORPHISM UI)
# ==============================================================================

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&display=swap"
    ],
    title="Clariô Corporate Intelligence | Optimization Engine"
)

server = app.server


def make_apple_kpi(title, value_id, sub_id, accent_color="#007AFF"):
    return html.Div([
        html.Div([
            html.Span(title,
                      style={"fontSize": "11px", "fontWeight": "700", "letterSpacing": "0.5px", "color": "#8E8E93",
                             "textTransform": "uppercase"}),
            html.Div(style={"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": accent_color})
        ], className="d-flex justify-content-between align-items-center mb-2"),
        html.H3("R$ --", id=value_id,
                style={"fontSize": "26px", "fontWeight": "700", "color": "#1C1C1E", "letterSpacing": "-0.5px"},
                className="mb-1"),
        html.Span("--", id=sub_id, style={"fontSize": "12px", "color": "#6E6E73", "fontWeight": "400"})
    ], style={
        "backgroundColor": "rgba(255, 255, 255, 0.85)",
        "backdropFilter": "blur(20px)",
        "WebkitBackdropFilter": "blur(20px)",
        "borderRadius": "18px",
        "padding": "20px",
        "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.04)",
        "border": "1px solid rgba(255, 255, 255, 0.6)"
    })


def make_apple_input(label_text, input_id, default_val, step_val="any"):
    return html.Div([
        html.Label(label_text,
                   style={"fontSize": "12px", "fontWeight": "500", "color": "#3A3A3C", "marginBottom": "6px"}),
        dbc.Input(
            id=input_id, type="number", value=default_val, step=step_val,  # "any" permite aceitar qualquer casa decimal
            style={
                "backgroundColor": "#EFEFF4",
                "border": "none",
                "borderRadius": "10px",
                "padding": "10px 14px",
                "fontSize": "14px",
                "fontWeight": "500",
                "color": "#1C1C1E"
            }
        )
    ], className="mb-3")


app.layout = html.Div([
    # Topbar / macOS Header
    html.Div([
        html.Div([
            html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%", "backgroundColor": "#FF5F56",
                            "marginRight": "8px"}),
            html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%", "backgroundColor": "#FFBD2E",
                            "marginRight": "8px"}),
            html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%", "backgroundColor": "#27C93F"}),
        ], className="d-flex align-items-center me-3"),
        html.Span("Clariô Corporate Intelligence — Strategy Playbook",
                  style={"fontSize": "13px", "fontWeight": "600", "color": "#8E8E93"}),
        dbc.Button("Exportar Relatório PDF", id="btn-export-pdf", color="primary", className="ms-auto btn-sm",
                   style={"borderRadius": "8px", "fontWeight": "600"}),
        dcc.Download(id="download-pdf")
    ], style={
        "padding": "12px 28px",
        "backgroundColor": "rgba(255, 255, 255, 0.8)",
        "borderBottom": "1px solid rgba(0,0,0,0.05)",
        "display": "flex",
        "alignItems": "center"
    }),

    # Conteúdo da Página
    dbc.Container([
        # Header do Painel
        html.Div([
            html.H1("Otimizador de Lucro Líquido",
                    style={"fontSize": "32px", "fontWeight": "700", "color": "#1C1C1E", "letterSpacing": "-0.8px"},
                    className="mb-1"),
            html.P("Simulação de elasticidade-preço, ponto ótimo e governança de margens.",
                   style={"fontSize": "15px", "color": "#6E6E73"}, className="mb-4")
        ], className="mt-4"),

        dbc.Row([
            # Painel Lateral de Entradas
            dbc.Col([
                html.Div([
                    html.H6("Coordenadas da Fase de Indução",
                            style={"fontSize": "13px", "fontWeight": "700", "color": "#1C1C1E"}, className="mb-3"),
                    make_apple_input("Preço Atual (R$)", "input-p-curr", 150.0, "any"),
                    make_apple_input("Volume Atual (un/dia)", "input-q-curr", 70, "any"),
                    make_apple_input("Preço de Teste (R$)", "input-p-test", 180.0, "any"),
                    make_apple_input("Volume no Teste (un/dia)", "input-q-test", 46, "any"),

                    html.Hr(style={"borderColor": "#E5E5EA", "margin": "20px 0"}),

                    html.H6("Estrutura Operacional",
                            style={"fontSize": "13px", "fontWeight": "700", "color": "#1C1C1E"}, className="mb-3"),
                    make_apple_input("Custos Fixos Diários - CF (R$)", "input-cf", 1500.0, "any"),
                    make_apple_input("Custo Variável Unit. - CVU (R$)", "input-cvu", 40.0, "any"),
                ], style={
                    "backgroundColor": "rgba(255, 255, 255, 0.75)",
                    "backdropFilter": "blur(30px)",
                    "WebkitBackdropFilter": "blur(30px)",
                    "borderRadius": "20px",
                    "padding": "24px",
                    "boxShadow": "0 10px 40px rgba(0,0,0,0.03)",
                    "border": "1px solid rgba(255,255,255,0.8)"
                }, className="mb-4")
            ], xs=12, md=4, lg=3),

            # Conteúdo de Resultados
            dbc.Col([
                # Grid de KPIs Topo
                dbc.Row([
                    dbc.Col(make_apple_kpi("Preço Ideal (Clariô)", "kpi-p-opt", "kpi-p-opt-sub", "#34C759"), md=4),
                    dbc.Col(make_apple_kpi("Lucro Líquido Máximo", "kpi-profit-max", "kpi-profit-max-sub", "#007AFF"),
                            md=4),
                    dbc.Col(make_apple_kpi("Volume de Demanda Ideal", "kpi-vol-opt", "kpi-vol-opt-sub", "#FF9500"),
                            md=4),
                ], className="g-3 mb-4"),

                # Painel de Storytelling Automático
                html.Div([
                    html.H6("💡 Diagnóstico Executivo de Precificação",
                            style={"fontSize": "13px", "fontWeight": "700", "color": "#007AFF"}, className="mb-2"),
                    dcc.Markdown(id="storytelling-text",
                                 style={"fontSize": "14px", "lineHeight": "1.6", "color": "#1C1C1E"}, className="mb-0")
                ], style={
                    "backgroundColor": "rgba(255, 255, 255, 0.85)",
                    "backdropFilter": "blur(20px)",
                    "WebkitBackdropFilter": "blur(20px)",
                    "borderRadius": "18px",
                    "padding": "20px",
                    "boxShadow": "0 8px 30px rgba(0, 0, 0, 0.03)",
                    "borderLeft": "5px solid #007AFF",
                    "marginBottom": "24px"
                }),

                # Gráfico
                html.Div([
                    dcc.Graph(id="chart-optimization", config={"displayModeBar": False})
                ], style={
                    "backgroundColor": "rgba(255, 255, 255, 0.85)",
                    "backdropFilter": "blur(20px)",
                    "WebkitBackdropFilter": "blur(20px)",
                    "borderRadius": "20px",
                    "padding": "20px",
                    "boxShadow": "0 10px 30px rgba(0, 0, 0, 0.03)",
                    "border": "1px solid rgba(255, 255, 255, 0.6)",
                    "marginBottom": "24px"
                }),

                # Tabela Comparativa de Estratégias
                html.Div([
                    html.H6("Matriz Comparativa de Estratégias de Mercado",
                            style={"fontSize": "15px", "fontWeight": "700", "color": "#1C1C1E",
                                   "marginBottom": "16px"}),
                    html.Div(id="table-container")
                ], style={
                    "backgroundColor": "rgba(255, 255, 255, 0.85)",
                    "backdropFilter": "blur(20px)",
                    "WebkitBackdropFilter": "blur(20px)",
                    "borderRadius": "20px",
                    "padding": "24px",
                    "boxShadow": "0 10px 30px rgba(0, 0, 0, 0.03)",
                    "border": "1px solid rgba(255, 255, 255, 0.6)"
                })
            ], xs=12, md=8, lg=9)
        ])
    ], fluid=True, style={"maxWidth": "1400px"})
], style={
    "backgroundColor": "#F5F5F7",
    "fontFamily": "-apple-system, 'SF Pro Display', BlinkMacSystemFont, sans-serif",
    "minHeight": "100vh",
    "paddingBottom": "60px"
})


# ==============================================================================
# 4. CALLBACKS & REATIVIDADE
# ==============================================================================

@app.callback(
    [
        Output("kpi-p-opt", "children"),
        Output("kpi-p-opt-sub", "children"),
        Output("kpi-profit-max", "children"),
        Output("kpi-profit-max-sub", "children"),
        Output("kpi-vol-opt", "children"),
        Output("kpi-vol-opt-sub", "children"),
        Output("storytelling-text", "children"),
        Output("chart-optimization", "figure"),
        Output("table-container", "children"),
    ],
    [
        Input("input-p-curr", "value"),
        Input("input-q-curr", "value"),
        Input("input-p-test", "value"),
        Input("input-q-test", "value"),
        Input("input-cf", "value"),
        Input("input-cvu", "value"),
    ]
)
def update_dashboard(p_curr, q_curr, p_test, q_test, cf, cvu):
    if None in [p_curr, q_curr, p_test, q_test, cf, cvu] or p_curr == p_test:
        return ["--"] * 6 + ["Aguardando parâmetros válidos...", go.Figure(), html.Div()]

    engine = ClarioOptimizationEngine(p_curr, q_curr, p_test, q_test, cf, cvu)

    p_opt = engine.get_max_profit_price()
    fin_opt = engine.calculate_financials(p_opt)
    fin_curr = engine.calculate_financials(p_curr)

    delta_profit = fin_opt["lucro_liquido"] - fin_curr["lucro_liquido"]

    # KPIs
    kpi_p_opt_val = f"R$ {p_opt:,.2f}"
    kpi_p_opt_sub = f"Sensibilidade (b): {engine.b:.2f}"

    kpi_profit_val = f"R$ {fin_opt['lucro_liquido']:,.2f}"
    kpi_profit_sub = f"+R$ {delta_profit:,.2f}/dia vs. atual"

    kpi_vol_val = f"{fin_opt['volume']:,.0f} un."
    kpi_vol_sub = f"Margem Contrib.: R$ {fin_opt['margem_contrib']:,.2f}"

    # Data Storytelling
    story = (
        f"A transição do preço praticado de **R$ {p_curr:,.2f}** para o **Preço Ideal Clariô de R$ {p_opt:,.2f}** "
        f"reajusta a demanda para **{fin_opt['volume']:,.0f} unidades/dia**. "
        f"Apesar de uma oscilação no volume, essa estratégia maximiza a margem de contribuição unitária para **R$ {fin_opt['margem_contrib']:,.2f}**, "
        f"gerando um **Lucro Líquido Diário de R$ {fin_opt['lucro_liquido']:,.2f}** (+R$ {delta_profit:,.2f}/dia em comparação ao cenário original)."
    )

    # Gráfico
    p_max_chart = max(engine.a / engine.b, p_test) * 1.1 if engine.b > 0 else p_curr * 2
    prices = np.linspace(0, p_max_chart, 120)

    revenues = [engine.calculate_financials(p)["faturamento"] for p in prices]
    profits = [engine.calculate_financials(p)["lucro_liquido"] for p in prices]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=prices, y=revenues,
        mode="lines",
        name="Faturamento Bruto",
        line=dict(color="#8E8E93", width=2, dash="dot"),
        hovertemplate="Preço: R$ %{x:.2f}<br>Faturamento: R$ %{y:,.2f}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=prices, y=profits,
        mode="lines",
        name="Lucro Líquido (Real)",
        line=dict(color="#34C759", width=3.5, shape="spline"),
        hovertemplate="Preço: R$ %{x:.2f}<br>Lucro Líquido: R$ %{y:,.2f}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=[p_opt], y=[fin_opt["lucro_liquido"]],
        mode="markers+text",
        name="Lucro Máximo (Clariô)",
        marker=dict(size=12, color="#007AFF", line=dict(width=3, color="#FFFFFF")),
        text=[f"  PI: R$ {p_opt:.2f}"],
        textposition="top center",
        textfont=dict(color="#007AFF", size=13, family="-apple-system")
    ))

    fig.update_layout(
        template="plotly_white",
        title=dict(text="Curva Quadrática de Otimização Financeira",
                   font=dict(size=16, family="-apple-system", color="#1C1C1E")),
        xaxis=dict(title="Preço Praticado (R$)", gridcolor="#F2F2F7", showline=False),
        yaxis=dict(title="Valor Financeiro Diário (R$)", gridcolor="#F2F2F7", showline=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Tabela de Resultados
    bench_data = engine.generate_benchmark_data()
    df_table = pd.DataFrame(bench_data)

    # Formatação visual
    df_table["Preço"] = df_table["Preço"].apply(lambda x: f"R$ {x:,.2f}")
    df_table["Volume"] = df_table["Volume"].apply(lambda x: f"{x:,.0f} un.")
    df_table["Faturamento"] = df_table["Faturamento"].apply(lambda x: f"R$ {x:,.2f}")
    df_table["Custos Totais"] = df_table["Custos Totais"].apply(lambda x: f"R$ {x:,.2f}")
    df_table["Lucro Líquido"] = df_table["Lucro Líquido"].apply(lambda x: f"R$ {x:,.2f}")

    table_component = dash_table.DataTable(
        data=df_table.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df_table.columns],
        style_header={
            'backgroundColor': '#F2F2F7',
            'color': '#8E8E93',
            'fontWeight': '700',
            'fontSize': '12px',
            'border': 'none',
            'textTransform': 'uppercase'
        },
        style_cell={
            'backgroundColor': 'transparent',
            'color': '#1C1C1E',
            'textAlign': 'center',
            'fontFamily': '-apple-system, sans-serif',
            'fontSize': '13px',
            'padding': '12px 16px',
            'borderBottom': '1px solid #E5E5EA'
        },
        style_data_conditional=[
            {
                'if': {'filter_query': '{Estratégia} = "Lucro Máximo (Clariô)"'},
                'backgroundColor': 'rgba(52, 199, 89, 0.12)',
                'color': '#248A3D',
                'fontWeight': '600'
            }
        ]
    )

    return (
        kpi_p_opt_val, kpi_p_opt_sub,
        kpi_profit_val, kpi_profit_sub,
        kpi_vol_val, kpi_vol_sub,
        story,
        fig,
        table_component
    )


# Callback para Download do PDF
@app.callback(
    Output("download-pdf", "data"),
    Input("btn-export-pdf", "n_clicks"),
    State("input-p-curr", "value"),
    State("input-q-curr", "value"),
    State("input-p-test", "value"),
    State("input-q-test", "value"),
    State("input-cf", "value"),
    State("input-cvu", "value"),
    prevent_initial_call=True
)
def export_pdf_callback(n_clicks, p_curr, q_curr, p_test, q_test, cf, cvu):
    if n_clicks is None:
        return dash.no_update

    engine = ClarioOptimizationEngine(p_curr, q_curr, p_test, q_test, cf, cvu)
    pdf_bytes = generate_clario_pdf(engine)

    return dcc.send_bytes(pdf_bytes, filename="Clario_Relatorio_Otimizacao_Lucro.pdf")


if __name__ == "__main__":
    app.run(debug=False)