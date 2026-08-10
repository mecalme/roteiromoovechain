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

# Inicialização de estados para persistência dos filtros
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
    st.markdown("Visão geral em tempo real da auditoria e andamento dos roteiros.")
    
    if not df_dados.empty:
        if "Status" in df_dados.columns:
            total_auditorias = len(df_dados)
            pendentes = len(df_dados[df_dados["Status"].str.contains("Pendente", case=False, na=False)])
            justificadas = len(df_dados[df_dados["Status"].str.contains("Justificad", case=False, na=False)])
            canceladas = len(df_dados[df_dados["Status"].str.contains("Cancelad", case=False, na=False)])
            auditadas = len(df_dados[df_dados["Status"].str.contains("Auditado", case=False, na=False)])
            
            taxa_conclusao = (auditadas / total_auditorias * 100) if total_auditorias > 0 else 0
        else:
            total_auditorias = len(df_dados)
            pendentes, justificadas, canceladas, auditadas, taxa_conclusao = 0, 0, 0, 0, 0

        # Linha de KPIs Profissionais
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Pontos Totais", total_auditorias)
        col2.metric("Auditados", auditadas, f"{taxa_conclusao:.1f}% do roteiro")
        col3.metric("Pendentes", pendentes)
        col4.metric("Justificados", justificadas)
        col5.metric("Canceladas", canceladas)
        
        st.markdown("---")
        
        # Grid visual com Gráficos Profissionais (Plotly)
        col_graf1, col_graf2 = st.columns([2, 1])
        
        with col_graf1:
            st.subheader("📍 Pontos por Bairro (Ordenado por Volume)")
            if "Bairro" in df_dados.columns and "Status" in df_dados.columns:
                df_bairro_status = df_dados.groupby(["Bairro", "Status"]).size().reset_index(name="Quantidade")
                
                # Ordena os bairros pelo total de registros para o gráfico ficar limpo
                ordem_bairros = df_dados["Bairro"].value_counts().index.tolist()
                
                fig_bairro_status = px.bar(
                    df_bairro_status,
                    x="Bairro",
                    y="Quantidade",
                    color="Status",
                    barmode="stack",
                    category_orders={"Bairro": ordem_bairros},
                    color_discrete_map={
                        "Auditado": "#2ecc71",
                        "Pendente": "#f39c12",
                        "Justificado": "#3498db",
                        "Cancelada": "#e74c3c"
                    }
                )
                fig_bairro_status.update_layout(
                    xaxis_tickangle=-45,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_bairro_status, use_container_width=True)
                
        with col_graf2:
            st.subheader("📊 Distribuição de Status")
            if "Status" in df_dados.columns:
                df_status_counts = df_dados["Status"].value_counts().reset_index()
                df_status_counts.columns = ["Status", "Quantidade"]
                
                fig_pie = px.pie(
                    df_status_counts,
                    names="Status",
                    values="Quantidade",
                    hole=0.4,
                    color="Status",
                    color_discrete_map={
                        "Auditado": "#2ecc71",
                        "Pendente": "#f39c12",
                        "Justificado": "#3498db",
                        "Cancelada": "#e74c3c"
                    }
                )
                fig_pie.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("A carregar dados do Google Sheets...")

elif opcao == "🗺️ Mapa Interativo":
    st.title("🗺️ Mapa Interativo de Auditorias")
    if not df_dados.empty and "Latitude" in df_dados.columns and "Longitude" in df_dados.columns:
        m = folium.Map(location=[-27.5954, -48.5480], zoom_start=12)
        
        def get_color(status):
            status_str = str(status).lower()
            if "auditado" in status_str:
                return "green"
            elif "pendente" in status_str:
                return "orange"
            elif "justificad" in status_str:
                return "blue"
            elif "cancelad" in status_str:
                return "red"
            return "gray"

        for _, row in df_dados.iterrows():
            try:
                lat_val = row["Latitude"]
                lon_val = row["Longitude"]
                
                if pd.isna(lat_val) or pd.isna(lon_val) or str(lat_val).strip() == "" or str(lon_val).strip() == "":
                    continue
                    
                lat = float(lat_val)
                lon = float(lon_val)
                
                dest = "Local"
                for col_name in ["Destinatário", "Cliente", "Nome", "Empresa", "Local"]:
                    if col_name in row and pd.notna(row[col_name]):
                        dest = str(row[col_name])
                        break
                        
                status = row.get("Status", "N/D")
                bairro = row.get("Bairro", "N/D")
                
                popup_html = f"<b>{dest}</b><br>Bairro: {bairro}<br>Status: {status}"
                
                folium.Marker(
                    [lat, lon],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=dest,
                    icon=folium.Icon(color=get_color(status), icon="info-sign")
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
    st.title("📋 Tabela de Dados e Ações")
    st.write("Filtre, selecione linhas através das caixas de seleção e abra o painel de edição abaixo:")
    
    if not df_dados.empty:
        st.subheader("🔍 Filtros de Pesquisa")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        
        estados_disponiveis = sorted(df_dados["Estado"].dropna().unique().tolist()) if "Estado" in df_dados.columns else []
        cidades_disponiveis = sorted(df_dados["Cidade"].dropna().unique().tolist()) if "Cidade" in df_dados.columns else []
        bairros_disponiveis = sorted(df_dados["Bairro"].dropna().unique().tolist()) if "Bairro" in df_dados.columns else []
        status_disponiveis = sorted(df_dados["Status"].dropna().unique().tolist()) if "Status" in df_dados.columns else []
        
        with f_col1:
            st.session_state["filtro_estado"] = st.multiselect("Estado", estados_disponiveis, default=st.session_state["filtro_estado"])
        with f_col2:
            st.session_state["filtro_cidade"] = st.multiselect("Cidade", cidades_disponiveis, default=st.session_state["filtro_cidade"])
        with f_col3:
            st.session_state["filtro_bairro"] = st.multiselect("Bairro", bairros_disponiveis, default=st.session_state["filtro_bairro"])
        with f_col4:
            st.session_state["filtro_status"] = st.multiselect("Status", status_disponiveis, default=st.session_state["filtro_status"])
            
        df_filtrado = df_dados.copy()
        if st.session_state["filtro_estado"] and "Estado" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Estado"].isin(st.session_state["filtro_estado"])]
        if st.session_state["filtro_cidade"] and "Cidade" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Cidade"].isin(st.session_state["filtro_cidade"])]
        if st.session_state["filtro_bairro"] and "Bairro" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Bairro"].isin(st.session_state["filtro_bairro"])]
        if st.session_state["filtro_status"] and "Status" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Status"].isin(st.session_state["filtro_status"])]

        st.markdown("---")
        
        if "Selecionar" not in df_filtrado.columns:
            df_filtrado.insert(0, "Selecionar", False)
            
        tabela_selecao = st.data_editor(
            df_filtrado, 
            use_container_width=True, 
            key="tabela_selecao_v3",
            column_config={
                "Selecionar": st.column_config.CheckboxColumn(
                    "Selecionar",
                    help="Marque as linhas que deseja editar",
                    default=False,
                )
            },
            disabled=[col for col in df_filtrado.columns if col != "Selecionar"]
        )
        
        linhas_selecionadas_indices = tabela_selecao[tabela_selecao["Selecionar"] == True].index
        
        if len(linhas_selecionadas_indices) > 0:
            st.markdown("---")
            st.subheader(f"✏️ Painel de Edição ({len(linhas_selecionadas_indices)} linha(s) selecionada(s))")
            st.write("Edite os dados selecionados abaixo e clique em guardar:")
            
            df_para_editar = df_dados.loc[linhas_selecionadas_indices].copy()
            
            edited_panel = st.data_editor(
                df_para_editar,
                use_container_width=True,
                key="painel_edicao_ativo"
            )
            
            if st.button("Guardar Alterações na Planilha"):
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
                    sheet = client.open("Roteiro MooveChain Florianóplis 2026").sheet1
                    
                    cabecalhos_planilha = sheet.row_values(1)
                    
                    for idx in linhas_selecionadas_indices:
                        linha_planilha = idx + 2
                        linha_editada = edited_panel.loc[idx]
                        
                        valores_linha = []
                        for col in cabecalhos_planilha:
                            if col in linha_editada:
                                val = linha_editada[col]
                                valores_linha.append(str(val) if pd.notna(val) else "")
                            else:
                                valores_linha.append("")
                        
                        num_colunas = len(valores_linha)
                        range_celulas = gspread.utils.rowcol_to_a1(linha_planilha, 1) + ":" + gspread.utils.rowcol_to_a1(linha_planilha, num_colunas)
                        sheet.update(range_celulas, [valores_linha])
                    
                    st.success("Dados alterados e guardados com sucesso no Google Sheets!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar dados na planilha: {e}")
        else:
            st.info("ℹ️ Selecione pelo menos uma linha na tabela acima com o 'checkbox' para habilitar o Painel de Edição.")
    else:
        st.info("Nenhum dado disponível na tabela principal.")

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