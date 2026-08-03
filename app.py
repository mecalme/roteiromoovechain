import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
import plotly.express as px
from datetime import date

LISTA_STATUS = ["Pendente", "Auditado", "Cancelado", "Justificado"]
CATEGORIAS_MANUTENCAO = ["Troca de Óleo / Azeite", "Motor", "Pneus", "Relação / Transmissão", "Freios", "Elétrica", "Outros"]
TIPOS_VEICULO = ["Carro", "Moto"]

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
    sheet = spreadsheet.get_worksheet(0) # Aba principal de endereços
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
        df["Status"].astype(str).replace(["", "nan", "None"], "Pendente")
    )

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


# --- FUNÇÕES AUXILIARES DE FROTA E CUSTOS ---
def obter_ou_criar_aba(nome_aba, cabecalho_padrao):
    try:
        aba = spreadsheet.worksheet(nome_aba)
    except gspread.exceptions.WorksheetNotFound:
        aba = spreadsheet.add_worksheet(title=nome_aba, rows=100, cols=20)
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

    st.markdown("### 1. 🎯 Progresso Global de Auditorias")

    st.progress(pct_conclusao / 100)
    st.caption(f"🎯 Conclusão Global: **{pct_conclusao:.1f}%** do total auditado")

    st.markdown("<br>", unsafe_allow_html=True)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

    with col_kpi1:
        st.metric(
            label="📍 Total Geral de Pontos",
            value=f"{total_geral:,}".replace(",", ".")
        )

    with col_kpi2:
        st.metric(
            label="✅ Visitas Concluídas",
            value=f"{concluidos:,}".replace(",", "."),
            delta=f"{pct_conclusao:.1f}% do Total",
            delta_color="normal"
        )

    with col_kpi3:
        pct_restante = (restantes / total_geral * 100) if total_geral > 0 else 0.0
        st.metric(
            label="⏳ Restantes / Pendentes",
            value=f"{restantes:,}".replace(",", "."),
            delta=f"-{pct_restante:.1f}% Restantes",
            delta_color="inverse"
        )

    with col_kpi4:
        st.metric(
            label="🎯 Progresso Global",
            value=f"{pct_conclusao:.1f}%"
        )

    st.markdown("---")

    st.markdown("### 2. 📊 Progresso por Bairro")

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
        
        fig_stacked.update_layout(
            xaxis_tickangle=-45,
            legend_title_text="Situação",
            height=450,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        st.plotly_chart(fig_stacked, use_container_width=True)
    else:
        st.info("Nenhum dado disponível para exibir no gráfico.")

    st.markdown("---")

    # --- 3. MAPA DE CALOR POR BAIRRO (DENSIDADE) ---
    st.markdown("### 3. 🔥 Mapa de Calor (Densidade de Pontos por Bairro)")
    
    df_calor = df.groupby("Bairro").size().reset_index(name="Total_Pontos")
    df_calor = df_calor.sort_values(by="Total_Pontos", ascending=False)

    if not df_calor.empty:
        fig_heatmap = px.bar(
            df_calor,
            x="Bairro",
            y="Total_Pontos",
            color="Total_Pontos",
            color_continuous_scale="Reds",
            title="Concentração de Pontos de Auditoria por Bairro",
            labels={"Bairro": "Bairro", "Total_Pontos": "Volume de Pontos"},
            text="Total_Pontos"
        )
        fig_heatmap.update_layout(
            xaxis_tickangle=-45,
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("Sem dados suficientes para o mapa de calor.")


# --- ABA 2: MAPA GOOGLE MY MAPS + LEGENDA VISÍVEL NO TOPO ---
elif opcao == "🗺️ Visualizar Mapa de Pontos":
    st.subheader("🗺️ Mapa Google My Maps de Pontos")
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

    MAP_EMBED_URL = "https://www.google.com/maps/d/embed?mid=1-eBhSz898WjsoX9JXQbYOb0t-3S3DHs&ehbc=2E312F"

    st.components.v1.iframe(
        src=MAP_EMBED_URL,
        width=1300,
        height=600,
        scrolling=True
    )


# --- ABA 3: TABELA DE DADOS E AÇÕES (RESTRITO) ---
elif opcao == "📋 Tabela de Dados e Ações" and st.session_state["autenticado"]:
    st.subheader("📋 Tabela de Destinatários e Rotas")

    col_bairro, col_dest, col_status = st.columns([1, 1.2, 0.8])
    
    with col_bairro:
        todos_bairros = sorted(
            [str(b) for b in df["Bairro"].unique() if str(b).strip() != ""]
        )
        bairros_sel = st.multiselect(
            "Filtrar por Bairro(s):",
            options=todos_bairros,
            default=[],
            placeholder="Selecione bairro(s)..."
        )

    df_filtrado = df.copy()

    if bairros_sel:
        df_filtrado = df_filtrado[df_filtrado["Bairro"].astype(str).isin(bairros_sel)]

    with col_dest:
        todos_destinatarios = sorted(
            [str(d) for d in df_filtrado["Destinatário"].unique() if str(d).strip() != ""]
        )
        destinatarios_sel = st.multiselect(
            "Filtrar por Destinatário(s):",
            options=todos_destinatarios,
            default=[],
            placeholder="Pesquise/selecione destinatário(s)..."
        )

    with col_status:
        status_sel = st.selectbox("Filtrar por Status:", ["Todos"] + LISTA_STATUS)

    if destinatarios_sel:
        df_filtrado = df_filtrado[df_filtrado["Destinatário"].astype(str).isin(destinatarios_sel)]

    if status_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Status"].astype(str) == status_sel]

    df_filtrado["🚗 Navegar"] = df_filtrado.apply(
        lambda r: f"https://www.google.com/maps/dir/?api=1&destination={r['Latitude']},{r['Longitude']}"
        if pd.notnull(r['Latitude']) and str(r['Latitude']).strip() != "" else "",
        axis=1
    )

    st.write(f"Exibindo **{len(df_filtrado)}** de **{len(df)}** registros.")

    df_exibicao = df_filtrado.drop(columns=["_linha_sheets", "Identificador_Unico"], errors="ignore")

    event = st.dataframe(
        df_exibicao,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabela_destinatarios"
    )

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
    else:
        with col_info:
            st.info("👆 Marque a caixinha de seleção na primeira coluna de uma linha para editar.")


# --- ABA 4: EDITAR REGISTRO EXISTENTE (RESTRITO) ---
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

    dest_sel = st.selectbox(
        "Selecione o Destinatário para editar:",
        options=lista_identificadores,
        index=idx_default,
        key="select_destino_form_edit"
    )

    if dest_sel:
        st.session_state["destinatario_para_editar"] = dest_sel
        dados = df[df["Identificador_Unico"] == dest_sel].iloc[0]
        linha_real = int(dados["_linha_sheets"])

        st.info(f"📍 Editando Registro da **Linha {linha_real}** no Google Sheets: **{dados['Destinatário']}**")

        with st.form("f_edit"):
            n_dest = st.text_input("Destinatário", value=str(dados["Destinatário"]))
            n_rua = st.text_input("Rua", value=str(dados.get("Rua", "")))
            n_num = st.text_input("Número", value=str(dados.get("Numero", "")))
            n_bairro = st.text_input("Bairro", value=str(dados.get("Bairro", "")))
            n_cid = st.text_input("Cidade", value=str(dados.get("Cidade", "Florianópolis")))
            n_est = st.text_input("Estado", value=str(dados.get("Estado", "SC")))
            n_cep = st.text_input("CEP", value=str(dados.get("CEP", "")))
            
            st_atual = str(dados["Status"]).strip()
            idx_st = LISTA_STATUS.index(st_atual) if st_atual in LISTA_STATUS else 0
            n_st = st.selectbox("Status", LISTA_STATUS, index=idx_st)
            
            n_lat = st.text_input("Latitude", value=str(dados.get("Latitude", "")))
            n_lng = st.text_input("Longitude", value=str(dados.get("Longitude", "")))

            if st.form_submit_button("💾 Salvar Alterações na Planilha", type="primary"):
                try:
                    n_end_comp = f"{n_rua}, {n_num} - {n_bairro}, {n_cid} - {n_est}, CEP {n_cep}, Brasil"

                    if not n_lat or not n_lng:
                        n_lat, n_lng = geolocalizar_endereco(n_end_comp)

                    novos_valores = [
                        n_dest,
                        n_rua,
                        n_num,
                        n_bairro,
                        n_cid,
                        n_est,
                        n_cep,
                        n_end_comp,
                        n_st,
                        n_lat,
                        n_lng
                    ]
                    
                    intervalo = f"A{linha_real}:K{linha_real}"
                    sheet.update(range_name=intervalo, values=[novos_valores])
                    
                    st.cache_data.clear()
                    st.session_state["mensagem_sucesso_edicao"] = f"✅ Alteração salva com sucesso! O registro de **{n_dest}** (Linha {linha_real}) foi atualizado no Google Sheets."
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Erro ao salvar na planilha: {err}")


# --- ABA 5: ADICIONAR NOVO REGISTRO (RESTRITO) ---
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

                    sheet.append_row(
                        [
                            dest,
                            rua,
                            num,
                            bairro,
                            cid,
                            est,
                            cep,
                            end_comp,
                            st_novo,
                            lat,
                            lng
                        ]
                    )
                    st.success("✅ Novo destinatário adicionado ao Google Sheets!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Erro ao cadastrar na planilha: {err}")


# --- ABA 6: CUSTOS LOGÍSTICOS E FROTA (RESTRITO) ---
elif opcao == "🚚 Custos Logísticos (Frota)" and st.session_state["autenticado"]:
    st.subheader("🚚 Gestão e Controle de Custos Logísticos da Frota")
    st.markdown("---")

    # Conectar ou criar abas específicas para custos
    aba_veiculos = obter_ou_criar_aba("Frota_Veiculos", ["ID_Veiculo", "Tipo", "Marca_Modelo", "Ano", "Odometro_Atual"])
    aba_abastecer = obter_ou_criar_aba("Frota_Abastecimentos", ["Data", "Veiculo", "Odometro_Km", "Litros", "Custo_Total", "Km_Litro"])
    aba_manutencao = obter_ou_criar_aba("Frota_Manutencao", ["Data", "Veiculo", "Categoria", "Odometro_Km", "Custo", "Descricao"])

    # Carregar dados atuais de frota
    val_veiculos = aba_veiculos.get_all_values()
    df_veiculos = pd.DataFrame(val_veiculos[1:], columns=val_veiculos[0]) if len(val_veiculos) > 1 else pd.DataFrame(columns=["ID_Veiculo", "Tipo", "Marca_Modelo", "Ano", "Odometro_Atual"])

    val_abast = aba_abastecer.get_all_values()
    df_abast = pd.DataFrame(val_abast[1:], columns=val_abast[0]) if len(val_abast) > 1 else pd.DataFrame(columns=["Data", "Veiculo", "Odometro_Km", "Litros", "Custo_Total", "Km_Litro"])

    val_manu = aba_manutencao.get_all_values()
    df_manu = pd.DataFrame(val_manu[1:], columns=val_manu[0]) if len(val_manu) > 1 else pd.DataFrame(columns=["Data", "Veiculo", "Categoria", "Odometro_Km", "Custo", "Descricao"])

    tab_frota, tab_abast, tab_manu, tab_relatorio = st.tabs([
        "🚗 1. Cadastrar Veículos", 
        "⛽ 2. Registrar Abastecimento", 
        "🔧 3. Registrar Manutenção", 
        "📊 4. Relatório e Indicadores"
    ])

    # --- ABA 6.1: CADASTRAR VEÍCULOS ---
    with tab_frota:
        st.markdown("### Cadastrar Nova Unidade (Carro ou Moto)")
        with st.form("form_cad_veiculo"):
            f_tipo = st.selectbox("Tipo de Veículo", TIPOS_VEICULO)
            f_modelo = st.text_input("Marca e Modelo (Ex: Honda CG 160 / Fiat Strada)")
            f_ano = st.text_input("Ano (Ex: 2023)")
            f_odometro = st.number_input("Odômetro Inicial / Atual (Km)", min_value=0, step=100)

            if st.form_submit_button("Cadastrar Veículo", type="primary"):
                if f_modelo:
                    id_v = f"{f_tipo} - {f_modelo} ({f_ano})"
                    try:
                        aba_veiculos.append_row([id_v, f_tipo, f_modelo, str(f_ano), str(f_odometro)])
                        st.success(f"✅ Veículo **{id_v}** cadastrado com sucesso!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao salvar veículo: {err}")
                else:
                    st.warning("Preencha o modelo do veículo.")

        st.markdown("---")
        st.markdown("### Frota Atualmente Cadastrada")
        if not df_veiculos.empty:
            st.dataframe(df_veiculos, use_container_width=True)
        else:
            st.info("Nenhum veículo cadastrado até o momento.")

    # --- ABA 6.2: REGISTRAR ABASTECIMENTO ---
    with tab_abast:
        st.markdown("### Registro de Consumo de Combustível")
        
        if df_veiculos.empty:
            st.warning("⚠️ Cadastre pelo menos um veículo na aba anterior antes de registrar abastecimentos.")
        else:
            lista_ids_veiculos = df_veiculos["ID_Veiculo"].tolist()
            with st.form("form_abastecimento"):
                a_veiculo = st.selectbox("Selecione o Veículo", lista_ids_veiculos)
                a_data = st.date_input("Data do Abastecimento", value=date.today())
                a_odometro = st.number_input("Odômetro Atual no Painel (Km)", min_value=0, step=10)
                a_litros = st.number_input("Quantidade de Litros", min_value=0.1, format="%.2f")
                a_custo = st.number_input("Custo Total (R$)", min_value=0.01, format="%.2f")

                if st.form_submit_button("Salvar Abastecimento", type="primary"):
                    try:
                        # Buscar último odômetro registrado para calcular Km/Litro
                        df_v_abast = df_abast[df_abast["Veiculo"] == a_veiculo]
                        km_litro = 0.0
                        if not df_v_abast.empty:
                            ultimo_odometro = float(df_v_abast.iloc[-1]["Odometro_Km"])
                            delta_km = a_odometro - ultimo_odometro
                            if delta_km > 0 and a_litros > 0:
                                km_litro = round(delta_km / a_litros, 2)

                        aba_abastecer.append_row([
                            str(a_data),
                            a_veiculo,
                            str(a_odometro),
                            str(a_litros),
                            str(a_custo),
                            str(km_litro)
                        ])
                        
                        # Atualizar odômetro atual na tabela de veículos
                        cell = aba_veiculos.find(a_veiculo)
                        if cell:
                            aba_veiculos.update_cell(cell.row, 5, str(a_odometro))

                        st.success(f"✅ Abastecimento registrado! Consumo calculado: **{km_litro} km/l**")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao registrar abastecimento: {err}")

        st.markdown("---")
        st.markdown("### Histórico de Abastecimentos")
        if not df_abast.empty:
            st.dataframe(df_abast, use_container_width=True)
        else:
            st.info("Nenhum abastecimento registrado.")

    # --- ABA 6.3: REGISTRAR MANUTENÇÃO ---
    with tab_manu:
        st.markdown("### Registro de Gastos com Manutenção (Peças e Serviços)")

        if df_veiculos.empty:
            st.warning("⚠️ Cadastre pelo menos um veículo na primeira aba antes de registrar manutenções.")
        else:
            lista_ids_veiculos = df_veiculos["ID_Veiculo"].tolist()
            with st.form("form_manutencao"):
                m_veiculo = st.selectbox("Selecione o Veículo", lista_ids_veiculos, key="m_veiculo_sel")
                m_data = st.date_input("Data da Manutenção", value=date.today())
                m_categoria = st.selectbox("Categoria do Gasto", CATEGORIAS_MANUTENCAO)
                m_odometro = st.number_input("Odômetro no Momento do Serviço (Km)", min_value=0, step=10, key="m_odo")
                m_custo = st.number_input("Custo Total (R$)", min_value=0.01, format="%.2f", key="m_custo_val")
                m_desc = st.text_area("Descrição detalhada (Ex: Troca de óleo 10W40 e filtro)")

                if st.form_submit_button("Salvar Manutenção", type="primary"):
                    try:
                        aba_manutencao.append_row([
                            str(m_data),
                            m_veiculo,
                            m_categoria,
                            str(m_odometro),
                            str(m_custo),
                            m_desc
                        ])
                        st.success("✅ Registro de manutenção salvo com sucesso!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao registrar manutenção: {err}")

        st.markdown("---")
        st.markdown("### Histórico de Manutenções e Controle de Troca de Óleo")
        if not df_manu.empty:
            # Calcular km rodado desde a última manutenção por categoria / veículo
            st.dataframe(df_manu, use_container_width=True)
        else:
            st.info("Nenhum registro de manutenção encontrado.")

    # --- ABA 6.4: RELATÓRIO E INDICADORES ---
    with tab_relatorio:
        st.markdown("### 📊 Consolidado de Custos e Desempenho da Frota")

        if not df_abast.empty or not df_manu.empty:
            # Converter tipos numéricos para cálculos
            if not df_abast.empty:
                df_abast["Custo_Total"] = pd.to_numeric(df_abast["Custo_Total"], errors="coerce").fillna(0)
                df_abast["Litros"] = pd.to_numeric(df_abast["Litros"], errors="coerce").fillna(0)
                df_abast["Km_Litro"] = pd.to_numeric(df_abast["Km_Litro"], errors="coerce").fillna(0)

            if not df_manu.empty:
                df_manu["Custo"] = pd.to_numeric(df_manu["Custo"], errors="coerce").fillna(0)

            total_gasto_combustivel = df_abast["Custo_Total"].sum() if not df_abast.empty else 0.0
            total_gasto_manutencao = df_manu["Custo"].sum() if not df_manu.empty else 0.0
            custo_total_geral = total_gasto_combustivel + total_gasto_manutencao

            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("⛽ Gasto Total Combustível", f"R$ {total_gasto_combustivel:,.2f}")
            with col_r2:
                st.metric("🔧 Gasto Total Manutenção", f"R$ {total_gasto_manutencao:,.2f}")
            with col_r3:
                st.metric("💰 Custo Logístico Total", f"R$ {custo_total_geral:,.2f}")

            st.markdown("---")
            st.markdown("### 📈 Desempenho de Consumo Médio (Km/L) por Veículo")
            if not df_abast.empty:
                df_media_km = df_abast[df_abast["Km_Litro"] > 0].groupby("Veiculo")["Km_Litro"].mean().reset_index()
                if not df_media_km.empty:
                    fig_km = px.bar(
                        df_media_km,
                        x="Veiculo",
                        y="Km_Litro",
                        title="Média de Km por Litro (Eficiência de Consumo)",
                        labels={"Veiculo": "Veículo", "Km_Litro": "Média Km/L"},
                        color="Km_Litro",
                        color_continuous_scale="Greens",
                        text="Km_Litro"
                    )
                    st.plotly_chart(fig_km, use_container_width=True)
                else:
                    st.info("Adicione pelo menos dois abastecimentos sequenciais no mesmo veículo para calcular a média de km/l.")

            st.markdown("---")
            st.markdown("### 🛠️ Custos de Manutenção por Categoria")
            if not df_manu.empty:
                df_cat_manu = df_manu.groupby("Categoria")["Custo"].sum().reset_index()
                fig_cat = px.pie(
                    df_cat_manu,
                    names="Categoria",
                    values="Custo",
                    title="Distribuição de Gastos com Manutenção",
                    hole=0.4
                )
                st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("Registre alguns dados de abastecimento e manutenção para visualizar os indicadores financeiros.")