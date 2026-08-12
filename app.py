import streamlit as st
import pandas as pd
from datetime import datetime, date

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO CUSTOMIZADA (CSS & DESIGN)
# ==============================================================================
st.set_page_config(
    page_title="Gestão de Anticoagulação - RNI",
    page_icon="🩸",
    layout="wide"
)

# Injeção de CSS personalizado para fontes, cores, cards e caixas de informação
st.markdown("""
    <style>
    /* Importação de Fonte Google (Roboto / Poppins) */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }

    /* Estilização de Titulo Principal com Gradiente */
    .title-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }

    .sub-header {
        color: #64748B;
        font-size: 1.0rem;
        margin-bottom: 25px;
    }

    /* Cards Informativos Personalizados */
    .custom-card {
        background-color: #F8FAFC;
        border-radius: 12px;
        padding: 20px;
        border-left: 6px solid #3B82F6;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }

    /* Emblemas de Status (Badges Coloridas) */
    .badge-verde {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-amarela {
        background-color: #FEF08A;
        color: #713F12;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-vermelha {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }

    /* Estilização dos Botões */
    .stButton>button {
        background-color: #1E3A8A;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        padding: 10px 24px;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background-color: #2563EB;
        color: white;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. BANCO DE DADOS EM MEMÓRIA (SESSÃO)
# ==============================================================================
if "pacientes" not in st.session_state:
    st.session_state.pacientes = pd.DataFrame(columns=["Prontuário", "Nome", "Indicação", "RNI_Alvo_Min", "RNI_Alvo_Max"])

if "registros_rni" not in st.session_state:
    st.session_state.registros_rni = pd.DataFrame(columns=[
        "Data", "Prontuário", "RNI", "Dose_Semanal_mg", "Status", "Conduta", "Eventos_Adversos"
    ])

# ==============================================================================
# 3. LÓGICA DE AVALIAÇÃO COM CORES E BADGES CUSTOMIZADAS
# ==============================================================================
def avaliar_rni(rni, min_alvo, max_alvo):
    if rni < min_alvo:
        return "INFRATERAPÊUTICO", "badge-amarela", "⚠️ **RNI Abaixo do Alvo:** Avaliar adesão, interações medicamentosas ou ajuste de dose semanal."
    elif rni > max_alvo:
        if rni >= 4.5:
            return "CRÍTICO (RNI ≥ 4.5)", "badge-vermelha", "🚨 **RNI Criticamente Elevado:** Alto risco hemorrágico! Considerar pausa de dose e/ou Vitamina K conforme protocolo."
        return "SUPRATERAPÊUTICO", "badge-vermelha", "🛑 **RNI Acima do Alvo:** Avaliar redução da dose semanal e retorno precoce."
    else:
        return "DENTRO DO ALVO", "badge-verde", "✅ **RNI na Faixa Terapêutica:** Manter posologia atual e agendar retorno de rotina."

# ==============================================================================
# 4. INTERFACE E CABEÇALHO
# ==============================================================================
st.markdown('<h1 class="title-header">🩺 Ambulatório de Anticoagulação - Manejo de Varfarina</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Sistema de Suporte à Decisão Clínica e Registro de RNI para Farmácia Clínica</p>', unsafe_allow_html=True)

# Menu de Navegação na Barra Lateral
st.sidebar.image("https://img.icons8.com/color/96/medical-heart.png", width=70)
st.sidebar.title("Menu do Sistema")
aba = st.sidebar.radio("Selecione o Módulo:", ["1. Cadastrar Paciente", "2. Registrar Consulta / RNI", "3. Painel do Paciente & TTR"])

# ==============================================================================
# ABA 1: CADASTRO DE PACIENTE
# ==============================================================================
if aba == "1. Cadastrar Paciente":
    st.subheader("👤 Cadastro de Paciente")
    
    with st.container():
        st.markdown("""
        <div class="custom-card">
            <b>Dica Clínica:</b> Utilize identificadores anônimos (ex: PAC-001) para garantir a privacidade e conformidade com a LGPD.
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("form_cadastro"):
            col1, col2 = st.columns(2)
            with col1:
                prontuario = st.text_input("Prontuário / ID Anônimo*", placeholder="Ex: PAC-001")
                nome = st.text_input("Iniciais ou Nome do Paciente*", placeholder="Ex: A.B.C.")
            with col2:
                indicacao = st.selectbox("Indicação da Anticoagulação", [
                    "Fibrilação Atrial (FA)", "Prótese Valvar Mecânica", "Trombose Venosa Profunda (TVP)",
                    "Embolia Pulmonar (EP)", "Outra Indicação"
                ])
                faixa_alvo = st.selectbox("Faixa Alvo de RNI", ["2.0 - 3.0", "2.5 - 3.5"])
            
            btn_salvar = st.form_submit_button("💾 Salvar Paciente")
            
            if btn_salvar:
                if not prontuario or not nome:
                    st.error("Preencha todos os campos obrigatórios (*).")
                elif prontuario in st.session_state.pacientes["Prontuário"].values:
                    st.warning("Já existe um paciente cadastrado com este ID.")
                else:
                    rni_min, rni_max = map(float, faixa_alvo.split(" - "))
                    novo_p = pd.DataFrame([{
                        "Prontuário": prontuario,
                        "Nome": nome,
                        "Indicação": indicacao,
                        "RNI_Alvo_Min": rni_min,
                        "RNI_Alvo_Max": rni_max
                    }])
                    st.session_state.pacientes = pd.concat([st.session_state.pacientes, novo_p], ignore_index=True)
                    st.success(f"Paciente **{nome}** cadastrado com sucesso!")

    st.markdown("### Lista de Pacientes no Ambulatório")
    st.dataframe(st.session_state.pacientes, use_container_width=True)

# ==============================================================================
# ABA 2: REGISTRO DE CONSULTA / RNI
# ==============================================================================
elif aba == "2. Registrar Consulta / RNI":
    st.subheader("📋 Registro de Exame e Conduta")
    
    if st.session_state.pacientes.empty:
        st.info("Nenhum paciente cadastrado. Cadastre um paciente na aba '1. Cadastrar Paciente'.")
    else:
        lista_pacientes = st.session_state.pacientes["Prontuário"] + " - " + st.session_state.pacientes["Nome"]
        paciente_sel = st.selectbox("Selecione o Paciente:", lista_pacientes)
        id_prontuario = paciente_sel.split(" - ")[0]
        
        dados_p = st.session_state.pacientes[st.session_state.pacientes["Prontuário"] == id_prontuario].iloc[0]
        
        # Caixas de Resumo do Paciente Selecionado
        st.markdown(f"""
        <div class="custom-card">
            <b>Paciente:</b> {dados_p['Nome']} | <b>Indicação:</b> {dados_p['Indicação']} | <b>Faixa Alvo de RNI:</b> {dados_p['RNI_Alvo_Min']} a {dados_p['RNI_Alvo_Max']}
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("form_rni"):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_exame = st.date_input("Data da Consulta", value=date.today())
                rni_valor = st.number_input("RNI Atual*", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
            with col2:
                dose_semanal = st.number_input("Dose Semanal Total (mg)", min_value=0.0, step=2.5, value=35.0)
                eventos = st.multiselect("Eventos / Queixas", [
                    "Sem queixas", "Gengivorragia / Equimoses", "Epistaxe",
                    "Sangramento Maior", "Esquecimento de Dose"
                ])
            with col3:
                conduta = st.text_area("Conduta Farmacoterapêutica", placeholder="Ajuste de dosagem, orientação sobre alimentos ricos em Vitamina K, retorno em X dias...")
            
            btn_avaliar = st.form_submit_button("🔬 Avaliar RNI e Registrar")
            
        if btn_avaliar:
            status, classe_badge, orientacao = avaliar_rni(rni_valor, dados_p["RNI_Alvo_Min"], dados_p["RNI_Alvo_Max"])
            
            # Exibe Resultado Visual com a Badge Personalizada
            st.markdown(f"""
            <div style="margin-top: 15px; margin-bottom: 15px;">
                <b>Status Clinico:</b> <span class="{classe_badge}">{status}</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.info(orientacao)
            
            # Grava no histórico
            novo_r = pd.DataFrame([{
                "Data": data_exame.strftime("%d/%m/%Y"),
                "Prontuário": id_prontuario,
                "RNI": rni_valor,
                "Dose_Semanal_mg": dose_semanal,
                "Status": status,
                "Conduta": conduta,
                "Eventos_Adversos": ", ".join(eventos) if eventos else "Nenhum"
            }])
            st.session_state.registros_rni = pd.concat([st.session_state.registros_rni, novo_r], ignore_index=True)

# ==============================================================================
# ABA 3: PAINEL DO PACIENTE & TTR
# ==============================================================================
elif aba == "3. Painel do Paciente & TTR":
    st.subheader("📊 Indicadores Clínicos e Evolução")
    
    if st.session_state.registros_rni.empty:
        st.info("Nenhum exame cadastrado no sistema.")
    else:
        lista_pacientes = st.session_state.pacientes["Prontuário"] + " - " + st.session_state.pacientes["Nome"]
        paciente_sel = st.selectbox("Escolha o Paciente para Analisar:", lista_pacientes)
        id_prontuario = paciente_sel.split(" - ")[0]
        
        dados_p = st.session_state.pacientes[st.session_state.pacientes["Prontuário"] == id_prontuario].iloc[0]
        hist = st.session_state.registros_rni[st.session_state.registros_rni["Prontuário"] == id_prontuario]
        
        if hist.empty:
            st.warning("Este paciente ainda não possui histórico registrado.")
        else:
            # Métricas em Cards Visuais
            total = len(hist)
            no_alvo = len(hist[hist["Status"] == "DENTRO DO ALVO"])
            ttr = (no_alvo / total) * 100
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Consultas/Exames", total)
            c2.metric("Exames na Faixa Alvo", no_alvo)
            c3.metric("% no Alvo (TTR Direto)", f"{ttr:.1f}%")
            
            st.markdown("---")
            st.markdown("### Evolução do RNI no Tempo")
            
            df_g = hist.copy()
            df_g["Alvo Mínimo"] = dados_p["RNI_Alvo_Min"]
            df_g["Alvo Máximo"] = dados_p["RNI_Alvo_Max"]
            
            st.line_chart(
                df_g.set_index("Data")[["RNI", "Alvo Mínimo", "Alvo Máximo"]],
                color=["#2563EB", "#059669", "#059669"]
            )
            
            st.markdown("### Histórico Completo de Atendimentos")
            st.dataframe(hist.drop(columns=["Prontuário"]), use_container_width=True)
