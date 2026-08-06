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

# Inicializar estados para filtros persistentes
if "filtro_estado" not in st.session_state:
    st.session_state["filtro_estado"] = []
if "filtro_cidade" not in st.session_state:
    st.session_state["filtro_cidade"] = []
if "filtro_bairro" not in st.session_state:
    st.session_state["filtro_bairro"] = []
if "filtro_status" not in st.session_state:
    st.session_state["filtro_status"] = []

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
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df, worksheet
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Sheets: {e}")
        return pd.DataFrame(), None

df_dados, worksheet = carregar_dados()

# --- 4. BARRA LATERAL E NAVEGAÇÃO ---
st.sidebar.title("🚚 MooveChain 2026")

# Autenticação de Administrador
senha_input = st.sidebar.text_input("Palavra-passe de Administrador", type="password")
senha_correta = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")

if senha_input == senha_correta:
    st.session_state["autenticado"] = True
    st.sidebar.success("Modo Administrador Ativo")
elif senha_input and senha_input != senha_correta:
    st.sidebar.error("Palavra-passe incorreta")

# Definição das Opções do Menu Lateral (Respeitando a visibilidade por senha)
opcoes_menu = ["📊 Dashboard", "🗺️ Mapa Interativo"]
if st.session_state["autenticado"]:
    opcoes_menu.extend([
        "➕ Adicionar Novo Registro",
        "📋 Tabela de Dados e Ações",
        "🛠️ Manutenção e Limpeza de Coordenadas",
        "💰 Custos Logísticos"
    ])

opcao = st.sidebar.radio("Navegação", opcoes_menu)

# --- 5. LÓGICA DAS ABAS ---

if opcao == "📊 Dashboard":
    st.title("📊 Dashboard Executivo de Auditorias")
    
    if not df_dados.empty:
        # Tratamento do status para métricas
        total_auditorias = len(df_dados)
        
        def conta_status(termo):
            if "Status" in df_dados.columns:
                return len(df_dados[df_dados["Status"].astype(str).str.contains(termo, case=False, na=False)])
            return 0

        pendentes = conta_status("Pendente")
        justificadas = conta_status("Justificad")
        canceladas = conta_status("Cancelad")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Auditorias", total_auditorias)
        col2.metric("Pendentes", pendentes)
        col3.metric("Justificadas", justificadas)
        col4.metric("Canceladas", canceladas)
        
        st.markdown("---")
        st.subheader("📍 Volume por Bairro detalhado por Status")
        if "Bairro" in df_dados.columns and "Status" in df_dados.columns:
            df_bairro_status = df_dados.groupby(["Bairro", "Status"]).size().reset_index(name="Quantidade")
            fig_bairro_status = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Quantidade",
                color="Status",
                barmode="group",
                title="Distribuição por Bairro e Status"
            )
            st.plotly_chart(fig_bairro_status, use_container_width=True)
    else:
        st.info("Nenhum dado disponível no momento.")

elif opcao == "🗺️ Mapa Interativo":
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
        st_folium(m, width=1200, height=550)
    else:
        st.info("Dados geográficos insuficientes para exibir o mapa.")

elif opcao == "➕ Adicionar Novo Registro":
    if st.session_state.get("autenticado", False):
        st.title("➕ Adicionar Novo Registro")
        with st.form("form_novo"):
            destinatario = st.text_input("Destinatário")
            rua = st.text_input("Rua")
            numero = st.text_input("Número")
            bairro = st.text_input("Bairro")
            cidade = st.text_input("Cidade", value="Florianópolis")
            estado = st.text_input("Estado", value="SC")
            cep = st.text_input("CEP")
            status = st.selectbox("Status", ["Pendente", "Auditado", "Justificada", "Cancelada"])
            
            submitted = st.form_submit_button("Adicionar Registro")
            if submitted and worksheet:
                try:
                    endereco_completo = f"{rua}, {numero} - {bairro}, {cidade} - {estado}, CEP {cep}"
                    geolocator = Nominatim(user_agent="moovechain_app")
                    location = geolocator.geocode(endereco_completo)
                    lat = location.latitude if location else 0.0
                    lon = location.longitude if location else 0.0
                    
                    nova_linha = [destinatario, rua, numero, bairro, cidade, estado, cep, endereco_completo, status, lat, lon, ""]
                    worksheet.append_row(nova_linha)
                    st.success("Registro adicionado com sucesso! Atualize a página.")
                    st.cache_data.clear()
                except Exception as ex:
                    st.error(f"Erro ao adicionar: {ex}")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "📋 Tabela de Dados e Ações":
    if st.session_state.get("autenticado", False):
        st.title("📋 Tabela de Dados, Filtros e Edição em Massa")
        
        if not df_dados.empty:
            # --- PAINEL DE FILTROS PERSISTENTES ---
            st.markdown("### 🔍 Filtros Persistentes")
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            
            estados_disponiveis = df_dados["Estado"].dropna().unique().tolist() if "Estado" in df_dados.columns else []
            cidades_disponiveis = df_dados["Cidade"].dropna().unique().tolist() if "Cidade" in df_dados.columns else []
            bairros_disponiveis = df_dados["Bairro"].dropna().unique().tolist() if "Bairro" in df_dados.columns else []
            status_disponiveis = df_dados["Status"].dropna().unique().tolist() if "Status" in df_dados.columns else []
            
            with col_f1:
                st.session_state["filtro_estado"] = st.multiselect("Estado", estados_disponiveis, default=st.session_state["filtro_estado"])
            with col_f2:
                st.session_state["filtro_cidade"] = st.multiselect("Cidade", cidades_disponiveis, default=st.session_state["filtro_cidade"])
            with col_f3:
                st.session_state["filtro_bairro"] = st.multiselect("Bairro", bairros_disponiveis, default=st.session_state["filtro_bairro"])
            with col_f4:
                st.session_state["filtro_status"] = st.multiselect("Status", status_disponiveis, default=st.session_state["filtro_status"])
            
            # Aplicar filtros ao DataFrame
            df_filtrado = df_dados.copy()
            if st.session_state["filtro_estado"]:
                df_filtrado = df_filtrado[df_filtrado["Estado"].isin(st.session_state["filtro_estado"])]
            if st.session_state["filtro_cidade"]:
                df_filtrado = df_filtrado[df_filtrado["Cidade"].isin(st.session_state["filtro_cidade"])]
            if st.session_state["filtro_bairro"]:
                df_filtrado = df_filtrado[df_filtrado["Bairro"].isin(st.session_state["filtro_bairro"])]
            if st.session_state["filtro_status"]:
                df_filtrado = df_filtrado[df_filtrado["Status"].isin(st.session_state["filtro_status"])]
                
            st.markdown(f"**Registros encontrados com os filtros atuais:** {len(df_filtrado)}")
            
            # --- TABELA DE EDIÇÃO E SELEÇÃO ---
            st.markdown("### ✏️ Edição Interativa e Ações")
            st.info("Pode editar os campos diretamente na tabela abaixo. Para excluir linhas, selecione a caixa correspondente na tabela e clique no botão de eliminação.")
            
            # Adicionar coluna de seleção para exclusão
            df_filtrado_edit = df_filtrado.copy()
            df_filtrado_edit.insert(0, "Selecionar", False)
            
            edited_df = st.data_editor(
                df_filtrado_edit,
                use_container_width=True,
                num_rows="dynamic",
                key="editor_tabela_dados"
            )
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("💾 Gravar Alterações", type="primary"):
                    try:
                        # Atualizar a planilha inteira ou sincronizar as alterações
                        # Remove a coluna auxiliar 'Selecionar' antes de enviar ao Sheets
                        df_para_salvar = edited_df.drop(columns=["Selecionar"])
                        worksheet.clear()
                        worksheet.update([df_para_salvar.columns.values.tolist()] + df_para_salvar.values.tolist())
                        st.success("Alterações gravadas com sucesso no Google Sheets!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao gravar alterações: {ex}")
                        
            with col_btn2:
                if st.button("🗑️ Eliminar Linhas Selecionadas"):
                    try:
                        # Identificar linhas selecionadas
                        linhas_selecionadas = edited_df[edited_df["Selecionar"] == True]
                        if not linhas_selecionadas.empty:
                            # Remover do dataframe original com base em índices ou identificadores únicos
                            indices_a_remover = linhas_selecionadas.index
                            df_atualizado = df_dados.drop(index=indices_a_remover).reset_index(drop=True)
                            
                            worksheet.clear()
                            worksheet.update([df_atualizado.columns.values.tolist()] + df_atualizado.values.tolist())
                            st.success(f"{len(linhas_selecionadas)} linha(s) eliminada(s) com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.warning("Nenhuma linha foi selecionada para eliminação.")
                    except Exception as ex:
                        st.error(f"Erro ao eliminar linhas: {ex}")
        else:
            st.info("Sem dados disponíveis.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "🛠️ Manutenção e Limpeza de Coordenadas":
    if st.session_state.get("autenticado", False):
        st.title("🛠️ Manutenção e Limpeza de Coordenadas")
        st.write("Ferramentas de manutenção de dados geográficos.")
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
                if "Categoria" in df_custos.columns and "Valor" in df_custos.columns:
                    fig_pizza = px.pie(df_custos, names="Categoria", values="Valor", title="Distribuição de Custos Logísticos")
                    st.plotly_chart(fig_pizza, use_container_width=True)
            else:
                st.info("Nenhum dado na aba Controle_Custos.")
        except Exception as e:
            st.error(f"Erro ao carregar custos: {e}")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")