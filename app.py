import logging
import re
import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import gspread
from google.oauth2.service_account import Credentials

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA E VARIÁVEIS GLOBAIS
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis",
    page_icon="📍",
    layout="wide",
)

EMAIL_INTEGRACAO = "integracaoplanilhasmapas@moovechain-mapas.iam.gserviceaccount.com"
LISTA_STATUS = ["Pendente", "Auditado", "Cancelado", "Justificado"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# -----------------------------------------------------------------------------
# 2. ESTILIZAÇÃO CSS CUSTOMIZADA
# -----------------------------------------------------------------------------

st.markdown("""
    <style>
        .stApp { background-color: #f0f4f8; color: #102a43; }
        [data-testid="stSidebar"] { background-color: #1e3a8a; border-right: 1px solid #1e40af; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label { color: #ffffff !important; }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 8px; border: none; font-weight: bold; }
        .stButton>button:hover { background-color: #1d4ed8; color: white; }
        div[data-testid="stMetricValue"] { color: #1e3a8a; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. CONEXÃO COM O GOOGLE SHEETS E CACHE DE DADOS
# -----------------------------------------------------------------------------

@st.cache_resource
def conectar_google_sheets():
    try:
        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Obtém as credenciais do st.secrets
        if "gcp_service_account" in st.secrets:
            cred_dict = dict(st.secrets["gcp_service_account"])
            credenciais = Credentials.from_service_account_info(cred_dict, scopes=escopos)
        else:
            st.error("⚠️ Credenciais 'gcp_service_account' não encontradas no st.secrets.")
            return None
            
        cliente = gspread.authorize(credenciais)
        return cliente
    except Exception as e:
        logging.error(f"Erro ao conectar ao Google Sheets: {e}")
        return None

cliente_gs = conectar_google_sheets()

@st.cache_data(ttl=600)
def carregar_dados_principais():
    if not cliente_gs:
        return pd.DataFrame()
    try:
        sh = cliente_gs.open("Roteiro MooveChain Florianóplis 2026")
        worksheet = sh.worksheet("Planilha1")
        dados = worksheet.get_all_records()
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        logging.error(f"Erro ao carregar dados da aba principal: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def carregar_dados_custos():
    if not cliente_gs:
        return pd.DataFrame()
    try:
        sh = cliente_gs.open("Roteiro MooveChain Florianóplis 2026")
        worksheet = sh.worksheet("Controle_Custos")
        dados = worksheet.get_all_records()
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        logging.error(f"Erro ao carregar dados de custos: {e}")
        return pd.DataFrame()

df_dados = carregar_dados_principais()

# -----------------------------------------------------------------------------
# 4. MENU LATERAL E CONTROLE DE AUTENTICAÇÃO DE ADMIN
# -----------------------------------------------------------------------------

st.sidebar.title("📍 MooveChain - Florianópolis")
st.sidebar.markdown("---")

# Gestão de Sessão do Administrador
if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False

with st.sidebar.expander("🔐 Painel Administrativo", expanded=not st.session_state["admin_autenticado"]):
    if not st.session_state["admin_autenticado"]:
        senha_input = st.text_input("Senha de Administrador", type="password")
        if st.button("Entrar"):
            senha_correta = st.secrets.get("ADMIN_PASSWORD", "moove2026")
            if senha_input == senha_correta:
                st.session_state["admin_autenticado"] = True
                st.success("Autenticado com sucesso!")
                st.rerun()
            else:
                st.error("Senha incorreta.")
    else:
        st.success("Modo Administrador Ativo")
        if st.button("Terminar Sessão"):
            st.session_state["admin_autenticado"] = False
            st.rerun()

st.sidebar.markdown("---")

# Definição dinâmica das opções do menu com base na autenticação
opcoes_menu = [
    "🗺️ Mapa Geral", 
    "📋 Tabela de Destinatários e Rotas"
]

if st.session_state["admin_autenticado"]:
    opcoes_menu.extend([
        "🚛 Custo Logístico de Frota",
        "✏️ Editar Registro Existente",
        "➕ Adicionar Novo Registro",
        "🛠️ Manutenção e Otimização do App"
    ])

opcao = st.sidebar.selectbox("Navegação", opcoes_menu)

st.sidebar.markdown("---")
st.sidebar.markdown(f"<small>🤖 Integração: <br>{EMAIL_INTEGRACAO}</small>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. LÓGICA DAS ABAS DA APLICAÇÃO
# -----------------------------------------------------------------------------

# --- ABA 1: MAPA GERAL ---
if opcao == "🗺️ Mapa Geral":
    st.subheader("🗺️ Mapa Geral de Rotas e Auditorias")
    st.markdown("---")
    
    if not df_dados.empty:
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        for _, row in df_dados.iterrows():
            try:
                lat = float(row.get("Latitude", 0))
                lon = float(row.get("Longitude", 0))
                if lat != 0 and lon != 0:
                    folium.Marker(
                        [lat, lon],
                        popup=f"<b>{row.get('Destinatário')}</b><br>{row.get('Endereco_Completo')}",
                        tooltip=row.get('Destinatário')
                    ).add_to(m)
            except Exception:
                continue
        st_folium(m, width="100%", height=500)
    else:
        st.warning("Nenhum dado encontrado na planilha principal.")

# --- ABA 2: TABELA DE DESTINATÁRIOS ---
elif opcao == "📋 Tabela de Destinatários e Rotas":
    st.subheader("📋 Tabela de Destinatários e Rotas")
    st.markdown("---")
    if not df_dados.empty:
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.warning("Nenhum registo disponível.")

# --- ABA 3: CUSTO LOGÍSTICO DE FROTA (RESTRITO A ADMIN) ---
elif opcao == "🚛 Custo Logístico de Frota":
    if not st.session_state.get("admin_autenticado", False):
        st.error("Acesso restrito. Por favor, autentique-se como Administrador no menu lateral.")
    else:
        st.subheader("🚛 Controle de Custos Logísticos da Frota")
        st.markdown("---")
        df_custos = carregar_dados_custos()
        if not df_custos.empty:
            st.dataframe(df_custos, use_container_width=True)
        else:
            st.info("A aba 'Controle_Custos' está vazia ou não pôde ser lida corretamente no Google Sheets.")

# --- ABA 4: EDITAR REGISTRO ---
elif opcao == "✏️ Editar Registro Existente":
    if not st.session_state.get("admin_autenticado", False):
        st.error("Acesso restrito.")
    else:
        st.subheader("✏️ Editar Registro na Planilha")
        st.info("Módulo em construção - utilize diretamente o Google Sheets para edições em massa.")

# --- ABA 5: NOVO REGISTRO ---
elif opcao == "➕ Adicionar Novo Registro":
    if not st.session_state.get("admin_autenticado", False):
        st.error("Acesso restrito.")
    else:
        st.subheader("➕ Novo Registro")
        with st.form("f_novo"):
            dest = st.text_input("Destinatário")
            rua = st.text_input("Rua")
            num = st.text_input("Número")
            bairro = st.text_input("Bairro")
            cid = st.text_input("Cidade", value="Florianópolis")
            est = st.text_input("Estado", value="SC")
            cep = st.text_input("CEP")
            st_novo = st.selectbox("Status", LISTA_STATUS)
            submitted = st.form_submit_button("Salvar")
            if submitted:
                st.success("Formulário submetido com sucesso!")

# --- ABA 6: MANUTENÇÃO ---
elif opcao == "🛠️ Manutenção e Otimização do App":
    if not st.session_state.get("admin_autenticado", False):
        st.error("Acesso restrito.")
    else:
        st.subheader("🛠️ Painel de Manutenção e Reparo de Dados")
        st.markdown("---")
        if st.button("🔄 Limpar Cache e Recarregar"):
            st.cache_data.clear()
            st.success("Cache limpo com sucesso!")
            st.rerun()