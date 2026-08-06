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
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open("Roteiro MooveChain Florianóplis 2026")
        
        # Carrega dados principais
        sheet_principal = spreadsheet.sheet1
        dados_principais = sheet_principal.get_all_records()
        df_dados = pd.DataFrame(dados_principais)
        
        # Tenta carregar custos se existir a aba Controle_Custos
        try:
            sheet_custos = spreadsheet.worksheet("Controle_Custos")
            dados_custos = sheet_custos.get_all_records()
            df_custos = pd.DataFrame(dados_custos)
        except Exception:
            df_custos = pd.DataFrame()
            
        return df_dados, df_custos
    except Exception as e:
        st.error(f"Erro ao ligar ao Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_dados, df_custos = carregar_dados()

# --- 4. BARRA LATERAL (MENU E AUTENTICAÇÃO) ---
st.sidebar.title("🚚 Painel MooveChain")

# Gestão de Autenticação na barra lateral
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Palavra-passe Admin", type="password")
    senha_correta = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")
    if st.sidebar.button("Entrar"):
        if senha_digitada == senha_correta:
            st.session_state["autenticado"] = True
            st.success("Acesso concedido!")
            st.rerun()
        else:
            st.sidebar.error("Palavra-passe incorreta.")
else:
    st.sidebar.success("Modo Administrador Ativo")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Navegação")

# Definição das opções do menu lateral fixo
opcoes_publicas = ["📊 Dashboard Principal", "🗺️ Mapa Interativo"]
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

opcao = st.sidebar.radio("Ir para:", lista_menu)

# --- 5. LÓGICA DAS SECÇÕES DA APLICAÇÃO ---

if opcao == "📊 Dashboard Principal