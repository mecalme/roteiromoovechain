import logging
import re
import gspread
import pandas as pd
import plotly.express as px
import folium
import streamlit as st
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# NOVO IMPORT: Biblioteca de autenticação moderna e suportada pelo Google
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
# 3. CONEXÃO COM O GOOGLE SHEETS (NOVA LÓGICA DE AUTENTICAÇÃO)
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Autenticando no Google Drive...")
def obter_cliente_gspread():
    """Autentica e retorna o cliente gspread usando a biblioteca google-auth moderna."""
    try:
        # Novos escopos modernos recomendados pela Google
        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Obtém o dicionário de credenciais dos secrets
        # Nota: Ajuste "gcp_service_account" para o nome que você usou no seu secrets.toml
        # Pode ser que esteja como "google_credentials" ou algo similar no seu ambiente.
        cred_dict = dict(st.secrets["gcp_service_account"])
        
        # TRATAMENTO CRÍTICO: Corrige a quebra de linha da chave privada para evitar o erro de RSA Inválida
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            
        # Cria as credenciais e autoriza a conexão
        credenciais = Credentials.from_service_account_info(cred_dict, scopes=escopos)
        return gspread.authorize(credenciais)
        
    except Exception as e:
        logging.error(f"Erro Crítico de Autenticação: {e}")
        st.error(f"Falha na autenticação com o Google: {e}. Verifique as chaves no Painel do Streamlit.")
        return None

@st.cache_data(ttl=300, show_spinner="Baixando dados da planilha...")
def carregar_dados():
    """Abre a planilha e converte os dados para um DataFrame do Pandas."""
    client = obter_cliente_gspread()
    if not client:
        return pd.DataFrame()
        
    try:
        # Abre a planilha pelo nome exato do arquivo (recomendado usar URL se o nome falhar)
        # Se preferir usar URL: sheet = client.open_by_url("SUA_URL_AQUI").sheet1
        sheet = client.open("Roteiro MooveChain Florianóplis 2026").sheet1
        
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)
        return df
    except Exception as e:
        logging.error(f"Erro ao ler os dados da planilha: {e}")
        st.error("Conexão feita, mas não foi possível ler a planilha. Verifique se o e-mail de serviço tem permissão de Editor nela.")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# 4. FUNÇÃO DE GEOLOCALIZAÇÃO
# -----------------------------------------------------------------------------
def geolocalizar_endereco(endereco: str):
    if not endereco or not isinstance(endereco, str):
        return "", ""
        
    geolocator = Nominatim(user_agent="moovechain_geocoder_app_v2")
    try:
        query = f"{endereco}, Florianópolis, Santa Catarina, Brasil"
        location = geolocator.geocode(query, timeout=10)
        
        if location:
            lat, lon = location.latitude, location.longitude
            # Limites geográficos de Florianópolis e arredores
            if -27.90 <= lat <= -27.35 and -48.70 <= lon <= -48.30:
                return str(lat), str(lon)
            else:
                logging.warning(f"Coordenadas ignoradas por estarem fora da região: ({lat}, {lon})")
                return "", ""
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
    senha_correta = st.secrets.get("ADMIN_PASSWORD", "moovechain2026") # Senha padrão atualizada
    
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

# Opções de Menu
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

opcao = st.sidebar.radio("Navegação:", OPCOES_MENU, label_visibility="collapsed")

# -----------------------------------------------------------------------------
# 6. RENDERIZAÇÃO DAS ABAS / PÁGINAS
# -----------------------------------------------------------------------------
df_dados = carregar_dados()

# --- ABA 1: DASHBOARD ---
if opcao == "📊 Dashboard Auditorias":
    st.title("📊 Dashboard Auditorias MooveChain")
    
    if df_dados.empty:
        st.warning("Nenhum dado encontrado na planilha. Verifique a aba de manutenção.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Registros", len(df_dados))
        
        col_status = next((c for c in df_dados.columns if "status" in c.lower()), None)
        if col_status:
            concluidos = len(df_dados[df_dados[col_status].astype(str).str.lower().isin(["concluído", "auditado"])])
            c2.metric("Pontos Auditados", concluidos)
            c3.metric("Pontos Pendentes", len(df_dados) - concluidos)
            
            fig = px.pie(df_dados, names=col_status, title="Distribuição por Status", hole=0.3)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Gráfico indisponível: Coluna 'Status' não encontrada na base.")

# --- ABA 2: MAPA DE PONTOS ---
elif opcao == "🗺️ Mapa de Pontos":
    st.title("🗺️ Mapa Geográfico de Pontos")
    
    col_lat = next((c for c in df_dados.columns if "lat" in c.lower()), None)
    col_lon = next((c for c in df_dados.columns if "lon" in c.lower() or "lng" in c.lower()), None)
    
    if col_lat and col_lon:
        df_mapa = df_dados.copy()
        df_mapa["lat_num"] = pd.to_numeric(df_mapa[col_lat], errors="coerce")
        df_mapa["lon_num"] = pd.to_numeric(df_mapa[col_lon], errors="coerce")
        
        df_mapa = df_mapa.dropna(subset=["lat_num", "lon_num"])
        df_mapa = df_mapa[
            (df_mapa["lat_num"] >= -27.90) & (df_mapa["lat_num"] <= -27.35) &
            (df_mapa["lon_num"] >= -48.70) & (df_mapa["lon_num"] <= -48.30)
        ]
        
        if not df_mapa.empty:
            m = folium.Map(location=[-27.5948, -48.5482], zoom_start=11)
            for _, row in df_mapa.iterrows():
                info = str(row.get(df_mapa.columns[0], "Ponto MooveChain"))
                folium.Marker(
                    location=[row["lat_num"], row["lon_num"]],
                    popup=info,
                    tooltip=info,
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)
            
            st_folium(m, width=1100, height=500)
        else:
            st.warning("Nenhum ponto com coordenadas válidas para exibição.")

# --- ABA 3: CUSTOS LOGÍSTICOS ---
elif opcao == "🚛 Custos Logísticos (frota)":  # (ou o nome exato que usas no teu menu)
    if st.session_state.get("admin_autenticado", False):
        st.subheader("🚛 Custo Logísticos (frota)")
        st.markdown("---")
        try:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            sh = gc.open("Roteiro MooveChain Florianóplis 2026")
            aba_custos = sh.worksheet("Controle_Custos")
            dados_custos = aba_custos.get_all_records()
            
            if dados_custos:
                df_custos = pd.DataFrame(dados_custos)
                st.dataframe(df_custos, use_container_width=True)
            else:
                st.warning("A aba 'Controle_Custos' está vazia.")
        except Exception as e:
            st.error(f"Erro ao carregar a aba: {e}")
    else:
        st.warning("🔒 Esta seção é restrita aos administradores do sistema.")

# --- ABA 4: ADICIONAR NOVO REGISTRO (ADMIN) ---
elif opcao == "➕ Adicionar Novo Registro":
    st.title("➕ Adicionar Novo Registro")
    with st.form("form_novo_registro"):
        nome = st.text_input("Identificador / Destinatário:")
        endereco = st.text_input("Endereço (Rua e Número - Floripa):")
        submetido = st.form_submit_button("Geolocalizar e Salvar")
        
        if submetido:
            if endereco:
                lat, lon = geolocalizar_endereco(endereco)
                if lat and lon:
                    st.success(f"Sucesso! Coordenadas geradas: ({lat}, {lon})")
                else:
                    st.warning("Atenção: Não foi possível obter as coordenadas precisas para este endereço.")
            else:
                st.error("Preencha o endereço.")

# --- ABA 5: TABELA E AÇÕES (ADMIN) ---
elif opcao == "📋 Tabela de Dados e Ações":
    st.title("📋 Gerenciamento da Tabela")
    if not df_dados.empty:
        st.dataframe(df_dados, use_container_width=True)
        if st.button("🔄 Forçar Atualização de Dados"):
            st.cache_data.clear()
            st.rerun()

# --- ABA 6: MANUTENÇÃO E LIMPEZA (ADMIN) ---
elif opcao == "🧹 Manutenção e Limpeza de Coordenadas":
    st.title("🧹 Ferramenta de Limpeza de Coordenadas")
    
    col_lat = next((c for c in df_dados.columns if "lat" in c.lower()), None)
    col_lon = next((c for c in df_dados.columns if "lon" in c.lower() or "lng" in c.lower()), None)
    
    if col_lat and col_lon:
        df_corrup = df_dados.copy()
        df_corrup["lat_num"] = pd.to_numeric(df_corrup[col_lat], errors="coerce")
        df_corrup["lon_num"] = pd.to_numeric(df_corrup[col_lon], errors="coerce")
        
        invalidos = df_corrup[
            df_corrup["lat_num"].isna() | df_corrup["lon_num"].isna() |
            (df_corrup["lat_num"] < -27.90) | (df_corrup["lat_num"] > -27.35) |
            (df_corrup["lon_num"] < -48.70) | (df_corrup["lon_num"] > -48.30)
        ]
        
        if not invalidos.empty:
            st.error(f"⚠️ Atenção: {len(invalidos)} registros com coordenadas fora de SC ou corrompidas (ex: -51.635).")
            st.dataframe(invalidos)
        else:
            st.success("Tudo certo! Sem lixo geográfico detectado.")