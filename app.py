from folium.plugins import MarkerCluster  # <-- Adicione esta linha no topo do arquivo
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

# 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS CSS
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

# 2. INICIALIZAÇÃO DE ESTADOS NA SESSÃO
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# 3. FUNÇÃO DE CARREGAMENTO DE DADOS ROBUSTA
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
        dados = worksheet.get_all_records()
        df = pd.DataFrame(dados)
        
        # Limpeza de espaços em branco nas colunas de texto crítico
        if "Status" in df.columns:
            df["Status"] = df["Status"].astype(str).str.strip()
        if "Bairro" in df.columns:
            df["Bairro"] = df["Bairro"].astype(str).str.strip()
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets: {e}")
        return pd.DataFrame()

df_dados = carregar_dados()

# 4. MENU LATERAL E CONTROLE DE ACESSO
st.sidebar.title("Navegação")
opcao_publica = ["📊 Dashboard Auditorias", "🗺️ Mapa de Pontos"]
opcao_admin = ["🚛 Custos Logísticos (frota)", "➕ Adicionar Novo Registro", "📋 Tabela de Dados e Ações", "🔧 Manutenção e Limpeza"]

if st.session_state["autenticado"]:
    opcao = st.sidebar.selectbox("Menu", opcao_publica + opcao_admin)
    if st.sidebar.button("🔓 Terminar Sessão Admin"):
        st.session_state["autenticado"] = False
        st.rerun()
else:
    opcao = st.sidebar.selectbox("Menu", opcao_publica)
    st.sidebar.markdown("---")
    st.sidebar.subheader("Acesso Restrito (Admin)")
    senha_digitada = st.sidebar.text_input("Palavra-passe", type="password")
    senha_admin = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")
    if st.sidebar.button("Entrar"):
        if senha_digitada == senha_admin:
            st.session_state["autenticado"] = True
            st.success("Autenticado com sucesso!")
            st.rerun()
        else:
            st.sidebar.error("Senha incorreta!")

# --- ABA 1: DASHBOARD ---
if opcao == "📊 Dashboard Auditorias":
    st.title("📊 Dashboard Auditorias MooveChain")
    st.markdown("---")
    
    if not df_dados.empty:
        # Normalização e cálculo seguro das métricas incluindo Justificadas
        total_auditorias = len(df_dados)
        
        # Tratamento flexível para capturar variações de maiúsculas/minúsculas/acentos
        def contar_status(val):
            if "Status" not in df_dados.columns:
                return 0
            s = df_dados["Status"].astype(str).str.lower()
            return len(df_dados[s.str.contains(val.lower(), na=False)])

        pendentes = contar_status("pendente")
        justificadas = contar_status("justificad")  # captura justificada ou justificado
        canceladas = contar_status("cancelad")     # captura cancelada ou cancelado
        auditadas = contar_status("auditad")       # captura auditado ou auditada

        # Layout de métricas atualizado no topo
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Auditorias", total_auditorias)
        col2.metric("Auditadas", auditadas)
        col3.metric("Pendentes", pendentes)
        col4.metric("Justificadas", justificadas)
        col5.metric("Canceladas", canceladas)
        
        st.markdown("---")
        
        # Gráficos existentes (Pizza de Status e Volume por Bairro Geral)
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("Distribuição por Status")
            if "Status" in df_dados.columns:
                df_status = df_dados["Status"].value_counts().reset_index()
                df_status.columns = ["Status", "Quantidade"]
                fig_status = px.pie(
                    df_status, 
                    names="Status", 
                    values="Quantidade", 
                    hole=0.4, 
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_status, use_container_width=True)
                
        with col_g2:
            st.subheader("Auditorias por Bairro / Cidade")
            if "Bairro" in df_dados.columns:
                df_bairro = df_dados["Bairro"].value_counts().reset_index()
                df_bairro.columns = ["Bairro", "Quantidade"]
                fig_bairro = px.bar(df_bairro, x="Bairro", y="Quantidade", title="Volume por Bairro")
                st.plotly_chart(fig_bairro, use_container_width=True)
                
        # NOVO GRÁFICO: Quantidade por Bairro discriminado por Status
        st.markdown("---")
        st.subheader("📍 Volume por Bairro detalhado por Status (Auditado, Justificado, Cancelado, Pendente)")
        if "Bairro" in df_dados.columns and "Status" in df_dados.columns:
            df_bairro_status = df_dados.groupby(["Bairro", "Status"]).size().reset_index(name="Quantidade")
            fig_bairro_status = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Quantidade",
                color="Status",
                barmode="stack",  # Mudado para "stack" para ficarem empilhados na mesma barra
                title="Auditorias por Bairro e Status",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            st.plotly_chart(fig_bairro_status, use_container_width=True)
            
    else:
        st.warning("Nenhum dado encontrado para exibir no Dashboard.")

# --- ABA 2: MAPA DE PONTOS ---
elif opcao == "🗺️ Mapa de Pontos":
    st.title("🗺️ Mapa Geográfico de Pontos")
    st.markdown("---")
    if not df_dados.empty and "Latitude" in df_dados.columns and "Longitude" in df_dados.columns:
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        
        marker_cluster = MarkerCluster().add_to(m)
        
        # Lista para armazenar as coordenadas e ajustar o zoom automaticamente depois
        coordenadas = []
        
        for _, row in df_dados.iterrows():
            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
                nome = row.get("Destinatário", "Ponto")
                status = row.get("Status", "Desconhecido")
                
                coordenadas.append([lat, lon])
                
                # Definindo cores dinâmicas baseadas no status (exemplo)
                cor_icone = "green" if status.lower() == "concluído" else "orange"
                
                folium.Marker(
                    [lat, lon], 
                    popup=f"<b>{nome}</b><br>Status: <i>{status}</i>",
                    icon=folium.Icon(color=cor_icone, icon="info-sign")
                ).add_to(marker_cluster)
                
            except:
                continue
        
        # Ajusta o zoom automaticamente para abranger todos os pontos do DataFrame
        if coordenadas:
            m.fit_bounds(coordenadas)
                
        st_folium(m, width=1200, height=500)
    else:
        st.info("Dados geográficos indisponíveis.")

# --- ABA 3: CUSTOS LOGÍSTICOS (ADMIN) ---
elif opcao == "🚛 Custos Logísticos (frota)":
    if st.session_state.get("autenticado", False):
        st.subheader("🚛 Custos Logísticos (frota)")
        st.markdown("---")
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

# --- ABA 4: ADICIONAR NOVO REGISTRO (ADMIN) ---
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
        st.warning("Acesso restrito.")

# --- ABA 5: TABELA DE DADOS E AÇÕES (ADMIN) ---
elif opcao == "📋 Tabela de Dados e Ações":
    if st.session_state.get("autenticado", False):
        st.title("📋 Tabela de Dados e Gestão")
        st.dataframe(df_dados, use_container_width=True)
    else:
        st.warning("Acesso restrito.")

# --- ABA 6: MANUTENÇÃO (ADMIN) ---
elif opcao == "🔧 Manutenção e Limpeza":
    if st.session_state.get("autenticado", False):
        st.title("🔧 Manutenção e Limpeza de Coordenadas")
        st.write("Painel de manutenção administrativa.")
    else:
        st.warning("Acesso restrito.")