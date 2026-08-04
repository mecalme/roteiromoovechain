from datetime import date
import re
import time
import folium
from geopy.geocoders import Nominatim
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis",
    page_icon="📍",
    layout="wide",
)

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown(
    """
    <style>
    .stApp { background-color: #f0f4f8; color: #102a43; }
    [data-testid="stSidebar"] { background-color: #1e3a8a; border-right: 1px solid #1e40af; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] span, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #ffffff !important; }
    h1, h2, h3, h4, h5, h6 { color: #0f172a !important; }
    [data-testid="stSidebar"] .stButton>button { background-color: #2563eb !important; color: white !important; border-radius: 6px; font-weight: 600; border: 1px solid #3b82f6; }
    [data-testid="stSidebar"] .stButton>button:hover { background-color: #1d4ed8 !important; color: white !important; }
    .stButton>button, div.stFormSubmitButton>button { background-color: #10b981 !important; color: white !important; border-radius: 6px; font-weight: 600; border: none; }
    .stButton>button:hover, div.stFormSubmitButton>button:hover { background-color: #059669 !important; color: white !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-left: 4px solid #10b981; }
    .legenda-container { background-color: #ffffff; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; border-left: 5px solid #2563eb; }
    .popup-status-box { background-color: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-top: 20px; border-left: 5px solid #10b981; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📍 Roteiro MooveChain - Florianópolis")

# --- CONTROLE DE AUTENTICAÇÃO (ADMIN) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

st.sidebar.markdown("### 🔐 Acesso Administrativo")
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Senha do Administrador:", type="password")
    if st.sidebar.button("Entrar", key="btn_login"):
        senha_correta = st.secrets.get("admin_password", "moovechain2026")
        if senha_digitada == senha_correta:
            st.session_state["autenticado"] = True
            st.sidebar.success("✅ Acesso liberado!")
            st.rerun()
        else:
            st.sidebar.error("❌ Senha incorreta.")
else:
    st.sidebar.success("👤 Modo Administrador Ativo")
    if st.sidebar.button("Sair (Logout)", key="btn_logout"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")

# --- CONEXÃO E FUNÇÕES DO GOOGLE SHEETS & GEOLOCALIZAÇÃO ---
@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Roteiro MooveChain Florianópolis")

@st.cache_data(ttl=86400)
def geolocalizar_endereco(endereco):
    try:
        geolocator = Nominatim(user_agent="moovechain_floripa_geo_2026", timeout=12)
        query_completa = f"{endereco}, Florianópolis, SC, Brasil"
        location = geolocator.geocode(query_completa)
        if location:
            lat_f = float(location.latitude)
            lon_f = float(location.longitude)
            if -27.85 <= lat_f <= -27.30 and -48.65 <= lon_f <= -48.35:
                return str(lat_f), str(lon_f)
    except Exception:
        pass
    return "", ""

try:
    spreadsheet = conectar_sheets()
    sheet = spreadsheet.get_worksheet(0)
    todos_os_valores = sheet.get_all_values()
except Exception as e:
    st.error(f"❌ Erro ao ler a planilha: {e}")
    st.stop()

def obter_ou_criar_aba(nome_aba, cabecalho_padrao):
    try:
        aba = spreadsheet.worksheet(nome_aba)
    except gspread.exceptions.WorksheetNotFound:
        aba = spreadsheet.add_worksheet(title=nome_aba, rows=100, cols=10)
        aba.append_row(cabecalho_padrao)
    return aba

# --- GERENCIAMENTO DE ESTADO DO MENU DINÂMICO ---
OPCOES_MENU_BASE = [
    "📊 Dashboard Auditorias MooveChain",
    "🗺️ Visualizar Mapa de Pontos",
]

OPCOES_MENU_ADMIN = [
    "💰 Controle de Ganhos / Faturamento",
    "📋 Tabela de Dados e Ações",
    "✏️ Editar Registro Existente",
    "➕ Adicionar Novo Registro",
    "🛠️ Manutenção e Otimização do App",
    "🚚 Custos Logísticos (Frota)",
]

if st.session_state.get("autenticado", False):
    OPCOES_MENU = OPCOES_MENU_BASE + OPCOES_MENU_ADMIN
else:
    OPCOES_MENU = OPCOES_MENU_BASE

if "menu_selecionado" not in st.session_state or st.session_state["menu_selecionado"] not in OPCOES_MENU:
    st.session_state["menu_selecionado"] = OPCOES_MENU[0]

if "destinatario_para_editar" not in st.session_state:
    st.session_state["destinatario_para_editar"] = None
if "mensagem_sucesso_edicao" not in st.session_state:
    st.session_state["mensagem_sucesso_edicao"] = None

# --- MENU LATERAL EM ESTILO LISTA ---
st.sidebar.markdown("### Navegação")
for op in OPCOES_MENU:
    if st.sidebar.button(op, use_container_width=True, key=f"menu_btn_{op}"):
        st.session_state["menu_selecionado"] = op
        st.rerun()

opcao = st.session_state["menu_selecionado"]

LISTA_STATUS = ["Pendente", "Auditado", "Cancelado", "Justificado"]

# --- ROTEAMENTO DAS ABAS ---
if opcao == "📊 Dashboard Auditorias MooveChain":
    st.subheader("📊 Dashboard Auditorias MooveChain")
    st.markdown("---")
    st.info("Painel geral de visualização das auditorias em andamento.")

elif opcao == "💰 Controle de Ganhos / Faturamento" and st.session_state["autenticado"]:
    st.subheader("💰 Painel Restrito de Ganhos e Faturamento")
    st.markdown("---")
    st.markdown("Gerencie abaixo os pontos noturnos e visualize o faturamento detalhado por ponto auditado.")

elif opcao == "🗺️ Visualizar Mapa de Pontos":
    st.subheader("🗺️ Mapa Interativo de Pontos por Status")
    st.markdown("---")
    st.info("Carregando mapa interativo...")

elif opcao == "📋 Tabela de Dados e Ações" and st.session_state["autenticado"]:
    st.subheader("📋 Tabela de Destinatários e Rotas")
    st.markdown("---")
    if len(todos_os_valores) > 1:
        df_dados = pd.DataFrame(todos_os_valores[1:], columns=todos_os_valores[0])
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.warning("Nenhum dado encontrado na planilha.")

elif opcao == "✏️ Editar Registro Existente" and st.session_state["autenticado"]:
    st.subheader("✏️ Editar Registro na Planilha")
    st.markdown("---")
    st.info("Selecione um registro para editar as informações.")

elif opcao == "➕ Adicionar Novo Registro" and st.session_state["autenticado"]:
    st.subheader("➕ Novo Registro")
    st.markdown("---")
    with st.form("f_novo"):
        dest = st.text_input("Destinatário")
        rua = st.text_input("Rua")
        num = st.text_input("Número")
        bairro = st.text_input("Bairro")
        cid = st.text_input("Cidade", value="Florianópolis")
        est = st.text_input("Estado", value="SC")
        cep = st.text_input("CEP")
        st_novo = st.selectbox("Status", LISTA_STATUS)
        
        submitted = st.form_submit_button("Salvar Novo Registro")
        if submitted:
            if not dest or not rua:
                st.warning("⚠️ Preencha ao menos os campos Destinatário e Rua.")
            else:
                endereco_completo = f"{rua}, {num} - {bairro}"
                lat, lon = geolocalizar_endereco(endereco_completo)
                
                nova_linha = [dest, rua, num, bairro, cid, est, cep, endereco_completo, st_novo, lat, lon]
                try:
                    sheet.append_row(nova_linha)
                    st.success("✅ Registro adicionado com sucesso à planilha!")
                except Exception as e:
                    st.error(f"❌ Erro ao salvar na planilha: {e}")

elif opcao == "🛠️ Manutenção e Otimização do App" and st.session_state["autenticado"]:
    st.subheader("🛠️ Painel de Manutenção e Reparo de Dados")
    st.markdown("---")
    st.markdown("Utilize as ferramentas abaixo para escanear a base de dados em busca de inconsistências geográficas.")

elif opcao == "🚚 Custos Logísticos (Frota)" and st.session_state["autenticado"]:
    st.subheader("🚚 Controle de Custos Logísticos (Abastecimentos e Manutenções)")
    st.markdown("---")
    st.info("Módulo de controle de custos e manutenções da frota ativo.")
    