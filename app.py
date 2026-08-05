import logging
import re
import gspread
import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis 2026",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração de logs para capturar erros sem interromper a interface
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Injeção de CSS personalizado
st.markdown("""
    <style>
        .main {
            background-color: #f8f9fa;
        }
        .stMetric {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .css-1d3 Sterling {
            padding-top: 1rem;
        }
        .stButton>button {
            border-radius: 8px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. INICIALIZAÇÃO DE ESTADOS NA SESSÃO
# -----------------------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# -----------------------------------------------------------------------------
# 3. CONEXÃO COM O GOOGLE SHEETS
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Conectando ao Google Sheets...")
def obter_cliente_gspread():
    """Autentica e retorna o cliente do gspread usando st.secrets."""
    try:
        escopo = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        credenciais_dict = dict(st.secrets["gcp_service_account"])
        credenciais = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, escopo)
        return gspread.authorize(credenciais)
    except Exception as e:
        logging.error(f"Erro ao autenticar no Google Sheets: {e}")
        st.error("Não foi possível conectar ao Google Sheets. Verifique as credenciais em st.secrets.")
        return None

@st.cache_data(ttl=300, show_spinner="Carregando dados da planilha...")
def carregar_dados():
    """Carrega os dados da planilha e converte para DataFrame Pandas."""
    client = obter_cliente_gspread()
    if not client:
        return pd.DataFrame()
    try:
        sheet_url = st.secrets.get("SHEET_URL", "")
        if sheet_url:
            sheet = client.open_by_url(sheet_url).sheet1
        else:
            sheet = client.open("Roteiro MooveChain").sheet1
        
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        logging.error(f"Erro ao carregar dados: {e}")
        st.error(f"Erro ao acessar a planilha: {e}")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# 4. FUNÇÃO DE GEOLOCALIZAÇÃO
# -----------------------------------------------------------------------------
def geolocalizar_endereco(endereco: str):
    """
    Geolocaliza um endereço em Florianópolis/SC e valida as coordenadas.
    Retorna uma tupla (latitude, longitude) ou ("","") em caso de falha.
    """
    if not endereco or not isinstance(endereco, str):
        return "", ""
        
    geolocator = Nominatim(user_agent="moovechain_geocoder_app_v2")
    try:
        # Força o contexto para Florianópolis, SC
        query = f"{endereco}, Florianópolis, Santa Catarina, Brasil"
        location = geolocator.geocode(query, timeout=10)
        
        if location:
            lat, lon = location.latitude, location.longitude
            
            # Limites geográficos (Bounding Box) de Florianópolis e arredores próximos
            if -27.90 <= lat <= -27.35 and -48.70 <= lon <= -48.30:
                return str(lat), str(lon)
            else:
                logging.warning(f"Endereço '{endereco}' gerou coordenadas fora do limite: ({lat}, {lon})")
                return "", ""
    except Exception as e:
        logging.error(f"Falha na geolocalização do endereço '{endereco}': {e}")
        
    return "", ""

# -----------------------------------------------------------------------------
# 5. CONTROLE DE ACESSO E MENU LATERAL
# -----------------------------------------------------------------------------
st.sidebar.title("🚚 MooveChain")
st.sidebar.markdown("---")

# Seção de Login na Sidebar
st.sidebar.subheader("🔒 Autenticação")
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Senha Admin", type="password", key="input_senha")
    senha_correta = st.secrets.get("ADMIN_PASSWORD", "admin123")
    
    if st.sidebar.button("Entrar"):
        if senha_digitada == senha_correta:
            st.session_state["autenticado"] = True
            st.sidebar.success("Acesso Admin concedido!")
            st.rerun()
        else:
            st.sidebar.error("Senha incorreta!")
else:
    st.sidebar.success("Modo Administrador Ativo")
    if st.sidebar.button("Sair (Logout)"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")

# Construção Dinâmica das Opções do Menu
OPCOES_MENU = [
    "📊 Dashboard Auditorias",
    "🗺️ Mapa de Pontos",
    "🚚 Custos Logísticos (Frota)"
]

if st.session_state["autenticado"]:
    OPCOES_MENU.extend([
        "➕ Adicionar Novo Registro",
        "📋 Tabela de Dados e Ações",
        "🧹 Manutenção e Limpeza de Coordenadas"
    ])

opcao = st.sidebar.radio("Selecione a Ferramenta:", OPCOES_MENU)

# -----------------------------------------------------------------------------
# 6. RENDERIZAÇÃO DAS ABAS / PÁGINAS
# -----------------------------------------------------------------------------
df_dados = carregar_dados()

# --- ABA 1: DASHBOARD ---
if opcao == "📊 Dashboard Auditorias":
    st.title("📊 Dashboard Auditorias MooveChain")
    
    if df_dados.empty:
        st.warning("Nenhum dado encontrado na planilha.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Registros", len(df_dados))
        
        col_status = next((c for c in df_dados.columns if "status" in c.lower()), None)
        if col_status:
            c2.metric("Status Concluídos", len(df_dados[df_dados[col_status].astype(str).str.lower() == "concluído"]))
            c3.metric("Status Pendentes", len(df_dados[df_dados[col_status].astype(str).str.lower() != "concluído"]))
            
            fig = px.pie(df_dados, names=col_status, title="Distribuição por Status")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Coluna de 'Status' não encontrada para métricas detalhadas.")

# --- ABA 2: MAPA DE PONTOS ---
elif opcao == "🗺️ Mapa de Pontos":
    st.title("🗺️ Mapa Geográfico de Pontos")
    
    col_lat = next((c for c in df_dados.columns if "lat" in c.lower()), None)
    col_lon = next((c for c in df_dados.columns if "lon" in c.lower() or "lng" in c.lower()), None)
    
    if col_lat and col_lon:
        # Converte e filtra coordenadas válidas
        df_mapa = df_dados.copy()
        df_mapa["lat_num"] = pd.to_numeric(df_mapa[col_lat], errors="coerce")
        df_mapa["lon_num"] = pd.to_numeric(df_mapa[col_lon], errors="coerce")
        
        # Filtra dentro dos limites válidos de Florianópolis
        df_mapa = df_mapa.dropna(subset=["lat_num", "lon_num"])
        df_mapa = df_mapa[
            (df_mapa["lat_num"] >= -27.90) & (df_mapa["lat_num"] <= -27.35) &
            (df_mapa["lon_num"] >= -48.70) & (df_mapa["lon_num"] <= -48.30)
        ]
        
        if not df_mapa.empty:
            m = folium.Map(location=[-27.5948, -48.5482], zoom_start=11)
            for _, row in df_mapa.iterrows():
                info = str(row.get("Nome", row.get("Endereco", "Ponto MooveChain")))
                folium.Marker(
                    location=[row["lat_num"], row["lon_num"]],
                    popup=info,
                    tooltip=info,
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)
            
            st_folium(m, width=1100, height=500)
            st.caption(f"Exibindo {len(df_mapa)} pontos geolocalizados com sucesso.")
        else:
            st.warning("Nenhum ponto com coordenadas válidas em Florianópolis foi encontrado.")
    else:
        st.error("Colunas de Latitude e Longitude não encontradas no DataFrame.")

# --- ABA 3: CUSTOS LOGÍSTICOS ---
elif opcao == "🚚 Custos Logísticos (Frota)":
    st.title("🚚 Controle de Custos Logísticos (Frota)")
    st.info("Módulo de gestão financeira e operacional da frota MooveChain.")
    
    if not df_dados.empty:
        st.dataframe(df_dados.head(10), use_container_width=True)

# --- ABA 4: ADICIONAR NOVO REGISTRO (ADMIN) ---
elif opcao == "➕ Adicionar Novo Registro":
    st.title("➕ Adicionar Novo Registro")
    
    with st.form("form_novo_registro"):
        nome = st.text_input("Nome / Identificador:")
        endereco = st.text_input("Endereço (Florianópolis):")
        observacao = st.text_area("Observações:")
        
        submetido = st.form_submit_button("Salvar Registro")
        
        if submetido:
            if not endereco:
                st.error("Por favor, preencha o endereço.")
            else:
                lat, lon = geolocalizar_endereco(endereco)
                if lat and lon:
                    st.success(f"Endereço geolocalizado com sucesso: ({lat}, {lon})")
                else:
                    st.warning("Não foi possível geolocalizar o endereço com precisão. O registro será salvo sem coordenadas ajustadas.")
                
                # Lógica para salvar na planilha via gspread...
                st.cache_data.clear()

# --- ABA 5: TABELA E AÇÕES (ADMIN) ---
elif opcao == "📋 Tabela de Dados e Ações":
    st.title("📋 Gerenciamento de Tabela de Dados")
    
    if not df_dados.empty:
        st.dataframe(df_dados, use_container_width=True)
        
        if st.button("🔄 Recarregar Dados"):
            st.cache_data.clear()
            st.rerun()

# --- ABA 6: MANUTENÇÃO E LIMPEZA (ADMIN) ---
elif opcao == "🧹 Manutenção e Limpeza de Coordenadas":
    st.title("🧹 Ferramenta de Limpeza de Coordenadas Inválidas")
    st.markdown("Identifique e corrija registros que possuem coordenadas fora de Florianópolis ou formatadas incorretamente.")
    
    col_lat = next((c for c in df_dados.columns if "lat" in c.lower()), None)
    col_lon = next((c for c in df_dados.columns if "lon" in c.lower() or "lng" in c.lower()), None)
    
    if col_lat and col_lon:
        df_corrup = df_dados.copy()
        df_corrup["lat_num"] = pd.to_numeric(df_corrup[col_lat], errors="coerce")
        df_corrup["lon_num"] = pd.to_numeric(df_corrup[col_lon], errors="coerce")
        
        # Filtra entradas fora dos limites normais ou nulas
        invalidos = df_corrup[
            df_corrup["lat_num"].isna() | 
            df_corrup["lon_num"].isna() |
            (df_corrup["lat_num"] < -27.90) | (df_corrup["lat_num"] > -27.35) |
            (df_corrup["lon_num"] < -48.70) | (df_corrup["lon_num"] > -48.30)
        ]
        
        st.subheader(f"Linhas com Coordenadas Suspeitas ou Inexistentes: {len(invalidos)}")
        if not invalidos.empty:
            st.dataframe(invalidos[[c for c in [col_lat, col_lon, "Endereco", "Nome"] if c in invalidos.columns]])
        else:
            st.success("Todas as coordenadas da planilha parecem estar corretas!")