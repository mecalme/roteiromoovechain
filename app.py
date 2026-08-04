import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão de Pontos - Florianópolis",
    page_icon="🗺️",
    layout="wide"
)

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown("""
    <style>
        .main {
            background-color: #f8fafc;
        }
        .stButton>button {
            border-radius: 8px;
            font-weight: bold;
        }
        .legenda-container {
            background-color: #ffffff;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 20px;
            border-left: 5px solid #1e3a8a;
        }
        .popup-status-box {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            margin-top: 25px;
            border: 1px solid #e2e8f0;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM O GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    try:
        escopos = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        credenciais_dict = dict(st.secrets["gcp_service_account"])
        credenciais = Credentials.from_service_account_info(credenciais_dict, scopes=escopos)
        cliente = gspread.authorize(credenciais)
        
        url_planilha = "https://docs.google.com/spreadsheets/d/1uYKUOVmKMn4CzTNH_9ex7ooTXCfGjTm5pEqZ1Tc8sKE/edit?usp=drive_link"
        planilha = cliente.open_by_url(url_planilha)
        sheet = planilha.get_worksheet(0)
        
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar com o Google Sheets: {e}")
        return None

sheet = conectar_google_sheets()

@st.cache_data(ttl=60)
def carregar_dados():
    if sheet is None:
        return pd.DataFrame(), []
    
    dados = sheet.get_all_records()
    cabecalho = sheet.row_values(1)
    df = pd.DataFrame(dados)
    
    df["_linha_sheets"] = range(2, len(df) + 2)
    
    if "Destinatário" in df.columns:
        df["Identificador_Unico"] = df["Destinatário"].astype(str) + " (Linha " + df["_linha_sheets"].astype(str) + ")"
    else:
        df["Identificador_Unico"] = "Linha " + df["_linha_sheets"].astype(str)
        
    return df, cabecalho

df, cabecalho = carregar_dados()

LISTA_STATUS = ["Auditado", "Pendente", "Cancelado", "Justificado"]

# --- MENU LATERAL (SIDEBAR) ---
st.sidebar.title("📍 Navegação")
opcao = st.sidebar.selectbox(
    "Escolha a Seção:",
    ["🗺️ Visualizar Mapa de Pontos", "📋 Tabela de Dados e Ações"]
)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Dica:** As alterações feitas no status salvam diretamente na sua planilha do Google Drive em tempo real.")

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado ou planilha vazia. Verifique a conexão com o Google Sheets.")
else:
    # --- ABA 1: MAPA INTERATIVO DINÂMICO (FOLIUM) ---
    if opcao == "🗺️ Visualizar Mapa de Pontos":
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

        mapa_floripa = folium.Map(location=[-27.5954, -48.5480], zoom_start=14, control_scale=True)

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

        coordenadas_fixas_centro = {
            "SPITFIRE PIZZARIA": (-27.5945, -48.5520),
            "BARRA COMPANY": (-27.5950, -48.5505),
            "ATELIE 389": (-27.5958, -48.5475),
            "N&M ENTRETENIMENTO": (-27.5952, -48.5492),
            "MADA BAR": (-27.5951, -48.5490),
            "HENSLINHAEMING": (-27.5948, -48.5500),
            "MM JANELA BAR": (-27.5947, -48.5510),
            "CASA TUM": (-27.5955, -48.5508),
            "BOTECO DA ILHA": (-27.5904, -48.5125),
            "RAYLTON CUNHA": (-27.5930, -48.5530),
            "TL BAR": (-27.5940, -48.5515),
            "BOROGODO": (-27.5962, -48.5460),
            "BARZIN": (-27.5942, -48.5518),
            "MES DA SILVA": (-27.5949, -48.5498),
            "RAFAEL DE JESUS": (-27.5925, -48.5540),
            "PIT FLORIPA": (-27.6012, -48.5190),
            "GREEN BAR": (-27.5890, -48.5140),
            "GAPO COMERCIO": (-27.5885, -48.5150),
            "BOTECO TIO GETHER": (-27.7520, -48.5080)
        }

        for _, row in df.iterrows():
            try:
                lat, lon = None, None
                
                destinatario = str(row.get("Destinatário", "")).strip()
                status = row.get("Status", "Pendente")
                bairro = row.get("Bairro", "Centro")
                rua = str(row.get("Rua", "")).strip()
                numero = str(row.get("Número", "")).strip()
                
                lat_raw = str(row.get("Latitude", "")).strip()
                lon_raw = str(row.get("Longitude", "")).strip()
                
                if lat_raw and lon_raw and lat_raw not in ["nan", "None", ""]:
                    try:
                        lat_f = float(lat_raw)
                        lon_f = float(lon_raw)
                        if -27.8 < lat_f < -27.3 and -48.7 < lon_f < -48.3:
                            lat, lon = lat_f, lon_f
                    except ValueError:
                        pass

                if lat is None or lon is None:
                    for chave, coord in coordenadas_fixas_centro.items():
                        if chave in destinatario.upper():
                            lat, lon = coord
                            break

                if lat is None or lon is None:
                    lat, lon = -27.5954, -48.5480

                popup_html = f"<b>Estabelecimento:</b> {destinatario}<br><b>Endereço:</b> {rua}, {numero} - {bairro}<br><b>Status:</b> {status}"
                
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=obter_cor_marcador(status), icon="info-sign")
                ).add_to(mapa_floripa)
            except Exception:
                continue

        st_folium(mapa_floripa, width=1300, height=600)

        # --- PAINEL FLUTUANTE ABAIXO DO MAPA PARA ALTERAR STATUS ---
        st.markdown("""
            <div class="popup-status-box">
                <h4 style="margin-top: 0; color: #1e3a8a !important;">🔄 Ação Rápida: Atualizar Status de um Ponto</h4>
                <p style="font-size: 14px; margin-bottom: 10px;">Selecione o ponto diretamente na lista abaixo para modificar o seu status na planilha em tempo real:</p>
            </div>
        """, unsafe_allow_html=True)

        with st.form("form_status_mapa"):
            col_map1, col_map2, col_map3 = st.columns([2, 1, 1])
            with col_map1:
                ponto_sel_mapa = st.selectbox("Escolha o Estabelecimento:", options=df["Identificador_Unico"].tolist())
            with col_map2:
                novo_status_mapa = st.selectbox("Novo Status:", options=LISTA_STATUS)
            with col_map3:
                st.markdown("<br>", unsafe_allow_html=True)
                btn_atualizar_mapa = st.form_submit_button("💾 Salvar Novo Status", type="primary", use_container_width=True)

            if btn_atualizar_mapa:
                try:
                    dados_ponto = df[df["Identificador_Unico"] == ponto_sel_mapa].iloc[0]
                    linha_alvo = int(dados_ponto["_linha_sheets"])
                    idx_status_col = cabecalho.index("Status") + 1 if "Status" in cabecalho else 9
                    
                    sheet.update_cell(linha_alvo, idx_status_col, novo_status_mapa)
                    
                    st.cache_data.clear()
                    st.success(f"✅ Status do estabelecimento **{dados_ponto['Destinatário']}** atualizado para **{novo_status_mapa}** com sucesso!")
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Erro ao atualizar status: {err}")

    # --- ABA 2: TABELA DE DADOS E AÇÕES ---
    elif opcao == "📋 Tabela de Dados e Ações":
        st.subheader("📋 Gestão e Visualização da Tabela")
        st.markdown("---")
        
        filtro_status = st.multiselect("Filtrar por Status:", options=LISTA_STATUS, default=LISTA_STATUS)
        
        df_filtrado = df[df["Status"].isin(filtro_status)] if "Status" in df.columns else df
        
        colunas_exibicao = [c for c in df_filtrado.columns if not c.startswith("_") and c != "Identificador_Unico"]
        st.dataframe(df_filtrado[colunas_exibicao], use_container_width=True, height=450)
        
        st.markdown("### ✏️ Atualização Individual de Status via Tabela")
        with st.form("form_tabela_status"):
            col_t1, col_t2, col_t3 = st.columns([2, 1, 1])
            with col_t1:
                ponto_sel_tabela = st.selectbox("Selecione o Destinatário:", options=df["Identificador_Unico"].tolist(), key="tab_sel")
            with col_t2:
                novo_status_tabela = st.selectbox("Novo Status:", options=LISTA_STATUS, key="tab_stat")
            with col_t3:
                st.markdown("<br>", unsafe_allow_html=True)
                btn_tabela = st.form_submit_button("💾 Atualizar Linha", type="primary", use_container_width=True)
                
            if btn_tabela:
                try:
                    dados_ponto = df[df["Identificador_Unico"] == ponto_sel_tabela].iloc[0]
                    linha_alvo = int(dados_ponto["_linha_sheets"])
                    idx_status_col = cabecalho.index("Status") + 1 if "Status" in cabecalho else 9
                    
                    sheet.update_cell(linha_alvo, idx_status_col, novo_status_tabela)
                    
                    st.cache_data.clear()
                    st.success(f"✅ Status atualizado com sucesso para **{novo_status_tabela}**!")
                    st.rerun()
                except Exception as err:
                    st.error(f"❌ Erro ao atualizar: {err}")