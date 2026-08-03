import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
import plotly.express as px
from datetime import date
import folium
from streamlit_folium import st_folium

LISTA_STATUS = ["Pendente", "Auditado", "Cancelado", "Justificado"]
TIPOS_REGISTRO = [
    "Abastecimento", 
    "Troca de Óleo", 
    "troca de Óleo + filtro", 
    "Pneus", 
    "Reparo no Motor", 
    "Filtro de Combustível (+1)", 
    "Filtro de Óleo (+1)", 
    "Outros"
]

st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis",
    page_icon="📍",
    layout="wide",
)

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown("""
    <style>
    .stApp {
        background-color: #f0f4f8;
        color: #102a43;
    }
    [data-testid="stSidebar"] {
        background-color: #1e3a8a;
        border-right: 1px solid #1e40af;
    }
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label {
        color: #ffffff !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #0f172a !important;
    }
    [data-testid="stSidebar"] .stButton>button {
        background-color: #2563eb !important;
        color: white !important;
        border-radius: 6px;
        font-weight: 600;
        border: 1px solid #3b82f6;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: #1d4ed8 !important;
        color: white !important;
    }
    .stButton>button, div.stFormSubmitButton>button {
        background-color: #10b981 !important;
        color: white !important;
        border-radius: 6px;
        font-weight: 600;
        border: none;
    }
    .stButton>button:hover, div.stFormSubmitButton>button:hover {
        background-color: #059669 !important;
        color: white !important;
    }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border-left: 4px solid #10b981;
    }
    .legenda-container {
        background-color: #ffffff;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 20px;
        border-left: 5px solid #2563eb;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📍 Roteiro MooveChain - Florianópolis")

# --- CONTROLE DE AUTENTICAÇÃO (ADMIN) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

st.sidebar.markdown("### 🔐 Acesso Administrativo")
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input("Senha do Administrador:", type="password")
    if st.sidebar.button("Entrar", key="btn_login"):
        senha_correta = st.secrets.get("admin_password", "moovechain2026")
        if senha_digitada == senha_correta:
            st.session_state["autenticado"] = True
            st.sidebar.success("✅ Acesso liberado!")
            st.rerun()
        else:
            st.sidebar.error("❌ Senha incorreta.")
else:
    st.sidebar.success("👤 Modo Administrador Ativo")
    if st.sidebar.button("Sair (Logout)", key="btn_logout"):
        st.session_state["autenticado"] = False
        st.rerun()

st.sidebar.markdown("---")

# --- GERENCIAMENTO DE ESTADO DO MENU ---
if st.session_state["autenticado"]:
    OPCOES_MENU = [
        "📊 Dashboard Auditorias MooveChain",
        "🗺️ Visualizar Mapa de Pontos",
        "📋 Tabela de Dados e Ações",
        "✏️ Editar Registro Existente",
        "➕ Adicionar Novo Registro",
        "🚚 Custos Logísticos (Frota)",
    ]
else:
    OPCOES_MENU = [
        "📊 Dashboard Auditorias MooveChain",
        "🗺️ Visualizar Mapa de Pontos",
    ]

if "menu_selecionado" not in st.session_state or st.session_state["menu_selecionado"] not in OPCOES_MENU:
    st.session_state["menu_selecionado"] = OPCOES_MENU[0]

if "destinatario_para_editar" not in st.session_state:
    st.session_state["destinatario_para_editar"] = None

if "mensagem_sucesso_edicao" not in st.session_state:
    st.session_state["mensagem_sucesso_edicao"] = None


@st.cache_resource
def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key("12sENMxX1FoQ6KYNgnlnXzD3abDqO4VH_jypcB-nQGks")
    return spreadsheet


@st.cache_data(ttl=86400)
def geolocalizar_endereco(endereco):
    try:
        geolocator = Nominatim(user_agent="moovechain_app_fast_2026", timeout=10)
        location = geolocator.geocode(endereco)
        if location:
            return str(location.latitude), str(location.longitude)
    except Exception:
        pass
    return "", ""


try:
    spreadsheet = conectar_sheets()
    sheet = spreadsheet.get_worksheet(0)
    todos_os_valores = sheet.get_all_values()

    if len(todos_os_valores) > 1:
        cabecalho = [str(c).strip() for c in todos_os_valores[0]]
        dados = todos_os_valores[1:]

        df = pd.DataFrame(dados, columns=cabecalho)
        df["_linha_sheets"] = range(2, len(dados) + 2)
    else:
        st.warning("A planilha principal parece estar vazia.")
        st.stop()

    if "Status" not in df.columns:
        df["Status"] = "Pendente"
    df["Status"] = (
        df["Status"].astype(str).str.strip().replace(["", "nan", "None"], "Pendente")
    )
    # Padroniza a primeira letra maiúscula para contagens precisas
    df["Status"] = df["Status"].str.capitalize()

    if "Bairro" in df.columns:
        df["Bairro"] = df["Bairro"].astype(str).str.strip()
        df["Bairro"] = df["Bairro"].replace(["", "nan", "None"], "Não Especificado")

    if "Destinatário" in df.columns:
        df["Destinatário"] = df["Destinatário"].astype(str).str.strip()

    df["Identificador_Unico"] = df.apply(
        lambda r: f"Linha {r['_linha_sheets']} | {r['Destinatário']} ({r.get('Bairro', '')} - {r.get('Rua', '')})",
        axis=1
    )

except Exception as e:
    st.error(f"❌ Erro ao ler a planilha: {e}")
    st.stop()


def obter_ou_criar_aba(nome_aba, cabecalho_padrao):
    try:
        aba = spreadsheet.worksheet(nome_aba)
    except gspread.exceptions.WorksheetNotFound:
        aba = spreadsheet.add_worksheet(title=nome_aba, rows=100, cols=10)
        aba.append_row(cabecalho_padrao)
    return aba


# --- MENU LATERAL EM ESTILO LISTA ---
st.sidebar.markdown("### Navegação")
for op in OPCOES_MENU:
    if st.sidebar.button(op, use_container_width=True, key=f"menu_btn_{op}"):
        st.session_state["menu_selecionado"] = op
        st.rerun()

opcao = st.session_state["menu_selecionado"]


# --- ABA 1: DASHBOARD AUDITORIAS MOOVECHAIN ---
if opcao == "📊 Dashboard Auditorias MooveChain":
    st.subheader("📊 Dashboard Auditorias MooveChain")
    st.markdown("---")

    status_padrao = ["Auditado", "Cancelado", "Justificado"]
    status_medicao = st.multiselect(
        "⚙️ Status considerados como Concluídos:",
        options=LISTA_STATUS,
        default=status_padrao,
        help="Escolha quais status representam uma visita/medição finalizada."
    )

    total_geral = len(df)
    df_concluidos = df[df["Status"].isin(status_medicao)]
    concluidos = len(df_concluidos)
    restantes = total_geral - concluidos
    pct_conclusao = (concluidos / total_geral * 100) if total_geral > 0 else 0.0

    # Contagens individuais para cada status
    qtd_auditado = len(df[df["Status"] == "Auditado"])
    qtd_pendente = len(df[df["Status"] == "Pendente"])
    qtd_cancelado = len(df[df["Status"] == "Cancelado"])
    qtd_justificado = len(df[df["Status"] == "Justificado"])

    st.markdown("### 1. 📌 Detalhamento por Status Atual")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric(label="🟢 Auditados", value=f"{qtd_auditado:,}".replace(",", "."))
    with col_s2:
        st.metric(label="🟡 Pendentes", value=f"{qtd_pendente:,}".replace(",", "."))
    with col_s3:
        st.metric(label="🔴 Cancelados", value=f"{qtd_cancelado:,}".replace(",", "."))
    with col_s4:
        st.metric(label="🔵 Justificados", value=f"{qtd_justificado:,}".replace(",", "."))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 2. 🎯 Progresso Global de Auditorias")
    st.progress(pct_conclusao / 100)
    st.caption(f"🎯 Conclusão Global: **{pct_conclusao:.1f}%** do total auditado")

    st.markdown("<br>", unsafe_allow_html=True)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        st.metric(label="📍 Total Geral de Pontos", value=f"{total_geral:,}".replace(",", "."))
    with col_kpi2:
        st.metric(label="✅ Visitas Concluídas", value=f"{concluidos:,}".replace(",", "."), delta=f"{pct_conclusao:.1f}% do Total")
    with col_kpi3:
        pct_restante = (restantes / total_geral * 100) if total_geral > 0 else 0.0
        st.metric(label="⏳ Restantes / Pendentes", value=f"{restantes:,}".replace(",", "."), delta=f"-{pct_restante:.1f}% Restantes", delta_color="inverse")
    with col_kpi4:
        st.metric(label="🎯 Progresso Global", value=f"{pct_conclusao:.1f}%")

    st.markdown("---")
    st.markdown("### 3. 📊 Progresso por Bairro")

    df_barras = df.copy()
    df_barras["Situacao"] = df_barras["Status"].apply(
        lambda s: "Concluído" if s in status_medicao else "Pendente"
    )

    df_agrupado = (
        df_barras.groupby(["Bairro", "Situacao"])
        .size()
        .reset_index(name="Quantidade")
    )

    ordem_bairros = (
        df_barras.groupby("Bairro")
        .size()
        .sort_values(ascending=False)
        .index.tolist()
    )

    if not df_agrupado.empty:
        fig_stacked = px.bar(
            df_agrupado,
            x="Bairro",
            y="Quantidade",
            color="Situacao",
            title="Distribuição de Concluídos vs Pendentes por Bairro",
            labels={"Bairro": "Bairro", "Quantidade": "Qtd. de Pontos", "Situacao": "Status"},
            color_discrete_map={"Concluído": "#10b981", "Pendente": "#3b82f6"},
            category_orders={"Bairro": ordem_bairros, "Situacao": ["Concluído", "Pendente"]},
            barmode="stack",
            text="Quantidade"
        )
        fig_stacked.update_layout(xaxis_tickangle=-45, height=450, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_stacked, use_container_width=True)


# --- ABA 2: MAPA INTERATIVO DINÂMICO (FOLIUM) ---
elif opcao == "🗺️ Visualizar Mapa de Pontos":
    st.subheader("🗺️ Mapa Interativo de Pontos por Status")
    st.markdown("---")

    st.markdown("""
        <div class="legenda-container">
            <h4 style="margin-top: 0; color: #1e3a8a !important;">📌 Legenda e Significado dos Alfinetes no Mapa</h4>
            <p style="margin-bottom: 12px; font-size: 14px;">Consulte abaixo o significado das cores dos marcadores exibidos no mapa interativo:</p>
            <ul style="list-style-type: none; padding-left: 0; display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 0;">
                <li>🟢 <b>Verde:</b> Auditado</li>
                <li>🟡 <b>Amarelo / Laranja:</b> Pendente</li>
                <li>🔴 <b>Vermelho:</b> Cancelado</li>
                <li>🔵 <b>Azul:</b> Justificado</li>
            </ul>
        </div>
    """, unsafe_allow_html=True)

    mapa_floripa = folium.Map(location=[-27.5954, -48.5480], zoom_start=12, control_scale=True)

    def obter_cor_marcador(status):
        status_limpo = str(status).strip().capitalize()
        if status_limpo == "Auditado":
            return "green"
        elif status_limpo == "Pendente":
            return "orange"
        elif status_limpo == "Cancelado":
            return "red"
        elif status_limpo == "Justificado":
            return "blue"
        else:
            return "gray"

    for _, row in df.iterrows():
        try:
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
            status = row["Status"]
            destinatario = row["Destinatário"]
            bairro = row.get("Bairro", "Não informado")
            
            cor = obter_cor_marcador(status)
            popup_html = f"<b>Destinatário:</b> {destinatario}<br><b>Bairro:</b> {bairro}<br><b>Status:</b> {status}"
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=cor, icon="info-sign")
            ).add_to(mapa_floripa)
        except (ValueError, TypeError):
            continue

    st_folium(mapa_floripa, width=1300, height=600)


# --- ABA 3: TABELA DE DADOS E AÇÕES ---
elif opcao == "📋 Tabela de Dados e Ações" and st.session_state["autenticado"]:
    st.subheader("📋 Tabela de Destinatários e Rotas")

    col_bairro, col_dest, col_status = st.columns([1, 1.2, 0.8])
    with col_bairro:
        todos_bairros = sorted([str(b) for b in df["Bairro"].unique() if str(b).strip() != ""])
        bairros_sel = st.multiselect("Filtrar por Bairro(s):", options=todos_bairros, default=[])

    df_filtrado = df.copy()
    if bairros_sel:
        df_filtrado = df_filtrado[df_filtrado["Bairro"].astype(str).isin(bairros_sel)]

    with col_dest:
        todos_destinatarios = sorted([str(d) for d in df_filtrado["Destinatário"].unique() if str(d).strip() != ""])
        destinatarios_sel = st.multiselect("Filtrar por Destinatário(s):", options=todos_destinatarios, default=[])

    with col_status:
        status_sel = st.selectbox("Filtrar por Status:", ["Todos"] + LISTA_STATUS)

    if destinatarios_sel:
        df_filtrado = df_filtrado[df_filtrado["Destinatário"].astype(str).isin(destinatarios_sel)]
    if status_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Status"].astype(str) == status_sel]

    st.write(f"Exibindo **{len(df_filtrado)}** de **{len(df)}** registros.")
    df_exibicao = df_filtrado.drop(columns=["_linha_sheets", "Identificador_Unico"], errors="ignore")

    event = st.dataframe(df_exibicao, use_container_width=True, on_select="rerun", selection_mode="single-row", key="tabela_destinatarios")
    rows_selecionadas = event.selection.get("rows", [])

    st.markdown("---")
    col_info, col_btn = st.columns([3, 1])
    if len(rows_selecionadas) > 0:
        idx_linha = rows_selecionadas[0]
        registro_selecionado = df_filtrado.iloc[idx_linha]
        id_unico = registro_selecionado["Identificador_Unico"]

        with col_info:
            st.success(f"📌 **Selecionado:** {registro_selecionado['Destinatário']} (Linha {registro_selecionado['_linha_sheets']} no Sheets)")
        with col_btn:
            if st.button("✏️ Editar Registro Selecionado", type="primary", use_container_width=True):
                st.session_state["destinatario_para_editar"] = id_unico
                st.session_state["mensagem_sucesso_edicao"] = None
                st.session_state["menu_selecionado"] = "✏️ Editar Registro Existente"
                st.rerun()


# --- ABA 4: EDITAR REGISTRO EXISTENTE ---
elif opcao == "✏️ Editar Registro Existente" and st.session_state["autenticado"]:
    st.subheader("✏️ Editar Registro na Planilha")

    if st.session_state.get("mensagem_sucesso_edicao"):
        st.success(st.session_state["mensagem_sucesso_edicao"])
        if st.button("📋 Voltar para a Tabela de Dados", type="secondary"):
            st.session_state["mensagem_sucesso_edicao"] = None
            st.session_state["menu_selecionado"] = "📋 Tabela de Dados e Ações"
            st.rerun()
        st.markdown("---")

    lista_identificadores = df["Identificador_Unico"].tolist()
    idx_default = 0
    if st.session_state["destinatario_para_editar"] in lista_identificadores:
        idx_default = lista_identificadores.index(st.session_state["destinatario_para_editar"])

    dest_sel = st.selectbox("Selecione o Destinatário para editar:", options=lista_identificadores, index=idx_default)

    if dest_sel:
        st.session_state["destinatario_para_editar"] = dest_sel
        dados = df[df["Identificador_Unico"] == dest_sel].iloc[0]
        linha_real = int(dados["_linha_sheets"])

        with st.form("f_edit"):
            n_dest = st.text_input("Destinatário", value=str(dados["Destinatário"]))
            n_rua = st.text_input("Rua", value=str(dados.get("Rua", "")))
            n_num = st.text_input("Número", value=str(dados.get("Numero", "")))
            n_bairro = st.text_input("Bairro", value=str(dados.get("Bairro", "")))
            n_cid = st.text_input("Cidade", value=str(dados.get("Cidade", "Florianópolis")))
            n_est = st.text_input("Estado", value=str(dados.get("Estado", "SC")))
            n_cep = st.text_input("CEP", value=str(dados.get("CEP", "")))
            
            st_atual = str(dados["Status"]).strip().capitalize()
            idx_st = LISTA_STATUS.index(st_atual) if st_atual in LISTA_STATUS else 0
            n_st = st.selectbox("Status", LISTA_STATUS, index=idx_st)
            
            n_lat = st.text_input("Latitude", value=str(dados.get("Latitude", "")))
            n_lng = st.text_input("Longitude", value=str(dados.get("Longitude", "")))

            if st.form_submit_button("💾 Salvar Alterações na Planilha", type="primary"):
                try:
                    n_end_comp = f"{n_rua}, {n_num} - {n_bairro}, {n_cid} - {n_est}, CEP {n_cep}, Brasil"
                    if not n_lat or not n_lng:
                        n_lat, n_lng = geolocalizar_endereco(n_end_comp)

                    novos_valores = [n_dest, n_rua, n_num, n_bairro, n_cid, n_est, n_cep, n_end_comp, n_st, n_lat, n_lng]
                    sheet.update(range_name=f"A{linha_real}:K{linha_real}", values=[novos_valores])
                    
                    st.cache_data.clear()
                    st.session_state["mensagem_sucesso_edicao"] = f"✅ Alteração salva com sucesso para **{n_dest}**!"
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Erro ao salvar na planilha: {err}")


# --- ABA 5: ADICIONAR NOVO REGISTRO ---
elif opcao == "➕ Adicionar Novo Registro" and st.session_state["autenticado"]:
    st.subheader("➕ Novo Registro")
    with st.form("f_novo"):
        dest = st.text_input("Destinatário")
        rua = st.text_input("Rua")
        num = st.text_input("Número")
        bairro = st.text_input("Bairro")
        cid = st.text_input("Cidade", value="Florianópolis")
        est = st.text_input("Estado", value="SC")
        cep = st.text_input("CEP")
        st_novo = st.selectbox("Status", LISTA_STATUS)

        if st.form_submit_button("➕ Cadastrar", type="primary"):
            if dest:
                try:
                    end_comp = f"{rua}, {num} - {bairro}, {cid} - {est}, CEP {cep}, Brasil"
                    lat, lng = geolocalizar_endereco(end_comp)
                    sheet.append_row([dest, rua, num, bairro, cid, est, cep, end_comp, st_novo, lat, lng])
                    st.success("✅ Novo destinatário adicionado ao Google Sheets!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Erro ao cadastrar na planilha: {err}")


# --- ABA 6: CUSTOS LOGÍSTICOS E FROTA ---
elif opcao == "🚚 Custos Logísticos (Frota)" and st.session_state["autenticado"]:
    st.subheader("🚚 Controle de Custos Logísticos (Abastecimentos e Manutenções)")
    st.markdown("---")

    aba_custos = obter_ou_criar_aba("Controle_Custos", ["Data", "Tipo de Registro", "Local / Posto", "Odômetro (KM)", "Custo (R$)", "Litros"])

    val_custos = aba_custos.get_all_values()
    if len(val_custos) > 1:
        df_custos = pd.DataFrame(val_custos[1:], columns=val_custos[0])
        df_custos["_linha_sheets"] = range(2, len(val_custos) + 1)
    else:
        df_custos = pd.DataFrame(columns=["Data", "Tipo de Registro", "Local / Posto", "Odômetro (KM)", "Custo (R$)", "Litros", "_linha_sheets"])

    tab_novo_lancamento, tab_editar_lancamento, tab_tabela_custos, tab_relatorio_custos = st.tabs([
        "➕ Novo Lançamento", 
        "✏️ Editar Lançamento", 
        "📋 Tabela de Registros", 
        "📊 Indicadores e Métricas"
    ])

    with tab_novo_lancamento:
        st.markdown("### Adicionar Novo Registro de Custo / Abastecimento")
        with st.form("form_novo_custo"):
            c_data = st.date_input("Data", value=date.today())
            c_tipo = st.selectbox("Tipo de Registro", TIPOS_REGISTRO)
            c_local = st.text_input("Local / Posto (Ex: Primos Pequeno Príncipe, Posto Ipiranga, Moto Moto)")
            c_odometro = st.text_input("Odômetro (KM) (Ex: 925.690)")
            c_custo = st.text_input("Custo (R$) (Ex: 45,09)")
            c_litros = st.text_input("Litros (Deixar em branco se for manutenção)")

            if st.form_submit_button("Salvar Registro", type="primary"):
                try:
                    aba_custos.append_row([
                        str(c_data),
                        c_tipo,
                        c_local,
                        c_odometro,
                        c_custo,
                        c_litros
                    ])
                    st.success("✅ Registro adicionado com sucesso ao Google Sheets!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as err:
                    st.error(f"Erro ao salvar registro: {err}")

    with tab_editar_lancamento:
        st.markdown("### ✏️ Editar Lançamento Existente")
        if not df_custos.empty:
            df_custos["Identificador_Custo"] = df_custos.apply(
                lambda r: f"Linha {r['_linha_sheets']} | {r['Data']} - {r['Tipo de Registro']} ({r['Local / Posto']} - {r['Odômetro (KM)']})", 
                axis=1
            )
            
            sel_custo_edit = st.selectbox("Selecione o registro que deseja alterar:", options=df_custos["Identificador_Custo"].tolist())
            
            if sel_custo_edit:
                dados_c = df_custos[df_custos["Identificador_Custo"] == sel_custo_edit].iloc[0]
                l_real = int(dados_c["_linha_sheets"])

                with st.form("form_edicao_custo"):
                    e_data = st.text_input("Data", value=str(dados_c["Data"]))
                    
                    t_atual = str(dados_c["Tipo de Registro"]).strip()
                    idx_t = TIPOS_REGISTRO.index(t_atual) if t_atual in TIPOS_REGISTRO else 0
                    e_tipo = st.selectbox("Tipo de Registro", TIPOS_REGISTRO, index=idx_t)
                    
                    e_local = st.text_input("Local / Posto", value=str(dados_c["Local / Posto"]))
                    e_odometro = st.text_input("Odômetro (KM)", value=str(dados_c["Odômetro (KM)"]))
                    e_custo = st.text_input("Custo (R$)", value=str(dados_c["Custo (R$)"]))
                    e_litros = st.text_input("Litros", value=str(dados_c["Litros"]))

                    if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                        try:
                            novos_valores_custo = [e_data, e_tipo, e_local, e_odometro, e_custo, e_litros]
                            aba_custos.update(range_name=f"A{l_real}:F{l_real}", values=[novos_valores_custo])
                            st.success(f"✅ Registro da linha {l_real} atualizado com sucesso!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as err:
                            st.error(f"❌ Erro ao atualizar o registro: {err}")
        else:
            st.info("Nenhum registro encontrado para edição.")

    with tab_tabela_custos:
        st.markdown("### Histórico Completo de Lançamentos")
        if not df_custos.empty:
            st.dataframe(df_custos.drop(columns=["_linha_sheets", "Identificador_Custo"], errors="ignore"), use_container_width=True)
        else:
            st.info("Ainda não há registros na aba de custos.")

    with tab_relatorio_custos:
        st.markdown("### 📊 Indicadores de Consumo (Km/L) e Manutenção Preventiva")

        if not df_custos.empty:
            df_analise = df_custos.copy()
            df_analise["Odometro_Clean"] = pd.to_numeric(df_analise["Odômetro (KM)"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False), errors="coerce")
            
            df_analise["Custo_Clean"] = pd.to_numeric(
                df_analise["Custo (R$)"]
                .astype(str)
                .str.replace("R$", "", regex=False)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip(), 
                errors="coerce"
            ).fillna(0)

            df_analise["Litros_Clean"] = pd.to_numeric(
                df_analise["Litros"]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.strip(), 
                errors="coerce"
            ).fillna(0)

            df_abast_calc = df_analise[df_analise["Tipo de Registro"].str.contains("Abastecimento", case=False, na=False)].sort_values(by="Odometro_Clean")

            if len(df_abast_calc) >= 2:
                df_abast_calc["Delta_Km"] = df_abast_calc["Odometro_Clean"].diff()
                df_abast_calc["Km_Por_Litro"] = df_abast_calc.apply(
                    lambda r: round(r["Delta_Km"] / r["Litros_Clean"], 2) if r["Litros_Clean"] > 0 and r["Delta_Km"] > 0 else 0, 
                    axis=1
                )

                media_geral_km_l = df_abast_calc[df_abast_calc["Km_Por_Litro"] > 0]["Km_Por_Litro"].mean()
                st.metric("⛽ Consumo Médio Geral", f"{media_geral_km_l:.2f} km/l" if not pd.isna(media_geral_km_l) else "Calculando...")

                st.markdown("#### Histórico Calculado de Consumo (Km/L por Abastecimento)")
                st.dataframe(df_abast_calc[["Data", "Local / Posto", "Odômetro (KM)", "Litros", "Km_Por_Litro"]], use_container_width=True)
            else:
                st.info("Insira mais abastecimentos para calcular a média de km por litro.")

            st.markdown("---")
            st.markdown("#### 🛠️ Controle de Troca de Óleo por KM Rodado")
            df_oleo = df_analise[df_analise["Tipo de Registro"].str.contains("Óleo|oleo", case=False, na=False)].sort_values(by="Odometro_Clean")
            if not df_oleo.empty:
                st.dataframe(df_oleo[["Data", "Tipo de Registro", "Local / Posto", "Odômetro (KM)", "Custo (R$)"]], use_container_width=True)
                
                ultimo_oleo = df_oleo.iloc[-1]["Odometro_Clean"]
                odometro_atual_geral = df_analise["Odometro_Clean"].max()
                
                if not pd.isna(ultimo_oleo) and not pd.isna(odometro_atual_geral):
                    km_desde_troca = odometro_atual_geral - ultimo_oleo
                    st.metric("🔧 Quilometragem rodada desde a última troca de óleo", f"{km_desde_troca:,.0f} km".replace(",", "."))
            else:
                st.info("Nenhum registro de troca de óleo encontrado para realizar o comparativo.")
        else:
            st.info("Adicione registros na aba de custos para visualizar os relatórios.")