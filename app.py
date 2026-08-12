import streamlit as st
import pandas as pd
from datetime import datetime, date

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Gestão de Anticoagulação - RNI",
    page_icon="🩺",
    layout="wide"
)

# --- INICIALIZAÇÃO DO BANCO DE DADOS EM MEMÓRIA (MOCK) ---
if "pacientes" not in st.session_state:
    st.session_state.pacientes = pd.DataFrame(columns=["Prontuário", "Nome", "Indicação", "RNI_Alvo_Min", "RNI_Alvo_Max"])

if "registros_rni" not in st.session_state:
    st.session_state.registros_rni = pd.DataFrame(columns=[
        "Data", "Prontuário", "RNI", "Dose_Semanal_mg", "Status", "Conduta", "Eventos_Adversos"
    ])

# --- FUNÇÃO DE LÓGICA DE DECISÃO CLÍNICA ---
def avaliar_rni(rni, min_alvo, max_alvo):
    if rni < min_alvo:
        return "INFRATERAPÊUTICO", "warning", "⚠️ RNI abaixo do alvo. Avaliar adesão, interações medicamentosas ou necessidade de aumento de dose."
    elif rni > max_alvo:
        if rni >= 4.5:
            return "CRÍTICO / SUPRATERAPÊUTICO", "error", "🚨 RNI criticamente alto! Risco de sangramento. Avaliar suspensão de dose/Vitamina K conforme protocolo local."
        return "SUPRATERAPÊUTICO", "error", "🛑 RNI acima do alvo. Avaliar redução de dose e reavaliação em curto período."
    else:
        return "DENTRO DO ALVO", "success", "✅ RNI na faixa terapêutica. Manter posologia e agendar retorno de rotina."

# --- INTERFACE PRINCIPAL ---
st.title("🩺 Sistema de Acompanhamento de Anticoagulação (Varfarina)")
st.caption("Protótipo Ambulatorial de Manejo de RNI para Farmácia Clínica")

# Menu Lateral (Navegação)
aba = st.sidebar.radio("Navegação", ["1. Cadastrar Paciente", "2. Registrar Consulta / RNI", "3. Painel do Paciente & TTR"])

# ----------------------------------------------------
# ABA 1: CADASTRO DE PACIENTE
# ----------------------------------------------------
if aba == "1. Cadastrar Paciente":
    st.header("👤 Cadastro de Paciente")
    
    with st.form("form_cadastro"):
        col1, col2 = st.columns(2)
        with col1:
            prontuario = st.text_input("Prontuário / ID Anônimo*", help="Ex: PAC-001 (Preserve a privacidade do paciente)")
            nome = st.text_input("Iniciais ou Nome Completo*")
        with col2:
            indicacao = st.selectbox("Indicação da Anticoagulação", [
                "Fibrilação Atrial", "Prótese Valvar Mecânica", "Trombose Venosa Profunda (TVP)",
                "Embolia Pulmonar (EP)", "Outra"
            ])
            faixa_alvo = st.selectbox("Faixa Alvo de RNI", ["2.0 - 3.0", "2.5 - 3.5"])
        
        btn_cadastrar = st.form_submit_button("Salvar Paciente")
        
        if btn_cadastrar:
            if not prontuario or not nome:
                st.error("Preencha os campos obrigatórios (Prontuário e Nome).")
            elif prontuario in st.session_state.pacientes["Prontuário"].values:
                st.warning("Já existe um paciente cadastrado com este Prontuário.")
            else:
                rni_min, rni_max = map(float, faixa_alvo.split(" - "))
                novo_paciente = pd.DataFrame([{
                    "Prontuário": prontuario,
                    "Nome": nome,
                    "Indicação": indicacao,
                    "RNI_Alvo_Min": rni_min,
                    "RNI_Alvo_Max": rni_max
                }])
                st.session_state.pacientes = pd.concat([st.session_state.pacientes, novo_paciente], ignore_index=True)
                st.success(f"Paciente {nome} cadastrado com sucesso!")

    st.subheader("Pacientes Cadastrados")
    st.dataframe(st.session_state.pacientes, use_container_width=True)

# ----------------------------------------------------
# ABA 2: REGISTRO DE CONSULTA / RNI
# ----------------------------------------------------
elif aba == "2. Registrar Consulta / RNI":
    st.header("📋 Registro de Exame e Conduta")
    
    if st.session_state.pacientes.empty:
        st.info("Nenhum paciente cadastrado. Vá até a aba 'Cadastrar Paciente' primeiro.")
    else:
        # Seleção do paciente
        lista_pacientes = st.session_state.pacientes["Prontuário"] + " - " + st.session_state.pacientes["Nome"]
        paciente_sel = st.selectbox("Selecione o Paciente", lista_pacientes)
        id_prontuario = paciente_sel.split(" - ")[0]
        
        # Dados do paciente selecionado
        dados_pac = st.session_state.pacientes[st.session_state.pacientes["Prontuário"] == id_prontuario].iloc[0]
        st.info(f"**Indicação:** {dados_pac['Indicação']} | **Faixa Alvo:** {dados_pac['RNI_Alvo_Min']} a {dados_pac['RNI_Alvo_Max']}")
        
        with st.form("form_rni"):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_exame = st.date_input("Data da Coleta/Consulta", value=date.today())
                rni_valor = st.number_input("Valor do RNI*", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
            with col2:
                dose_semanal = st.number_input("Dose Semanal Atual (mg)", min_value=0.0, step=2.5, value=35.0)
                eventos = st.multiselect("Sintomas / Eventos Recentes", [
                    "Sem queixas", "Sangramento menor (gengivorragia/equimose)", 
                    "Sangramento maior", "Sinais de Trombose/AIT", "Baixa Adesão/Dose Esquecida"
                ])
            with col3:
                conduta = st.text_area("Conduta Farmacoterapêutica / Anotações", placeholder="Ex: Mantida dose. Reforçada orientação sobre dieta e interações.")
            
            btn_registrar = st.form_submit_button("Avaliar e Registrar")
        
        if btn_registrar:
            status, tipo_alerta, mensagem_alerta = avaliar_rni(rni_valor, dados_pac["RNI_Alvo_Min"], dados_pac["RNI_Alvo_Max"])
            
            # Exibe o alerta visual
            if tipo_alerta == "success":
                st.success(f"**Status:** {status}\n\n{mensagem_alerta}")
            elif tipo_alerta == "warning":
                st.warning(f"**Status:** {status}\n\n{mensagem_alerta}")
            else:
                st.error(f"**Status:** {status}\n\n{mensagem_alerta}")
            
            # Salva o registro
            novo_registro = pd.DataFrame([{
                "Data": data_exame.strftime("%d/%m/%Y"),
                "Prontuário": id_prontuario,
                "RNI": rni_valor,
                "Dose_Semanal_mg": dose_semanal,
                "Status": status,
                "Conduta": conduta,
                "Eventos_Adversos": ", ".join(eventos) if eventos else "Nenhum"
            }])
            st.session_state.registros_rni = pd.concat([st.session_state.registros_rni, novo_registro], ignore_index=True)

# ----------------------------------------------------
# ABA 3: PAINEL DO PACIENTE & TTR
# ----------------------------------------------------
elif aba == "3. Painel do Paciente & TTR":
    st.header("📊 Histórico e Indicadores Clínicos")
    
    if st.session_state.registros_rni.empty:
        st.info("Nenhum registro de RNI realizado até o momento.")
    else:
        lista_pacientes = st.session_state.pacientes["Prontuário"] + " - " + st.session_state.pacientes["Nome"]
        paciente_sel = st.selectbox("Filtrar Paciente", lista_pacientes)
        id_prontuario = paciente_sel.split(" - ")[0]
        
        dados_pac = st.session_state.pacientes[st.session_state.pacientes["Prontuário"] == id_prontuario].iloc[0]
        historico = st.session_state.registros_rni[st.session_state.registros_rni["Prontuário"] == id_prontuario]
        
        if historico.empty:
            st.warning("Este paciente ainda não possui histórico de exames.")
        else:
            # --- CÁLCULO DE MÉTRICAS (TTR SIMPLIFICADO) ---
            total_exames = len(historico)
            no_alvo = len(historico[historico["Status"] == "DENTRO DO ALVO"])
            ttr_percentual = (no_alvo / total_exames) * 100
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total de Exames", total_exames)
            col_m2.metric("Exames na Faixa Alvo", no_alvo)
            col_m3.metric("% de Exames no Alvo (TTR Direto)", f"{ttr_percentual:.1f}%")
            
            st.markdown("---")
            
            # --- GRÁFICO DE EVOLUÇÃO DO RNI ---
            st.subheader("Evolução Temporal do RNI")
            df_grafico = historico.copy()
            df_grafico["Limite_Inferior"] = dados_pac["RNI_Alvo_Min"]
            df_grafico["Limite_Superior"] = dados_pac["RNI_Alvo_Max"]
            
            st.line_chart(
                df_grafico.set_index("Data")[["RNI", "Limite_Inferior", "Limite_Superior"]],
                color=["#FF4B4B", "#00CC66", "#00CC66"]
            )
            
            # --- TABELA DE HISTÓRICO ---
            st.subheader("Histórico Detalhado")
            st.dataframe(historico.drop(columns=["Prontuário"]), use_container_width=True)
