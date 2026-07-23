import dash
from dash import dcc, html, Input, Output, State, dash_table, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import io

from analise_csv import process_uploaded_csv, get_product_kpis
from relatorios_pdf import generate_clario_pdf

# ==============================================================================
# INICIALIZAÇÃO DO APP DASH
# ==============================================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css"
    ],
    title="Clariô | Pricing Engine"
)
server = app.server


# ==============================================================================
# CÁLCULO FINANCEIRO & MODELAGEM DE ELASTICIDADE
# ==============================================================================
def calculate_pricing_model(p_min, q_pmin, p_max, q_pmax, custos_fixos_rateados, cvu):
    try:
        p_min = float(p_min) if p_min is not None else 100.0
        q_pmin = float(q_pmin) if q_pmin is not None else 10.0
        p_max = float(p_max) if p_max is not None else 115.0
        q_pmax = float(q_pmax) if q_pmax is not None else 8.5
        custos_fixos = float(custos_fixos_rateados) if custos_fixos_rateados is not None else 0.0
        cvu = float(cvu) if cvu is not None else 10.0
    except (ValueError, TypeError):
        return None

    if p_min <= 0: p_min = 10.0
    if q_pmin <= 0: q_pmin = 1.0

    if p_max <= p_min:
        p_max = round(p_min * 1.15, 2)
        q_pmax = round(max(0.1, q_pmin * 0.85), 2)

    if q_pmax <= 0:
        q_pmax = round(max(0.1, q_pmin * 0.85), 2)

    if pd.isna(q_pmin) or pd.isna(q_pmax) or q_pmax >= q_pmin:
        b = 1.25
    else:
        try:
            b_calc = -(np.log(q_pmax) - np.log(q_pmin)) / (np.log(p_max) - np.log(p_min))
            if np.isnan(b_calc) or np.isinf(b_calc) or b_calc <= 0:
                b = 1.25
            else:
                b = b_calc
        except Exception:
            b = 1.25

    b = min(max(b, 0.5), 3.0)
    a = q_pmin / (p_min ** (-b))

    min_markup_price = cvu * 1.15
    limite_desconto_historico = p_min * 0.50
    min_p_sim = max(min_markup_price, limite_desconto_historico)
    max_p_sim = p_max * 1.6

    p_range = np.linspace(min_p_sim, max_p_sim, 200)
    q_range = a * (p_range ** (-b))

    receita_range = p_range * q_range
    custo_var_range = cvu * q_range
    custo_total_range = custos_fixos + custo_var_range
    lucro_range = receita_range - custo_total_range

    idx_opt = np.argmax(lucro_range)
    p_ideal = round(float(p_range[idx_opt]), 2)
    q_ideal = max(1, int(round(q_range[idx_opt])))
    lucro_ideal = round(float(lucro_range[idx_opt]), 2)
    faturamento_ideal = round(float(receita_range[idx_opt]), 2)
    custo_var_ideal = round(float(custo_var_range[idx_opt]), 2)
    custo_total_ideal = round(float(custo_total_range[idx_opt]), 2)

    margem_contrib_unit = p_ideal - cvu
    margem_contrib_perc = (margem_contrib_unit / p_ideal * 100) if p_ideal > 0 else 0
    ponto_equilibrio_unidades = int(np.ceil(custos_fixos / margem_contrib_unit)) if margem_contrib_unit > 0 else 0

    q_base = max(1, int(round(q_pmin)))
    lucro_base = round((p_min * q_base) - (custos_fixos + cvu * q_base), 2)
    incremento_diario = round(lucro_ideal - lucro_base, 2)

    def f_money(val):
        if pd.isna(val): return "R$ 0,00"
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    p_vol, q_vol = p_min, int(round(q_pmin))
    fat_vol = p_vol * q_vol
    custo_vol = custos_fixos + (cvu * q_vol)
    lucro_vol = fat_vol - custo_vol

    idx_rec = np.argmax(receita_range)
    p_rec = round(float(p_range[idx_rec]), 2)
    q_rec = int(round(q_range[idx_rec]))
    fat_rec = p_rec * q_rec
    custo_rec = custos_fixos + (cvu * q_rec)
    lucro_rec = fat_rec - custo_rec

    p_test, q_test = p_max, int(round(q_pmax))
    fat_test = p_test * q_test
    custo_test = custos_fixos + (cvu * q_test)
    lucro_test = fat_test - custo_test

    table_data = [
        {"Estratégia": "Volume (Maior Desconto)", "Preço": f_money(p_vol), "Volume": f"{q_vol:,} un.".replace(",", "."),
         "Faturamento": f_money(fat_vol), "Custos Totais": f_money(custo_vol), "Lucro Líquido": f_money(lucro_vol),
         "_class": ""},
        {"Estratégia": "Receita Máxima", "Preço": f_money(p_rec), "Volume": f"{q_rec:,} un.".replace(",", "."),
         "Faturamento": f_money(fat_rec), "Custos Totais": f_money(custo_rec), "Lucro Líquido": f_money(lucro_rec),
         "_class": ""},
        {"Estratégia": "Lucro Máximo (Recomendado)", "Preço": f_money(p_ideal),
         "Volume": f"{q_ideal:,} un.".replace(",", "."), "Faturamento": f_money(faturamento_ideal),
         "Custos Totais": f_money(custo_total_ideal), "Lucro Líquido": f_money(lucro_ideal), "_class": "highlight-row"},
        {"Estratégia": "Preço Atual / Teste", "Preço": f_money(p_test), "Volume": f"{q_test:,} un.".replace(",", "."),
         "Faturamento": f_money(fat_test), "Custos Totais": f_money(custo_test), "Lucro Líquido": f_money(lucro_test),
         "_class": ""},
    ]

    return {
        "p_ideal": p_ideal, "q_ideal": q_ideal, "lucro_ideal": lucro_ideal,
        "faturamento_ideal": faturamento_ideal, "custo_var_ideal": custo_var_ideal,
        "custo_total_ideal": custo_total_ideal, "sensibilidade_b": round(b, 4),
        "demanda_potencial_a": round(a, 2), "elasticidade_estimada": round(-b, 4),
        "margem_contrib_unit": round(margem_contrib_unit, 2), "margem_contrib_perc": round(margem_contrib_perc, 1),
        "ponto_equilibrio_unidades": ponto_equilibrio_unidades, "incremento_diario": incremento_diario,
        "p_range": p_range, "lucro_range": lucro_range, "receita_range": receita_range, "table_data": table_data
    }


# ==============================================================================
# LAYOUT CLARIÔ
# ==============================================================================
app.layout = html.Div([
    dcc.Store(id="stored-csv-data"),
    dcc.Download(id="download-sku-report"),

    # MODAL DE INGESTÃO DE VENDAS (SUBSTITUI O CARD ANTIGO)
    dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle("Ingestão de Dados", style={"fontWeight": "800", "color": "var(--clario-dark)"})),
            dbc.ModalBody([
                html.Div("Faça o upload do arquivo CSV contendo o histórico de vendas para abastecer o simulador.",
                         className="mb-4 text-muted", style={"fontSize": "14px"}),
                dcc.Upload(
                    id="upload-data",
                    style={
                        "border": "2px dashed #CBD5E1", "borderRadius": "12px",
                        "padding": "32px", "textAlign": "center", "cursor": "pointer",
                        "backgroundColor": "#F8FAFC", "transition": "all 0.3s ease"
                    },
                    children=html.Div([
                        html.I(className="bi bi-cloud-arrow-up fs-1 text-primary mb-2"),
                        html.Div("Arraste o arquivo CSV aqui", className="fw-bold text-dark",
                                 style={"fontSize": "15px"}),
                        html.Div("ou clique para buscar do computador", className="text-muted",
                                 style={"fontSize": "12px", "marginTop": "4px"})
                    ])
                ),
                html.Div(id="upload-status-msg", className="mt-3 text-center fw-bold", style={"fontSize": "13px"})
            ], style={"padding": "24px"}),
            dbc.ModalFooter(
                dbc.Button("Concluir e Fechar", id="close-upload-modal", className="btn-clario-dark ms-auto",
                           n_clicks=0)
            ),
        ],
        id="modal-upload", size="lg", is_open=False, centered=True
    ),

    # MODAL DA MATRIZ GLOBAL
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Matriz Global de Portfólio",
                                           style={"fontWeight": "800", "color": "var(--clario-dark)"})),
            dbc.ModalBody(id="global-matrix-content", style={"padding": "24px"}),
            dbc.ModalFooter(
                dbc.Button("Fechar", id="close-matrix-modal", className="btn-clario-light ms-auto", n_clicks=0)),
        ],
        id="modal-global-matrix", size="xl", is_open=False,
    ),

    html.Div(className="clario-sidebar", children=[
        html.Div([
            html.Div(className="clario-logo-container", children=[html.Span("clari", className="clario-logo-text"),
                                                                  html.Span("ô", className="clario-logo-accent")]),
            html.Div("Pricing Engine", className="text-muted fw-bold mb-4",
                     style={"fontSize": "11px", "letterSpacing": "1px", "textTransform": "uppercase"}),
            html.Div(className="clario-menu-item active",
                     children=[html.I(className="bi bi-grid-1x2-fill"), html.Span("Otimização SKU")]),
            html.Div(id="btn-global-matrix", className="clario-menu-item",
                     children=[html.I(className="bi bi-layers-fill"), html.Span("Matriz Global")]),
            html.Div(id="btn-report-sku", className="clario-menu-item",
                     children=[html.I(className="bi bi-file-earmark-pdf-fill"), html.Span("Exportar PDF")]),
        ]),
        html.Div(className="clario-user-profile", children=[
            html.Div("B", className="clario-avatar"),
            html.Div([html.Div("Brian Bezerra", className="fw-bold text-dark", style={"fontSize": "13px"}),
                      html.Div("Plano Premium", className="text-muted", style={"fontSize": "11px"})])
        ])
    ]),

    html.Div(className="clario-main-content", children=[
        html.Div(className="d-flex justify-content-between align-items-center mb-4", children=[
            html.Div([html.H2("Salut, Brian.", className="fw-bold mb-1", style={"letterSpacing": "-0.5px"}),
                      html.P("Visão consolidada da otimização de preço e margens de demanda.",
                             className="text-muted mb-0", style={"fontSize": "14px"})]),
            html.Button([html.I(className="bi bi-plus-lg me-2"), "Nova Simulação"], id="btn-new-sim",
                        className="btn-clario-dark")
        ]),

        # CARDS DE FILTRO E CONFIGURAÇÃO
        dbc.Row(className="g-3 mb-4", children=[
            dbc.Col(width=12, lg=4, md=4,
                    children=html.Div(className="clario-card h-100 d-flex flex-column justify-content-between",
                                      children=[
                                          html.Div(
                                              [html.Label("1. Período das Diárias", className="fw-bold text-dark mb-2",
                                                          style={"fontSize": "13px"}),
                                               dcc.DatePickerRange(id="date-picker-range", display_format="DD/MM/YYYY",
                                                                   start_date_placeholder_text="Início",
                                                                   end_date_placeholder_text="Fim", clearable=False,
                                                                   style={"width": "100%"}, className="mb-2")]),
                                          html.Div(id="date-range-info", className="text-muted",
                                                   style={"fontSize": "11px"}, children="Carregue o CSV para filtrar.")
                                      ])),
            dbc.Col(width=12, lg=4, md=4,
                    children=html.Div(className="clario-card h-100 d-flex flex-column justify-content-between",
                                      children=[
                                          html.Div([html.Label("2. Custo Fixo Empresa (R$/dia)",
                                                               className="fw-bold text-dark mb-2",
                                                               style={"fontSize": "13px"}),
                                                    dcc.Input(id="inputCompanyCF", type="number", value=1500,
                                                              placeholder="Ex: 1500", className="clario-input mb-2")]),
                                          html.Div("Custo fixo diário total a ser rateado.", className="text-muted",
                                                   style={"fontSize": "11px"})
                                      ])),
            dbc.Col(width=12, lg=4, md=4,
                    children=html.Div(className="clario-card h-100 d-flex flex-column justify-content-between",
                                      children=[
                                          html.Div([html.Label("3. Seleção do SKU", className="fw-bold text-dark mb-2",
                                                               style={"fontSize": "13px"}),
                                                    dcc.Dropdown(id="productSelect", placeholder="Aguardando CSV...",
                                                                 className="mb-2")]),
                                          html.Button("Carregar no Simulador", id="btnTransferParams",
                                                      className="btn-clario-dark w-100")
                                      ]))
        ]),

        # CARDS DE RESULTADO (COMEÇAM ZERADOS)
        dbc.Row(className="g-3 mb-4", children=[
            dbc.Col(width=12, md=4, children=html.Div(className="clario-card clario-kpi-card", children=[
                html.Div("PREÇO IDEAL (P*)", className="clario-kpi-title"),
                html.Div(id="kpi-preco-ideal", className="clario-kpi-value", children="R$ 0,00"),
                html.Div(id="kpi-sensibilidade", className="text-muted fw-bold", style={"fontSize": "12px"},
                         children="Sensibilidade (b): -")])),
            dbc.Col(width=12, md=4, children=html.Div(className="clario-card clario-kpi-card kpi-green", children=[
                html.Div("LUCRO LÍQUIDO DIÁRIO", className="clario-kpi-title"),
                html.Div(id="kpi-lucro-liquido", className="clario-kpi-value", style={"color": "var(--clario-green)"},
                         children="R$ 0,00"), html.Div(id="kpi-incremento", className="fw-bold",
                                                       style={"fontSize": "12px", "color": "var(--clario-green)"},
                                                       children="+R$ 0,00/dia vs base")])),
            dbc.Col(width=12, md=4, children=html.Div(className="clario-card clario-kpi-card kpi-orange", children=[
                html.Div("VOLUME ESTIMADO", className="clario-kpi-title"),
                html.Div(id="kpi-volume-estimado", className="clario-kpi-value", children="0 un."),
                html.Div(id="kpi-margem-unit", className="text-muted fw-bold", style={"fontSize": "12px"},
                         children="Margem Uni.: R$ 0,00")]))
        ]),

        dbc.Row(className="g-4", children=[
            dbc.Col(width=12, lg=4, children=html.Div(className="clario-card", children=[
                html.H6("Parâmetros do Modelo", className="fw-bold mb-3", style={"fontSize": "15px"}),
                html.Div([html.Label("Preço Mínimo Observado (R$)", className="fw-bold text-muted mb-1",
                                     style={"fontSize": "12px"}),
                          dcc.Input(id="inputPCurr", type="number", value=None, className="clario-input mb-3")]),
                html.Div([html.Label("Volume Médio no Preço Mínimo", className="fw-bold text-muted mb-1",
                                     style={"fontSize": "12px"}),
                          dcc.Input(id="inputQCurr", type="number", value=None, className="clario-input mb-3")]),
                html.Div([html.Label("Preço Máximo Observado (R$)", className="fw-bold text-muted mb-1",
                                     style={"fontSize": "12px"}),
                          dcc.Input(id="inputPTest", type="number", value=None, className="clario-input mb-3")]),
                html.Div([html.Label("Volume Médio no Preço Máximo", className="fw-bold text-muted mb-1",
                                     style={"fontSize": "12px"}),
                          dcc.Input(id="inputQTest", type="number", value=None, className="clario-input mb-3")]),
                html.Hr(style={"borderColor": "var(--clario-border)", "margin": "16px 0"}),
                html.Div([html.Label("Custo Fixo Rateado do SKU (R$/dia)", className="fw-bold text-muted mb-1",
                                     style={"fontSize": "12px"}),
                          dcc.Input(id="inputCustosFixos", type="number", value=None, className="clario-input mb-3")]),
                html.Div([html.Label("Custo Variável Unitário (CVU)", className="fw-bold text-muted mb-1",
                                     style={"fontSize": "12px"}),
                          dcc.Input(id="inputCvu", type="number", value=None, className="clario-input")]),
            ])),
            dbc.Col(width=12, lg=8, children=[
                html.Div(id="callout-summary", className="clario-card mb-4 py-3 px-4",
                         style={"backgroundColor": "var(--clario-orange-bg)", "borderColor": "#FFEDD5"},
                         children="Aguardando dados da simulação."),
                html.Div(className="clario-card mb-4", children=[
                    html.H6("Detalhamento Técnico dos Parâmetros", className="fw-bold mb-3",
                            style={"fontSize": "14px"}), dbc.Row(id="panel-technical-params", className="g-2")]),
                html.Div(className="clario-card mb-4", children=[
                    dcc.Graph(id="chartElasticity", config={"displayModeBar": False}, style={"height": "360px"})]),
                html.Div(className="clario-card", children=[
                    html.H6("Comparativo de Estratégias", className="fw-bold mb-3", style={"fontSize": "14px"}),
                    html.Div(id="table-container")])
            ])
        ])
    ])
])


# ==============================================================================
# CALLBACKS DA APLICAÇÃO
# ==============================================================================

# 0. ABRIR / FECHAR MODAL DE UPLOAD DE CSV
@app.callback(
    Output("modal-upload", "is_open"),
    [Input("btn-new-sim", "n_clicks"), Input("close-upload-modal", "n_clicks")],
    [State("modal-upload", "is_open")],
    prevent_initial_call=True
)
def toggle_upload_modal(n_open, n_close, is_open):
    if n_open or n_close:
        return not is_open
    return is_open


# 1. PROCESSAR CSV ENVIADO NO MODAL
@app.callback(
    [Output("stored-csv-data", "data"), Output("productSelect", "options"),
     Output("date-picker-range", "min_date_allowed"), Output("date-picker-range", "max_date_allowed"),
     Output("date-picker-range", "start_date"), Output("date-picker-range", "end_date"),
     Output("date-range-info", "children"), Output("upload-status-msg", "children")],
    [Input("upload-data", "contents")], [State("upload-data", "filename")], prevent_initial_call=True
)
def handle_csv_upload(contents, filename):
    if not contents:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    df = process_uploaded_csv(contents, filename)
    if df is None or "SKU" not in df.columns:
        return dash.no_update, [], None, None, None, None, "Erro ao processar o CSV.", html.Span("Erro ao ler CSV.",
                                                                                                 className="text-danger")

    options = [{"label": sku, "value": sku} for sku in sorted(df["SKU"].dropna().unique())]

    min_date_str, max_date_str = None, None
    if "Data_Dia" in df.columns and df["Data_Dia"].notna().any():
        df["Data_Dia"] = pd.to_datetime(df["Data_Dia"], errors="coerce")
        df = df.dropna(subset=["Data_Dia"])
        try:
            min_date = df["Data_Dia"].min().date()
            max_date = df["Data_Dia"].max().date()
            min_date_str, max_date_str = str(min_date), str(max_date)
            info_text = f"✓ {len(df):,} vendas ({df['SKU'].nunique()} SKUs) | {min_date.strftime('%d/%m/%Y')} a {max_date.strftime('%d/%m/%Y')}".replace(
                ",", ".")
            status_msg = html.Span([html.I(className="bi bi-check-circle-fill me-2"),
                                    f"Arquivo '{filename}' processado com sucesso! Feche esta janela."],
                                   className="text-success")
        except Exception:
            info_text = f"✓ {len(df):,} vendas carregadas.".replace(",", ".")
            status_msg = html.Span([html.I(className="bi bi-check-circle-fill me-2"), f"Arquivo '{filename}' lido."],
                                   className="text-success")
    else:
        info_text = f"✓ {len(df):,} vendas carregadas sem coluna de data.".replace(",", ".")
        status_msg = html.Span([html.I(className="bi bi-check-circle-fill me-2"), "Carregado sem datas."],
                               className="text-success")

    return df.to_json(date_format="iso",
                      orient="split"), options, min_date_str, max_date_str, min_date_str, max_date_str, info_text, status_msg


# 2. SELEÇÃO DE SKU NO SIMULADOR
@app.callback(
    [Output("inputPCurr", "value"), Output("inputQCurr", "value"), Output("inputPTest", "value"),
     Output("inputQTest", "value"), Output("inputCvu", "value"), Output("inputCustosFixos", "value")],
    [Input("btnTransferParams", "n_clicks")],
    [State("stored-csv-data", "data"), State("productSelect", "value"), State("date-picker-range", "start_date"),
     State("date-picker-range", "end_date"), State("inputCompanyCF", "value")],
    prevent_initial_call=True
)
def transfer_params_from_csv(n_clicks, stored_data, selected_sku, start_date, end_date, company_cf):
    if not stored_data or not selected_sku:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    df = pd.read_json(io.StringIO(stored_data), orient="split")

    if "Data_Dia" in df.columns:
        df["Data_Dia"] = pd.to_datetime(df["Data_Dia"], errors="coerce").dt.date
        df = df.dropna(subset=["Data_Dia"])

    if start_date and end_date and "Data_Dia" in df.columns:
        s_dt = pd.to_datetime(start_date).date()
        e_dt = pd.to_datetime(end_date).date()
        df = df[(df["Data_Dia"] >= s_dt) & (df["Data_Dia"] <= e_dt)]

    cf_diario_empresa = float(company_cf or 1500.0)
    kpis = get_product_kpis(df, selected_sku, cf_diario=cf_diario_empresa)

    if not kpis:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    return (
        kpis["p_min"], kpis["q_pmin"], kpis["p_max"], kpis["q_pmax"], kpis["cvu"], kpis["cf_rateado"]
    )


# 3. ATUALIZAÇÃO REATIVA DO SIMULADOR INDIVIDUAL (COM ZERO-STATE)
@app.callback(
    [Output("kpi-preco-ideal", "children"), Output("kpi-sensibilidade", "children"),
     Output("kpi-lucro-liquido", "children"), Output("kpi-incremento", "children"),
     Output("kpi-volume-estimado", "children"), Output("kpi-margem-unit", "children"),
     Output("callout-summary", "children"), Output("panel-technical-params", "children"),
     Output("chartElasticity", "figure"), Output("table-container", "children")],
    [Input("inputPCurr", "value"), Input("inputQCurr", "value"), Input("inputPTest", "value"),
     Input("inputQTest", "value"), Input("inputCustosFixos", "value"), Input("inputCvu", "value")]
)
def update_dashboard(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu):
    empty_fig = go.Figure().update_layout(template="plotly_white", xaxis=dict(visible=False), yaxis=dict(visible=False),
                                          annotations=[dict(text="Aguardando dados para simulação...", xref="paper",
                                                            yref="paper", showarrow=False,
                                                            font=dict(size=14, color="#94A3B8"))])

    # Trava: se algum parâmetro for nulo, a tela fica em repouso (zerada)
    if None in [p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu]:
        return "R$ 0,00", "-", "R$ 0,00", "-", "0 un.", "-", "Aguardando processamento do CSV ou entrada manual de parâmetros.", [], empty_fig, html.Div()

    res = calculate_pricing_model(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu)

    if res is None:
        return "R$ 0,00", "-", "R$ 0,00", "-", "0 un.", "-", "Insira parâmetros numéricos válidos.", [], empty_fig, html.Div()

    def f_m(val):
        if pd.isna(val): return "R$ 0,00"
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def f_q(val):
        if pd.isna(val): return "0 un."
        return f"{int(round(val)):,} un.".replace(",", ".")

    kpi_p_ideal = f_m(res['p_ideal'])
    kpi_sens = f"Sensibilidade (b): {res['sensibilidade_b']:.4f}"
    kpi_lucro = f_m(res['lucro_ideal'])
    kpi_inc = f"+{f_m(res['incremento_diario'])}/dia vs base"
    kpi_vol = f_q(res['q_ideal'])
    kpi_margem = f"Margem Uni.: {f_m(res['margem_contrib_unit'])}"

    callout = html.Span([
        html.I(className="bi bi-info-circle-fill me-2", style={"color": "var(--clario-orange)"}),
        f"O Preço Ideal de ", html.Strong(f_m(res['p_ideal'])),
        f" estimula uma demanda diária de ", html.Strong(f_q(res['q_ideal'])),
        f", projetando um Lucro Líquido de ", html.Strong(f_m(res['lucro_ideal'])),
        f" (ganho adicional de ", html.Strong(f"+{f_m(res['incremento_diario'])}/dia"), f")."
    ])

    tech_params_cards = [
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px",
                   "border": "1px solid #E2E8F0"},
            children=[html.Div("Elasticidade (ε)",
                               style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)",
                                      "textTransform": "uppercase"}),
                      html.Div(f"{res['elasticidade_estimada']:.4f}",
                               style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-dark)"})])),
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px",
                   "border": "1px solid #E2E8F0"},
            children=[html.Div("Margem Contrib. (R$)",
                               style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)",
                                      "textTransform": "uppercase"}),
                      html.Div(f_m(res['margem_contrib_unit']),
                               style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-green)"})])),
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px",
                   "border": "1px solid #E2E8F0"},
            children=[html.Div("Margem Contrib. (%)",
                               style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)",
                                      "textTransform": "uppercase"}),
                      html.Div(f"{res['margem_contrib_perc']:.1f}%",
                               style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-green)"})])),
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px",
                   "border": "1px solid #E2E8F0"},
            children=[html.Div("Break-even (Unidades)",
                               style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)",
                                      "textTransform": "uppercase"}),
                      html.Div(f_q(res['ponto_equilibrio_unidades']),
                               style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-dark)"})])),
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=res["p_range"], y=res["receita_range"], mode="lines", name="Faturamento",
                             line=dict(color="#94A3B8", width=1.5, dash="dash")))
    fig.add_trace(go.Scatter(x=res["p_range"], y=res["lucro_range"], mode="lines", name="Lucro Líquido", fill="tozeroy",
                             fillcolor="rgba(255, 107, 53, 0.08)", line=dict(color="#FF6B35", width=3)))
    fig.add_trace(go.Scatter(x=[res["p_ideal"]], y=[res["lucro_ideal"]], mode="markers+text", name="Preço Ideal (P*)",
                             marker=dict(color="#0F172A", size=12, symbol="circle"),
                             text=[f"P* = {f_m(res['p_ideal'])}"], textposition="top center",
                             textfont=dict(color="#0F172A", size=12, family="-apple-system, sans-serif")))
    fig.add_vline(x=res["p_ideal"], line_width=1, line_dash="dot", line_color="#FF6B35")

    fig.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=20, r=20, t=30, b=20),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      xaxis=dict(title="Preço Praticado (R$)", gridcolor="#F1F5F9"),
                      yaxis=dict(title="Valor Financeiro (R$)", gridcolor="#F1F5F9"))

    rows = [html.Tr(className=r["_class"],
                    children=[html.Td(r["Estratégia"]), html.Td(r["Preço"]), html.Td(r["Volume"]),
                              html.Td(r["Faturamento"]), html.Td(r["Custos Totais"]), html.Td(r["Lucro Líquido"])]) for
            r in res["table_data"]]
    table = html.Table(className="clario-table", children=[html.Thead(html.Tr(
        [html.Th("Estratégia"), html.Th("Preço"), html.Th("Volume"), html.Th("Faturamento"), html.Th("Custos Totais"),
         html.Th("Lucro Líquido")])), html.Tbody(rows)])

    return kpi_p_ideal, kpi_sens, kpi_lucro, kpi_inc, kpi_vol, kpi_margem, callout, tech_params_cards, fig, table


# 4. EXPORTAÇÃO DO RELATÓRIO PDF
@app.callback(
    Output("download-sku-report", "data"),
    Input("btn-report-sku", "n_clicks"),
    [State("productSelect", "value"), State("inputPCurr", "value"), State("inputQCurr", "value"),
     State("inputPTest", "value"), State("inputQTest", "value"), State("inputCustosFixos", "value"),
     State("inputCvu", "value")],
    prevent_initial_call=True
)
def export_sku_report(n_clicks, selected_sku, p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu):
    if not selected_sku: return dash.no_update
    res = calculate_pricing_model(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu)
    if not res: return dash.no_update
    pdf_bytes = generate_clario_pdf(res, selected_sku, p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu)
    return dcc.send_bytes(pdf_bytes,
                          f"Diagnostico_Executivo_{selected_sku.split(' - ')[0] if ' - ' in selected_sku else selected_sku}.pdf")


# ==============================================================================
# 5. MATRIZ GLOBAL (VISÃO EXECUTIVA TOTALIZADA NO PERÍODO) - CLARIÔ UI
# ==============================================================================
@app.callback(
    [Output("modal-global-matrix", "is_open"), Output("global-matrix-content", "children")],
    [Input("btn-global-matrix", "n_clicks"), Input("close-matrix-modal", "n_clicks")],
    [State("modal-global-matrix", "is_open"), State("stored-csv-data", "data"), State("inputCompanyCF", "value"),
     State("date-picker-range", "start_date"), State("date-picker-range", "end_date")],
    prevent_initial_call=True
)
def toggle_global_matrix(btn_open, btn_close, is_open, stored_data, company_cf, start_date, end_date):
    ctx = dash.callback_context
    if not ctx.triggered: return is_open, dash.no_update
    if ctx.triggered[0]["prop_id"].split(".")[0] == "close-matrix-modal": return False, dash.no_update
    if not stored_data: return True, html.Div("Por favor, carregue o CSV primeiro na tela principal.",
                                              className="text-center text-muted py-5 fw-bold")

    df = pd.read_json(io.StringIO(stored_data), orient="split")

    if "Data_Dia" in df.columns:
        df["Data_Dia"] = pd.to_datetime(df["Data_Dia"], errors="coerce").dt.date
        df = df.dropna(subset=["Data_Dia"])

    # Contagem Absoluta do Período Filtrado
    if start_date and end_date and "Data_Dia" in df.columns:
        s_dt = pd.to_datetime(start_date).date()
        e_dt = pd.to_datetime(end_date).date()
        df = df[(df["Data_Dia"] >= s_dt) & (df["Data_Dia"] <= e_dt)]
        total_dias_periodo = max(1, (e_dt - s_dt).days + 1)
    elif "Data_Dia" in df.columns and not df.empty:
        d_min = df['Data_Dia'].min()
        d_max = df['Data_Dia'].max()
        total_dias_periodo = max(1, (d_max - d_min).days + 1)
    else:
        total_dias_periodo = 1

    if df.empty: return True, html.Div("Nenhuma venda no período.", className="text-center text-muted py-5")

    skus_unicos = df["SKU"].dropna().unique()
    cf_total = float(company_cf or 1500.0)
    cf_rateado_sku = cf_total / max(1, len(skus_unicos))

    if 'Custo' not in df.columns: df['Custo'] = 40.0
    df['Faturamento'] = df['Preco'] * df['Volume']
    df['Custo_Total'] = df['Custo'] * df['Volume']

    daily_df = df.groupby(['SKU', 'Data_Dia']).agg(
        {'Volume': 'sum', 'Faturamento': 'sum', 'Custo_Total': 'sum'}).reset_index()

    # Acumuladores de Média Diária
    vol_base_diario, rec_base_diario, luc_base_diario, mc_base_diario = 0, 0, 0, 0
    vol_opt_diario, rec_opt_diario, luc_opt_diario, mc_opt_diario = 0, 0, 0, 0
    rows = []

    for sku in sorted(skus_unicos):
        sku_daily = daily_df[(daily_df["SKU"] == sku) & (daily_df["Volume"] > 0)].copy()
        if sku_daily.empty: continue

        sku_daily['Preco_Medio'] = sku_daily['Faturamento'] / sku_daily['Volume']

        # Diluição Financeira Diária Exata
        fat_total_sku = sku_daily['Faturamento'].sum()
        vol_total_sku = sku_daily['Volume'].sum()
        cv_total_sku = sku_daily['Custo_Total'].sum()

        fat_diario = fat_total_sku / total_dias_periodo
        vol_diario = vol_total_sku / total_dias_periodo
        cv_diario = cv_total_sku / total_dias_periodo

        p_medio = fat_total_sku / vol_total_sku if vol_total_sku > 0 else 0
        cvu = cv_total_sku / vol_total_sku if vol_total_sku > 0 else 0

        mc_diaria = fat_diario - cv_diario
        lucro_diario = mc_diaria - cf_rateado_sku

        vol_base_diario += vol_diario
        rec_base_diario += fat_diario
        luc_base_diario += lucro_diario
        mc_base_diario += mc_diaria

        # Lógica de Modelagem com Trava Anti-Float
        sku_daily['Preco_Base'] = sku_daily['Preco_Medio'].round(2)
        resumo_precos = sku_daily.groupby('Preco_Base').agg({'Volume': 'mean'}).reset_index()

        p_min = float(resumo_precos['Preco_Base'].min())
        p_max = float(resumo_precos['Preco_Base'].max())

        try:
            q_pmin = float(resumo_precos.loc[resumo_precos['Preco_Base'] == p_min, 'Volume'].iloc[0])
            q_pmax = float(resumo_precos.loc[resumo_precos['Preco_Base'] == p_max, 'Volume'].iloc[0])
        except (IndexError, KeyError):
            q_pmin = sku_daily['Volume'].mean()
            q_pmax = q_pmin * 0.8

        if pd.isna(q_pmin) or pd.isna(q_pmax) or p_max <= p_min or q_pmax >= q_pmin:
            b = 1.25
        else:
            try:
                b_calc = -(np.log(q_pmax) - np.log(q_pmin)) / (np.log(p_max) - np.log(p_min))
                if np.isnan(b_calc) or np.isinf(b_calc):
                    b = 1.25
                else:
                    b = min(max(b_calc, 0.5), 3.0)
            except:
                b = 1.25

        a = vol_diario / (p_medio ** (-b)) if p_medio > 0 else 0
        p_range = np.linspace(max(cvu * 1.05, p_min * 0.5), p_max * 1.6, 100)
        q_range = a * (p_range ** (-b))

        receita_sim = p_range * q_range
        custo_sim = cvu * q_range
        lucro_sim = receita_sim - custo_sim - cf_rateado_sku

        idx_opt = np.argmax(lucro_sim)
        p_ideal = float(p_range[idx_opt])
        q_ideal = float(q_range[idx_opt])
        fat_ideal = float(receita_sim[idx_opt])
        mc_ideal = fat_ideal - float(custo_sim[idx_opt])
        lucro_ideal = float(lucro_sim[idx_opt])

        if lucro_ideal <= lucro_diario or p_ideal < cvu:
            p_ideal = p_medio
            q_ideal = vol_diario
            fat_ideal = fat_diario
            mc_ideal = mc_diaria
            lucro_ideal = lucro_diario

        vol_opt_diario += q_ideal
        rec_opt_diario += fat_ideal
        luc_opt_diario += lucro_ideal
        mc_opt_diario += mc_ideal

        upside_diario = max(0.0, lucro_ideal - lucro_diario)

        # RENDERIZAÇÃO DE STATUS HTML PARA A TABELA
        if lucro_diario < 0:
            status = "<i class='bi bi-exclamation-triangle-fill' style='color: #EF4444; margin-right: 6px;'></i> Alerta de Margem"
        elif upside_diario > 15.0:
            status = "<i class='bi bi-rocket-fill' style='color: #FF6B35; margin-right: 6px;'></i> Oportunidade"
        elif (mc_diaria / fat_diario * 100 if fat_diario > 0 else 0) > 45.0:
            status = "<i class='bi bi-star-fill' style='color: #0284C7; margin-right: 6px;'></i> Gerador de Margem"
        else:
            status = "<i class='bi bi-arrow-repeat' style='color: #64748B; margin-right: 6px;'></i> Estável"

        def f_m(val):
            if pd.isna(val): return "R$ 0,00"
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def f_q(val):
            if pd.isna(val): return "0 un."
            return f"{int(round(val)):,} un.".replace(",", ".")

        rows.append({
            "Produto / SKU": sku,
            "Preço Atual": f_m(p_medio),
            "Preço Ideal": f_m(p_ideal),
            "Vol Atual": f_q(vol_diario * total_dias_periodo),
            "Vol Otimizado": f_q(q_ideal * total_dias_periodo),
            "Lucro Atual": f_m(lucro_diario * total_dias_periodo),
            "Lucro Otimizado": f_m(lucro_ideal * total_dias_periodo),
            "Upside": f"+{f_m(upside_diario * total_dias_periodo)}" if upside_diario > 0 else "-",
            "Estratégia": status
        })

    def global_money(val):
        if pd.isna(val): return "R$ 0,00"
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def global_vol(val):
        if pd.isna(val): return "0 un."
        return f"{int(round(val)):,} un.".replace(",", ".")

    # CÁLCULO FINAL EXECUTIVO (TOTALIZADO NO PERÍODO)
    vol_base_total = vol_base_diario * total_dias_periodo
    rec_base_total = rec_base_diario * total_dias_periodo
    luc_base_total = luc_base_diario * total_dias_periodo

    vol_opt_total = vol_opt_diario * total_dias_periodo
    rec_opt_total = rec_opt_diario * total_dias_periodo
    luc_opt_total = luc_opt_diario * total_dias_periodo

    ganho_total_periodo = (luc_opt_diario - luc_base_diario) * total_dias_periodo

    margem_base_pct = (mc_base_diario / rec_base_diario * 100) if rec_base_diario > 0 else 0
    margem_opt_pct = (mc_opt_diario / rec_opt_diario * 100) if rec_opt_diario > 0 else 0

    clario_font = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif"

    def make_card(t, v, border_color, text_color):
        return html.Div(className="clario-card p-3 text-center d-flex flex-column justify-content-center",
                        style={"borderTop": f"4px solid {border_color}", "height": "110px",
                               "boxShadow": "0 2px 10px -2px rgba(15, 23, 42, 0.03)"},
                        children=[html.Div(t, style={"fontSize": "11px", "fontWeight": "700",
                                                     "color": "var(--clario-text-muted)", "letterSpacing": "0.6px",
                                                     "textTransform": "uppercase"}),
                                  html.Div(v, style={"fontSize": "26px", "fontWeight": "800", "color": text_color,
                                                     "marginTop": "8px", "letterSpacing": "-0.5px"})])

    fig_comp = go.Figure(data=[
        go.Bar(name='Cenário Atual', x=['Faturamento', 'Lucro Líquido'], y=[rec_base_total, luc_base_total],
               marker_color='#0F172A', text=[global_money(rec_base_total), global_money(luc_base_total)],
               textposition='auto'),
        go.Bar(name='Cenário Otimizado', x=['Faturamento', 'Lucro Líquido'], y=[rec_opt_total, luc_opt_total],
               marker_color='#FF6B35', text=[global_money(rec_opt_total), global_money(luc_opt_total)],
               textposition='auto')
    ])

    fig_comp.update_layout(barmode='group', template="plotly_white", height=340, margin=dict(l=10, r=10, t=40, b=20),
                           legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
                           font=dict(family=clario_font, color="#0F172A", size=12),
                           hoverlabel=dict(font_family=clario_font))

    # LEGENDA PREMIUM DA MATRIZ
    legenda_estrategia = html.Div(
        className="d-flex align-items-center flex-wrap mb-4 p-3",
        style={"backgroundColor": "#F8FAFC", "borderRadius": "10px", "border": "1px solid #E2E8F0", "fontSize": "13px"},
        children=[
            html.Span("LEGENDA ESTRATÉGICA:", className="fw-bold me-4",
                      style={"color": "#64748B", "letterSpacing": "0.5px", "fontSize": "11px"}),
            html.Div(className="d-flex align-items-center me-4", children=[
                html.I(className="bi bi-exclamation-triangle-fill me-2",
                       style={"color": "#EF4444", "fontSize": "15px"}),
                html.Span("Alerta de Margem", style={"fontWeight": "600", "color": "#0F172A"})
            ]),
            html.Div(className="d-flex align-items-center me-4", children=[
                html.I(className="bi bi-rocket-fill me-2", style={"color": "#FF6B35", "fontSize": "15px"}),
                html.Span("Oportunidade", style={"fontWeight": "600", "color": "#0F172A"})
            ]),
            html.Div(className="d-flex align-items-center me-4", children=[
                html.I(className="bi bi-star-fill me-2", style={"color": "#0284C7", "fontSize": "15px"}),
                html.Span("Gerador", style={"fontWeight": "600", "color": "#0F172A"})
            ]),
            html.Div(className="d-flex align-items-center", children=[
                html.I(className="bi bi-arrow-repeat me-2", style={"color": "#64748B", "fontSize": "15px"}),
                html.Span("Estável", style={"fontWeight": "600", "color": "#0F172A"})
            ]),
        ]
    )

    table_columns = [
        {"name": col, "id": col} if col != "Estratégia" else {"name": col, "id": col, "presentation": "markdown"}
        for col in rows[0].keys()
    ]

    content = html.Div([
        dbc.Row([dbc.Col(html.Div(className="clario-card p-4 text-center mb-4",
                                  style={"backgroundColor": "var(--clario-orange-bg)",
                                         "border": "1px solid rgba(255, 107, 53, 0.25)"},
                                  children=[
                                      html.Div(f"POTENCIAL DE GANHO NO PERÍODO ({total_dias_periodo} DIAS)",
                                               style={"fontSize": "12px", "fontWeight": "800",
                                                      "color": "var(--clario-orange)", "letterSpacing": "0.5px"}),
                                      html.Div(f"+{global_money(ganho_total_periodo)}",
                                               style={"fontSize": "32px", "fontWeight": "800",
                                                      "color": "var(--clario-orange)", "marginTop": "6px",
                                                      "letterSpacing": "-1px"})]), width=12)]),

        html.Div(
            f"Diagnóstico de {len(skus_unicos)} SKUs distribuídos em uma janela de {total_dias_periodo} dias. Custo Fixo Diário de {global_money(cf_total)} rateado por presença na base.",
            className="text-muted mb-4", style={"fontSize": "13px", "fontWeight": "500"}),

        html.H6(f"Cenário Atual (Total em {total_dias_periodo} dias)", className="fw-bold mb-3",
                style={"fontSize": "15px", "color": "var(--clario-dark)", "letterSpacing": "-0.3px"}),
        dbc.Row([
            dbc.Col(
                make_card("Faturamento Acumulado", global_money(rec_base_total), "#64748B", "var(--clario-text-muted)"),
                width=3),
            dbc.Col(make_card("Margem Média Portfólio", f"{margem_base_pct:.1f}%", "#0284C7", "var(--clario-blue)"),
                    width=3),
            dbc.Col(make_card("Lucro Líq. Acumulado", global_money(luc_base_total), "#10B981", "var(--clario-green)"),
                    width=3),
            dbc.Col(make_card("Volume Venda Acumulado", global_vol(vol_base_total), "#0F172A", "var(--clario-dark)"),
                    width=3)
        ], className="mb-4 g-3"),

        html.H6(f"Cenário Otimizado (Total em {total_dias_periodo} dias)", className="fw-bold mb-3",
                style={"fontSize": "15px", "color": "var(--clario-dark)", "letterSpacing": "-0.3px"}),
        dbc.Row([
            dbc.Col(
                make_card("Faturamento Otimizado", global_money(rec_opt_total), "#64748B", "var(--clario-text-muted)"),
                width=3),
            dbc.Col(make_card("Margem Otimizada", f"{margem_opt_pct:.1f}%", "#0284C7", "var(--clario-blue)"), width=3),
            dbc.Col(make_card("Lucro Otimizado", global_money(luc_opt_total), "#10B981", "var(--clario-green)"),
                    width=3),
            dbc.Col(make_card("Volume Otimizado", global_vol(vol_opt_total), "#0F172A", "var(--clario-dark)"), width=3)
        ], className="mb-5 g-3"),

        dbc.Row([
            dbc.Col([html.H6("Comparativo Visual", className="fw-bold mb-3",
                             style={"fontSize": "15px", "color": "var(--clario-dark)", "letterSpacing": "-0.3px"}),
                     html.Div(dcc.Graph(figure=fig_comp, config={"displayModeBar": False}),
                              className="clario-card p-2")], md=4),

            dbc.Col([
                html.H6("Detalhamento por SKU (Acumulado no Período)", className="fw-bold mb-3",
                        style={"fontSize": "15px", "color": "var(--clario-dark)", "letterSpacing": "-0.3px"}),
                legenda_estrategia,
                dash_table.DataTable(
                    data=rows,
                    columns=table_columns,
                    filter_action="native",
                    sort_action="native",
                    page_size=8,
                    markdown_options={"html": True},
                    css=[{"selector": "p", "rule": "margin: 0px;"}],
                    style_table={"overflowX": "auto", "border": "1px solid var(--clario-border)",
                                 "borderRadius": "12px"},
                    style_header={"backgroundColor": "#F8FAFC", "fontWeight": "700", "color": "#64748B",
                                  "fontSize": "11px", "textTransform": "uppercase", "letterSpacing": "0.5px",
                                  "borderBottom": "2px solid #E2E8F0", "fontFamily": clario_font},
                    style_cell={"padding": "12px 14px", "textAlign": "left", "fontFamily": clario_font,
                                "fontSize": "13.5px", "color": "#0F172A", "borderBottom": "1px solid #F1F5F9"},
                    style_filter={"backgroundColor": "#FFFFFF", "color": "#94A3B8"},
                    style_data_conditional=[
                        {"if": {"column_id": "Upside"}, "color": "#10B981", "fontWeight": "800"},
                        {"if": {"filter_query": '{Estratégia} contains "Oportunidade"', "column_id": "Estratégia"},
                         "color": "#FF6B35", "fontWeight": "700"},
                        {"if": {"filter_query": '{Estratégia} contains "Alerta"', "column_id": "Estratégia"},
                         "color": "#EF4444", "fontWeight": "700"},
                        {"if": {"filter_query": '{Estratégia} contains "Gerador"', "column_id": "Estratégia"},
                         "color": "#0284C7", "fontWeight": "700"}
                    ]
                )
            ], md=8)
        ])
    ])
    return True, content


if __name__ == "__main__":
    app.run(debug=True, port=8050)