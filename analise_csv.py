import pandas as pd
import io
import base64

def process_uploaded_csv(contents, filename):
    """
    Decodifica o CSV enviado e mapeia as colunas necessárias para a análise,
    garantindo a tipagem correta de datas e números para evitar quebras matemáticas.
    """
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        # Suporte a arquivos CSV delimitados por vírgula ou ponto e vírgula
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        if df.shape[1] == 1:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), sep=';')

        # Mapeamento dinâmico de variações de nomes de colunas
        column_mapping = {}
        for col in df.columns:
            col_clean = str(col).strip().lower().replace('_', ' ').replace('.', '')

            if any(term in col_clean for term in ['produto', 'product', 'sku', 'item']):
                column_mapping[col] = 'SKU'
            elif any(term in col_clean for term in ['preco', 'price', 'valor', 'p_unitario']):
                column_mapping[col] = 'Preco'
            elif any(term in col_clean for term in ['qtd', 'quantidade', 'volume', 'qty', 'vendas']):
                column_mapping[col] = 'Volume'
            elif any(term in col_clean for term in ['custo', 'cost', 'custo unitario', 'cvu', 'custo var']):
                column_mapping[col] = 'Custo'
            elif any(term in col_clean for term in ['data', 'date', 'dia', 'criado']):
                column_mapping[col] = 'Data_Dia'

        df = df.rename(columns=column_mapping)

        # Limpeza e conversões numéricas seguras (Trata vírgulas brasileiras)
        if 'Preco' in df.columns:
            df['Preco'] = pd.to_numeric(df['Preco'].astype(str).str.replace(',', '.'), errors='coerce')
        if 'Volume' in df.columns:
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
        if 'Custo' in df.columns:
            df['Custo'] = pd.to_numeric(df['Custo'].astype(str).str.replace(',', '.'), errors='coerce')

        # CORREÇÃO CRÍTICA 1: Força leitura de data em padrão Brasileiro (DD/MM/YYYY)
        if 'Data_Dia' in df.columns:
            df['Data_Dia'] = pd.to_datetime(df['Data_Dia'], dayfirst=True, errors='coerce')

        return df

    except Exception as e:
        print(f"Erro Crítico ao processar o arquivo CSV: {e}")
        return None


def get_product_kpis(df, selected_sku, cf_diario=0.0):
    """
    Extrai as métricas consolidadas, com travas para cálculos de ponto flutuante,
    impedindo que o motor de elasticidade receba "NaN" e congele a interface.
    """
    if df is None or 'SKU' not in df.columns or selected_sku not in df['SKU'].values:
        return None

    df_sku = df[df['SKU'] == selected_sku].copy()

    # Garantir presença de datas para agrupar corretamente
    if "Data_Dia" in df_sku.columns and df_sku["Data_Dia"].notna().any():
        df_sku['Date'] = pd.to_datetime(df_sku['Data_Dia'], dayfirst=True, errors='coerce').dt.date
    else:
        df_sku['Date'] = pd.to_datetime('2024-01-01').date()

    df_sku = df_sku.dropna(subset=['Date'])
    if df_sku.empty:
        return None

    # Calcular o Custo Variável Total e Faturamento por linha
    if 'Custo' in df_sku.columns and not df_sku['Custo'].dropna().empty:
        df_sku['Custo_Total'] = df_sku['Custo'].fillna(40.0) * df_sku['Volume']
    else:
        df_sku['Custo'] = 40.0
        df_sku['Custo_Total'] = 40.0 * df_sku['Volume']

    df_sku['Faturamento'] = df_sku['Preco'] * df_sku['Volume']

    # AGREGAÇÃO DIÁRIA
    daily = df_sku.groupby('Date').agg({
        'Volume': 'sum',
        'Faturamento': 'sum',
        'Custo_Total': 'sum'
    }).reset_index()

    # Filtrar dias com volume zerado para proteger a divisão
    daily = daily[daily['Volume'] > 0]
    if daily.empty:
        return None

    daily['Preco_Medio'] = daily['Faturamento'] / daily['Volume']

    # CORREÇÃO CRÍTICA 2: Bug do Ponto Flutuante
    # Arredondar cria "faixas" numéricas exatas, protegendo o código de quebras de dízima.
    daily['Preco_Base'] = daily['Preco_Medio'].round(2)

    # Agrupa o volume médio histórico por faixa de preço exata
    resumo_precos = daily.groupby('Preco_Base').agg({'Volume': 'mean'}).reset_index()

    p_min = resumo_precos['Preco_Base'].min()
    p_max = resumo_precos['Preco_Base'].max()

    # Localização direta usando as faixas exatas blindadas
    try:
        q_curr = float(resumo_precos.loc[resumo_precos['Preco_Base'] == p_min, 'Volume'].iloc[0])
        q_test = float(resumo_precos.loc[resumo_precos['Preco_Base'] == p_max, 'Volume'].iloc[0])
    except (IndexError, KeyError):
        q_curr = daily['Volume'].mean()
        q_test = q_curr * 0.8

    # Custo Variável Unitário Ponderado
    avg_cost = daily['Custo_Total'].sum() / daily['Volume'].sum() if daily['Volume'].sum() > 0 else 40.0

    # Lógica de segurança de Posição (Fallback) se não existir variação para curva
    if pd.isna(q_test) or p_min >= p_max:
        p_max = p_min * 1.2 if p_min > 0 else 100.0
        q_test = q_curr * 0.8 if q_curr > 0 else 10.0

    if pd.isna(q_curr) or q_curr <= 0:
        q_curr = daily['Volume'].mean()

    # Rateio inteligente
    total_skus = df['SKU'].nunique() if 'SKU' in df.columns else 1
    cf_rateado = float(cf_diario) / max(1, total_skus)

    return {
        "p_min": round(float(p_min), 2),
        "q_pmin": round(float(q_curr), 2),
        "p_max": round(float(p_max), 2),
        "q_pmax": round(float(q_test), 2),
        "cvu": round(float(avg_cost), 2),
        "cf_rateado": round(float(cf_rateado), 2)
    }