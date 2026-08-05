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
# 3. CONEXÃO COM O GOOGLE SHEETS E CARREGAMENTO DE DADOS
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Autenticando no Google Drive...")
def obter_cliente_gspread():
    try:
        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        if "gcp_service_account" in st.secrets:
            cred_dict = dict(st.secrets["gcp_service_account"])
            credenciais = Credentials.from_service_account_info(cred_dict, scopes=escopos)
            client = gspread.authorize(credenciais)
            return client
        else:
            st.error("⚠️ O secret 'gcp_service_account' não foi encontrado nas configurações do Streamlit.")
            return None
    except Exception as e:
        st.error(f"Erro na autenticação do Google Sheets: {e}")
        return None

@st.cache_data(ttl=300, show_spinner="Baixando dados da planilha...")
def carregar_dados():
    client = obter_cliente_gspread()
    if not client:
        return pd.DataFrame()
    try:
        sh = client.open("Roteiro MooveChain Florianóplis 2026")
        # Ajusta para o nome exato da aba principal de dados, caso exista
        try:
            aba = sh.worksheet("Página1") # Altere se a sua aba principal tiver outro nome
        except:
            aba = sh.get_worksheet(0)
        dados = aba.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha principal: {e}")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# 4. FUNÇÃO DE GEOLOCALIZAÇÃO
# -----------------------------------------------------------------------------
def geolocalizar_endereco(endereco: str):
    if not endereco or not isinstance(endereco, str):
        return "", ""
    try:
        geolocator = Nominatim(user_agent="moovechain_app_2026")
        loc = geolocator.geocode(endereco + ", Florianópolis, SC, Brasil")
        if loc:
            return loc.latitude, loc.longitude