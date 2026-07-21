import io
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# Módulo de Análise CSV
from analise_csv import process_uploaded_csv, get_product_kpis

# Módulo de PDF Executivo Clariô
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


# ==============================================================================
# 1. CORE MATEMÁTICO (CLARIÓ FRAMEWORK)
# ==============================================================================

class ClarioOptimizationEngine:
    def __init__(self, p_curr: float, q_curr: float, p_test: float, q_test: float, cf: float, cvu: float):
        self.p_curr = float(p_curr)
        self.q_curr = float(q_curr)
        self.p_test = float(p_test)
        self.q_test = float(q_test)
        self.cf = float(cf)
        self.cvu = float(cvu)

        if abs(self.p_curr - self.p_test) < 1e-6:
            raise ValueError("O Preço de Teste deve ser diferente do Preço Atual.")

        self.b = (self.q_curr - self.q_test) / (self.p_test - self.p_curr)
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
            "price": price, "volume": q, "faturamento": faturamento,
            "custo_total": custo_total, "lucro_liquido": lucro_liquido,
            "margem_contrib": margem_contrib, "margem_liquida_pct": margem_liquida_pct
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
                "Estratégia": sc["estratégia"], "Preço": fin["price"], "Volume": fin["volume"],
                "Faturamento": fin["faturamento"], "Custos Totais": fin["custo_total"],
                "Lucro Líquido": fin["lucro_liquido"]
            })
        return data


# ==============================================================================
# 2. GERADOR DE PDF EXECUTIVO
# ==============================================================================

def generate_clario_pdf(engine: ClarioOptimizationEngine) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('ClarioTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20,
                                 textColor=colors.HexColor('#0F172A'), spaceAfter=4)
    subtitle_style = ParagraphStyle('ClarioSubTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
                                    textColor=colors.HexColor('#007AFF'), spaceAfter=15, textTransform='uppercase')
    section_heading = ParagraphStyle('ClarioSection', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12,
                                     textColor=colors.HexColor('#1E293B'), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('ClarioBody', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13,
                                textColor=colors.HexColor('#334155'))

    p_opt = engine.get_max_profit_price()
    fin_opt = engine.calculate_financials(p_opt)
    fin_curr = engine.calculate_financials(engine.p_curr)
    delta_profit = fin_opt["lucro_liquido"] - fin_curr["lucro_liquido"]

    story.append(Paragraph("CLARIÔ CORPORATE INTELLIGENCE", subtitle_style))
    story.append(Paragraph("Relatório Executivo de Otimização de Margem", title_style))
    story.append(Paragraph("Data-Driven Strategy Playbook — Diagnóstico e Governança Financeira", body_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceAfter=15))

    kpi_data = [[
        Paragraph(f"<b>Preço Ideal (Clariô):</b><br/><font size=14 color='#007AFF'><b>R$ {p_opt:,.2f}</b></font>",
                  body_style),
        Paragraph(
            f"<b>Lucro Líquido Diário:</b><br/><font size=14 color='#34C759'><b>R$ {fin_opt['lucro_liquido']:,.2f}</b></font>",
            body_style),
        Paragraph(
            f"<b>Ganho Adicionado:</b><br/><font size=14 color='#FF9500'><b>+R$ {delta_profit:,.2f}/dia</b></font>",
            body_style)
    ]]
    kpi_table = Table(kpi_data, colWidths=[180, 180, 180])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("1. Memorial de Cálculo da Demanda", section_heading))
    memorial_text = (
        f"Preço Atual de <b>R$ {engine.p_curr:,.2f}</b> (Volume: {engine.q_curr:.0f} un.) e "
        f"Preço Ajustado de <b>R$ {engine.p_test:,.2f}</b> (Volume: {engine.q_test:.0f} un.).<br/>"
        f"• <b>Sensibilidade (b):</b> {engine.b:.4f}<br/>• <b>Demanda Teórica (a):</b> {engine.a:.2f}<br/>"
        f"• <b>Estrutura:</b> CF R$ {engine.cf:,.2f} / CVU R$ {engine.cvu:,.2f}"
    )
    story.append(Paragraph(memorial_text, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==============================================================================
# 3. INTERFACE DASHBOARD (UI)
# ==============================================================================

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP,
                          "https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&display=swap"],
    title="Clariô Corporate Intelligence | Optimization Engine"
)
server = app.server


def make_kpi_card(title, value_id, sub_id, accent_color="#007AFF"):
    return html.Div([
        html.Div([
            html.Span(title, style={"fontSize": "11px", "fontWeight": "700", "color": "#8E8E93",
                                    "textTransform": "uppercase"}),
            html.Div(style={"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": accent_color})
        ], className="d-flex justify-content-between align-items-center mb-2"),
        html.H3("R$ --", id=value_id, style={"fontSize": "24px", "fontWeight": "700", "color": "#1C1C1E"},
                className="mb-1"),
        html.Span("--", id=sub_id, style={"fontSize": "12px", "color": "#6E6E73"})
    ], style={"backgroundColor": "rgba(255, 255, 255, 0.85)", "borderRadius": "18px", "padding": "20px",
              "border": "1px solid rgba(255, 255, 255, 0.6)"})


def make_input_field(label_text, input_id, default_val):
    return html.Div([
        html.Label(label_text,
                   style={"fontSize": "12px", "fontWeight": "500", "color": "#3A3A3C", "marginBottom": "6px"}),
        dbc.Input(id=input_id, type="number", value=default_val, step="any",
                  style={"backgroundColor": "#EFEFF4", "border": "none", "borderRadius": "10px", "padding": "10px",
                         "fontSize": "14px", "color": "#1C1C1E"})
    ], className="mb-3")


app.layout = html.Div([
    # Store para guardar DataFrame temporário do CSV
    dcc.Store(id="stored-csv-data"),

    # Topbar
    html.Div([
        html.Span("Clariô Corporate Intelligence — Strategy Playbook",
                  style={"fontSize": "13px", "fontWeight": "600", "color": "#8E8E93"}),
        dbc.Button("Exportar Relatório PDF", id="btn-export-pdf", color="primary", className="ms-auto btn-sm",
                   style={"borderRadius": "8px"}),
        dcc.Download(id="download-pdf")
    ], style={"padding": "12px 28px", "backgroundColor": "rgba(255, 255, 255, 0.8)",
              "borderBottom": "1px solid rgba(0,0,0,0.05)", "display": "flex", "alignItems": "center"}),

    dbc.Container([
        html.Div([
            html.H1("Otimizador de Lucro Líquido", style={"fontSize": "32px", "fontWeight": "700", "color": "#1C1C1E"},
                    className="mb-1"),
            html.P("Análise de histórico de vendas em CSV, elasticidade-preço e governança de margens.",
                   style={"fontSize": "15px", "color": "#6E6E73"}, className="mb-4")
        ], className="mt-4"),

        # Bloco 1: Upload e Análise CSV
        html.Div([
            html.H5("📂 1. Ingestão de Dados de Vendas (CSV)", style={"fontSize": "16px", "fontWeight": "700"},
                    className="mb-3"),
            dbc.Row([
                dbc.Col([
                    dcc.Upload(
                        id='upload-data',
                        children=html.Div(['Arraste seu CSV aqui ou ', html.A('Clique para Selecionar',
                                                                              style={"color": "#007AFF",
                                                                                     "fontWeight": "600"})]),
                        style={'width': '100%', 'height': '80px', 'lineHeight': '80px', 'borderWidth': '2px',
                               'borderStyle': 'dashed', 'borderColor': '#C7C7CC', 'borderRadius': '14px',
                               'textAlign': 'center', 'backgroundColor': '#FFFFFF', 'cursor': 'pointer'}
                    ),
                    html.Div(id='upload-status-msg', className="mt-2", style={"fontSize": "13px"})
                ], md=6),
                dbc.Col([
                    html.Label("Selecione o Produto:", style={"fontSize": "12px", "fontWeight": "600"}),
                    dcc.Dropdown(id="product-dropdown", placeholder="Aguardando CSV...",
                                 style={"borderRadius": "10px"}),
                    dbc.Button("⚡ Transferir Dados do CSV para o Simulador", id="btn-transfer-params", color="success",
                               className="w-100 mt-3", style={"borderRadius": "10px", "fontWeight": "600"})
                ], md=6)
            ])
        ], style={"backgroundColor": "#FFFFFF", "borderRadius": "20px", "padding": "24px", "marginBottom": "24px",
                  "boxShadow": "0 8px 30px rgba(0,0,0,0.03)"}),

        # Bloco 2: Simulador Otimizador
        dbc.Row([
            # Sidebar Inputs
            dbc.Col([
                html.Div([
                    html.H6("Coordenadas da Indução", style={"fontSize": "13px", "fontWeight": "700"},
                            className="mb-3"),
                    make_input_field("Preço Atual / Mínimo (R$)", "input-p-curr", 150.0),
                    make_input_field("Volume Média P. Mínimo (un/dia)", "input-q-curr", 70.0),
                    make_input_field("Preço de Teste / Máximo (R$)", "input-p-test", 180.0),
                    make_input_field("Volume Média P. Máximo (un/dia)", "input-q-test", 46.0),
                    html.Hr(),
                    html.H6("Estrutura Operacional", style={"fontSize": "13px", "fontWeight": "700"}, className="mb-3"),
                    make_input_field("Custos Fixos Diários - CF (R$)", "input-cf", 1500.0),
                    make_input_field("Custo Variável Unit. - CVU (R$)", "input-cvu", 40.0),
                ], style={"backgroundColor": "#FFFFFF", "borderRadius": "20px", "padding": "24px",
                          "boxShadow": "0 8px 30px rgba(0,0,0,0.03)"})
            ], xs=12, md=4, lg=3),

            # Resultados
            dbc.Col([
                dbc.Row([
                    dbc.Col(make_kpi_card("Preço Ideal (Clariô)", "kpi-p-opt", "kpi-p-opt-sub", "#34C759"), md=4),
                    dbc.Col(make_kpi_card("Lucro Líquido Máximo", "kpi-profit-max", "kpi-profit-max-sub", "#007AFF"),
                            md=4),
                    dbc.Col(make_kpi_card("Volume Ideal", "kpi-vol-opt", "kpi-vol-opt-sub", "#FF9500"), md=4),
                ], className="g-3 mb-4"),

                html.Div([
                    html.H6("💡 Diagnóstico Executivo",
                            style={"fontSize": "13px", "fontWeight": "700", "color": "#007AFF"}, className="mb-2"),
                    dcc.Markdown(id="storytelling-text", style={"fontSize": "14px", "color": "#1C1C1E"})
                ], style={"backgroundColor": "#FFFFFF", "borderRadius": "18px", "padding": "20px",
                          "borderLeft": "5px solid #007AFF", "marginBottom": "24px"}),

                html.Div([dcc.Graph(id="chart-optimization", config={"displayModeBar": False})],
                         style={"backgroundColor": "#FFFFFF", "borderRadius": "20px", "padding": "20px",
                                "marginBottom": "24px"}),
                html.Div([html.Div(id="table-container")],
                         style={"backgroundColor": "#FFFFFF", "borderRadius": "20px", "padding": "24px"})
            ], xs=12, md=8, lg=9)
        ])
    ], fluid=True, style={"maxWidth": "1400px"})
], style={"backgroundColor": "#F5F5F7", "fontFamily": "-apple-system, sans-serif", "minHeight": "100vh",
          "paddingBottom": "60px"})


# ==============================================================================
# 4. CALLBACKS
# ==============================================================================

# Callback 1: Lê CSV e guarda no Store
@app.callback(
    [Output("stored-csv-data", "data"), Output("upload-status-msg", "children"), Output("product-dropdown", "options"),
     Output("product-dropdown", "value")],
    Input("upload-data", "contents")
)
def handle_csv_upload(contents):
    if contents is None:
        return None, "", [], None

    df, status = process_uploaded_csv(contents)
    if df is None:
        return None, html.Span(status, style={"color": "#FF3B30", "fontWeight": "600"}), [], None

    products = sorted(df['produto'].unique().tolist())
    dropdown_opts = [{"label": p, "value": p} for p in products]

    return df.to_json(date_format='iso', orient='split'), html.Span(f"✅ CSV carregado ({len(df)} linhas)",
                                                                    style={"color": "#34C759",
                                                                           "fontWeight": "600"}), dropdown_opts, \
    products[0]


# Callback 2: Transfere do CSV para os Inputs do Simulador
@app.callback(
    [Output("input-p-curr", "value"), Output("input-q-curr", "value"), Output("input-p-test", "value"),
     Output("input-q-test", "value")],
    Input("btn-transfer-params", "n_clicks"),
    [State("stored-csv-data", "data"), State("product-dropdown", "value")],
    prevent_initial_call=True
)
def transfer_params(n_clicks, json_data, selected_product):
    if not json_data or not selected_product:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    df = pd.read_json(json_data, orient='split')
    kpis = get_product_kpis(df, selected_product)

    if kpis:
        return kpis["p_min"], kpis["q_min"], kpis["p_max"], kpis["q_max"]
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


# Callback 3: Otimizador Principal
@app.callback(
    [
        Output("kpi-p-opt", "children"), Output("kpi-p-opt-sub", "children"),
        Output("kpi-profit-max", "children"), Output("kpi-profit-max-sub", "children"),
        Output("kpi-vol-opt", "children"), Output("kpi-vol-opt-sub", "children"),
        Output("storytelling-text", "children"), Output("chart-optimization", "figure"),
        Output("table-container", "children")
    ],
    [
        Input("input-p-curr", "value"), Input("input-q-curr", "value"),
        Input("input-p-test", "value"), Input("input-q-test", "value"),
        Input("input-cf", "value"), Input("input-cvu", "value")
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

    story = (
        f"A transição de **R$ {p_curr:,.2f}** para o **Preço Ideal de R$ {p_opt:,.2f}** "
        f"reajusta a demanda para **{fin_opt['volume']:,.0f} un/dia**, maximizando a margem de contribuição unitária para "
        f"**R$ {fin_opt['margem_contrib']:,.2f}** e gerando **Lucro Líquido Diário de R$ {fin_opt['lucro_liquido']:,.2f}** (+R$ {delta_profit:,.2f}/dia)."
    )

    p_max_chart = max(engine.a / engine.b, p_test) * 1.1 if engine.b > 0 else p_curr * 2
    prices = np.linspace(0, p_max_chart, 120)
    revenues = [engine.calculate_financials(p)["faturamento"] for p in prices]
    profits = [engine.calculate_financials(p)["lucro_liquido"] for p in prices]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prices, y=revenues, mode="lines", name="Faturamento Bruto",
                             line=dict(color="#8E8E93", dash="dot")))
    fig.add_trace(
        go.Scatter(x=prices, y=profits, mode="lines", name="Lucro Líquido", line=dict(color="#34C759", width=3.5)))
    fig.add_trace(go.Scatter(x=[p_opt], y=[fin_opt["lucro_liquido"]], mode="markers+text", name="Lucro Máximo",
                             marker=dict(size=12, color="#007AFF"), text=[f"  PI: R$ {p_opt:.2f}"],
                             textposition="top center"))

    fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")

    df_table = pd.DataFrame(engine.generate_benchmark_data())
    for col in ["Preço", "Faturamento", "Custos Totais", "Lucro Líquido"]:
        df_table[col] = df_table[col].apply(lambda x: f"R$ {x:,.2f}")
    df_table["Volume"] = df_table["Volume"].apply(lambda x: f"{x:,.0f} un.")

    table = dash_table.DataTable(
        data=df_table.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df_table.columns],
        style_header={'backgroundColor': '#F2F2F7', 'fontWeight': '700'},
        style_cell={'textAlign': 'center', 'padding': '10px'}
    )

    return f"R$ {p_opt:,.2f}", f"Sensibilidade: {engine.b:.2f}", f"R$ {fin_opt['lucro_liquido']:,.2f}", f"+R$ {delta_profit:,.2f}/dia", f"{fin_opt['volume']:,.0f} un.", f"Margem: R$ {fin_opt['margem_contrib']:,.2f}", story, fig, table


# Callback PDF
@app.callback(
    Output("download-pdf", "data"),
    Input("btn-export-pdf", "n_clicks"),
    [State("input-p-curr", "value"), State("input-q-curr", "value"), State("input-p-test", "value"),
     State("input-q-test", "value"), State("input-cf", "value"), State("input-cvu", "value")],
    prevent_initial_call=True
)
def export_pdf(n_clicks, p_curr, q_curr, p_test, q_test, cf, cvu):
    engine = ClarioOptimizationEngine(p_curr, q_curr, p_test, q_test, cf, cvu)
    return dcc.send_bytes(generate_clario_pdf(engine), filename="Relatorio_Otimizacao_Clario.pdf")


if __name__ == "__main__":
    app.run(debug=False)