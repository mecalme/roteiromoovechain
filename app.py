import logging
import re
import gspread
import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from google.oauth2.service_account import Credentials

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis 2026",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. INICIALIZAÇÃO DE ESTADOS NA SESSÃO
# -----------------------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# -----------------------------------------------------------------------------
# 3. FUNÇÃO DE CARREGAMENTO DE DADOS DO GOOGLE SHEETS
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: As credenciais 'gcp_service_account' não foram encontradas nos Secrets do Streamlit.")
            return pd.DataFrame()
            
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
        gc = gspread.authorize(credentials)
        
        # Nome exato da planilha configurada
        sh = gc.open("Roteiro MooveChain Florianóplis 2026")
        worksheet = sh.worksheet("Planilha1")
        
        dados = worksheet.get_all_records()
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets: {e}")
        return pd.DataFrame()

df_dados = carregar_dados()

# -----------------------------------------------------------------------------
# 4. MENU LATERAL E CONTROLE DE AUTENTICAÇÃO (ADMIN)
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/delivery--v1.png", width=80)
st.sidebar.title("MooveChain 2026")

# Opções padrão visíveis para qualquer usuário
opcoes_publicas = [
    "📊 Dashboard Auditorias",
    "🗺️ Mapa de Pontos"
]

# Opções restritas que só aparecem se o administrador introduzir a chave correta
opcoes_restritas = [
    "🚛 Custos Logísticos (frota)",
    "➕ Adicionar Novo Registro",
    "📋 Tabela de Dados e Ações",
    "🛠️ Manutenção e Limpeza de Coordenadas"
]

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Acesso Restrito (Admin)")
senha_digitada = st.sidebar.text_input("Palavra-passe Admin:", type="password")

senha_correta = st.secrets.get("ADMIN_PASSWORD", "admin123")

if senha_digitada == senha_correta:
    st.session_state["autenticado"] = True
    st.sidebar.success("Modo Administrador Ativo!")
else:
    if senha_digitada:
        st.sidebar.error("Palavra-passe incorreta.")
    st.session_state["autenticado"] = False

# Monta o menu dinamicamente com base no estado de autenticação
if st.session_state["autenticado"]:
    lista_menu = opcoes_publicas + opcoes_restritas
else:
    lista_menu = opcoes_publicas

opcao = st.sidebar.selectbox("Navegação do Menu", lista_menu)

st.sidebar.markdown("---")
st.sidebar.info("Projeto de Auditoria e Logística - Florianópolis 2026")

# -----------------------------------------------------------------------------
# 5. LÓGICA DAS ABAS DA APLICAÇÃO
# -----------------------------------------------------------------------------

# --- ABA 1: DASHBOARD AUDITORIAS ---
if opcao == "📊 Dashboard Auditorias":
    st.title("📊 Dashboard Auditorias MooveChain")
    st.markdown("Visão geral dos indicadores de auditorias realizadas e pendentes na região.")
    
    if not df_dados.empty and "Status" in df_dados.columns:
        # Cálculo das métricas solicitadas
        total_auditorias = len(df_dados)
        
        # Normaliza textos de status para evitar falhas por maiúsculas/minúsculas
        status_col = df_dados["Status"].astype(str).str.strip().str.capitalize()
        
        total_pendentes = len(df_dados[status_col == "Pendente"])
        total_justificadas = len(df_dados[status_col == "Justificada"])
        total_canceladas = len(df_dados[status_col == "Cancelada"])
        total_auditados = len(df_dados[status_col == "Auditado"])

        # Exibição dos quadros (métricas) no topo
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Auditorias", total_auditorias)
        col2.metric("Auditados", total_auditados)
        col3.metric("Pendentes", total_pendentes)
        col4.metric("Justificadas", total_justificadas)
        col5.metric("Canceladas", total_canceladas)
        
        st.markdown("---")
        
        # Gráficos e visualizações adicionais do Dashboard
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Distribuição por Status")
            fig_status = px.pie(
                df_dados, 
                names="Status", 
                title="Proporção de Status das Auditorias",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig_status, use_container_width=True)
            
        with col_g2:
            st.subheader("Auditorias por Bairro / Cidade")
            if "Bairro" in df_dados.columns:
                df_bairro = df_dados["Bairro"].value_counts().reset_index()
                df_bairro.columns = ["Bairro", "Quantidade"]
                fig_bairro = px.bar(df_bairro, x="Bairro", y="Quantidade", title="Volume por Bairro")
                st.plotly_chart(fig_bairro, use_container_width=True)
                
        st.markdown("---")
        st.subheader("Base de Dados Completa Visualizada")
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.warning("Não foram encontrados dados de auditoria ou a coluna 'Status' não está presente.")

# --- ABA 2: MAPA DE PONTOS ---
elif opcao == "🗺️ Mapa de Pontos":
    st.title("🗺️ Mapa Geográfico de Pontos")
    st.markdown("Visualização espacial dos locais auditados e pendentes.")
    
    if not df_dados.empty and "Latitude" in df_dados.columns and "Longitude" in df_dados.columns:
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        
        for idx, row in df_dados.iterrows():
            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
                nome_dest = row.get("Destinatário", "Ponto")
                status_p = row.get("Status", "Desconhecido")
                
                cor = "green" if status_p == "Auditado" else "orange"
                
                folium.Marker(
                    [lat, lon],
                    popup=f"<b>{nome_dest}</b><br>Status: {status_p}",
                    icon=folium.Icon(color=cor, icon="info-sign")
                ).add_to(m)
            except Exception:
                continue
                
        st_folium(m, width=1100, height=550)
    else:
        st.warning("Coordenadas geográficas não disponíveis na base de dados.")

# --- ABA 3: CUSTOS LOGÍSTICOS (ADMIN) ---
elif opcao == "🚛 Custos Logísticos (frota)":
    st.subheader("🚛 Custos Logísticos (frota)")
    st.markdown("Painel restrito de acompanhamento de despesas de frota e abastecimento.")
    st.markdown("---")
    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = gc.open("Roteiro MooveChain Florianóplis 2026")
        aba_custos = sh.worksheet("Controle_Custos")
        dados_custos = aba_custos.get_all_records()
        
        if dados_custos:
            df_custos = pd.DataFrame(dados_custos)
            st.dataframe(df_custos, use_container_width=True)
            
            if "Valor" in df_custos.columns:
                fig_pizza = px.pie(df_custos, names="Destinatário" if "Destinatário" in df_custos.columns else df_custos.columns[0], values="Valor", title="Distribuição de Custos")
                st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("A aba 'Controle_Custos' encontra-se vazia.")
    except Exception as e:
        st.error(f"Erro ao carregar dados de custos logísticos: {e}")

# --- ABA 4: ADICIONAR NOVO REGISTRO (ADMIN) ---
elif opcao == "➕ Adicionar Novo Registro":
    st.title("➕ Adicionar Novo Registro")
    with st.form("form_novo_registro"):
        nome = st.text_input("Identificador / Destinatário:")
        endereco = st.text_input("Endereço (Rua e Número - Floripa):")
        submetido = st.form_submit_button("Geolocalizar e Salvar")
        
        if submetido:
            st.success(f"Registro '{nome}' processado com sucesso!")

# --- ABA 5: TABELA DE DADOS E AÇÕES (ADMIN) ---
elif opcao == "📋 Tabela de Dados e Ações":
    st.title("📋 Tabela de Dados e Ações (Admin)")
    if not df_dados.empty:
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.info("Nenhum dado disponível para gestão.")

# --- ABA 6: MANUTENÇÃO E LIMPEZA DE COORDENADAS (ADMIN) ---
elif opcao == "🛠️ Manutenção e Limpeza de Coordenadas":
    st.title("🛠️ Manutenção e Limpeza de Coordenadas")
    st.markdown("Ferramenta de validação e correção de geolocalização em lote.")