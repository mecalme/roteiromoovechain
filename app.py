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

# --- 3. FUNÇÃO DE CARREGAMENTO DE DADOS ROBUSTA ---
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            credentials_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open("Roteiro MooveChain Florianóplis 2026")
        
        # Carrega dados principais
        sheet_principal = spreadsheet.sheet1
        dados_principais = sheet_principal.get_all_records()
        df_dados = pd.DataFrame(dados_principais)
        
        # Tenta carregar custos se existir a aba Controle_Custos
        try:
            sheet_custos = spreadsheet.worksheet("Controle_Custos")
            dados_custos = sheet_custos.get_all_records()
            df_custos = pd.DataFrame(dados_custos)
        except Exception:
            df_custos = pd.DataFrame()
            
        return df_dados, df_custos
    except Exception as e:
        st.error(f"Erro ao ligar ao Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_dados, df_custos = carregar_dados()

# --- 4. BARRA LATERAL (MENU E AUTENTICAÇÃO) ---
st.sidebar.title("🚚 Painel MooveChain")

# Gestão de Autenticação na barra lateral
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Palavra-passe Admin", type="password")
    senha_correta = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")
    if st.sidebar.button("Entrar"):
        if senha_digitada == senha_correta:
            st.session_state["autenticado"] = True
            st.success("Acesso concedido!")
            st.rerun()
        else:
            st.sidebar.error("Palavra-passe incorreta.")
else:
    st.sidebar.success("Modo Administrador Ativo")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Navegação")

# Definição das opções do menu lateral fixo
opcoes_publicas = ["📊 Dashboard Principal", "🗺️ Mapa Interativo"]
opcoes_admin = [
    "➕ Adicionar Novo Registro",
    "📋 Tabela de Dados e Ações",
    "🛠️ Manutenção e Limpeza de Coordenadas",
    "💰 Custos Logísticos"
]

if st.session_state["autenticado"]:
    lista_menu = opcoes_publicas + opcoes_admin
else:
    lista_menu = opcoes_publicas

opcao = st.sidebar.radio("Ir para:", lista_menu)

# --- 5. LÓGICA DAS SECÇÕES DA APLICAÇÃO ---

if opcao == "📊 Dashboard Principal":
    st.title("📊 Dashboard - Roteiro MooveChain Florianópolis 2026")
    
    if not df_dados.empty:
        # Tratamento seguro da coluna Status
        if "Status" in df_dados.columns:
            total_auditorias = len(df_dados)
            pendentes = len(df_dados[df_dados["Status"].str.contains("Pendente", case=False, na=False)])
            justificadas = len(df_dados[df_dados["Status"].str.contains("Justificad", case=False, na=False)])
            canceladas = len(df_dados[df_dados["Status"].str.contains("Cancelad", case=False, na=False)])
            auditadas = len(df_dados[df_dados["Status"].str.contains("Auditado", case=False, na=False)])
        else:
            total_auditorias = len(df_dados)
            pendentes, justificadas, canceladas, auditadas = 0, 0, 0, 0

        # Métricas no topo
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total de Auditorias", total_auditorias)
        col2.metric("Auditadas", auditadas)
        col3.metric("Pendentes", pendentes)
        col4.metric("Justificadas", justificadas)
        col5.metric("Canceladas", canceladas)
        
        st.markdown("---")
        
        # Gráfico por Bairro detalhado por Status
        st.subheader("📍 Volume por Bairro detalhado por Status")
        if "Bairro" in df_dados.columns and "Status" in df_dados.columns:
            df_bairro_status = df_dados.groupby(["Bairro", "Status"]).size().reset_index(name="Quantidade")
            fig_bairro_status = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Quantidade",
                color="Status",
                barmode="group",
                title="Distribuição de Auditorias por Bairro e Status"
            )
            st.plotly_chart(fig_bairro_status, use_container_width=True)
    else:
        st.info("A carregar dados do Google Sheets...")

elif opcao == "🗺️ Mapa Interativo":
    st.title("🗺️ Mapa Interativo de Auditorias")
    if not df_dados.empty and "Latitude" in df_dados.columns and "Longitude" in df_dados.columns:
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        for _, row in df_dados.iterrows():
            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
                dest = row.get("Destinatário", "Local")
                status = row.get("Status", "N/D")
                folium.Marker(
                    [lat, lon],
                    popup=f"<b>{dest}</b><br>Status: {status}",
                    tooltip=dest
                ).add_to(m)
            except Exception:
                continue
        st_folium(m, width=1200, height=500)
    else:
        st.warning("Coordenadas não disponíveis para exibir o mapa.")

elif opcao == "➕ Adicionar Novo Registro" and st.session_state["autenticado"]:
    st.title("➕ Adicionar Novo Registro de Auditoria")
    with st.form("form_novo_registro"):
        col_a, col_b = st.columns(2)
        with col_a:
            destinatario = st.text_input("Destinatário")
            rua = st.text_input("Rua")
            numero = st.text_input("Número")
            bairro = st.text_input("Bairro")
        with col_b:
            cidade = st.text_input("Cidade", value="Florianópolis")
            estado = st.text_input("Estado", value="SC")
            cep = st.text_input("CEP")
            status_reg = st.selectbox("Status Inicial", ["Pendente", "Auditado", "Justificada", "Cancelada"])
        
        submitted = st.form_submit_button("Guardar Novo Registo")
        if submitted:
            try:
                credentials_dict = dict(st.secrets["gcp_service_account"])
                creds = Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                )
                client = gspread.authorize(creds)
                sheet = client.open("Roteiro MooveChain Florianóplis 2026").sheet1
                sheet.append_row([destinatario, rua, numero, bairro, cidade, estado, cep, "", status_reg, "", "", ""])
                st.success("Registo adicionado com sucesso!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao adicionar registo: {e}")

elif opcao == "📋 Tabela de Dados e Ações" and st.session_state["autenticado"]:
    st.title("📋 Tabela de Dados e Ações (Filtros e Edição Múltipla)")
    
    if not df_dados.empty:
        # Filtros Persistentes
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            estados_disp = ["Todos"] + list(df_dados["Estado"].dropna().unique()) if "Estado" in df_dados.columns else ["Todos"]
            filtro_estado = st.selectbox("Estado", estados_disp)
        with col_f2:
            cidades_disp = ["Todas"] + list(df_dados["Cidade"].dropna().unique()) if "Cidade" in df_dados.columns else ["Todas"]
            filtro_cidade = st.selectbox("Cidade", cidades_disp)
        with col_f3:
            bairros_disp = ["Todos"] + list(df_dados["Bairro"].dropna().unique()) if "Bairro" in df_dados.columns else ["Todos"]
            filtro_bairro = st.selectbox("Bairro", bairros_disp)
        with col_f4:
            status_disp = ["Todos"] + list(df_dados["Status"].dropna().unique()) if "Status" in df_dados.columns else ["Todos"]
            filtro_status = st.selectbox("Status", status_disp)
            
        df_filtrado = df_dados.copy()
        if filtro_estado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Estado"] == filtro_estado]
        if filtro_cidade != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Cidade"] == filtro_cidade]
        if filtro_bairro != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Bairro"] == filtro_bairro]
        if filtro_status != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Status"] == filtro_status]
            
        st.write(f"A exibir {len(df_filtrado)} registros filtrados:")
        
        # Inserção de coluna de seleção para edição múltipla
        df_filtrado["Selecionar"] = False
        df_editado = st.data_editor(
            df_filtrado,
            use_container_width=True,
            num_rows="fixed",
            key="tabela_edicao_multipla"
        )
        
        # Painel de Ação de Edição Múltipla
        linhas_selecionadas = df_editado[df_editado["Selecionar"] == True]
        
        if not linhas_selecionadas.empty:
            st.markdown("---")
            st.subheader("✏️ Painel de Edição Múltipla")
            st.info(f"{len(linhas_selecionadas)} linha(s) selecionada(s) para alteração em lote.")
            
            novo_status_lote = st.selectbox("Novo Status para Selecionados", ["Auditado", "Pendente", "Justificada", "Cancelada"])
            
            if st.button("💾 Gravar Alterações na Planilha"):
                try:
                    credentials_dict = dict(st.secrets["gcp_service_account"])
                    creds = Credentials.from_service_account_info(
                        credentials_dict,
                        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
                    )
                    client = gspread.authorize(creds)
                    spreadsheet = client.open("Roteiro MooveChain Florianóplis 2026")
                    worksheet_principal = spreadsheet.sheet1
                    
                    header = worksheet_principal.row_values(1)
                    col_status_idx = header.index("Status") + 1 if "Status" in header else 9
                    
                    # Atualiza cada linha selecionada com base no índice original do dataframe
                    for idx in linhas_selecionadas.index:
                        row_sheet = int(idx) + 2  # 1 do cabeçalho + 1 do index Python 0-based
                        worksheet_principal.update_cell(row_sheet, col_status_idx, novo_status_lote)
                        
                    st.success("✅ Alterações gravadas com sucesso no Google Sheets!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar o Google Sheets: {e}")
    else:
        st.info("Nenhum dado disponível na tabela.")

elif opcao == "🛠️ Manutenção e Limpeza de Coordenadas" and st.session_state["autenticado"]:
    st.title("🛠️ Manutenção e Limpeza de Coordenadas")
    st.write("Ferramenta para reprocessamento geográfico de endereços pendentes.")

elif opcao == "💰 Custos Logísticos" and st.session_state["autenticado"]:
    st.title("💰 Custos Logísticos")
    if not df_custos.empty:
        st.dataframe(df_custos, use_container_width=True)
        if "Categoria" in df_custos.columns and "Valor" in df_custos.columns:
            fig_custos = px.pie(df_custos, names="Categoria", values="Valor", title="Distribuição de Custos Logísticos")
            st.plotly_chart(fig_custos, use_container_width=True)
    else:
        st.info("Nenhum dado de custos encontrado na aba 'Controle_Custos'.")