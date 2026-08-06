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
    lista_menu = opcoes_publicas +