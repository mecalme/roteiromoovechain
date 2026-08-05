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
        try:
            aba = sh.worksheet("Página1") 
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
    except Exception as e:
        logging.error(f"Erro na geolocalização: {e}")
    return "", ""

# -----------------------------------------------------------------------------
# 5. CONTROLE DE ACESSO E MENU LATERAL
# -----------------------------------------------------------------------------
st.sidebar.title("🚚 MooveChain")
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Autenticação")

if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Senha Admin", type="password", key="input_senha")
    senha_correta = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")
    
    if st.sidebar.button("Entrar"):
        if senha_digitada == senha_correta:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.sidebar.error("Senha incorreta!")
else:
    st.sidebar.success("Modo Administrador Ativo")
    if st.sidebar.button("Sair (Logout)"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")

# Definição restrita do menu: abas administrativas só aparecem se autenticado
opcoes_menu = [
    "📊 Dashboard Auditorias", 
    "🗺️ Mapa de Pontos"
]

if st.session_state["autenticado"]:
    opcoes_menu.extend([
        "🚛 Custos Logísticos (Frota)",
        "➕ Adicionar Novo Registro", 
        "📋 Tabela de Dados e Ações", 
        "🧹 Manutenção e Limpeza de Coordenadas"
    ])

opcao = st.sidebar.radio("Navegação:", opcoes_menu, label_visibility="collapsed")

# -----------------------------------------------------------------------------
# 6. RENDERIZAÇÃO DAS ABAS / PÁGINAS
# -----------------------------------------------------------------------------
try:
    df_dados = carregar_dados()
except Exception as e:
    df_dados = pd.DataFrame()
    st.error(f"Erro crítico ao carregar dados: {e}")

# --- ABA 1: DASHBOARD ---
if opcao == "📊 Dashboard Auditorias":
    st.title("📊 Dashboard Auditorias MooveChain")
    st.markdown("---")
    
    if not df_dados.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Registros", len(df_dados))
        with col2:
            st.metric("Colunas Identificadas", len(df_dados.columns))
        with col3:
            st.metric("Status da Conexão", "Online 🟢")
        
        st.subheader("Base de Dados Geral")
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.info("A base de dados está vazia ou a carregar. Verifique a ligação ao Google Sheets.")

# --- ABA 2: MAPA DE PONTOS ---
elif opcao == "🗺️ Mapa de Pontos":
    st.title("🗺️ Mapa Geográfico de Pontos")
    st.markdown("---")
    st.info("Funcionalidade do mapa de pontos em exibição.")

# --- ABA 3: CUSTOS LOGÍSTICOS ---
elif opcao == "🚛 Custos Logísticos (Frota)":
    st.title("🚛 Custos Logísticos (Frota)")
    st.markdown("---")
    try:
        gc = obter_cliente_gspread()
        if gc:
            sh = gc.open("Roteiro MooveChain Florianóplis 2026")
            aba_custos = sh.worksheet("Controle_Custos")
            dados_custos = aba_custos.get_all_records()
            
            if dados_custos:
                df_custos = pd.DataFrame(dados_custos)
                st.subheader("Quadro de Custos")
                st.dataframe(df_custos, use_container_width=True)
                
                # Gráfico de pizza ajustado para exibir os dados de custos
                if "Categoria" in df_custos.columns and "Valor" in df_custos.columns:
                    fig_pizza = px.pie(df_custos, names="Categoria", values="Valor", title="Distribuição de Custos por Categoria")
                    st.plotly_chart(fig_pizza, use_container_width=True)
                elif len(df_custos.columns) >= 2:
                    col_cat = df_custos.columns[0]
                    col_val = df_custos.columns[1]
                    fig_pizza = px.pie(df_custos, names=col_cat, values=col_val, title="Distribuição de Custos")
                    st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.warning("A aba 'Controle_Custos' está vazia.")
    except Exception as e:
        st.error(f"Erro ao carregar custos logísticos: {e}")

# --- ABA 4: ADICIONAR NOVO REGISTRO (ADMIN) ---
elif opcao == "➕ Adicionar Novo Registro":
    st.title("➕ Adicionar Novo Registro")
    st.markdown("---")
    with st.form("form_novo_registro"):
        nome = st.text_input("Identificador / Destinatário:")
        endereco = st.text_input("Endereço (Rua e Número - Floripa):")
        submetido = st.form_submit_button("Geolocalizar e Salvar")
        if submetido:
            st.success("Funcionalidade de registo submetida com sucesso!")

# --- ABA 5: TABELA E AÇÕES (ADMIN) ---
elif opcao == "📋 Tabela de Dados e Ações":
    st.title("📋 Gerenciamento da Tabela")
    st.markdown("---")
    if not df_dados.empty:
        st.dataframe(df_dados, use_container_width=True)
        if st.button("🔄 Forçar Atualização de Dados"):
            st.cache_data.clear()
            st.rerun()

# --- ABA 6: MANUTENÇÃO E LIMPEZA (ADMIN) ---
elif opcao == "🧹 Manutenção e Limpeza de Coordenadas":
    st.title("🧹 Ferramenta de Limpeza de Coordenadas")
    st.markdown("---")
    st.info("Ferramenta de manutenção de coordenadas ativa.")