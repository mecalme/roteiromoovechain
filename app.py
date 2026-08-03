import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
import plotly.express as px

LISTA_STATUS = ["Pendente", "Auditado", "Cancelado", "Justificado"]

st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis",
    page_icon="📍",
    layout="wide",
)

st.title("📍 Roteiro MooveChain - Florianópolis")

# --- GERENCIAMENTO DE ESTADO ---
OPCOES_MENU = [
    "🗺️ Visualizar Mapa de Pontos",
    "📋 Tabela de Dados e Ações",
    "📊 Dashboard Auditorias MooveChain",
    "✏️ Editar Registro Existente",
    "➕ Adicionar Novo Registro",
]

if "menu_selecionado" not in st.session_state:
    st.session_state["menu_selecionado"] = OPCOES_MENU[0]

if "destinatario_para_editar" not in st.session_state:
    st.session_state["destinatario_para_editar"] = None

if "mensagem_sucesso_edicao" not in st.session_state:
    st.session_state["mensagem_sucesso_edicao"] = None


def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(
        "12sENMxX1FoQ6KYNgnlnXzD3abDqO4VH_jypcB-nQGks"
    ).sheet1
    return sheet


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
    sheet = conectar_sheets()
    todos_os_valores = sheet.get_all_values()

    if len(todos_os_valores) > 1:
        cabecalho = [str(c).strip() for c in todos_os_valores[0]]
        dados = todos_os_valores[1:]

        df = pd.DataFrame(dados, columns=cabecalho)
        df["_linha_sheets"] = range(2, len(dados) + 2)
    else:
        st.warning("A planilha parece estar vazia.")
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


# --- MENU LATERAL SINCRONIZADO ---
def mudar_aba():
    st.session_state["menu_selecionado"] = st.session_state["menu_radio_widget"]

opcao = st.sidebar.radio(
    "Selecione uma opção:",
    OPCOES_MENU,
    index=OPCOES_MENU.index(st.session_state["menu_selecionado"]),
    key="menu_radio_widget",
    on_change=mudar_aba
)


# --- ABA 1: MAPA GOOGLE MY MAPS ---
if st.session_state["menu_selecionado"] == "🗺️ Visualizar Mapa de Pontos":
    st.subheader("🗺️ Mapa Google My Maps")
    st.markdown("---")

    MAP_EMBED_URL = "https://www.google.com/maps/d/embed?mid=1-eBhSz898WjsoX9JXQbYOb0t-3S3DHs&ehbc=2E312F"

    st.components.v1.iframe(
        src=MAP_EMBED_URL,
        width=1300,
        height=650,
        scrolling=True
    )


# --- ABA 2: TABELA DE DADOS E AÇÕES ---
elif st.session_state["menu_selecionado"] == "📋 Tabela de Dados e Ações":
    st.subheader("📋 Tabela de Destinatários")

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

    st.write(f"Exibindo **{len(df_filtrado)}** de **{len(df)}** registros. *(Marque a caixinha da linha para selecionar para edição)*")

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
        with col_btn:
            if st.button("✏️ Ir para Tela de Edição", type="secondary", use_container_width=True):
                st.session_state["mensagem_sucesso_edicao"] = None
                st.session_state["menu_selecionado"] = "✏️ Editar Registro Existente"
                st.rerun()


# --- ABA 3: DASHBOARD AUDITORIAS MOOVECHAIN ---
elif st.session_state["menu_selecionado"] == "📊 Dashboard Auditorias MooveChain":
    st.subheader("📊 Dashboard Auditorias MooveChain")
    st.markdown("---")

    # Configuração dos status considerados como 'Concluídos'
    status_padrao = ["Auditado", "Cancelado", "Justificado"]
    status_medicao = st.multiselect(
        "⚙️ Status considerados como Concluídos:",
        options=LISTA_STATUS,
        default=status_padrao,
        help="Escolha quais status representam uma visita/medição finalizada."
    )

    # Cálculo dos KPIs Globais
    total_geral = len(df)
    df_concluidos = df[df["Status"].isin(status_medicao)]
    concluidos = len(df_concluidos)
    restantes = total_geral - concluidos
    pct_conclusao = (concluidos / total_geral * 100) if total_geral > 0 else 0.0

    st.markdown("### 1. 🎯 Avance Auditorias MooveChain")

    # Indicador de Barra de Progresso Destacado
    st.progress(pct_conclusao / 100)
    st.caption(f"🎯 Conclusão Global: **{pct_conclusao:.1f}%** do total auditado")

    st.markdown("<br>", unsafe_allow_html=True)

    # Cartões de Destaque KPI
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

    # 2. 📊 Gráfico de Barras Empilhadas (Stacked Bar Chart por Bairro)
    st.markdown("### 2. 📊 Progresso de auditorias")

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
            color_discrete_map={"Concluído": "#2ca02c", "Pendente": "#ff7f0e"},
            category_orders={"Bairro": ordem_bairros, "Situacao": ["Concluído", "Pendente"]},
            barmode="stack",
            text="Quantidade"
        )
        
        fig_stacked.update_layout(
            xaxis_tickangle=-45,
            legend_title_text="Situação",
            height=450
        )
        
        st.plotly_chart(fig_stacked, use_container_width=True)
    else:
        st.info("Nenhum dado disponível para exibir no gráfico.")

    st.markdown("---")

    # 3. 🗺️ Dashboard Geográfico / Mapa de Pins Focado em Florianópolis
    st.markdown("### 3. 🗺️ Mapa de calor")
    st.markdown("Visualização geográfica centralizada em Florianópolis para otimização de trajetos em campo.")

    df_mapa = df.copy()
    df_mapa["Latitude"] = pd.to_numeric(df_mapa["Latitude"], errors="coerce")
    df_mapa["Longitude"] = pd.to_numeric(df_mapa["Longitude"], errors="coerce")
    df_mapa = df_mapa.dropna(subset=["Latitude", "Longitude"])

    # Filtrar apenas pontos que estão na região aproximada de Florianópolis para evitar desvios para outros estados
    df_mapa = df_mapa[
        (df_mapa["Latitude"] >= -27.9) & (df_mapa["Latitude"] <= -27.3) &
        (df_mapa["Longitude"] >= -48.7) & (df_mapa["Longitude"] <= -48.3)
    ]

    if not df_mapa.empty:
        cores_status = {
            "Auditado": "#2ca02c",
            "Pendente": "#d62728",
            "Justificado": "#ff7f0e",
            "Cancelado": "#7f7f7f"
        }

        fig_mapa = px.scatter_mapbox(
            df_mapa,
            lat="Latitude",
            lon="Longitude",
            color="Status",
            hover_name="Destinatário",
            hover_data=["Rua", "Numero", "Bairro"],
            color_discrete_map=cores_status,
            zoom=11.5,
            center={"lat": -27.5954, "lon": -48.5480},
            height=600,
            title="Mapa de Pins - Florianópolis (Status de Auditoria)"
        )

        fig_mapa.update_traces(marker=dict(size=12))
        fig_mapa.update_layout(
            mapbox_style="open-street-map",
            margin={"r": 0, "t": 40, "l": 0, "b": 0}
        )

        st.plotly_chart(fig_mapa, use_container_width=True)
    else:
        st.warning("⚠️ Não foram encontrados pontos com coordenadas válidas dentro da região de Florianópolis. Verifique se as latitudes/longitudes na planilha estão corretas.")


# --- ABA 4: EDITAR REGISTRO EXISTENTE ---
elif st.session_state["menu_selecionado"] == "✏️ Editar Registro Existente":
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


# --- ABA 5: ADICIONAR NOVO REGISTRO ---
elif st.session_state["menu_selecionado"] == "➕ Adicionar Novo Registro":
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
