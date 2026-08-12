import streamlit as st
import pandas as pd
import json
import os

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E DESIGN CUSTOMIZADO
# ==============================================================================
st.set_page_config(
    page_title="Ambulatório de Anticoagulação - RNI",
    page_icon="🩸",
    layout="wide"
)

# Estilização visual (CSS)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }
    
    .main-title {
        color: #1E3A8A;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0px;
    }
    
    .card-paciente {
        background-color: #F8FAFC;
        border-left: 5px solid #2563EB;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    
    .badge-target {
        background-color: #DBEAFE;
        color: #1E40AF;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CARREGAMENTO DO BANCO DE DADOS (JSON)
# ==============================================================================
@st.cache_data
def carregar_dados():
    if os.path.exists("dados.json"):
        with open("dados.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"patients": [], "agenda": {}}

dados = carregar_dados()
pacientes = dados.get("patients", [])

# ==============================================================================
# 3. CABEÇALHO DO APLICATIVO
# ==============================================================================
st.markdown('<h1 class="main-title">🩸 Sistema de Controle de Anticoagulação (Varfarina)</h1>', unsafe_allow_html=True)
st.caption("Painel de Acompanhamento Ambulatorial de Farmácia Clínica")
st.markdown("---")

# ==============================================================================
# 4. NAVEGAÇÃO E VISUALIZAÇÃO DOS PACIENTES
# ==============================================================================
st.sidebar.header("🔍 Filtros & Navegação")
opcoes_pacientes = [f"{p['name']} (ID: {p['id']})" for p in pacientes]

if not opcoes_pacientes:
    st.warning("Nenhum paciente encontrado no arquivo dados.json.")
else:
    paciente_selecionado_str = st.sidebar.selectbox("Selecione um Paciente:", opcoes_pacientes)
    idx_selecionado = opcoes_pacientes.index(paciente_selecionado_str)
    p = pacientes[idx_selecionado]

    # --- PAINEL PRINCIPAL DO PACIENTE ---
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"👤 {p['name']}")
        st.write(f"**Idade:** {p['age']} anos | **Contato:** {p.get('contact', 'Não informado')}")
        st.write(f"**Indicação Clínica:** {p['indication']}")
        st.markdown(f"**Faixa Alvo de RNI:** <span class='badge-target'>{p['target']}</span>", unsafe_allow_html=True)
        st.write(f"**Esquema Posológico Atual:** {p['doseCurrent']} mg/semana")

    with col2:
        st.metric(label="Último RNI Registrado", value=p['rniHistory'][0]['value'] if p['rniHistory'] else "N/A")
        st.write(f"**Complexidade do Paciente:** {p['level']}")
        st.write(f"**Usa Organizador de Comprimidos:** {p['organizer']}")

    st.markdown("---")

    # --- HISTÓRICO DE RNI E GRÁFICO ---
    tab1, tab2, tab3 = st.tabs(["📊 Evolução do RNI", "📝 Evolução Farmacêutica", "💊 Medicamentos em Uso"])

    with tab1:
        if p.get('rniHistory'):
            df_rni = pd.DataFrame(p['rniHistory'])
            df_rni['date'] = pd.to_datetime(df_rni['date'])
            df_rni = df_rni.sort_values('date')

            # Extrai os limites da faixa alvo
            try:
                min_alvo, max_alvo = map(float, p['target'].split('-'))
            except:
                min_alvo, max_alvo = 2.0, 3.0

            df_rni['Alvo Mínimo'] = min_alvo
            df_rni['Alvo Máximo'] = max_alvo

            st.markdown("### Gráfico de Tendência do RNI")
            st.line_chart(
                df_rni.set_index('date')[['value', 'Alvo Mínimo', 'Alvo Máximo']],
                color=["#2563EB", "#059669", "#059669"]
            )

            st.markdown("### Tabela de Exames")
            st.dataframe(df_rni[['date', 'value']].rename(columns={'date': 'Data da Coleta', 'value': 'RNI'}), use_container_width=True)
        else:
            st.info("Nenhum histórico de RNI registrado para este paciente.")

    with tab2:
        if p.get('evolution'):
            st.text_area("Registro da Última Consulta:", p['evolution'], height=300)
        else:
            st.info("Nenhuma evolução registrada recentemente.")

    with tab3:
        st.write("**Outros Medicamentos Relatados:**")
        st.info(p.get('meds', 'Nenhum outro medicamento registrado.'))
