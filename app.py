import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Configuração inicial da página em modo expandido
st.set_page_config(page_title="Roteiro Moovechain", page_icon="📍", layout="wide")

# 2. Conexão com o Google Sheets
@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    client = gspread.authorize(creds)
    sheet = client.open_by_key("12sENMxX1FoQ6KYNgnlnXzD3abDqO4VH_jypcB-nQGks").sheet1
    return sheet

# Carrega os dados da planilha de forma segura
try:
    sheet = conectar_sheets()
    dados = pd.DataFrame(sheet.get_all_records())
except Exception as e:
    st.error(f"Erro ao carregar os dados da planilha: {e}")
    st.stop()

# 3. Cabeçalho e Indicadores de Progresso (KPIs)
st.title("📍 Roteiro e Progresso de Auditorias - Moovechain")

total_pontos = len(dados)
# Se houver uma coluna de status, calcula os concluídos. Caso contrário, assume 0.
if 'Status' in dados.columns:
    concluidos = len(dados[dados['Status'] == 'Concluído'])
else:
    concluidos = 0

porcentagem = int((concluidos / total_pontos) * 100) if total_pontos > 0 else 0

# Exibe os cartões de métricas no topo
col1, col2, col3 = st.columns(3)
col1.metric(label="📊 Total de Pontos Mapeados", value=total_pontos)
col2.metric(label="✅ Auditorias Realizadas", value=concluidos)
col3.metric(label="🚀 Avanço Total", value=f"{porcentagem}%")

st.markdown("---")

# 4. Abas para organizar a visualização
aba_mapa, aba_tabela = st.tabs(["🗺️ Mapa e Rotas", "📋 Tabela de Dados"])

with aba_mapa:
    st.subheader("Visualização dos Pontos de Auditoria")
    # Se você já tiver o código do seu mapa antigo funcionando, cole ele aqui embaixo:
    # st.map(dados) ou o seu gráfico Plotly/Pydeck
    st.dataframe(dados, use_container_width=True)

with aba_tabela:
    st.subheader("Planilha Completa")
    st.dataframe(dados, use_container_width=True)