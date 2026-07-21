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
def calculate_pricing_model(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu):
    try:
        p_min = float(p_min) if p_min is not None else 100.0
        q_pmin = float(q_pmin) if q_pmin is not None else 10.0
        p_max = float(p_max) if p_max is not None else 115.0
        q_pmax = float(q_pmax) if q_pmax is not None else 8.5
        custos_fixos = float(custos_fixos) if custos_fixos is not None else 0.0
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

    if q_pmax >= q_pmin:
        b = 1.25
    else:
        try:
            b = -(np.log(q_pmax) - np.log(q_pmin)) / (np.log(p_max) - np.log(p_min))
            if np.isnan(b) or np.isinf(b) or b <= 0:
                b = 1.25
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
        {
            "Estratégia": "Volume (Maior Desconto)",
            "Preço": f_money(p_vol),
            "Volume": f"{q_vol:,} un.".replace(",", "."),
            "Faturamento": f_money(fat_vol),
            "Custos Totais": f_money(custo_vol),
            "Lucro Líquido": f_money(lucro_vol),
            "_class": ""
        },
        {
            "Estratégia": "Receita Máxima",
            "Preço": f_money(p_rec),
            "Volume": f"{q_rec:,} un.".replace(",", "."),
            "Faturamento": f_money(fat_rec),
            "Custos Totais": f_money(custo_rec),
            "Lucro Líquido": f_money(lucro_rec),
            "_class": ""
        },
        {
            "Estratégia": "Lucro Máximo (Recomendado)",
            "Preço": f_money(p_ideal),
            "Volume": f"{q_ideal:,} un.".replace(",", "."),
            "Faturamento": f_money(faturamento_ideal),
            "Custos Totais": f_money(custo_total_ideal),
            "Lucro Líquido": f_money(lucro_ideal),
            "_class": "highlight-row"
        },
        {
            "Estratégia": "Preço Atual / Teste",
            "Preço": f_money(p_test),
            "Volume": f"{q_test:,} un.".replace(",", "."),
            "Faturamento": f_money(fat_test),
            "Custos Totais": f_money(custo_test),
            "Lucro Líquido": f_money(lucro_test),
            "_class": ""
        },
    ]

    return {
        "p_ideal": p_ideal,
        "q_ideal": q_ideal,
        "lucro_ideal": lucro_ideal,
        "faturamento_ideal": faturamento_ideal,
        "custo_var_ideal": custo_var_ideal,
        "custo_total_ideal": custo_total_ideal,
        "sensibilidade_b": round(b, 4),
        "demanda_potencial_a": round(a, 2),
        "elasticidade_estimada": round(-b, 4),
        "margem_contrib_unit": round(margem_contrib_unit, 2),
        "margem_contrib_perc": round(margem_contrib_perc, 1),
        "ponto_equilibrio_unidades": ponto_equilibrio_unidades,
        "incremento_diario": incremento_diario,
        "p_range": p_range,
        "lucro_range": lucro_range,
        "receita_range": receita_range,
        "table_data": table_data
    }


# ==============================================================================
# LAYOUT CLARIÔ
# ==============================================================================
app.layout = html.Div(
    children=[
        dcc.Store(id="stored-csv-data"),
        dcc.Download(id="download-sku-report"),

        # MODAL MATRIZ GLOBAL
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Matriz Global de Portfólio")),
                dbc.ModalBody(id="global-matrix-content"),
                dbc.ModalFooter(
                    dbc.Button("Fechar", id="close-matrix-modal", className="btn-clario-light ms-auto", n_clicks=0)
                ),
            ],
            id="modal-global-matrix",
            size="xl",
            is_open=False,
        ),

        # SIDEBAR LATERAL CLARIÔ
        html.Div(
            className="clario-sidebar",
            children=[
                html.Div([
                    # LOGO CLARIÔ
                    html.Div(
                        className="clario-logo-container",
                        children=[
                            html.Span("clari", className="clario-logo-text"),
                            html.Span("ô", className="clario-logo-accent")
                        ]
                    ),
                    html.Div("Pricing Engine", className="text-muted fw-bold mb-4", style={"fontSize": "11px", "letterSpacing": "1px", "textTransform": "uppercase"}),

                    # MENUS DE NAVEGAÇÃO
                    html.Div(
                        className="clario-menu-item active",
                        children=[
                            html.I(className="bi bi-grid-1x2-fill"),
                            html.Span("Otimização SKU")
                        ]
                    ),
                    html.Div(
                        id="btn-global-matrix",
                        className="clario-menu-item",
                        children=[
                            html.I(className="bi bi-layers-fill"),
                            html.Span("Matriz Global")
                        ]
                    ),
                    html.Div(
                        id="btn-report-sku",
                        className="clario-menu-item",
                        children=[
                            html.I(className="bi bi-file-earmark-pdf-fill"),
                            html.Span("Exportar PDF")
                        ]
                    ),
                ]),

                # PERFIL DO USUÁRIO NO RODAPÉ DA SIDEBAR
                html.Div(
                    className="clario-user-profile",
                    children=[
                        html.Div("B", className="clario-avatar"),
                        html.Div([
                            html.Div("Brian Bezerra", className="fw-bold text-dark", style={"fontSize": "13px"}),
                            html.Div("Plano Premium", className="text-muted", style={"fontSize": "11px"})
                        ])
                    ]
                )
            ]
        ),

        # ÁREA DE CONTEÚDO PRINCIPAL
        html.Div(
            className="clario-main-content",
            children=[
                # HEADER SUPERIOR
                html.Div(
                    className="d-flex justify-content-between align-items-center mb-4",
                    children=[
                        html.Div([
                            html.H2("Salut, Brian.", className="fw-bold mb-1", style={"letterSpacing": "-0.5px"}),
                            html.P("Visão consolidada da otimização de preço e margens de demanda.", className="text-muted mb-0", style={"fontSize": "14px"})
                        ]),

                        html.Button(
                            [html.I(className="bi bi-plus-lg me-2"), "Nova Simulação"],
                            className="btn-clario-dark"
                        )
                    ]
                ),

                # SEÇÃO DE INGESTÃO, CONTROLE DE CUSTO FIXO E SELEÇÃO (4 COLUNAS)
                dbc.Row(
                    className="g-3 mb-4",
                    children=[
                        # STEP 1: CSV UPLOAD
                        dbc.Col(
                            width=12, lg=3, md=6,
                            children=html.Div(
                                className="clario-card h-100 d-flex flex-column justify-content-between",
                                children=[
                                    html.Div([
                                        html.Label("1. Ingestão de Vendas", className="fw-bold text-dark mb-2", style={"fontSize": "13px"}),
                                        dcc.Upload(
                                            id="upload-data",
                                            style={"border": "2px dashed #E2E8F0", "borderRadius": "10px", "padding": "12px", "textAlign": "center", "cursor": "pointer", "backgroundColor": "#F8FAFC"},
                                            children=html.Div([
                                                html.I(className="bi bi-cloud-arrow-up fs-4 text-primary mb-1"),
                                                html.Div("Arraste o CSV aqui", className="fw-bold", style={"fontSize": "12px"}),
                                                html.Div("ou clique para buscar", className="text-muted", style={"fontSize": "11px"})
                                            ])
                                        )
                                    ])
                                ]
                            )
                        ),

                        # STEP 2: FILTRO DE DATAS
                        dbc.Col(
                            width=12, lg=3, md=6,
                            children=html.Div(
                                className="clario-card h-100 d-flex flex-column justify-content-between",
                                children=[
                                    html.Div([
                                        html.Label("2. Período das Diárias", className="fw-bold text-dark mb-2", style={"fontSize": "13px"}),
                                        dcc.DatePickerRange(
                                            id="date-picker-range",
                                            display_format="DD/MM/YYYY",
                                            start_date_placeholder_text="Início",
                                            end_date_placeholder_text="Fim",
                                            clearable=False,
                                            style={"width": "100%"},
                                            className="mb-2"
                                        )
                                    ]),
                                    html.Div(
                                        id="date-range-info",
                                        className="text-muted",
                                        style={"fontSize": "11px"},
                                        children="Carregue o CSV para filtrar."
                                    )
                                ]
                            )
                        ),

                        # STEP 3: CUSTO FIXO EMPRESA (NOVO CAMPO INFORMADO PELO USUÁRIO)
                        dbc.Col(
                            width=12, lg=3, md=6,
                            children=html.Div(
                                className="clario-card h-100 d-flex flex-column justify-content-between",
                                children=[
                                    html.Div([
                                        html.Label("3. Custo Fixo Empresa (R$/dia)", className="fw-bold text-dark mb-2", style={"fontSize": "13px"}),
                                        dcc.Input(
                                            id="inputCompanyCF",
                                            type="number",
                                            value=1500,
                                            placeholder="Ex: 1500",
                                            className="clario-input mb-2"
                                        )
                                    ]),
                                    html.Div("Custo fixo diário total a ser rateado.", className="text-muted", style={"fontSize": "11px"})
                                ]
                            )
                        ),

                        # STEP 4: SELEÇÃO DE SKU
                        dbc.Col(
                            width=12, lg=3, md=6,
                            children=html.Div(
                                className="clario-card h-100 d-flex flex-column justify-content-between",
                                children=[
                                    html.Div([
                                        html.Label("4. Seleção do SKU", className="fw-bold text-dark mb-2", style={"fontSize": "13px"}),
                                        dcc.Dropdown(
                                            id="productSelect",
                                            placeholder="Aguardando CSV...",
                                            className="mb-2"
                                        )
                                    ]),
                                    html.Button(
                                        "Carregar no Simulador",
                                        id="btnTransferParams",
                                        className="btn-clario-dark w-100"
                                    )
                                ]
                            )
                        )
                    ]
                ),

                # SEÇÃO DE KPIS HERO
                dbc.Row(
                    className="g-3 mb-4",
                    children=[
                        dbc.Col(
                            width=12, md=4,
                            children=html.Div(
                                className="clario-card clario-kpi-card",
                                children=[
                                    html.Div("PREÇO IDEAL (P*)", className="clario-kpi-title"),
                                    html.Div(id="kpi-preco-ideal", className="clario-kpi-value", children="R$ 0,00"),
                                    html.Div(id="kpi-sensibilidade", className="text-muted fw-bold", style={"fontSize": "12px"}, children="Sensibilidade (b): -")
                                ]
                            )
                        ),
                        dbc.Col(
                            width=12, md=4,
                            children=html.Div(
                                className="clario-card clario-kpi-card kpi-green",
                                children=[
                                    html.Div("LUCRO LÍQUIDO DIÁRIO", className="clario-kpi-title"),
                                    html.Div(id="kpi-lucro-liquido", className="clario-kpi-value", style={"color": "var(--clario-green)"}, children="R$ 0,00"),
                                    html.Div(id="kpi-incremento", className="fw-bold", style={"fontSize": "12px", "color": "var(--clario-green)"}, children="+R$ 0,00/dia vs base")
                                ]
                            )
                        ),
                        dbc.Col(
                            width=12, md=4,
                            children=html.Div(
                                className="clario-card clario-kpi-card kpi-orange",
                                children=[
                                    html.Div("VOLUME ESTIMADO", className="clario-kpi-title"),
                                    html.Div(id="kpi-volume-estimado", className="clario-kpi-value", children="0 un."),
                                    html.Div(id="kpi-margem-unit", className="text-muted fw-bold", style={"fontSize": "12px"}, children="Margem Uni.: R$ 0,00")
                                ]
                            )
                        )
                    ]
                ),

                # PAINEL CENTRAL DE PARÂMETROS E GRÁFICO
                dbc.Row(
                    className="g-4",
                    children=[
                        # INPUTS DO SIMULADOR
                        dbc.Col(
                            width=12, lg=4,
                            children=html.Div(
                                className="clario-card",
                                children=[
                                    html.H6("Parâmetros do Modelo", className="fw-bold mb-3", style={"fontSize": "15px"}),

                                    html.Div([
                                        html.Label("Preço Mínimo Observado (R$)", className="fw-bold text-muted mb-1", style={"fontSize": "12px"}),
                                        dcc.Input(id="inputPCurr", type="number", value=150, className="clario-input mb-3")
                                    ]),

                                    html.Div([
                                        html.Label("Volume Médio no Preço Mínimo", className="fw-bold text-muted mb-1", style={"fontSize": "12px"}),
                                        dcc.Input(id="inputQCurr", type="number", value=70, className="clario-input mb-3")
                                    ]),

                                    html.Div([
                                        html.Label("Preço Máximo Observado (R$)", className="fw-bold text-muted mb-1", style={"fontSize": "12px"}),
                                        dcc.Input(id="inputPTest", type="number", value=180, className="clario-input mb-3")
                                    ]),

                                    html.Div([
                                        html.Label("Volume Médio no Preço Máximo", className="fw-bold text-muted mb-1", style={"fontSize": "12px"}),
                                        dcc.Input(id="inputQTest", type="number", value=46, className="clario-input mb-3")
                                    ]),

                                    html.Hr(style={"borderColor": "var(--clario-border)", "margin": "16px 0"}),

                                    html.Div([
                                        html.Label("Custo Fixo Rateado do SKU (R$/dia)", className="fw-bold text-muted mb-1", style={"fontSize": "12px"}),
                                        dcc.Input(id="inputCustosFixos", type="number", value=25, className="clario-input mb-3")
                                    ]),

                                    html.Div([
                                        html.Label("Custo Variável Unitário (CVU)", className="fw-bold text-muted mb-1", style={"fontSize": "12px"}),
                                        dcc.Input(id="inputCvu", type="number", value=40, className="clario-input")
                                    ]),
                                ]
                            )
                        ),

                        # ÁREA DO GRÁFICO E TABELA COMPARATIVA
                        dbc.Col(
                            width=12, lg=8,
                            children=[
                                # CALLOUT
                                html.Div(
                                    id="callout-summary",
                                    className="clario-card mb-4 py-3 px-4",
                                    style={"backgroundColor": "var(--clario-orange-bg)", "borderColor": "#FFEDD5"},
                                    children="Carregue o CSV de vendas para visualizar o diagnóstico de otimização."
                                ),

                                # PARÂMETROS TÉCNICOS
                                html.Div(
                                    className="clario-card mb-4",
                                    children=[
                                        html.H6("Detalhamento Técnico dos Parâmetros", className="fw-bold mb-3", style={"fontSize": "14px"}),
                                        dbc.Row(id="panel-technical-params", className="g-2")
                                    ]
                                ),

                                # GRÁFICO PLOTLY
                                html.Div(
                                    className="clario-card mb-4",
                                    children=[
                                        dcc.Graph(
                                            id="chartElasticity",
                                            config={"displayModeBar": False},
                                            style={"height": "360px"}
                                        )
                                    ]
                                ),

                                # TABELA COMPARATIVA
                                html.Div(
                                    className="clario-card",
                                    children=[
                                        html.H6("Comparativo de Estratégias", className="fw-bold mb-3", style={"fontSize": "14px"}),
                                        html.Div(id="table-container")
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)


# ==============================================================================
# CALLBACKS DA APLICAÇÃO
# ==============================================================================

# 1. PROCESSAR CSV ENVIADO
@app.callback(
    [
        Output("stored-csv-data", "data"),
        Output("productSelect", "options"),
        Output("date-picker-range", "min_date_allowed"),
        Output("date-picker-range", "max_date_allowed"),
        Output("date-picker-range", "start_date"),
        Output("date-picker-range", "end_date"),
        Output("date-range-info", "children")
    ],
    [Input("upload-data", "contents")],
    [State("upload-data", "filename")],
    prevent_initial_call=True
)
def handle_csv_upload(contents, filename):
    if not contents:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    df = process_uploaded_csv(contents, filename)
    if df is None or "SKU" not in df.columns:
        return dash.no_update, [], None, None, None, None, "Erro ao processar o CSV."

    options = [{"label": sku, "value": sku} for sku in sorted(df["SKU"].dropna().unique())]

    min_date_str, max_date_str = None, None
    if "Data_Dia" in df.columns and df["Data_Dia"].notna().any():
        min_date = df["Data_Dia"].min()
        max_date = df["Data_Dia"].max()
        min_date_str = str(min_date)
        max_date_str = str(max_date)

        info_text = f"✓ {len(df):,} vendas ({df['SKU'].nunique()} SKUs) | {pd.to_datetime(min_date).strftime('%d/%m/%Y')} a {pd.to_datetime(max_date).strftime('%d/%m/%Y')}".replace(",", ".")
    else:
        info_text = f"✓ {len(df):,} vendas carregadas sem coluna de data.".replace(",", ".")

    return (
        df.to_json(date_format="iso", orient="split"),
        options,
        min_date_str,
        max_date_str,
        min_date_str,
        max_date_str,
        info_text
    )


# 2. SELEÇÃO DE SKU E TRANSFERÊNCIA COM RATEIO BASEADO NO CUSTO FIXO INFORMADO PELO USUÁRIO
@app.callback(
    [
        Output("inputPCurr", "value"),
        Output("inputQCurr", "value"),
        Output("inputPTest", "value"),
        Output("inputQTest", "value"),
        Output("inputCvu", "value"),
        Output("inputCustosFixos", "value"),
    ],
    [Input("btnTransferParams", "n_clicks")],
    [
        State("stored-csv-data", "data"),
        State("productSelect", "value"),
        State("date-picker-range", "start_date"),
        State("date-picker-range", "end_date"),
        State("inputCompanyCF", "value")
    ],
    prevent_initial_call=True
)
def transfer_params_from_csv(n_clicks, stored_data, selected_sku, start_date, end_date, company_cf):
    if not stored_data or not selected_sku:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    df = pd.read_json(io.StringIO(stored_data), orient="split")

    if "Data_Dia" in df.columns:
        df["Data_Dia"] = pd.to_datetime(df["Data_Dia"]).dt.date

    if start_date and end_date and "Data_Dia" in df.columns:
        s_dt = pd.to_datetime(start_date).date()
        e_dt = pd.to_datetime(end_date).date()
        df = df[(df["Data_Dia"] >= s_dt) & (df["Data_Dia"] <= e_dt)]

    cf_diario_empresa = float(company_cf or 1500.0)
    kpis = get_product_kpis(df, selected_sku, cf_diario=cf_diario_empresa)

    if not kpis:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    return (
        kpis["p_min"],
        kpis["q_pmin"],
        kpis["p_max"],
        kpis["q_pmax"],
        kpis["cvu"],
        kpis["cf_rateado"]
    )


# 3. ATUALIZAÇÃO REATIVA DO SIMULADOR
@app.callback(
    [
        Output("kpi-preco-ideal", "children"),
        Output("kpi-sensibilidade", "children"),
        Output("kpi-lucro-liquido", "children"),
        Output("kpi-incremento", "children"),
        Output("kpi-volume-estimado", "children"),
        Output("kpi-margem-unit", "children"),
        Output("callout-summary", "children"),
        Output("panel-technical-params", "children"),
        Output("chartElasticity", "figure"),
        Output("table-container", "children")
    ],
    [
        Input("inputPCurr", "value"),
        Input("inputQCurr", "value"),
        Input("inputPTest", "value"),
        Input("inputQTest", "value"),
        Input("inputCustosFixos", "value"),
        Input("inputCvu", "value")
    ]
)
def update_dashboard(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu):
    res = calculate_pricing_model(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu)

    if res is None:
        empty_fig = go.Figure()
        empty_fig.update_layout(template="plotly_white")
        return "R$ 0,00", "-", "R$ 0,00", "-", "0 un.", "-", "Insira os parâmetros para calcular.", [], empty_fig, html.Div()

    def f_m(val):
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    kpi_p_ideal = f_m(res['p_ideal'])
    kpi_sens = f"Sensibilidade (b): {res['sensibilidade_b']:.4f}"
    kpi_lucro = f_m(res['lucro_ideal'])
    kpi_inc = f"+{f_m(res['incremento_diario'])}/dia vs base"
    kpi_vol = f"{res['q_ideal']:,} un.".replace(",", ".")
    kpi_margem = f"Margem Uni.: {f_m(res['margem_contrib_unit'])}"

    callout = html.Span([
        html.I(className="bi bi-info-circle-fill me-2", style={"color": "var(--clario-orange)"}),
        f"O Preço Ideal de ",
        html.Strong(f_m(res['p_ideal'])),
        f" estimula uma demanda diária de ",
        html.Strong(f"{res['q_ideal']:,} un/dia".replace(",", ".")),
        f", projetando um Lucro Líquido de ",
        html.Strong(f_m(res['lucro_ideal'])),
        f" (ganho adicional de ",
        html.Strong(f"+{f_m(res['incremento_diario'])}/dia"),
        f" em relação à base)."
    ])

    tech_params_cards = [
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px", "border": "1px solid #E2E8F0"},
            children=[
                html.Div("Elasticidade (ε)", style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)", "textTransform": "uppercase"}),
                html.Div(f"{res['elasticidade_estimada']:.4f}", style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-dark)"})
            ]
        )),
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px", "border": "1px solid #E2E8F0"},
            children=[
                html.Div("Margem Contrib. (R$)", style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)", "textTransform": "uppercase"}),
                html.Div(f_m(res['margem_contrib_unit']), style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-green)"})
            ]
        )),
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px", "border": "1px solid #E2E8F0"},
            children=[
                html.Div("Margem Contrib. (%)", style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)", "textTransform": "uppercase"}),
                html.Div(f"{res['margem_contrib_perc']:.1f}%", style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-green)"})
            ]
        )),
        dbc.Col(width=6, sm=4, md=3, children=html.Div(
            style={"background": "#F8FAFC", "borderRadius": "8px", "padding": "10px 14px", "border": "1px solid #E2E8F0"},
            children=[
                html.Div("Break-even (Unidades)", style={"fontSize": "11px", "fontWeight": "700", "color": "var(--clario-text-muted)", "textTransform": "uppercase"}),
                html.Div(f"{res['ponto_equilibrio_unidades']:,} un.".replace(",", "."), style={"fontSize": "15px", "fontWeight": "700", "color": "var(--clario-dark)"})
            ]
        )),
    ]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=res["p_range"],
        y=res["receita_range"],
        mode="lines",
        name="Faturamento",
        line=dict(color="#94A3B8", width=1.5, dash="dash")
    ))

    fig.add_trace(go.Scatter(
        x=res["p_range"],
        y=res["lucro_range"],
        mode="lines",
        name="Lucro Líquido",
        fill="tozeroy",
        fillcolor="rgba(255, 107, 53, 0.08)",
        line=dict(color="#FF6B35", width=3)
    ))

    fig.add_trace(go.Scatter(
        x=[res["p_ideal"]],
        y=[res["lucro_ideal"]],
        mode="markers+text",
        name="Preço Ideal (P*)",
        marker=dict(color="#0F172A", size=12, symbol="circle"),
        text=[f"P* = {f_m(res['p_ideal'])}"],
        textposition="top center",
        textfont=dict(color="#0F172A", size=12, family="-apple-system, sans-serif")
    ))

    fig.add_vline(x=res["p_ideal"], line_width=1, line_dash="dot", line_color="#FF6B35")

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Preço Praticado (R$)", gridcolor="#F1F5F9"),
        yaxis=dict(title="Valor Financeiro (R$)", gridcolor="#F1F5F9")
    )

    rows = []
    for row in res["table_data"]:
        rows.append(
            html.Tr(
                className=row["_class"],
                children=[
                    html.Td(row["Estratégia"]),
                    html.Td(row["Preço"]),
                    html.Td(row["Volume"]),
                    html.Td(row["Faturamento"]),
                    html.Td(row["Custos Totais"]),
                    html.Td(row["Lucro Líquido"])
                ]
            )
        )

    table = html.Table(
        className="clario-table",
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Estratégia"),
                    html.Th("Preço"),
                    html.Th("Volume"),
                    html.Th("Faturamento"),
                    html.Th("Custos Totais"),
                    html.Th("Lucro Líquido")
                ])
            ),
            html.Tbody(rows)
        ]
    )

    return (
        kpi_p_ideal, kpi_sens, kpi_lucro, kpi_inc, kpi_vol, kpi_margem,
        callout, tech_params_cards, fig, table
    )


# 4. EXPORTAÇÃO DO RELATÓRIO PDF
@app.callback(
    Output("download-sku-report", "data"),
    Input("btn-report-sku", "n_clicks"),
    [
        State("productSelect", "value"),
        State("inputPCurr", "value"),
        State("inputQCurr", "value"),
        State("inputPTest", "value"),
        State("inputQTest", "value"),
        State("inputCustosFixos", "value"),
        State("inputCvu", "value")
    ],
    prevent_initial_call=True
)
def export_sku_report(n_clicks, selected_sku, p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu):
    if not selected_sku:
        return dash.no_update

    res = calculate_pricing_model(p_min, q_pmin, p_max, q_pmax, custos_fixos, cvu)
    if not res:
        return dash.no_update

    pdf_bytes = generate_clario_pdf(
        res,
        selected_sku,
        p_min,
        q_pmin,
        p_max,
        q_pmax,
        custos_fixos,
        cvu
    )

    filename_clean = selected_sku.split(" - ")[0] if " - " in selected_sku else selected_sku

    return dcc.send_bytes(
        pdf_bytes,
        f"Diagnostico_Executivo_{filename_clean}.pdf"
    )

# 5. CONTROLE DO MODAL DE MATRIZ GLOBAL (SISTEMA DE INTELIGÊNCIA DE PORTFÓLIO)
@app.callback(
    [Output("modal-global-matrix", "is_open"), Output("global-matrix-content", "children")],
    [Input("btn-global-matrix", "n_clicks"), Input("close-matrix-modal", "n_clicks")],
    [
        State("modal-global-matrix", "is_open"),
        State("stored-csv-data", "data"),
        State("inputCompanyCF", "value"),
        State("date-picker-range", "start_date"),
        State("date-picker-range", "end_date")
    ],
    prevent_initial_call=True
)
def toggle_global_matrix(btn_open, btn_close, is_open, stored_data, company_cf, start_date, end_date):
    ctx = dash.callback_context
    if not ctx.triggered:
        return is_open, dash.no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "btn-global-matrix":
        if not stored_data:
            content = html.Div(
                "Por favor, carregue o arquivo CSV de histórico de vendas primeiro.",
                className="text-center text-muted py-5 fw-bold"
            )
            return True, content

        df = pd.read_json(io.StringIO(stored_data), orient="split")

        if "Data_Dia" in df.columns:
            df["Data_Dia"] = pd.to_datetime(df["Data_Dia"]).dt.date

        if start_date and end_date and "Data_Dia" in df.columns:
            s_dt = pd.to_datetime(start_date).date()
            e_dt = pd.to_datetime(end_date).date()
            df = df[(df["Data_Dia"] >= s_dt) & (df["Data_Dia"] <= e_dt)]

        if len(df) == 0:
            content = html.Div(
                "Nenhuma venda registrada no período selecionado.",
                className="text-center text-muted py-5"
            )
            return True, content

        total_skus = df["SKU"].nunique()
        cf_total = float(company_cf or 1500.0)

        # Rateio de Custo Fixo Diário
        df_valid = df.dropna(subset=['Data_Dia', 'SKU']) if 'Data_Dia' in df.columns else df
        if 'Data_Dia' in df.columns and df['Data_Dia'].notna().any():
            vendas_diarias = df_valid.groupby(['Data_Dia', 'SKU']).size().reset_index()[['Data_Dia', 'SKU']]
            skus_ativos_no_dia = vendas_diarias.groupby('Data_Dia')['SKU'].nunique()
        else:
            vendas_diarias = None
            skus_ativos_no_dia = None

        rows = []
        for sku in sorted(df["SKU"].dropna().unique()):
            df_s = df[df["SKU"] == sku]
            p_medio = float(df_s["Preco"].mean())
            cvu = float(df_s["Custo"].mean()) if "Custo" in df_s.columns and df_s["Custo"].notna().any() else 0.0
            v_total = float(df_s["Volume"].sum())

            dias_ativos = max(1, df_s["Data_Dia"].nunique() if "Data_Dia" in df_s.columns else 1)

            # Receita e Margem
            fat_total = (df_s["Preco"] * df_s["Volume"]).sum()
            custo_var_total = cvu * v_total
            margem_contrib_total = fat_total - custo_var_total
            margem_contrib_perc = (margem_contrib_total / fat_total * 100) if fat_total > 0 else 0

            # Rateio do Custo Fixo do SKU
            if vendas_diarias is not None and len(vendas_diarias[vendas_diarias['SKU'] == sku]) > 0:
                vendas_sku = vendas_diarias[vendas_diarias['SKU'] == sku]
                cf_sku_diario = float(vendas_sku['Data_Dia'].map(lambda d: cf_total / skus_ativos_no_dia[d]).mean())
            else:
                cf_sku_diario = cf_total / max(1, total_skus)

            lucro_liquido_diario = (margem_contrib_total / dias_ativos) - cf_sku_diario

            # Estimativa de Elasticidade & Preço Ideal (P*)
            p_min = float(df_s["Preco"].min())
            p_max = float(df_s["Preco"].max())

            if "Data_Dia" in df_s.columns:
                v_pmin = df_s[df_s["Preco"] == p_min].groupby("Data_Dia")["Volume"].sum().mean()
                v_pmax = df_s[df_s["Preco"] == p_max].groupby("Data_Dia")["Volume"].sum().mean()
            else:
                v_pmin = df_s[df_s["Preco"] == p_min]["Volume"].mean()
                v_pmax = df_s[df_s["Preco"] == p_max]["Volume"].mean()

            v_pmin = max(0.1, float(v_pmin) if not pd.isna(v_pmin) else 1.0)
            v_pmax = max(0.1, float(v_pmax) if not pd.isna(v_pmax) else 0.85)

            if p_max <= p_min or v_pmax >= v_pmin:
                b = 1.25
            else:
                b = -(np.log(v_pmax) - np.log(v_pmin)) / (np.log(p_max) - np.log(p_min))
                if np.isnan(b) or np.isinf(b) or b <= 0:
                    b = 1.25

            b = min(max(b, 0.5), 3.0)
            a = v_pmin / (p_min ** (-b))

            min_p = max(cvu * 1.15, p_min * 0.5)
            max_p = p_max * 1.6
            p_range = np.linspace(min_p, max_p, 100)
            q_range = a * (p_range ** (-b))
            lucro_sim = (p_range * q_range) - (cvu * q_range) - cf_sku_diario

            idx_opt = np.argmax(lucro_sim)
            p_ideal = round(float(p_range[idx_opt]), 2)
            lucro_ideal_diario = round(float(lucro_sim[idx_opt]), 2)
            ganho_potencial = max(0.0, lucro_ideal_diario - lucro_liquido_diario)

            # Classificação do SKU
            if lucro_liquido_diario < 0:
                categoria = "⚠️ Alerta de Margem"
            elif ganho_potencial > 15.0:
                categoria = "🚀 Oportunidade de Preço"
            elif margem_contrib_perc > 45.0:
                categoria = "⭐ Gerador de Margem"
            else:
                categoria = "🔄 Volume Estável"

            rows.append({
                "SKU": sku,
                "p_medio": p_medio,
                "p_ideal": p_ideal,
                "cvu": cvu,
                "v_total": v_total,
                "fat_total": fat_total,
                "margem_contrib_perc": margem_contrib_perc,
                "lucro_diario": lucro_liquido_diario,
                "ganho_potencial": ganho_potencial,
                "categoria": categoria
            })

        summary_df = pd.DataFrame(rows)

        # Totais Consolidados
        fat_portfolio = summary_df["fat_total"].sum()
        margem_media = summary_df["margem_contrib_perc"].mean()
        lucro_diario_total = summary_df["lucro_diario"].sum()
        upside_diario_total = summary_df["ganho_potencial"].sum()

        def f_m(val):
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Formatação para Exibição na Tabela
        summary_df["Preço Médio"] = summary_df["p_medio"].apply(f_m)
        summary_df["Preço Ideal (P*)"] = summary_df["p_ideal"].apply(f_m)
        summary_df["Custo Unitario"] = summary_df["cvu"].apply(f_m)
        summary_df["Margem %"] = summary_df["margem_contrib_perc"].apply(lambda x: f"{x:.1f}%")
        summary_df["Lucro Liq. Diário"] = summary_df["lucro_diario"].apply(f_m)
        summary_df["Upside Diário"] = summary_df["ganho_potencial"].apply(lambda x: f"+{f_m(x)}/dia" if x > 0 else "R$ 0,00")

        display_df = summary_df[[
            "SKU", "Preço Médio", "Preço Ideal (P*)", "Custo Unitario",
            "Margem %", "Lucro Liq. Diário", "Upside Diário", "categoria"
        ]].rename(columns={
            "SKU": "Produto / SKU",
            "categoria": "Estratégia / Status"
        })

        content = html.Div([
            # CARDS DE MÉTRICAS EXECUTIVAS
            dbc.Row([
                dbc.Col(width=12, sm=6, md=3, children=html.Div(
                    className="clario-card p-3 mb-3 text-center",
                    children=[
                        html.Div("FATURAMENTO TOTAL", className="text-muted fw-bold mb-1", style={"fontSize": "11px", "letterSpacing": "0.5px"}),
                        html.Div(f_m(fat_portfolio), className="fw-bold text-dark", style={"fontSize": "18px"})
                    ]
                )),
                dbc.Col(width=12, sm=6, md=3, children=html.Div(
                    className="clario-card p-3 mb-3 text-center",
                    children=[
                        html.Div("MARGEM MÉDIA PORTFÓLIO", className="text-muted fw-bold mb-1", style={"fontSize": "11px", "letterSpacing": "0.5px"}),
                        html.Div(f"{margem_media:.1f}%", className="fw-bold text-primary", style={"fontSize": "18px"})
                    ]
                )),
                dbc.Col(width=12, sm=6, md=3, children=html.Div(
                    className="clario-card p-3 mb-3 text-center",
                    children=[
                        html.Div("LUCRO LÍQUIDO DIÁRIO", className="text-muted fw-bold mb-1", style={"fontSize": "11px", "letterSpacing": "0.5px"}),
                        html.Div(f_m(lucro_diario_total), className="fw-bold text-success", style={"fontSize": "18px"})
                    ]
                )),
                dbc.Col(width=12, sm=6, md=3, children=html.Div(
                    className="clario-card p-3 mb-3 text-center",
                    style={"borderColor": "#FF6B35", "backgroundColor": "rgba(255, 107, 53, 0.05)"},
                    children=[
                        html.Div("POTENCIAL DE GANHO (UPSIDE)", className="fw-bold mb-1", style={"fontSize": "11px", "color": "#FF6B35", "letterSpacing": "0.5px"}),
                        html.Div(f"+{f_m(upside_diario_total)}/dia", className="fw-bold", style={"fontSize": "18px", "color": "#FF6B35"})
                    ]
                )),
            ]),

            html.Div(
                f"Exibindo diagnósticos para {total_skus} SKUs. Custo Fixo Diário de {f_m(cf_total)} rateado dinamicamente por presença diária.",
                className="text-muted mb-3 fw-semibold", style={"fontSize": "12px"}
            ),

            # TABELA INTERATIVA DE PORTFÓLIO
            dash_table.DataTable(
                data=display_df.to_dict("records"),
                columns=[{"name": i, "id": i} for i in display_df.columns],
                filter_action="native",
                sort_action="native",
                sort_mode="multi",
                page_size=12,
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "#F8FAFC",
                    "fontWeight": "bold",
                    "color": "#0F172A",
                    "borderBottom": "2px solid #E2E8F0",
                    "fontSize": "12px"
                },
                style_cell={
                    "padding": "10px 12px",
                    "textAlign": "left",
                    "fontFamily": "-apple-system, sans-serif",
                    "fontSize": "13px"
                },
                style_data_conditional=[
                    {
                        "if": {
                            "filter_query": '{Estratégia / Status} contains "Oportunidade"',
                            "column_id": "Estratégia / Status"
                        },
                        "color": "#FF6B35",
                        "fontWeight": "bold"
                    },
                    {
                        "if": {
                            "filter_query": '{Estratégia / Status} contains "Alerta"',
                            "column_id": "Estratégia / Status"
                        },
                        "color": "#DC2626",
                        "fontWeight": "bold"
                    },
                    {
                        "if": {
                            "filter_query": '{Estratégia / Status} contains "Gerador"',
                            "column_id": "Estratégia / Status"
                        },
                        "color": "#10B981",
                        "fontWeight": "bold"
                    },
                    {
                        "if": {
                            "column_id": "Upside Diário"
                        },
                        "fontWeight": "bold",
                        "color": "#FF6B35"
                    }
                ]
            )
        ])

        return True, content

    elif trigger_id == "close-matrix-modal":
        return False, dash.no_update

    return is_open, dash.no_update
# ==============================================================================
# EXECUÇÃO DO SERVIDOR
# ==============================================================================
if __name__ == "__main__":
    app.run(debug=True, port=8050)