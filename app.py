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
from datetime import date

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
    .main { background-color: #0f1117; color: #f1f5f9; }
    
    .stMetric { 
        background-color: #ffffff !important; 
        padding: 18px !important; 
        border-radius: 12px !important; 
        border: 1px solid #cbd5e1 !important; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); 
    }
    .stMetric label { color: #475569 !important; font-weight: 600 !important; }
    .stMetric [data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700 !important; }
    .stMetric [data-testid="stMetricDelta"] { color: #16a34a !important; font-weight: 600 !important; }

    .stButton>button { border-radius: 8px; font-weight: bold; }
    div[data-testid="stExpander"] { background-color: #1e293b; border-radius: 12px; border: 1px solid #334155; }
    </style>
""", unsafe_allow_html=True)

# --- 2. INICIALIZAÇÃO DE ESTADOS NA SESSÃO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "versao_dados" not in st.session_state:
    st.session_state["versao_dados"] = 0

if "filtro_estado" not in st.session_state:
    st.session_state["filtro_estado"] = []
if "filtro_cidade" not in st.session_state:
    st.session_state["filtro_cidade"] = []
if "filtro_bairro" not in st.session_state:
    st.session_state["filtro_bairro"] = []
if "filtro_status" not in st.session_state:
    st.session_state["filtro_status"] = []

if "mensagem_sucesso" not in st.session_state:
    st.session_state["mensagem_sucesso"] = ""

# --- 3. FUNÇÃO DE CARREGAMENTO DE DADOS COM CONTROLO DE VERSÃO ---
@st.cache_data(ttl=60)
def carregar_dados_cache(versao):
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
        
        sheet_principal = spreadsheet.sheet1
        dados_principais = sheet_principal.get_all_records()
        df_dados = pd.DataFrame(dados_principais)
            
        return df_dados
    except Exception as e:
        st.error(f"Erro ao ligar ao Google Sheets: {e}")
        return pd.DataFrame()

df_dados = carregar_dados_cache(st.session_state["versao_dados"])

# --- 4. BARRA LATERAL (MENU E AUTENTICAÇÃO) ---
st.sidebar.title("🚚 Painel MooveChain")

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
    "💰 Dashboard Financeiro",
    "➕ Adicionar Novo Registro",
    "📋 Tabela de Dados e Ações"
]

if st.session_state["autenticado"]:
    lista_menu = opcoes_publicas + opcoes_admin
else:
    lista_menu = opcoes_publicas

opcao = st.sidebar.radio("Ir para:", lista_menu)

if st.session_state["mensagem_sucesso"]:
    st.success(st.session_state["mensagem_sucesso"])
    st.session_state["mensagem_sucesso"] = ""

# --- 5. LÓGICA DAS SECÇÕES DA APLICAÇÃO ---

if opcao == "📊 Dashboard Principal":
    st.title("📊 Dashboard Auditorias Moovechain - 2026")
    
    if not df_dados.empty:
        if "Data_Visita" in df_dados.columns:
            df_dados["Data_Visita"] = pd.to_datetime(df_dados["Data_Visita"], dayfirst=True, errors="coerce")

        st.markdown("---")

        if "Status" in df_dados.columns:
            total_auditorias = len(df_dados)
            pendentes = len(df_dados[df_dados["Status"].str.contains("Pendente", case=False, na=False)])
            justificadas = len(df_dados[df_dados["Status"].str.contains("Justificado", case=False, na=False)])
            canceladas = len(df_dados[df_dados["Status"].str.contains("Cancelado", case=False, na=False)])
            auditadas = len(df_dados[df_dados["Status"].str.contains("Auditado", case=False, na=False)])
            
            progresso = int((auditadas / total_auditorias * 100)) if total_auditorias > 0 else 0
        else:
            total_auditorias = len(df_dados)
            pendentes, justificadas, canceladas, auditadas, progresso = 0, 0, 0, 0, 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Pontos Filtrados", total_auditorias)
        col2.metric("Auditados", auditadas, f"{progresso}% do conjunto")
        col3.metric("Pendentes", pendentes)
        col4.metric("Justificados", justificadas)
        
        st.markdown("### Progresso da Auditoria")
        st.progress(progresso / 100, text=f"Conclusão: {progresso}%")
        
        st.markdown("---")

        st.subheader("📈 Visão Geral dos Status (Distribuição)")
        if "Status" in df_dados.columns and not df_dados.empty:
            df_status_counts = df_dados["Status"].value_counts().reset_index()
            df_status_counts.columns = ["Status", "Quantidade"]
            df_status_counts["Percentual"] = (df_status_counts["Quantidade"] / total_auditorias * 100).round(1)
            
            fig_barras_status = px.bar(
                df_status_counts,
                x="Quantidade",
                y="Status",
                orientation="h",
                text=df_status_counts.apply(lambda r: f"{r['Quantidade']} ({r['Percentual']}%)", axis=1),
                color="Status",
                color_discrete_map={
                    "Auditado": "#22c55e",
                    "Pendente": "#f59e0b",
                    "Justificado": "#38bdf8",
                    "Cancelada": "#ef4444"
                }
            )
            fig_barras_status.update_traces(textposition="outside", textfont_size=13)
            fig_barras_status.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f1f5f9"),
                xaxis=dict(showgrid=True, gridcolor="#334155", title="Quantidade"),
                yaxis=dict(showgrid=False, title=""),
                margin=dict(l=10, r=40, t=10, b=10),
                showlegend=False
            )
            st.plotly_chart(fig_barras_status, use_container_width=True)
        st.markdown("---")
        st.subheader("🏘️ Distribuição de Status por Bairro (%)")
        if "Bairro" in df_dados.columns and "Status" in df_dados.columns and not df_dados.empty:
            df_bairro_status = df_dados.groupby(["Bairro", "Status"]).size().reset_index(name="Quantidade")
            
            totais_bairro = df_dados.groupby("Bairro").size().reset_index(name="Total_Bairro")
            df_bairro_status = df_bairro_status.merge(totais_bairro, on="Bairro")
            df_bairro_status["Percentual"] = (df_bairro_status["Quantidade"] / df_bairro_status["Total_Bairro"] * 100).round(1)
            
            fig_bairro = px.bar(
                df_bairro_status,
                x="Bairro",
                y="Percentual",
                color="Status",
                barmode="stack",
                text=df_bairro_status["Percentual"].apply(lambda x: f"{x}%" if x > 5 else ""),
                color_discrete_map={
                    "Auditado": "#22c55e",
                    "Pendente": "#f59e0b",
                    "Justificado": "#38bdf8",
                    "Cancelada": "#ef4444"
                }
            )
            fig_bairro.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f1f5f9"),
                xaxis=dict(title="Bairro", tickangle=-45),
                yaxis=dict(title="Percentual (%)", range=[0, 100]),
                margin=dict(l=10, r=10, t=30, b=10),
                legend_title="Status"
            )
            st.plotly_chart(fig_bairro, use_container_width=True)
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
                return "blue"
            elif "justificad" in status_str:
                return "red"
            elif "cancelad" in status_str:
                return "black"
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
                
        # Adicionado key dinâmica baseada na versão dos dados para forçar a re-renderização imediata
        st_folium(m, width=1200, height=500, key=f"mapa_interativo_{st.session_state['versao_dados']}")
    else:
        st.warning("Coordenadas não disponíveis para exibir o mapa.")

elif opcao == "💰 Dashboard Financeiro" and st.session_state["autenticado"]:
    st.title("💰 Dashboard Financeiro de Auditorias")
    st.write("Análise financeira com base nos valores da planilha ou tabela de ganhos.")

    if not df_dados.empty:
        df_fin = df_dados.copy()
        
        if "Data_Visita" in df_fin.columns:
            df_fin["Data_Visita"] = pd.to_datetime(df_fin["Data_Visita"], dayfirst=True, errors="coerce")

        coluna_ganho_alvo = None
        for col in ["Ganho", "Ganhos", "Valor", "Preço"]:
            if col in df_fin.columns:
                coluna_ganho_alvo = col
                break

        def limpar_moeda(val):
            if pd.isna(val):
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            val_str = str(val).strip()
            if not val_str or val_str.lower() in ["nan", "none", ""]:
                return 0.0
            val_str = val_str.replace("R$", "").replace("€", "").strip()
            if "," in val_str:
                val_str = val_str.replace(".", "").replace(",", ".")
            val_str = re.sub(r"[^\d\.-]", "", val_str)
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        st.markdown("### 📅 Filtros Financeiros")
        f_col1, f_col2 = st.columns([2, 2])

        with f_col1:
            status_disponiveis = sorted(df_fin["Status"].dropna().unique().tolist()) if "Status" in df_fin.columns else []
            filtro_status_fin = st.multiselect(
                "Filtrar por Status para Cálculo",
                status_disponiveis,
                default=status_disponiveis if status_disponiveis else []
            )

        with f_col2:
            if "Data_Visita" in df_fin.columns and not df_fin["Data_Visita"].dropna().empty:
                min_dt = df_fin["Data_Visita"].min().date()
                max_dt = df_fin["Data_Visita"].max().date()
                
                intervalo_dt = st.date_input(
                    "Intervalo de Datas da Visita",
                    value=(min_dt, max_dt),
                    min_value=min_dt,
                    max_value=max_dt
                )
                
                if isinstance(intervalo_dt, tuple) and len(intervalo_dt) == 2:
                    d_ini_fmt = intervalo_dt[0].strftime("%d/%m/%Y")
                    d_fim_fmt = intervalo_dt[1].strftime("%d/%m/%Y")
                    st.caption(f"📅 Período ativo: **{d_ini_fmt} até {d_fim_fmt}**")
            else:
                intervalo_dt = None

        df_calculo = df_fin.copy()
        if filtro_status_fin and "Status" in df_calculo.columns:
            df_calculo = df_calculo[df_calculo["Status"].isin(filtro_status_fin)]

        if intervalo_dt and len(intervalo_dt) == 2 and "Data_Visita" in df_calculo.columns:
            d_ini, d_fim = intervalo_dt
            df_calculo = df_calculo[
                ((df_calculo["Data_Visita"].dt.date >= d_ini) & 
                 (df_calculo["Data_Visita"].dt.date <= d_fim)) | 
                (df_calculo["Data_Visita"].isna())
            ]

        st.markdown("---")

        valores_calculados = []
        for _, row in df_calculo.iterrows():
            is_realizado = (
                not str(row.get("Status", "")).lower().startswith("pendente") and
                pd.notna(row.get("Data_Visita", pd.NaT))
            )
            
            if is_realizado:
                ganho_planilha = 0.0
                if coluna_ganho_alvo:
                    ganho_planilha = limpar_moeda(row.get(coluna_ganho_alvo, 0))
                
                if ganho_planilha > 0:
                    valores_calculados.append(ganho_planilha) 
                else:
                    valores_calculados.append(25.00) 
            else:
                valores_calculados.append(0.0)

        df_calculo["Ganho_Num"] = valores_calculados

        if intervalo_dt and len(intervalo_dt) == 2 and "Data_Visita" in df_calculo.columns:
            d_ini, d_fim = intervalo_dt
            df_calculo = df_calculo[
                (df_calculo["Data_Visita"].dt.date >= d_ini) & 
                (df_calculo["Data_Visita"].dt.date <= d_fim)
            ]

        mask_realizados_filtrados = (
            ~df_calculo["Status"].str.contains("Pendente", case=False, na=False) &
            df_calculo["Data_Visita"].notna()
        )
        total_pontos_realizados = len(df_calculo[mask_realizados_filtrados])
        total_ganho_filtrado = df_calculo["Ganho_Num"].sum()
        media_por_ponto = total_ganho_filtrado / total_pontos_realizados if total_pontos_realizados > 0 else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Ganhos Totais (Filtro Aplicado)", f"R$ {total_ganho_filtrado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        m2.metric("📍 Pontos Realizados", total_pontos_realizados)
        m3.metric("📊 Média por Ponto", f"R$ {media_por_ponto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.markdown("---")
        st.subheader("📊 Ganhos Acumulados por Status")
        if not df_calculo.empty and "Status" in df_calculo.columns:
            df_status_ganhos = df_calculo.groupby("Status")["Ganho_Num"].sum().reset_index()
            fig_fin_status = px.bar(
                df_status_ganhos,
                x="Status",
                y="Ganho_Num",
                text=df_status_ganhos["Ganho_Num"].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
                color="Status",
                color_discrete_map={
                    "Auditado": "#22c55e",
                    "Pendente": "#f59e0b",
                    "Justificado": "#38bdf8",
                    "Cancelada": "#ef4444"
                }
            )
            fig_fin_status.update_traces(textposition="outside", textfont_size=13)
            fig_fin_status.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f1f5f9"),
                xaxis=dict(title="Status do Ponto"),
                yaxis=dict(title="Ganhos (R$)"),
                margin=dict(l=10, r=10, t=20, b=10),
                showlegend=False
            )
            st.plotly_chart(fig_fin_status, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Detalhamento Financeiro dos Registos (Filtrado por Data)")
        colunas_exibir = [c for c in ["Destinatário", "Bairro", "Status", "Data_Visita", "Ganho_Num"] if c in df_calculo.columns]
        st.dataframe(df_calculo[colunas_exibir], use_container_width=True, hide_index=True)

    else:
        st.info("Nenhum dado financeiro disponível.")

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
                
                st.cache_data.clear()
                st.session_state["versao_dados"] += 1
                
                st.session_state["mensagem_sucesso"] = "✅ Registo adicionado com sucesso!"
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
        
        st.session_state["filtro_estado"] = [x for x in st.session_state["filtro_estado"] if x in estados_disponiveis]
        st.session_state["filtro_cidade"] = [x for x in st.session_state["filtro_cidade"] if x in cidades_disponiveis]
        st.session_state["filtro_bairro"] = [x for x in st.session_state["filtro_bairro"] if x in bairros_disponiveis]
        st.session_state["filtro_status"] = [x for x in st.session_state["filtro_status"] if x in status_disponiveis]
        
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
                    
                    st.cache_data.clear()
                    st.session_state["versao_dados"] += 1
                    
                    st.session_state["mensagem_sucesso"] = "✅ Alterações feitas e guardadas com sucesso no Google Sheets!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar dados na planilha: {e}")
        else:
            st.info("ℹ️ Selecione pelo menos uma linha na tabela acima com o 'checkbox' para habilitar o Painel de Edição.")
    else:
        st.info("Nenhum dado disponível na tabela principal.")