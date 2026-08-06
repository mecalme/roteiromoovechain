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

if "filtro_estado" not in st.session_state:
    st.session_state["filtro_estado"] = "Todos"
if "filtro_cidade" not in st.session_state:
    st.session_state["filtro_cidade"] = "Todos"
if "filtro_bairro" not in st.session_state:
    st.session_state["filtro_bairro"] = "Todos"
if "filtro_status" not in st.session_state:
    st.session_state["filtro_status"] = "Todos"

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

# --- 4. BARRA LATERAL E AUTENTICAÇÃO ---
st.sidebar.title("🚚 Navegação MooveChain")

# Opções públicas por padrão
opcoes_menu = ["Dashboard", "Mapa Interativo"]

# Se o administrador estiver autenticado, adiciona as abas restritas
if st.session_state["autenticado"]:
    opcoes_menu.extend([
        "Adicionar Novo Registro",
        "📋 Tabela de Dados e Ações",
        "🛠️ Manutenção e Limpeza de Coordenadas",
        "💰 Custos Logísticos"
    ])

opcao = st.sidebar.radio("Selecione a Secção", opcoes_menu)

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Acesso Administrativo")

if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Palavra-passe de Admin", type="password")
    if st.sidebar.button("Entrar"):
        senha_admin = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")
        if senha_digitada == senha_admin:
            st.session_state["autenticado"] = True
            st.sidebar.success("Acesso autorizado!")
            st.rerun()
        else:
            st.sidebar.error("Palavra-passe incorreta.")
else:
    st.sidebar.success("Sessão de Administrador Ativa")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["autenticado"] = False
        st.rerun()

# --- 5. LÓGICA DAS ABAS ---

if opcao == "Dashboard":
    st.title("📊 Dashboard Geral de Auditorias")
    
    if not df_dados.empty:
        # Tratamento de status para métricas robustas
        total_auditorias = len(df_dados)
        
        # Filtros seguros de status (insensíveis a maiúsculas/minúsculas)
        col_status = "Status" if "Status" in df_dados.columns else df_dados.columns[8]
        
        pendentes = len(df_dados[df_dados[col_status].astype(str).str.contains("Pendente", case=False, na=False)])
        justificadas = len(df_dados[df_dados[col_status].astype(str).str.contains("Justificad", case=False, na=False)])
        canceladas = len(df_dados[df_dados[col_status].astype(str).str.contains("Cancelad", case=False, na=False)])
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total de Auditorias", total_auditorias)
        m2.metric("Pendentes", pendentes)
        m3.metric("Justificadas", justificadas)
        m4.metric("Canceladas", canceladas)
        
        st.markdown("---")
        
        # NOVO GRÁFICO: Quantidade por Bairro discriminado por Status
        st.subheader("📍 Volume por Bairro detalhado por Status (Auditado, Justificado, Cancelado, Pendente)")
        if "Bairro" in df_dados.columns and col_status in df_dados.columns:
            df_bairro_status = df_dados.groupby(["Bairro", col_status]).size().reset_index(name="Quantidade")
            fig_bairro_status = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Quantidade",
                color=col_status,
                barmode="group",
                title="Distribuição de Auditorias por Bairro e Status"
            )
            st.plotly_chart(fig_bairro_status, use_container_width=True)
        else:
            st.info("Colunas de Bairro ou Status não encontradas para gerar o gráfico detalhado.")
    else:
        st.info("Sem dados disponíveis no momento.")

elif opcao == "Mapa Interativo":
    st.title("🗺️ Mapa Interativo de Auditorias")
    if not df_dados.empty and "Latitude" in df_dados.columns and "Longitude" in df_dados.columns:
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        marker_cluster = MarkerCluster().add_to(m)
        
        for _, row in df_dados.iterrows():
            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
                dest = row.get("Destinatário", "Local")
                status = row.get("Status", "N/D")
                folium.Marker(
                    location=[lat, lon],
                    popup=f"<b>{dest}</b><br>Status: {status}",
                    tooltip=dest
                ).add_to(marker_cluster)
            except:
                continue
        st_folium(m, width=1200, height=500)
    else:
        st.info("Coordenadas geográficas indisponíveis para exibição no mapa.")

elif opcao == "Adicionar Novo Registro":
    if st.session_state.get("autenticado", False):
        st.title("➕ Adicionar Novo Registro")
        st.write("Formulário para inclusão de novos locais de auditoria.")
        with st.form("form_novo_registro"):
            destinatario = st.text_input("Destinatário")
            rua = st.text_input("Rua")
            numero = st.text_input("Número")
            bairro = st.text_input("Bairro")
            cidade = st.text_input("Cidade", value="Florianópolis")
            estado = st.text_input("Estado", value="SC")
            cep = st.text_input("CEP")
            status_reg = st.selectbox("Status", ["Pendente", "Auditado", "Justificada", "Cancelada"])
            submitted = st.form_submit_button("Guardar Novo Registro")
            if submitted and worksheet_principal:
                novo_item = [destinatario, rua, numero, bairro, cidade, estado, cep, f"{rua}, {numero} - {bairro}, {cidade} - {estado}, CEP {cep}", status_reg, "", "", ""]
                worksheet_principal.append_row(novo_item)
                st.cache_data.clear()
                st.success("Registro adicionado com sucesso!")
                st.rerun()
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "📋 Tabela de Dados e Ações":
    if st.session_state.get("autenticado", False):
        st.title("📋 Tabela de Dados e Ações com Filtros Persistentes")
        
        if not df_dados.empty:
            # Painel de Filtros Persistentes
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            
            estados = ["Todos"] + list(df_dados["Estado"].dropna().unique()) if "Estado" in df_dados.columns else ["Todos"]
            cidades = ["Todos"] + list(df_dados["Cidade"].dropna().unique()) if "Cidade" in df_dados.columns else ["Todos"]
            bairros = ["Todos"] + list(df_dados["Bairro"].dropna().unique()) if "Bairro" in df_dados.columns else ["Todos"]
            status_list = ["Todos", "Pendente", "Auditado", "Justificada", "Cancelada"]
            
            with col_f1:
                st.session_state["filtro_estado"] = st.selectbox("Estado", estados, index=estados.index(st.session_state["filtro_estado"]) if st.session_state["filtro_estado"] in estados else 0)
            with col_f2:
                st.session_state["filtro_cidade"] = st.selectbox("Cidade", cidades, index=cidades.index(st.session_state["filtro_cidade"]) if st.session_state["filtro_cidade"] in cidades else 0)
            with col_f3:
                st.session_state["filtro_bairro"] = st.selectbox("Bairro", bairros, index=bairros.index(st.session_state["filtro_bairro"]) if st.session_state["filtro_bairro"] in bairros else 0)
            with col_f4:
                st.session_state["filtro_status"] = st.selectbox("Status", status_list, index=status_list.index(st.session_state["filtro_status"]) if st.session_state["filtro_status"] in status_list else 0)
            
            # Aplicar Filtros ao DataFrame
            df_filtrado = df_dados.copy()
            if st.session_state["filtro_estado"] != "Todos" and "Estado" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Estado"] == st.session_state["filtro_estado"]]
            if st.session_state["filtro_cidade"] != "Todos" and "Cidade" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Cidade"] == st.session_state["filtro_cidade"]]
            if st.session_state["filtro_bairro"] != "Todos" and "Bairro" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Bairro"] == st.session_state["filtro_bairro"]]
            if st.session_state["filtro_status"] != "Todos" and "Status" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Status"].astype(str).str.contains(st.session_state["filtro_status"], case=False, na=False)]
            
            st.write(f"A exibir {len(df_filtrado)} registros filtrados:")
            
            # Tabela Interativa com suporte a seleção e edição direta (Ativação correta dos botões)
            df_editado = st.data_editor(
                df_filtrado,
                use_container_width=True,
                num_rows="dynamic",
                key="tabela_editor_dados"
            )
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("💾 Gravar Alterações na Planilha"):
                    try:
                        # Atualiza a planilha inteira ou sincroniza as modificações
                        updated_data = [df_dados.columns.tolist()] + df_editado.values.tolist()
                        worksheet_principal.clear()
                        worksheet_principal.update(updated_data)
                        st.cache_data.clear()
                        st.success("Alterações gravadas com sucesso no Google Sheets!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao gravar alterações: {e}")
        else:
            st.info("Sem dados disponíveis na tabela.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "🛠️ Manutenção e Limpeza de Coordenadas":
    if st.session_state.get("autenticado", False):
        st.title("🛠️ Manutenção e Limpeza de Coordenadas")
        st.write("Ferramentas de suporte geográfico e validação de moradas.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "💰 Custos Logísticos":
    if st.session_state.get("autenticado", False):
        st.title("💰 Custos Logísticos")
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
            
            if not df_custos.empty:
                st.dataframe(df_custos, use_container_width=True)
                
                # Gráfico de pizza de Custos se houver coluna adequada
                if "Categoria" in df_custos.columns and "Valor" in df_custos.columns:
                    fig_pizza = px.pie(df_custos, names="Categoria", values="Valor", title="Distribuição de Custos Logísticos")
                    st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.info("Nenhum dado encontrado na aba Controle_Custos.")
        except Exception as e:
            st.error(f"Erro ao carregar custos logísticos: {e}")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")