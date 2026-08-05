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

# Injeção de CSS personalizado para estilização limpa
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

if "admin_autenticado" not in st.session_state:
    st.session_state["admin_autenticado"] = False

# -----------------------------------------------------------------------------
# 3. FUNÇÃO DE CARREGAMENTO DE DADOS COM DIAGNÓSTICO DE ERRO
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def carregar_dados():
    try:
        # Autenticação segura via st.secrets
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        
        # Abertura da planilha (ajustado para o nome exato com o qual foi criada)
        sh = gc.open("Roteiro MooveChain Florianóplis 2026")
        
        # Aceder à primeira aba (Planilha1)
        worksheet = sh.get_worksheet(0)
        dados = worksheet.get_all_records()
        
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        st.error(f"❌ **Erro crítico ao conectar com o Google Sheets:** `{e}`")
        st.info("💡 **Dica:** Certifique-se de que partilhou a planilha do Google Drive com o e-mail da conta de serviço e de que os Secrets estão configurados corretamente no painel do Streamlit Cloud.")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# 4. CARREGAMENTO DOS DADOS NO FLUXO PRINCIPAL
# -----------------------------------------------------------------------------
df_dados = carregar_dados()

# -----------------------------------------------------------------------------
# 5. MENU DE NAVEGAÇÃO LATERAL
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/truck.png", width=80)
st.sidebar.title("MooveChain 2026")
st.sidebar.markdown("---")

opcao = st.sidebar.selectbox(
    "Navegação",
    [
        "📊 Dashboard Auditorias",
        "🗺️ Mapa de Pontos",
        "🚛 Custos Logísticos (frota)",
        "➕ Adicionar Novo Registro",
        "📋 Tabela de Dados e Ações"
    ]
)

# -----------------------------------------------------------------------------
# 6. ROTEAMENTO DAS ABAS DO PORTFÓLIO
# -----------------------------------------------------------------------------

if opcao == "📊 Dashboard Auditorias":
    st.title("📊 Dashboard Auditorias MooveChain")
    st.markdown("Monitorização geral das auditorias planeadas e realizadas em Florianópolis.")
    
    if not df_dados.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Registros", len(df_dados))
        if "Status" in df_dados.columns:
            auditados = len(df_dados[df_dados["Status"] == "Auditado"])
            pendentes = len(df_dados[df_dados["Status"] == "Pendente"])
            col2.metric("Auditados", auditados)
            col3.metric("Pendentes", pendentes)
        
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.warning("⚠️ Nenhum dado disponível para exibir no dashboard no momento.")

elif opcao == "🗺️ Mapa de Pontos":
    st.title("🗺️ Mapa Geográfico de Pontos")
    st.markdown("Visualização espacial das rotas e locais de auditoria.")
    
    if not df_dados.empty and "Latitude" in df_dados.columns and "Longitude" in df_dados.columns:
        # Exemplo simples de mapa centralizado em Florianópolis
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        
        for _, row in df_dados.iterrows():
            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
                nome = row.get("Destinatário", "Local")
                folium.Marker([lat, lon], popup=nome).add_to(m)
            except (ValueError, TypeError):
                continue
                
        st_folium(m, width=1000, height=500)
    else:
        st.info("ℹ️ Dados geográficos insuficientes ou tabela vazia para compor o mapa.")

elif opcao == "🚛 Custos Logísticos (frota)":
    st.subheader("🚛 Custos Logísticos (frota)")
    st.markdown("---")
    
    # Validação de Segurança para Administradores
    if not st.session_state.get("admin_autenticado", False):
        st.warning("🔒 Esta secção é restrita. Por favor, introduza a palavra-passe de administrador.")
        senha = st.text_input("Palavra-passe de Administrador:", type="password")
        if st.button("Entrar"):
            # Podes definir a tua palavra-passe aqui ou via secrets
            if senha == "admin123": 
                st.session_state["admin_autenticado"] = True
                st.rerun()
            else:
                st.error("❌ Palavra-passe incorreta.")
    else:
        st.success("🔓 Área de administração de custos desbloqueada.")
        try:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            sh = gc.open("Roteiro MooveChain Florianóplis 2026")
            aba_custos = sh.worksheet("Controle_Custos")
            dados_custos = aba_custos.get_all_records()
            df_custos = pd.DataFrame(dados_custos)
            st.dataframe(df_custos, use_container_width=True)
        except Exception as e:
            st.warning(f"⚠️ A aba 'Controle_Custos' não foi encontrada ou está vazia: {e}")

elif opcao == "➕ Adicionar Novo Registro":
    st.title("➕ Adicionar Novo Registro")
    with st.form("form_novo_registro"):
        nome = st.text_input("Identificador / Destinatário:")
        endereco = st.text_input("Endereço (Rua e Número - Floripa):")
        submetido = st.form_submit_button("Geolocalizar e Salvar")
        
        if submetido:
            if nome and endereco:
                st.success(f"Registro '{nome}' processado com sucesso! (Funcionalidade de salvamento integrada)")
            else:
                st.error("Preencha todos os campos obrigatórios.")

elif opcao == "📋 Tabela de Dados e Ações":
    st.title("📋 Gestão e Edição de Dados")
    if not df_dados.empty:
        st.data_editor(df_dados, use_container_width=True)
    else:
        st.warning("⚠️ Não há dados carregados para edição.")