import pandas as pd
import numpy as np
import io
import base64


def process_uploaded_csv(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        try:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            if df.shape[1] == 1:
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep=';')
        except UnicodeDecodeError:
            df = pd.read_csv(io.StringIO(decoded.decode('latin-1')), sep=None, engine='python')

        column_mapping = {}
        for col in df.columns:
            col_clean = col.strip().lower().replace('_', ' ').replace('.', '')

            if any(term in col_clean for term in ['produto', 'product', 'sku', 'item']):
                column_mapping[col] = 'SKU'
            elif any(term in col_clean for term in ['preco', 'price', 'valor', 'p_unitario']):
                column_mapping[col] = 'Preco'
            elif any(term in col_clean for term in ['qtd', 'quantidade', 'volume', 'qty', 'vendas']):
                column_mapping[col] = 'Volume'
            elif any(term in col_clean for term in ['custo', 'cost', 'custo unitario', 'cvu', 'custo var']):
                column_mapping[col] = 'Custo'
            elif any(term in col_clean for term in ['data', 'date', 'dia', 'timestamp', 'time']):
                column_mapping[col] = 'Data'

        df = df.rename(columns=column_mapping)

        if 'Preco' in df.columns:
            df['Preco'] = pd.to_numeric(df['Preco'], errors='coerce')
        if 'Volume' in df.columns:
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
        if 'Custo' in df.columns:
            df['Custo'] = pd.to_numeric(df['Custo'], errors='coerce')
        if 'Data' in df.columns:
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            df['Data_Dia'] = df['Data'].dt.date

        return df

    except Exception as e:
        print(f"Erro ao processar o arquivo CSV: {e}")
        return None


def calculate_period_fixed_costs(df, cf_diario):
    if df is None or 'SKU' not in df.columns:
        return {}

    if 'Data_Dia' in df.columns and df['Data_Dia'].notna().any():
        df_valid = df.dropna(subset=['Data_Dia', 'SKU'])
        vendas_diarias = df_valid.groupby(['Data_Dia', 'SKU']).size().reset_index()[['Data_Dia', 'SKU']]
        skus_ativos_no_dia = vendas_diarias.groupby('Data_Dia')['SKU'].nunique()
        vendas_diarias['cf_alocado'] = vendas_diarias['Data_Dia'].map(lambda d: cf_diario / skus_ativos_no_dia[d])
        return vendas_diarias.groupby('SKU')['cf_alocado'].sum().to_dict()
    else:
        total_skus = df['SKU'].nunique()
        return {sku: cf_diario / total_skus for sku in df['SKU'].unique()}


def get_product_kpis(df, selected_sku, cf_diario=1500.0):
    """
    Extrai as métricas do SKU e calcula o Custo Fixo Rateado diário
    baseado no Custo Fixo Total informado pelo usuário (cf_diario).
    """
    if df is None or selected_sku not in df['SKU'].values:
        return None

    df_sku = df[df['SKU'] == selected_sku].copy()
    df_sku['Preco'] = pd.to_numeric(df_sku['Preco'], errors='coerce')
    df_sku['Volume'] = pd.to_numeric(df_sku['Volume'], errors='coerce')

    # Custo Variável Unitário Médio
    avg_cost = float(df_sku['Custo'].mean()) if 'Custo' in df_sku.columns and df_sku['Custo'].notna().any() else 40.0

    p_min = float(df_sku['Preco'].min())
    p_max = float(df_sku['Preco'].max())

    # Média Diária Real de Vendas por Preço
    if 'Data_Dia' in df_sku.columns and df_sku['Data_Dia'].notna().any():
        vendas_pmin = df_sku[df_sku['Preco'] == p_min].groupby('Data_Dia')['Volume'].sum()
        vendas_pmax = df_sku[df_sku['Preco'] == p_max].groupby('Data_Dia')['Volume'].sum()
        q_pmin_dia = float(vendas_pmin.mean()) if len(vendas_pmin) > 0 else float(df_sku[df_sku['Preco'] == p_min]['Volume'].mean())
        q_pmax_dia = float(vendas_pmax.mean()) if len(vendas_pmax) > 0 else float(df_sku[df_sku['Preco'] == p_max]['Volume'].mean())

        # Rateio Dinâmico do Custo Fixo Diário informado pelo Usuário
        df_valid = df.dropna(subset=['Data_Dia', 'SKU'])
        vendas_diarias = df_valid.groupby(['Data_Dia', 'SKU']).size().reset_index()[['Data_Dia', 'SKU']]
        skus_ativos_no_dia = vendas_diarias.groupby('Data_Dia')['SKU'].nunique()

        vendas_sku = vendas_diarias[vendas_diarias['SKU'] == selected_sku]
        if len(vendas_sku) > 0:
            cf_rateado_sku = float(vendas_sku['Data_Dia'].map(lambda d: cf_diario / skus_ativos_no_dia[d]).mean())
        else:
            cf_rateado_sku = cf_diario / max(1, df['SKU'].nunique())
    else:
        q_pmin_dia = float(df_sku[df_sku['Preco'] == p_min]['Volume'].mean())
        q_pmax_dia = float(df_sku[df_sku['Preco'] == p_max]['Volume'].mean())
        cf_rateado_sku = cf_diario / max(1, df['SKU'].nunique())

    q_pmin_dia = max(0.1, q_pmin_dia)
    q_pmax_dia = max(0.1, q_pmax_dia)

    if p_max <= p_min:
        p_max = round(p_min * 1.15, 2)
        q_pmax_dia = round(q_pmin_dia * 0.85, 2)

    if q_pmax_dia >= q_pmin_dia:
        q_pmax_dia = round(q_pmin_dia * 0.85, 2)

    return {
        "sku": selected_sku,
        "cvu": round(avg_cost, 2),
        "p_min": round(p_min, 2),
        "q_pmin": round(q_pmin_dia, 2),
        "p_max": round(p_max, 2),
        "q_pmax": round(q_pmax_dia, 2),
        "cf_rateado": round(cf_rateado_sku, 2)
    }