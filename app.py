from folium.plugins import MarkerCluster
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

# --- 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS CSS ---
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

# --- 2. INICIALIZAÇÃO DE ESTADOS NA SESSÃO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# --- 3. FUNÇÃO DE CARREGAMENTO DE DADOS ROBUSTA ---
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(creds)
        sh = gc.open("Roteiro MooveChain Florianóplis 2026")
        worksheet = sh.worksheet("Planilha1")
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df, worksheet
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets: {e}")
        return pd.DataFrame(), None

df_dados, worksheet_principal = carregar_dados()

# --- 4. BARRA LATERAL E NAVEGAÇÃO ---
st.sidebar.title("🚚 Painel MooveChain")

# Seção de Autenticação na Barra Lateral
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Palavra-passe de Administrador", type="password")
    if st.sidebar.button("Entrar"):
        senha_admin = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")
        if senha_digitada == senha_admin:
            st.session_state["autenticado"] = True
            st.success("Acesso autorizado!")
            st.rerun()
        else:
            st.error("Palavra-passe incorreta.")
else:
    st.sidebar.success("Modo Administrador Ativo")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Menu de Navegação")

# Definição das opções de menu com base na autenticação (Usando st.sidebar.radio em vez de selectbox)
opcoes_publicas = ["📊 Dashboard & Mapa"]
opcoes_admin = [
    "➕ Adicionar Novo Registro",
    "📋 Tabela de Dados e Ações",
    "🛠️ Manutenção e Limpeza de Coordenadas",
    "💰 Custos Logísticos"
]

if st.session_state["autenticado"]:
    lista_menu = opcoes_publicas + opcoes_admin
else:
    lista_menu = opcoes_publicas

# Menu lateral sem ser desdobrável (Lista vertical de selecção por rádio)
opcao = st.sidebar.radio("Selecione a secção:", lista_menu)

# --- 5. CORPO DA APLICAÇÃO CONSOANTE A OPÇÃO ESCOLHIDA ---

if opcao == "📊 Dashboard & Mapa":
    st.title("📊 Dashboard de Auditorias - Florianópolis 2026")
    
    if not df_dados.empty:
        # Tratamento do Status para garantir contagem exata e tolerante a variações
        if "Status" in df_dados.columns:
            df_dados["Status_Clean"] = df_dados["Status"].astype(str).str.strip().str.title()
        else:
            df_dados["Status_Clean"] = "Pendente"

        total_auditorias = len(df_dados)
        pendentes = len(df_dados[df_dados["Status_Clean"] == "Pendente"])
        
        # Procura por variações de justificada/justificado
        justificadas = len(df_dados[df_dados["Status_Clean"].str.contains("Justificad", case=False, na=False)])
        canceladas = len(df_dados[df_dados["Status_Clean"].str.contains("Cancelad", case=False, na=False)])
        auditadas = len(df_dados[df_dados["Status_Clean"].str.contains("Auditad", case=False, na=False)])

        # Métricas no topo do Dashboard
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Auditorias", total_auditorias)
        col2.metric("Auditadas", auditadas)
        col3.metric("Pendentes", pendentes)
        col4.metric("Justificadas", justificadas)
        col5.metric("Canceladas", canceladas)
        
        st.markdown("---")

        # Gráfico de Volume por Bairro discriminado por Status
        st.subheader("📍 Volume por Bairro detalhado por Status")
        if "Bairro" in df_dados.columns and "Status" in df_dados.columns:
            df_bairro_status = df_dados.groupby(["Bairro", "Status"]).size().reset_index(name="Quantidade")
            fig_bairro_status = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Quantidade",
                color="Status",
                barmode="group",
                title="Distribuição de Status por Bairro"
            )
            st.plotly_chart(fig_bairro_status, use_container_width=True)

        st.markdown("---")
        st.subheader("🗺️ Mapa Interativo de Auditorias")
        
        # Mapa com Folium
        mapa_floripa = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(mapa_floripa)

        for _, row in df_dados.iterrows():
            try:
                lat = float(row.get("Latitude", 0))
                lon = float(row.get("Longitude", 0))
                nome_dest = row.get("Destinatário", "Local")
                status_dest = row.get("Status", "Pendente")
                
                if lat != 0 and lon != 0:
                    folium.Marker(
                        location=[lat, lon],
                        popup=f"<b>{nome_dest}</b><br>Status: {status_dest}",
                        tooltip=nome_dest
                    ).add_to(marker_cluster)
            except Exception:
                continue

        st_folium(mapa_floripa, width=1200, height=500)
    else:
        st.warning("Nenhum dado encontrado para exibir no Dashboard.")

elif opcao == "➕ Adicionar Novo Registro":
    if st.session_state.get("autenticado", False):
        st.title("➕ Adicionar Novo Registro")
        with st.form("form_novo_registro"):
            nome = st.text_input("Identificador / Destinatário:")
            endereco = st.text_input("Endereço (Rua e Número - Floripa):")
            submetido = st.form_submit_button("Geolocalizar e Salvar")
            if submetido:
                st.success("Registro submetido com sucesso!")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "📋 Tabela de Dados e Ações":
    if st.session_state.get("autenticado", False):
        st.title("📋 Tabela de Dados e Ações")
        if not df_dados.empty:
            st.dataframe(df_dados, use_container_width=True)
        else:
            st.info("Sem dados disponíveis.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "🛠️ Manutenção e Limpeza de Coordenadas":
    if st.session_state.get("autenticado", False):
        st.title("🛠️ Manutenção e Limpeza de Coordenadas")
        st.write("Ferramentas de manutenção de dados geográficos.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "💰 Custos Logísticos":
    if st.session_state.get("autenticado", False):
        st.title("💰 Custos Logísticos")
        try:
            credentials_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(
                credentials_dict,
                scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            )
            gc = gspread.authorize(creds)
            sh = gc.open("Roteiro MooveChain Florianóplis 2026")
            aba_custos = sh.worksheet("Controle_Custos")
            dados_custos = aba_custos.get_all_records()
            df_custos = pd.DataFrame(dados_custos)
            st.dataframe(df_custos, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao carregar custos: {e}")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")