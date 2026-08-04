from datetime import date
import re
import time
import folium
from geopy.geocoders import Nominatim
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import streamlit as st

LISTA_STATUS = ["Pendente", "Auditado", "Cancelado", "Justificado"]
TIPOS_REGISTRO = [
    "Abastecimento",
    "Troca de Óleo",
    "troca de Óleo + filtro",
    "Pneus",
    "Reparo no Motor",
    "Filtro de Combustível (+1)",
    "Filtro de Óleo (+1)",
    "Outros",
]

# --- COORDENADAS MANUAIS PARA PONTOS CRÍTICOS DA SC-405 ---
COORDENADAS_FIXAS_SC405 = {
    "4733": {"lat": -27.674500, "lon": -48.491200, "nome": "CATBLACK BAR"},
    "3520": {"lat": -27.662100, "lon": -48.489500, "nome": "PARK HUB / Campeche Park"}
}

st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis",
    page_icon="📍",
    layout="wide",
)

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown(
    """
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
    .popup-status-box {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-top: 20px;
        border-left: 5px solid #10b981;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("📍 Roteiro MooveChain - Florianópolis")

# --- CONTROLE DE AUTENTICAÇÃO (ADMIN) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

st.sidebar.markdown("### 🔐 Acesso Administrativo")
if not st.session_state["autenticado"]:
    senha_digitada = st.sidebar.text_input(
        "Senha do Administrador:", type="password"
    )
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

# --- GERENCIAMENTO DE ESTADO DO MENU REFORMULADO ---
if st.session_state["autenticado"]:
    OPCOES_MENU = [
        "📊 Dashboard Auditorias MooveChain",
        "🗺️ Visualizar Mapa de Pontos",
        "💰 Controle de Ganhos / Faturamento",
        "📋 Tabela de Dados e Ações",
        "✏️ Editar Registro Existente",
        "➕ Adicionar Novo Registro",
        "🛠️ Manutenção e Otimização do App",
        "🚚 Custos Logísticos (Frota)",
    ]
else:
    OPCOES_MENU = [
        "📊 Dashboard Auditorias MooveChain",
        "🗺️ Visualizar Mapa de Pontos",
    ]

if (
    "menu_selecionado" not in st.session_state
    or st.session_state["menu_selecionado"] not in OPCOES_MENU
):
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
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            creds_dict, scope
        )
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "credentials.json", scope
        )

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(
        "12sENMxX1FoQ6KYNgnlnXzD3abDqO4VH_jypcB-nQGks"
    )
    return spreadsheet


@st.cache_data(ttl=86400)
def geolocalizar_endereco(endereco, rua="", numero=""):
    rua_upper = str(rua).upper()
    end_upper = str(endereco).upper()
    num_str = str(numero).strip()

    if "FRANCISCO MAGNO VIEIRA" in rua_upper or "SC-405" in rua_upper or "FRANCISCO MAGNO VIEIRA" in end_upper or "SC-405" in end_upper:
        if num_str in COORDENADAS_FIXAS_SC405:
            return str(COORDENADAS_FIXAS_SC405[num_str]["lat"]), str(COORDENADAS_FIXAS_SC405[num_str]["lon"])

    try:
        geolocator = Nominatim(
            user_agent="moovechain_floripa_geo_2026", timeout=12
        )
        query_completa = f"{endereco}, Florianópolis, SC, Brasil"
        location = geolocator.geocode(query_completa)
        if location:
            lat_f = float(location.latitude)
            lon_f = float(location.longitude)
            if -27.85 <= lat_f <= -27.30 and -48.65 <= lon_f <= -48.35:
                return str(lat_f), str(lon_f)
    except Exception:
        pass
    return "", ""


try:
    spreadsheet = conectar_sheets()
    sheet = spreadsheet.get_worksheet(0)
    todos_os_valores = sheet.get_all_values()

    if len(todos_os_valores) > 1:
        cabecalho = [str(c).strip() for c in todos_os_valores[0]]

        if "Data Visita" not in cabecalho:
            cabecalho.append("Data Visita")
            sheet.update(range_name="A1:Z1", values=[cabecalho])
            todos_os_valores = sheet.get_all_values()
            cabecalho = [str(c).strip() for c in todos_os_valores[0]]

        dados = todos_os_valores[1:]

        df = pd.DataFrame(dados, columns=cabecalho[: len(dados[0])])
        df["_linha_sheets"] = range(2, len(dados) + 2)
    else:
        st.warning("A planilha principal parece estar vazia.")
        st.stop()

    if "Status" not in df.columns:
        df["Status"] = "Pendente"
    df["Status"] = (
        df["Status"]
        .astype(str)
        .str.strip()
        .replace(["", "nan", "None"], "Pendente")
    )
    df["Status"] = df["Status"].str.capitalize()

    if "Bairro" in df.columns:
        df["Bairro"] = df["Bairro"].astype(str).str.strip()
        df["Bairro"] = df["Bairro"].replace(
            ["", "nan", "None"], "Não Especificado"
        )

    if "Destinatário" in df.columns:
        df["Destinatário"] = df["Destinatário"].astype(str).str.strip()

    df["Identificador_Unico"] = df.apply(
        lambda r: f"Linha {r['_linha_sheets']} | {r['Destinatário']} ({r.get('Bairro', '')} - {r.get('Rua', '')})",
        axis=1,
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


# --- ABA 1: DASHBOARD AUDITORIAS MOOVECHAIN (PÚBLICO) ---
if opcao == "📊 Dashboard Auditorias MooveChain":
    st.subheader("📊 Dashboard Auditorias MooveChain")
    st.markdown("---")

    st.markdown("### 🔍 Filtros Dinâmicos")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        estados_disponiveis = sorted(
            [
                str(e)
                for e in df.get("Estado", pd.Series(["SC"])).unique()
                if str(e).strip() != ""
            ]
        )
        estados_sel = st.multiselect(
            "Filtrar por Estado(s):", options=estados_disponiveis, default=[]
        )

    df_temp_est = (
        df[df["Estado"].astype(str).isin(estados_sel)]
        if estados_sel
        else df
    )

    with col_f2:
        cidades_disponiveis = sorted(
            [
                str(c)
                for c in df_temp_est.get(
                    "Cidade", pd.Series(["Florianópolis"])
                ).unique()
                if str(c).strip() != ""
            ]
        )
        cidades_sel = st.multiselect(
            "Filtrar por Cidade(s):", options=cidades_disponiveis, default=[]
        )

    df_temp_cid = (
        df_temp_est[df_temp_est["Cidade"].astype(str).isin(cidades_sel)]
        if cidades_sel
        else df_temp_est
    )

    with col_f3:
        bairros_disponiveis = sorted(
            [
                str(b)
                for b in df_temp_cid.get("Bairro", pd.Series()).unique()
                if str(b).strip() != ""
            ]
        )
        bairros_sel = st.multiselect(
            "Filtrar por Bairro(s):", options=bairros_disponiveis, default=[]
        )

    with col_f4:
        opcoes_status_filtro = ["Todos"] + LISTA_STATUS
        status_sel = st.multiselect(
            "Filtrar por Status:", options=opcoes_status_filtro, default=["Todos"]
        )

    df_dashboard = df.copy()
    if estados_sel:
        df_dashboard = df_dashboard[
            df_dashboard["Estado"].astype(str).isin(estados_sel)
        ]
    if cidades_sel:
        df_dashboard = df_dashboard[
            df_dashboard["Cidade"].astype(str).isin(cidades_sel)
        ]
    if bairros_sel:
        df_dashboard = df_dashboard[
            df_dashboard["Bairro"].astype(str).isin(bairros_sel)
        ]
    if status_sel and "Todos" not in status_sel:
        df_dashboard = df_dashboard[
            df_dashboard["Status"].astype(str).isin(status_sel)
        ]

    st.markdown("---")

    status_padrao = ["Auditado", "Cancelado", "Justificado"]
    status_medicao = st.multiselect(
        "⚙️ Status considerados como Concluídos:",
        options=LISTA_STATUS,
        default=status_padrao,
        help="Escolha quais status representam uma visita/medição finalizada.",
    )

    total_geral = len(df_dashboard)
    df_concluidos = df_dashboard[df_dashboard["Status"].isin(status_medicao)]
    concluidos = len(df_concluidos)
    restantes = total_geral - concluidos
    pct_conclusao = (
        (concluidos / total_geral * 100) if total_geral > 0 else 0.0
    )

    st.markdown("### 1. 🎯 Progresso Global de Auditorias")
    st.progress(pct_conclusao / 100 if total_geral > 0 else 0.0)
    st.caption(
        f"🎯 Conclusão Global: **{pct_conclusao:.1f}%** do total auditado (Total filtrado: {total_geral} pontos)"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        st.metric(
            label="📍 Total Geral de Pontos",
            value=f"{total_geral:,}".replace(",", "."),
        )
    with col_kpi2:
        st.metric(
            label="✅ Visitas Concluídas",
            value=f"{concluidos:,}".replace(",", "."),
            delta=f"{pct_conclusao:.1f}% do Total",
        )
    with col_kpi3:
        pct_restante = (
            (restantes / total_geral * 100) if total_geral > 0 else 0.0
        )
        st.metric(
            label="⏳ Restantes / Pendentes",
            value=f"{restantes:,}".replace(",", "."),
            delta=f"-{pct_restante:.1f}% Restantes",
            delta_color="inverse",
        )
    with col_kpi4:
        st.metric(label="🎯 Progresso Global", value=f"{pct_conclusao:.1f}%")

    st.markdown("---")

    qtd_auditado = len(df_dashboard[df_dashboard["Status"] == "Auditado"])
    qtd_pendente = len(df_dashboard[df_dashboard["Status"] == "Pendente"])
    qtd_cancelado = len(df_dashboard[df_dashboard["Status"] == "Cancelado"])
    qtd_justificado = len(df_dashboard[df_dashboard["Status"] == "Justificado"])

    st.markdown("### 2. 📌 Detalhamento por Status Atual")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric(
            label="🟢 Auditados",
            value=f"{qtd_auditado:,}".replace(",", "."),
        )
    with col_s2:
        st.metric(
            label="🟡 Pendentes",
            value=f"{qtd_pendente:,}".replace(",", "."),
        )
    with col_s3:
        st.metric(
            label="🔴 Cancelados",
            value=f"{qtd_cancelado:,}".replace(",", "."),
        )
    with col_s4:
        st.metric(
            label="🔵 Justificados",
            value=f"{qtd_justificado:,}".replace(",", "."),
        )

    st.markdown("---")
    st.markdown("### 3. 📊 Progresso por Bairro")

    df_barras = df_dashboard.copy()
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
            labels={
                "Bairro": "Bairro",
                "Quantidade": "Qtd. de Pontos",
                "Situacao": "Status",
            },
            color_discrete_map={"Concluído": "#10b981", "Pendente": "#3b82f6"},
            category_orders={
                "Bairro": ordem_bairros,
                "Situacao": ["Concluído", "Pendente"],
            },
            barmode="stack",
            text="Quantidade",
        )
        fig_stacked.update_layout(
            xaxis_tickangle=-45,
            height=450,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_stacked, use_container_width=True)
    else:
        st.info(
            "Nenhum dado encontrado para exibir no gráfico com os filtros selecionados."
        )


# --- ABA EXCLUSIVA ADMIN: CONTROLE DE GANHOS E FATURAMENTO ---
elif opcao == "💰 Controle de Ganhos / Faturamento" and st.session_state["autenticado"]:
    st.subheader("💰 Painel Restrito de Ganhos e Faturamento")
    st.markdown("---")
    st.markdown(
        "Gerencie abaixo os pontos noturnos e visualize o faturamento detalhado por ponto auditado e noturno dentro do período selecionado."
    )

    try:
        aba_noturnos = obter_ou_criar_aba(
            "Pontos_Noturnos", ["Identificador_Unico"]
        )
        valores_noturnos = aba_noturnos.get_all_values()
        lista_noturnos_cadastrados = (
            [row[0] for row in valores_noturnos[1:]]
            if len(valores_noturnos) > 1
            else []
        )
    except Exception:
        lista_noturnos_cadastrados = []

    ano_atual = date.today().year
    if "filtro_ganhos_desde" not in st.session_state:
        st.session_state["filtro_ganhos_desde"] = date(ano_atual, 1, 1)
    if "filtro_ganhos_hastá" not in st.session_state:
        st.session_state["filtro_ganhos_hastá"] = date(ano_atual, 12, 31)

    st.markdown("### 📅 Filtro de Período (De - Até)")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        data_desde = st.date_input(
            "Data Início (De):",
            value=st.session_state["filtro_ganhos_desde"],
            key="input_desde_ganhos",
        )
    with col_d2:
        data_hastá = st.date_input(
            "Data Fim (Até):",
            value=st.session_state["filtro_ganhos_hastá"],
            key="input_hasta_ganhos",
        )

    st.session_state["filtro_ganhos_desde"] = data_desde
    st.session_state["filtro_ganhos_hastá"] = data_hastá

    df_faturamento = df.copy()

    if "Data Visita" in df_faturamento.columns:
        df_faturamento["Data_Visita_DT"] = pd.to_datetime(
            df_faturamento["Data Visita"], errors="coerce"
        ).dt.date
        df_faturamento = df_faturamento[
            (df_faturamento["Data_Visita_DT"].isna())
            | (
                (df_faturamento["Data_Visita_DT"] >= data_desde)
                & (df_faturamento["Data_Visita_DT"] <= data_hastá)
            )
        ]

    df_faturamento["Eh_Noturno"] = df_faturamento[
        "Identificador_Unico"
    ].isin(lista_noturnos_cadastrados)


    def calcular_ganho_linha(row):
        status = row["Status"]
        noturno = row["Eh_Noturno"]
        if noturno:
            if status == "Auditado":
                return 35.0
            elif status == "Justificado":
                return 25.0
            else:
                return 0.0
        else:
            if status == "Auditado":
                return 25.0
            else:
                return 0.0


    df_faturamento["Ganho_R$"] = df_faturamento.apply(
        calcular_ganho_linha, axis=1
    )

    total_ganho = df_faturamento["Ganho_R$"].sum()
    total_auditados_normais = len(
        df_faturamento[
            (df_faturamento["Status"] == "Auditado")
            & (~df_faturamento["Eh_Noturno"])
        ]
    )
    total_auditados_noturnos = len(
        df_faturamento[
            (df_faturamento["Status"] == "Auditado")
            & (df_faturamento["Eh_Noturno"])
        ]
    )
    total_justificados_noturnos = len(
        df_faturamento[
            (df_faturamento["Status"] == "Justificado")
            & (df_faturamento["Eh_Noturno"])
        ]
    )

    col_fin1, col_fin2, col_fin3, col_fin4 = st.columns(4)
    with col_fin1:
        st.metric(
            label="💵 Faturamento no Período",
            value=f"R$ {total_ganho:,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
        )
    with col_fin2:
        st.metric(
            label="🟢 Auditados Padrão (R$ 25)",
            value=f"{total_auditados_normais}",
        )
    with col_fin3:
        st.metric(
            label="🌙 Auditados Noturnos (R$ 35)",
            value=f"{total_auditados_noturnos}",
        )
    with col_fin4:
        st.metric(
            label="🔵 Justificados Noturnos (R$ 25)",
            value=f"{total_justificados_noturnos}",
        )

    st.markdown("---")
    st.markdown("### ⚙️ Configuração de Pontos Noturnos")
    with st.form("form_config_noturno"):
        pontos_selecao_noturna = st.multiselect(
            "Estabelecimentos Noturnos:",
            options=df["Identificador_Unico"].tolist(),
            default=[
                p
                for p in lista_noturnos_cadastrados
                if p in df["Identificador_Unico"].tolist()
            ],
        )
        btn_salvar_noturnos = st.form_submit_button(
            "Salvar Configuração Noturna", type="primary"
        )

        if btn_salvar_noturnos:
            try:
                aba_noturnos.clear()
                aba_noturnos.append_row(["Identificador_Unico"])
                for p in pontos_selecao_noturna:
                    aba_noturnos.append_row([p])
                st.cache_data.clear()
                st.success(
                    "✅ Configuração de pontos noturnos salva com sucesso!"
                )
                st.rerun()
            except Exception as e_noturno:
                st.error(f"Erro ao salvar pontos noturnos: {e_noturno}")


# --- ABA 2: MAPA INTERATIVO DINÂMICO (FOLIUM) ---
elif opcao == "🗺️ Visualizar Mapa de Pontos":
    st.subheader("🗺️ Mapa Interativo de Pontos por Status")
    st.markdown("---")

    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )

    mapa_floripa = folium.Map(
        location=[-27.5954, -48.5480], zoom_start=14, control_scale=True
    )


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
            lat, lon = None, None
            lat_val = str(row.get("Latitude", "")).strip()
            lon_val = str(row.get("Longitude", "")).strip()

            if lat_val and lat_val not in ["nan", "None", ""]:
                try:
                    lat_f = float(lat_val)
                    if -27.85 <= lat_f <= -27.30:
                        lat = lat_f
                except ValueError:
                    pass

            if lon_val and lon_val not in ["nan", "None", ""]:
                try:
                    lon_f = float(lon_val)
                    if -48.65 <= lon_f <= -48.35:
                        lon = lon_f
                except ValueError:
                    pass

            endereco_completo = str(row.get("Endereço Completo", "")).strip()
            rua = str(row.get("Rua", "")).strip()
            numero = str(row.get("Numero", "")).strip()

            if lat is None or lon is None:
                if not endereco_completo or endereco_completo in ["nan", "None"]:
                    bairro = str(row.get("Bairro", "")).strip()
                    cidade = str(row.get("Cidade", "Florianópolis")).strip()
                    cep = str(row.get("CEP", "")).strip()
                    endereco_completo = (
                        f"{rua}, {numero} - {bairro}, {cidade} - SC, {cep}"
                    )

                lat_geo, lon_geo = geolocalizar_endereco(endereco_completo, rua=rua, numero=numero)
                if lat_geo and lon_geo:
                    try:
                        lat, lon = float(lat_geo), float(lon_geo)
                    except ValueError:
                        pass

            if lat is None or lon is None:
                lat, lon = -27.5954, -48.5480

            status = row.get("Status", "Pendente")
            destinatario = row.get("Destinatário", "Local")

            cor = obter_cor_marcador(status)
            popup_html = f"<b>Estabelecimento:</b> {destinatario}<br><b>Endereço:</b> {endereco_completo}<br><b>Status:</b> {status}"

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=cor, icon="info-sign"),
            ).add_to(mapa_floripa)
        except Exception:
            continue

    st_folium(mapa_floripa, width=1300, height=600)

    st.markdown(
        """
        <div class="popup-status-box">
            <h4 style="margin-top: 0; color: #1e3a8a !important;">🔄 Ação Rápida: Atualizar Status de um Ponto</h4>
            <p style="font-size: 14px; margin-bottom: 10px;">Selecione o ponto diretamente na lista abaixo para modificar o seu status na planilha em tempo real:</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    with st.form("form_status_mapa"):
        col_map1, col_map2, col_map3 = st.columns([2, 1, 1])
        with col_map1:
            ponto_sel_mapa = st.selectbox(
                "Escolha o Estabelecimento:",
                options=df["Identificador_Unico"].tolist(),
            )
        with col_map2:
            novo_status_mapa = st.selectbox(
                "Novo Status:", options=LISTA_STATUS
            )
        with col_map3:
            st.markdown("<br>", unsafe_allow_html=True)
            btn_atualizar_mapa = st.form_submit_button(
                "💾 Salvar Novo Status", type="primary", use_container_width=True
            )

        if btn_atualizar_mapa:
            try:
                dados_ponto = df[
                    df["Identificador_Unico"] == ponto_sel_mapa
                ].iloc[0]
                linha_alvo = int(dados_ponto["_linha_sheets"])
                idx_status_col = (
                    cabecalho.index("Status") + 1
                    if "Status" in cabecalho
                    else 9
                )
                idx_data_col = (
                    cabecalho.index("Data Visita") + 1
                    if "Data Visita" in cabecalho
                    else len(cabecalho)
                )

                sheet.update_cell(linha_alvo, idx_status_col, novo_status_mapa)

                if novo_status_mapa != "Pendente":
                    data_atual = date.today().strftime("%Y-%m-%d")
                    sheet.update_cell(linha_alvo, idx_data_col, data_atual)

                st.cache_data.clear()
                st.success(
                    f"✅ Status do estabelecimento **{dados_ponto['Destinatário']}** atualizado para **{novo_status_mapa}** com sucesso!"
                )
                st.rerun()
            except Exception as err:
                st.error(f"❌ Erro ao atualizar status: {err}")


# --- ABA 3: TABELA DE DADOS E AÇÕES ---
elif opcao == "📋 Tabela de Dados e Ações" and st.session_state["autenticado"]:
    st.subheader("📋 Tabela de Destinatários e Rotas")

    col_bairro, col_dest, col_status = st.columns([1, 1.2, 0.8])
    with col_bairro:
        todos_bairros = sorted(
            [str(b) for b in df["Bairro"].unique() if str(b).strip() != ""]
        )
        bairros_sel = st.multiselect(
            "Filtrar por Bairro(s):", options=todos_bairros, default=[]
        )

    df_filtrado = df.copy()
    if bairros_sel:
        df_filtrado = df_filtrado[
            df_filtrado["Bairro"].astype(str).isin(bairros_sel)
        ]

    with col_dest:
        todos_destinatarios = sorted(
            [
                str(d)
                for d in df_filtrado["Destinatário"].unique()
                if str(d).strip() != ""
            ]
        )
        destinatarios_sel = st.multiselect(
            "Filtrar por Destinatário(s):",
            options=todos_destinatarios,
            default=[],
        )

    with col_status:
        status_sel = st.selectbox(
            "Filtrar por Status:", ["Todos"] + LISTA_STATUS
        )

    if destinatarios_sel:
        df_filtrado = df_filtrado[
            df_filtrado["Destinatário"].astype(str).isin(destinatarios_sel)
        ]
    if status_sel != "Todos":
        df_filtrado = df_filtrado[
            df_filtrado["Status"].astype(str) == status_sel
        ]

    st.write(f"Exibindo **{len(df_filtrado)}** de **{len(df)}** registros.")
    df_exibicao = df_filtrado.drop(
        columns=["_linha_sheets", "Identificador_Unico"], errors="ignore"
    )

    event = st.dataframe(
        df_exibicao,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabela_destinatarios",
    )
    rows_selecionadas = event.selection.get("rows", [])

    st.markdown("---")
    col_info, col_btn = st.columns([3, 1])
    if len(rows_selecionadas) > 0:
        idx_linha = rows_selecionadas[0]
        registro_selecionado = df_filtrado.iloc[idx_linha]
        id_unico = registro_selecionado["Identificador_Unico"]

        with col_info:
            st.success(
                f"📌 **Selecionado:** {registro_selecionado['Destinatário']} (Linha {registro_selecionado['_linha_sheets']} no Sheets)"
            )
        with col_btn:
            if st.button(
                "✏️ Editar Registro Selecionado",
                type="primary",
                use_container_width=True,
            ):
                st.session_state["destinatario_para_editar"] = id_unico
                st.session_state["mensagem_sucesso_edicao"] = None
                st.session_state["menu_selecionado"] = (
                    "✏️ Editar Registro Existente"
                )
                st.rerun()


# --- ABA 4: EDITAR REGISTRO EXISTENTE ---
elif opcao == "✏️ Editar Registro Existente" and st.session_state["autenticado"]:
    st.subheader("✏️ Editar Registro na Planilha")

    if st.session_state.get("mensagem_sucesso_edicao"):
        st.success(st.session_state["mensagem_sucesso_edicao"])
        if st.button("📋 Voltar para a Tabela de Dados", type="secondary"):
            st.session_state["mensagem_sucesso_edicao"] = None
            st.session_state["menu_selecionado"] = (
                "📋 Tabela de Dados e Ações"
            )
            st.rerun()
        st.markdown("---")

    lista_identificadores = df["Identificador_Unico"].tolist()
    idx_default = 0
    if st.session_state["destinatario_para_editar"] in lista_identificadores:
        idx_default = lista_identificadores.index(
            st.session_state["destinatario_para_editar"]
        )

    dest_sel = st.selectbox(
        "Selecione o Destinatário para editar:",
        options=lista_identificadores,
        index=idx_default,
    )

    if dest_sel:
        st.session_state["destinatario_para_editar"] = dest_sel
        dados = df[df["Identificador_Unico"] == dest_sel].iloc[0]
        linha_real = int(dados["_linha_sheets"])

        with st.form("f_edit"):
            n_dest = st.text_input(
                "Destinatário", value=str(dados["Destinatário"])
            )
            n_rua = st.text_input("Rua", value=str(dados.get("Rua", "")))
            n_num = st.text_input("Número", value=str(dados.get("Numero", "")))
            n_bairro = st.text_input(
                "Bairro", value=str(dados.get("Bairro", ""))
            )
            n_cid = st.text_input(
                "Cidade", value=str(dados.get("Cidade", "Florianópolis"))
            )
            n_est = st.text_input(
                "Estado", value=str(dados.get("Estado", "SC"))
            )
            n_cep = st.text_input("CEP", value=str(dados.get("CEP", "")))

            st_atual = str(dados["Status"]).strip().capitalize()
            idx_st = (
                LISTA_STATUS.index(st_atual)
                if st_atual in LISTA_STATUS
                else 0
            )
            n_st = st.selectbox("Status", LISTA_STATUS, index=idx_st)

            n_lat = st.text_input(
                "Latitude", value=str(dados.get("Latitude", ""))
            )
            n_lng = st.text_input(
                "Longitude", value=str(dados.get("Longitude", ""))
            )
            n_data_visita = st.text_input(
                "Data Visita", value=str(dados.get("Data Visita", ""))
            )

            if st.form_submit_button(
                "💾 Salvar Alterações na Planilha", type="primary"
            ):
                try:
                    n_end_comp = f"{n_rua}, {n_num} - {n_bairro}, {n_cid} - {n_est}, {n_cep}"
                    
                    final_lat, final_lng = n_lat, n_lng
                    if not final_lat or not final_lng:
                        l_geo, l_lon_geo = geolocalizar_endereco(n_end_comp, rua=n_rua, numero=n_num)
                        if l_geo and l_lon_geo:
                            final_lat, final_lng = l_geo, l_lon_geo

                    sheet.update_cell(linha_real, cabecalho.index("Destinatário") + 1, n_dest)
                    if "Rua" in cabecalho: sheet.update_cell(linha_real, cabecalho.index("Rua") + 1, n_rua)
                    if "Numero" in cabecalho: sheet.update_cell(linha_real, cabecalho.index("Numero") + 1, n_num)
                    if "Bairro" in cabecalho: sheet.update_cell(linha_real, cabecalho.index("Bairro") + 1, n_bairro)
                    if "Status" in cabecalho: sheet.update_cell(linha_real, cabecalho.index("Status") + 1, n_st)
                    if "Latitude" in cabecalho: sheet.update_cell(linha_real, cabecalho.index("Latitude") + 1, final_lat)
                    if "Longitude" in cabecalho: sheet.update_cell(linha_real, cabecalho.index("Longitude") + 1, final_lng)

                    st.cache_data.clear()
                    st.session_state["mensagem_sucesso_edicao"] = f"✅ Registro de **{n_dest}** atualizado com sucesso!"
                    st.rerun()
                except Exception as ex_edit:
                    st.error(f"Erro ao salvar edição: {ex_edit}")


# --- ABA 5: ADICIONAR NOVO REGISTRO ---
elif opcao == "➕ Adicionar Novo Registro" and st.session_state["autenticado"]:
    st.subheader("➕ Adicionar Novo Ponto ao Roteiro")
    st.markdown("---")

    with st.form("form_adicionar_registro"):
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            novo_destinatario = st.text_input("Destinatário / Estabelecimento:")
            nova_rua = st.text_input("Rua:")
            novo_numero = st.text_input("Número:")
            novo_bairro = st.text_input("Bairro:")
        with col_n2:
            nova_cidade = st.text_input("Cidade:", value="Florianópolis")
            novo_estado = st.text_input("Estado:", value="SC")
            novo_cep = st.text_input("CEP:")
            novo_status = st.selectbox("Status Inicial:", LISTA_STATUS, index=0)

        btn_submit_novo = st.form_submit_button("➕ Cadastrar Ponto", type="primary")

        if btn_submit_novo:
            if not novo_destinatario.strip() or not nova_rua.strip():
                st.error("❌ Preencha pelo menos o Destinatário e a Rua.")
            else:
                try:
                    end_completo = f"{nova_rua}, {novo_numero} - {novo_bairro}, {nova_cidade} - {nova_estado}, {novo_cep}"
                    lat_g, lon_g = geolocalizar_endereco(end_completo, rua=nova_rua, numero=novo_numero)

                    nova_linha = [
                        novo_destinatario,
                        nova_rua,
                        novo_numero,
                        novo_bairro,
                        nova_cidade,
                        nova_estado,
                        novo_cep,
                        lat_g,
                        lon_g,
                        novo_status,
                        date.today().strftime("%Y-%m-%d") if novo_status != "Pendente" else ""
                    ]

                    while len(nova_linha) < len(cabecalho):
                        nova_linha.append("")

                    sheet.append_row(nova_linha[:len(cabecalho)])
                    st.cache_data.clear()
                    st.success(f"✅ Estabelecimento **{novo_destinatario}** adicionado com sucesso!")
                    time.sleep(1)
                    st.rerun()
                except Exception as err_add:
                    st.error(f"❌ Erro ao adicionar registro: {err_add}")


# --- ABA 6: MANUTENÇÃO E OTIMIZAÇÃO DO APP ---
elif opcao == "🛠️ Manutenção e Otimização do App" and st.session_state["autenticado"]:
    st.subheader("🛠️ Manutenção, Limpeza de Cache e Otimização")
    st.markdown("---")
    
    st.markdown("Utilize as ferramentas abaixo para revalidar coordenadas geográficas em lote ou limpar o cache do sistema caso perceba dados desatualizados na planilha.")

    col_m1, col_m2 = st.columns(2)
    
    with col_m1:
        st.markdown("### 🔄 Limpeza de Cache")
        st.write("Limpa o cache local armazenado para forçar a leitura imediata de novas alterações feitas diretamente no Google Sheets.")
        if st.button("🧹 Limpar Cache do Sistema", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("✅ Cache limpo com sucesso! Recarregue a página se necessário.")
            time.sleep(1)
            st.rerun()

    with col_m2:
        st.markdown("### 🗺️ Revalidação de Coordenadas")
        st.write("Varre os registros da planilha e recalcula as coordenadas geográficas ausentes ou incorretas.")
        if st.button("📍 Reotimizar Coordenadas", use_container_width=True):
            with st.spinner("Recalculando coordenadas dos pontos..."):
                atualizados = 0
                for idx, row in df.iterrows():
                    l_val = str(row.get("Latitude", "")).strip()
                    r_val = str(row.get("Rua", "")).strip()
                    n_val = str(row.get("Numero", "")).strip()
                    b_val = str(row.get("Bairro", "")).strip()
                    c_val = str(row.get("Cidade", "Florianópolis")).strip()
                    cep_v = str(row.get("CEP", "")).strip()
                    
                    if not l_val or l_val in ["nan", "None", ""]:
                        end_c = f"{r_val}, {n_val} - {b_val}, {c_val} - SC, {cep_v}"
                        nl, nlo = geolocalizar_endereco(end_c, rua=r_val, numero=n_val)
                        if nl and nlo:
                            linha_sh = int(row["_linha_sheets"])
                            idx_lat = cabecalho.index("Latitude") + 1 if "Latitude" in cabecalho else 8
                            idx_lon = cabecalho.index("Longitude") + 1 if "Longitude" in cabecalho else 9
                            sheet.update_cell(linha_sh, idx_lat, nl)
                            sheet.update_cell(linha_sh, idx_lon, nlo)
                            atualizados += 1
                
                st.cache_data.clear()
                st.success(f"✅ Revalidação concluída! {atualizados} pontos tiveram suas coordenadas atualizadas.")


# --- ABA 7: CUSTOS LOGÍSTICOS (FROTA) ---
elif opcao == "🚚 Custos Logísticos (Frota)" and st.session_state["autenticado"]:
    st.subheader("🚚 Controle de Custos Logísticos e Manutenção da Frota")
    st.markdown("---")
    st.markdown("Registre e acompanhe os gastos com abastecimento, troca de óleo, pneus e manutenções preventivas/corretivas.")

    aba_custos = obter_ou_criar_aba("Custos_Frota", ["Data", "Tipo_Registro", "Veiculo", "Valor_R$", "Quilometragem", "Observacoes"])
    
    with st.form("form_novo_custo_frota"):
        st.markdown("### ➕ Adicionar Novo Gasto / Manutenção")
        col_c1, col_c2, col_c3 = st.columns(3)
        
        with col_c1:
            data_gasto = st.date_input("Data do Registro:", value=date.today())
            tipo_reg = st.selectbox("Tipo de Registro:", TIPOS_REGISTRO)
        with col_c2:
            veiculo_reg = st.text_input("Identificação do Veículo / Placa:", value="Frota Principal")
            valor_reg = st.number_input("Valor (R$):", min_value=0.0, format="%.2f", step=10.0)
        with col_c3:
            km_reg = st.number_input("Quilometragem (KM atual):", min_value=0, step=100)
            obs_reg = st.text_input("Observações:")

        btn_salvar_custo = st.form_submit_button("💾 Salvar Registro na Frota", type="primary")

        if btn_salvar_custo:
            try:
                linha_custo = [
                    data_gasto.strftime("%Y-%m-%d"),
                    tipo_reg,
                    veiculo_reg,
                    str(valor_reg),
                    str(km_reg),
                    obs_reg
                ]
                aba_custos.append_row(linha_custo)
                st.success("✅ Registro logístico salvo com sucesso!")
                time.sleep(1)
                st.rerun()
            except Exception as e_custo:
                st.error(f"❌ Erro ao salvar custo logístico: {e_custo}")

    st.markdown("---")
    st.markdown("### 📊 Histórico de Custos Registrados")
    
    try:
        dados_custos = aba_custos.get_all_values()
        if len(dados_custos) > 1:
            df_custos = pd.DataFrame(dados_custos[1:], columns=dados_custos[0])
            df_custos["Valor_R$"] = pd.to_numeric(df_custos["Valor_R$"], errors="coerce").fillna(0.0)
            
            total_gasto_frota = df_custos["Valor_R$"].sum()
            st.metric(label="💰 Gasto Total Acumulado com Frota", value=f"R$ {total_gasto_frota:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            st.dataframe(df_custos, use_container_width=True)
        else:
            st.info("Nenhum registro de custo logístico cadastrado até o momento.")
    except Exception as e_ler_custos:
        st.warning(f"Não foi possível carregar os custos logísticos: {e_ler_custos}")