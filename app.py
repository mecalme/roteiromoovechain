from google.oauth2.service_account import Credentials
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium
import folium
import plotly.express as px
import pandas as pd
import gspread
import re
import logging
import streamlit as st
from folium.plugins import MarkerCluster

# --- 1. CONFIGURAÇÃO DA PÁGINA E ESTILOS CSS ---
st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis 2026",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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
        sheet = client.open("Roteiro MooveChain Florianóplis 2026")

        # Planilha Principal
        worksheet_principal = sheet.worksheet("Planilha1")
        data_principal = worksheet_principal.get_all_records()
        df_dados = pd.DataFrame(data_principal)

        # Planilha de Custos Logísticos (se existir)
        df_custos = pd.DataFrame()
        try:
            worksheet_custos = sheet.worksheet("Controle_Custos")
            data_custos = worksheet_custos.get_all_records()
            df_custos = pd.DataFrame(data_custos)
        except Exception:
            pass

        return df_dados, df_custos, worksheet_principal
    except Exception as e:
        st.error(f"Erro ao ligar ao Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), None


df_dados, df_custos, worksheet_principal = carregar_dados()

# --- 4. BARRA LATERAL (MENU E AUTENTICAÇÃO) ---
st.sidebar.title("🚚 Roteiro MooveChain")
st.sidebar.markdown("---")

# Opções do menu base
menu_opcoes = ["📊 Dashboard", "🗺️ Mapa e Rotas"]

# Adiciona opções restritas se autenticado
if st.session_state["autenticado"]:
    menu_opcoes.extend([
        "➕ Adicionar Novo Registro",
        "📋 Tabela de Dados e Ações",
        "🛠️ Manutenção e Limpeza de Coordenadas",
        "💰 Custos Logísticos"
    ])

opcao = st.sidebar.radio("Navegação", menu_opcoes)

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Área Administrativa")

if not st.session_state["autenticado"]:
    senha_input = st.sidebar.text_input(
        "Palavra-passe Admin", type="password", key="admin_password_input")
    senha_correta = st.secrets.get("ADMIN_PASSWORD", "moovechain2026")

    if st.sidebar.button("Entrar"):
        if senha_input == senha_correta:
            st.session_state["autenticado"] = True
            st.sidebar.success("Acesso autorizado!")
            st.rerun()
        else:
            st.sidebar.error("Palavra-passe incorreta.")
else:
    st.sidebar.success("Modo Administrador Ativo")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state["autenticado"] = False
        st.rerun()

# --- 5. LÓGICA DAS ABAS ---

if opcao == "📊 Dashboard":
    st.title("📊 Dashboard de Auditorias - MooveChain")
    st.markdown("Visão geral e métricas de desempenho das auditorias logísticas.")

    if not df_dados.empty and "Status" in df_dados.columns:
        total_auditorias = len(df_dados)
        # Limpeza e contagem insensível a maiúsculas/minúsculas
        df_dados["Status_Clean"] = df_dados["Status"].astype(
            str).str.strip().str.capitalize()

        pendentes = len(df_dados[df_dados["Status_Clean"] == "Pendente"])
        justificadas = len(
            df_dados[df_dados["Status_Clean"].str.contains("Justificad")])
        canceladas = len(
            df_dados[df_dados["Status_Clean"].str.contains("Cancelad")])
        auditadas = len(
            df_dados[df_dados["Status_Clean"].str.contains("Auditado")])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Auditorias", total_auditorias)
        col2.metric("Pendentes", pendentes)
        col3.metric("Justificadas", justificadas)
        col4.metric("Canceladas", canceladas)

        st.markdown("---")

        # Gráfico por Bairro e Status
        if "Bairro" in df_dados.columns:
            st.subheader(
                "📍 Volume por Bairro detalhado por Status (Auditado, Justificado, Cancelado, Pendente)")
            df_bairro_status = df_dados.groupby(
                ["Bairro", "Status_Clean"]).size().reset_index(name="Quantidade")
            fig_bairro_status = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Quantidade",
                color="Status_Clean",
                barmode="group",
                title="Distribuição de Auditorias por Bairro e Status"
            )
            st.plotly_chart(fig_bairro_status, use_container_width=True)
    else:
        st.info(
            "Nenhum dado de auditoria disponível ou coluna 'Status' ausente.")

elif opcao == "🗺️ Mapa e Rotas":
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
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(marker_cluster)
            except Exception:
                continue
        st_folium(m, width=1200, height=550)
    else:
        st.warning("Coordenadas geográficas insuficientes para renderizar o mapa.")

elif opcao == "➕ Adicionar Novo Registro":
    if st.session_state.get("autenticado", False):
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
                status_reg = st.selectbox(
                    "Status Inicial", ["Pendente", "Auditado", "Justificada", "Cancelada"])

            submitted = st.form_submit_button("Guardar Novo Registro")
            if submitted and worksheet_principal:
                endereco_completo = f"{rua}, {numero} - {bairro}, {cidade} - {estado}, CEP {cep}"
                novo_item = [destinatario, rua, numero, bairro,
                             cidade, estado, cep, endereco_completo, status_reg, "", "", ""]
                worksheet_principal.append_row(novo_item)
                st.cache_data.clear()
                st.success("Registro adicionado com sucesso!")
                st.rerun()
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "📋 Tabela de Dados e Ações":
    if st.session_state.get("autenticado", False):
        st.title("📋 Tabela de Dados e Ações com Edição Múltipla")
        st.write("Selecione as linhas que deseja alterar utilizando as caixas de seleção e clique em editar.")

        if not df_dados.empty:
            # Adiciona coluna de seleção (checkbox) interativa na tabela
            df_exibicao = df_dados.copy()
            df_exibicao.insert(0, "Selecionar", False)

            df_editado = st.data_editor(
                df_exibicao,
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn("Selecionar", required=True)
                },
                disabled=[c for c in df_exibicao.columns if c != "Selecionar" and c !=
                          "Status" and c != "Destinatário" and c != "Bairro"],
                hide_index=True,
                key="tabela_edicao_multipla"
            )

            # Identificar linhas selecionadas
            selecionados = df_editado[df_editado["Selecionar"] == True]

            if not selecionados.empty:
                st.markdown("---")
                st.subheader(
                    f"✏️ Painel de Edição (Registros selecionados: {len(selecionados)})")

                with st.form("form_edicao_multipla"):
                    novo_status_lote = st.selectbox(
                        "Alterar Status para os selecionados:",
                        ["Pendente", "Auditado", "Justificada", "Cancelada"]
                    )
                    btn_aplicar_lote = st.form_submit_button(
                        "💾 Gravar Alterações Múltiplas")

                    if btn_aplicar_lote and worksheet_principal:
                        # Atualiza no Google Sheets com base no índice original das linhas
                        for idx in selecionados.index:
                            # Linha na planilha do Google Sheets (considerando o cabeçalho na linha 1)
                            row_sheet = int(idx) + 2
                            col_status_idx = df_dados.columns.get_loc(
                                "Status") + 1
                            worksheet_principal.update_cell(
                                row_sheet, col_status_idx, novo_status_lote)

                        st.cache_data.clear()
                        st.success(
                            "Alterações gravadas com sucesso no Google Sheets!")
                        st.rerun()
        else:
            st.info("Não existem dados disponíveis para gerir.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "🛠️ Manutenção e Limpeza de Coordenadas":
    if st.session_state.get("autenticado", False):
        st.title("🛠️ Manutenção e Limpeza de Coordenadas")
        st.write(
            "Ferramentas de suporte geográfico, limpeza e validação de moradas.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")

elif opcao == "💰 Custos Logísticos":
    if st.session_state.get("autenticado", False):
        st.title("💰 Custos Logísticos")
        if not df_custos.empty:
            st.dataframe(df_custos, use_container_width=True)
            if "Categoria" in df_custos.columns and "Valor" in df_custos.columns:
                fig_custos = px.pie(
                    df_custos, names="Categoria", values="Valor", title="Distribuição de Custos Logísticos")
                st.plotly_chart(fig_custos, use_container_width=True)
        else:
            st.info(
                "Nenhum registo encontrado na aba 'Controle_Custos' do Google Sheets.")
    else:
        st.warning("Acesso restrito. Insira a palavra-passe de administrador na barra lateral.")