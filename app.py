from datetime import date, datetime
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

st.set_page_config(
    page_title="Roteiro MooveChain Florianópolis", page_icon="📍", layout="wide"
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
        background-color: #ffffff;
        border-right: 1px solid #d9e2ec;
    }
    .stButton>button {
        background-color: #0066cc;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #004999;
        color: white;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
  scope = [
      "https://spreadsheets.google.com/feeds",
      "https://www.googleapis.com/auth/drive",
  ]
  try:
    if "GOOGLE_CREDENTIALS_JSON" in st.secrets:
      import json

      creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
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
    return spreadsheet.get_worksheet(0)
  except Exception as e:
    st.error(f"Erro crítico ao conectar com o Google Sheets: {e}")
    return None


sheet = conectar_google_sheets()


# --- FUNÇÃO DE GEOCODIFICAÇÃO ---
@st.cache_data(ttl=86400)
def geolocalizar_endereco(endereco):
  try:
    geolocator = Nominatim(user_agent="moovechain_floripa_geo_2026", timeout=12)
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


# --- CARREGAR DADOS ---
@st.cache_data(ttl=60)
def carregar_dados():
  if sheet is None:
    return pd.DataFrame()
  try:
    dados = sheet.get_all_values()
    if len(dados) <= 1:
      return pd.DataFrame()
    cabecalho = [str(c).strip() for c in dados[0]]
    linhas = dados[1:]
    df = pd.DataFrame(linhas, columns=cabecalho[: len(linhas[0])])
    df["_linha_sheets"] = range(2, len(linhas) + 2)

    # Identificador único para cada linha
    if "Destinatário" in df.columns:
      df["Identificador_Unico"] = (
          df["Destinatário"].astype(str)
          + " - "
          + df.index.astype(str)
          + " ("
          + df.get("Bairro", "").astype(str)
          + ")"
      )
    else:
      df["Identificador_Unico"] = df.index.astype(str)

    return df
  except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    return pd.DataFrame()


df = carregar_dados()

# Inicialização de Variáveis de Sessão
if "autenticado" not in st.session_state:
  st.session_state["autenticado"] = True
if "menu_selecionado" not in st.session_state:
  st.session_state["menu_selecionado"] = (
      "🗺️ Mapa de Roteiro & Resumo"
      if not df.empty
      else "➕ Novo Registro"
  )
if "destinatario_para_editar" not in st.session_state:
  st.session_state["destinatario_para_editar"] = None
if "mensagem_sucesso_edicao" not in st.session_state:
  st.session_state["mensagem_sucesso_edicao"] = None


# --- BARRA LATERAL (MENU) ---
st.sidebar.title("📍 MooveChain Floripa")
st.sidebar.markdown("---")

opcoes_menu = [
    "🗺️ Mapa de Roteiro & Resumo",
    "📋 Tabela de Dados e Ações",
    "➕ Novo Registro",
    "✏️ Editar Registro Existente",
]

if st.session_state["menu_selecionado"] in opcoes_menu:
  indice_atual = opcoes_menu.index(st.session_state["menu_selecionado"])
else:
  indice_atual = 0

opcao = st.sidebar.radio(
    "Navegação", opcoes_menu, index=indice_atual, key="menu_radio_sel"
)
st.session_state["menu_selecionado"] = opcao

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Atualizar Cache de Dados"):
  st.cache_data.clear()
  st.rerun()


# =========================================================================
# ABA 1: MAPA DE ROTEIRO & RESUMO
# =========================================================================
if opcao == "🗺️ Mapa de Roteiro & Resumo" and st.session_state["autenticado"]:
  st.subheader("🗺️ Mapa Geral de Roteiro - Florianópolis")
  st.markdown("---")

  if df.empty:
    st.warning(
        "Nenhum registro encontrado na planilha. Cadastre novos dados na aba"
        " correspondente."
    )
  else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Registros", len(df))
    pendentes = (
        len(df[df["Status"].str.lower() == "pendente"])
        if "Status" in df.columns
        else 0
    )
    col2.metric("Pendentes", pendentes)
    auditados = (
        len(df[df["Status"].str.lower() == "auditado"])
        if "Status" in df.columns
        else 0
    )
    col3.metric("Auditados", auditados)
    bairros_unicos = (
        df["Bairro"].nunique() if "Bairro" in df.columns else 0
    )
    col4.metric("Bairros Atendidos", bairros_unicos)

    st.markdown("### Mapa de Localização")
    mapa_floripa = folium.Map(
        location=[-27.5954, -48.5480], zoom_start=11, tiles="OpenStreetMap"
    )

    pontos_mapeados = 0
    for _, row in df.iterrows():
      try:
        lat = float(row["Latitude"])
        lon = float(row["Longitude"])
        dest = row.get("Destinatário", "Local")
        bairro = row.get("Bairro", "")
        status = row.get("Status", "Pendente")

        cor_mapa = (
            "green"
            if status.lower() == "auditado"
            else "orange"
            if status.lower() == "pendente"
            else "blue"
        )

        folium.Marker(
            location=[lat, lon],
            popup=f"<b>{dest}</b><br>Bairro: {bairro}<br>Status: {status}",
            tooltip=dest,
            icon=folium.Icon(color=cor_mapa, icon="info-sign"),
        ).add_to(mapa_floripa)
        pontos_mapeados += 1
      except Exception:
        continue

    st_folium(mapa_floripa, width="100%", height=500)
    st.caption(f"Exibindo {pontos_mapeados} locais mapeados no mapa interativo.")


# =========================================================================
# ABA 2: TABELA DE DADOS E AÇÕES (COM FILTROS PERSISTENTES)
# =========================================================================
elif opcao == "📋 Tabela de Dados e Ações" and st.session_state["autenticado"]:
  st.subheader("📋 Tabela de Dados e Ações")
  st.markdown("---")

  if df.empty:
    st.warning("Nenhum dado cadastrado para exibir.")
  else:
    # Filtros com chaves persistentes no session_state
    col_bairro, col_dest, col_status = st.columns(3)

    with col_bairro:
      todos_bairros = sorted(
          [
              str(b)
              for b in df["Bairro"].unique()
              if str(b).strip() != "" and str(b) != "nan"
          ]
      )
      bairros_sel = st.multiselect(
          "Filtrar por Bairro(s):",
          options=todos_bairros,
          default=[],
          key="filtro_tabela_bairro",
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
          key="filtro_tabela_destinatario",
      )

    with col_status:
      status_sel = st.selectbox(
          "Filtrar por Status:",
          ["Todos"] + LISTA_STATUS,
          key="filtro_tabela_status",
      )

    if destinatarios_sel:
      df_filtrado = df_filtrado[
          df_filtrado["Destinatário"].astype(str).isin(destinatarios_sel)
      ]
    if status_sel != "Todos":
      df_filtrado = df_filtrado[df_filtrado["Status"].astype(str) == status_sel]

    st.write(f"Exibindo {len(df_filtrado)} de {len(df)} registros.")

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
      with col_info:
        st.info(
            f"📍 Selecionado: **{registro_selecionado['Destinatário']}** ("
            f"{registro_selecionado.get('Bairro', '')})"
        )
      with col_btn:
        if st.button("✏️ Editar este Registro", type="primary"):
          st.session_state["destinatario_para_editar"] = registro_selecionado[
              "Identificador_Unico"
          ]
          st.session_state["menu_selecionado"] = "✏️ Editar Registro Existente"
          st.rerun()


# =========================================================================
# ABA 3: NOVO REGISTRO
# =========================================================================
elif opcao == "➕ Novo Registro" and st.session_state["autenticado"]:
  st.subheader("➕ Adicionar Novo Registro na Planilha")
  st.markdown("---")

  with st.form("form_novo_registro"):
    c_data = st.date_input("Data do Registro", value=date.today())
    c_dest = st.text_input("Destinatário / Nome do Estabelecimento")
    c_rua = st.text_input("Rua")
    c_num = st.text_input("Número")
    c_bairro = st.text_input("Bairro")
    c_cid = st.text_input("Cidade", value="Florianópolis")
    c_est = st.text_input("Estado", value="SC")
    c_cep = st.text_input("CEP")
    c_status = st.selectbox("Status Inicial", LISTA_STATUS, index=0)

    if st.form_submit_button("🚀 Cadastrar e Geolocalizar", type="primary"):
      if not c_dest.strip() or not c_rua.strip():
        st.error(
            "Por favor, preencha pelo menos o Destinatário e a Rua do"
            " estabelecimento."
        )
      else:
        with st.spinner(
            "Geolocalizando endereço e salvando no Google Sheets..."
        ):
          endereco_completo = f"{c_rua}, {c_num} - {c_bairro}, {c_cid} - {c_est}, CEP {c_cep}, Brasil"
          lat, lon = geolocalizar_endereco(endereco_completo)

          nova_linha = [
              c_dest.strip(),
              c_rua.strip(),
              c_num.strip(),
              c_bairro.strip(),
              c_cid.strip(),
              c_est.strip(),
              c_cep.strip(),
              lat,
              lon,
              c_status,
              c_data.strftime("%Y-%m-%d"),
          ]

          try:
            sheet.append_row(nova_linha)
            st.cache_data.clear()
            st.success(
                f"✅ Estabelecimento **{c_dest}** cadastrado e geolocalizado com"
                f" sucesso! (Lat: {lat} | Lon: {lon})"
            )
          except Exception as e:
            st.error(f"Erro ao salvar no Google Sheets: {e}")


# =========================================================================
# ABA 4: EDITAR REGISTRO EXISTENTE (COM DATA PREDETERMINADA E VOLTAR PERSISTENTE)
# =========================================================================
elif opcao == "✏️ Editar Registro Existente" and st.session_state["autenticado"]:
  st.subheader("