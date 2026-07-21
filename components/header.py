import dash
from dash import html, dcc
import dash_bootstrap_components as dbc


def render_header():
    """Gera o cabeçalho fixo no estilo Fintech Light Glassmorphism."""
    return html.Nav([
        dbc.Container([
            html.Div([
                # Logo & Identidade Visual
                html.A([
                    html.I(className="bi bi-graph-up-arrow me-3 fs-4", style={"color": "var(--fintech-indigo)"}),
                    html.Span("Clariô Intelligence", className="page-main-title", style={"fontSize": "19px"})
                ], href="#", className="d-flex align-items-center text-decoration-none"),

                # Ações Desktop
                html.Div([
                    dbc.Button(
                        [html.I(className="bi bi-file-earmark-pdf me-2"), "Relatório SKU (PDF)"],
                        id="btn-report-sku",
                        className="ios-btn-glass me-2"
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-grid-3x3-gap-fill me-2"), "Matriz Global"],
                        id="btn-global-matrix",
                        className="ios-btn-primary"
                    )
                ], className="d-none d-md-flex align-items-center"),

                # Botão Hambúrguer para Telas Pequenas
                dbc.Button(
                    html.I(className="bi bi-list fs-4"),
                    id="btn-open-mobile-menu",
                    className="ios-btn-glass d-md-none",
                    style={"padding": "6px 12px"}
                )
            ], className="d-flex justify-content-between align-items-center")
        ], fluid=True, style={"maxWidth": "1280px"})
    ], className="sticky-glass-nav")


def render_mobile_overlay():
    """Menu Overlay para dispositivos móveis."""
    return dbc.Offcanvas(
        [
            html.Div([
                html.H5("Ações Rápidas", className="ios-label mb-3", style={"fontSize": "16px"}),
                dbc.Button([html.I(className="bi bi-file-earmark-pdf me-2"), "Baixar Relatório SKU (PDF)"],
                           id="btn-report-sku-mobile", className="ios-btn-glass w-100 mb-2"),
                dbc.Button([html.I(className="bi bi-grid-3x3-gap-fill me-2"), "Ver Matriz Global"],
                           id="btn-global-matrix-mobile", className="ios-btn-primary w-100")
            ])
        ],
        id="mobile-offcanvas",
        title="Clariô Intelligence",
        placement="end",
        is_open=False
    )