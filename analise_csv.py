import io
import base64
import pandas as pd


def process_uploaded_csv(contents):
    """Lê o arquivo CSV enviado pelo dcc.Upload e valida as colunas."""
    if contents is None:
        return None, "Aguardando envio do arquivo."

    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))

        required_cols = {'produto', 'preco', 'quantidade_venda', 'data'}
        if not required_cols.issubset(set(df.columns)):
            return None, f"Erro: O CSV precisa ter as colunas: {', '.join(required_cols)}"

        return df, "OK"
    except Exception as e:
        return None, f"Erro ao processar CSV: {str(e)}"


def get_product_kpis(df, product_name):
    """Extrai os preços extremos e as médias de vendas para um produto."""
    if df is None or product_name not in df['produto'].values:
        return None

    df_prod = df[df['produto'] == product_name].copy()

    p_min = float(df_prod['preco'].min())
    p_max = float(df_prod['preco'].max())

    q_avg_p_min = float(df_prod[df_prod['preco'] == p_min]['quantidade_venda'].mean())
    q_avg_p_max = float(df_prod[df_prod['preco'] == p_max]['quantidade_venda'].mean())

    return {
        "p_min": round(p_min, 2),
        "q_min": round(q_avg_p_min, 1),
        "p_max": round(p_max, 2),
        "q_max": round(q_avg_p_max, 1)
    }