import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO CSS
# ==============================================================================
st.set_page_config(
    page_title="Ambulatório de Anticoagulação - RNI",
    page_icon="🩸",
    layout="wide"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Estilização da Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    
    /* Cards Clínicos de Informações */
    .patient-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    
    .info-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .info-value {
        font-size: 1.05rem;
        font-weight: 600;
        color: #0F172A;
        margin-bottom: 8px;
    }
    
    /* Badges de Status de Risco */
    .badge-level {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .level-baixo { background-color: #DCFCE7; color: #166534; }
    .level-medio { background-color: #FEF3C7; color: #92400E; }
    .level-alto { background-color: #FEE2E2; color: #991B1B; }
    .level-alta { background-color: #E2E8F0; color: #475569; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES DE CÁLCULO DE TTR E PERSISTÊNCIA
# ==============================================================================
def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
    """Calcula o Time in Therapeutic Range (TTR) pelo Método de Rosendaal."""
    if not historico or len(historico) < 2:
        return 0.0
    
    try:
        df = pd.DataFrame(historico)
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = df['value'].astype(float)
        df = df.sort_values('date').reset_index(drop=True)
        
        dias_no_alvo = 0.0
        dias_totais = 0
        
        for i in range(len(df) - 1):
            d1, v1 = df.loc[i, 'date'], df.loc[i, 'value']
            d2, v2 = df.loc[i+1, 'date'], df.loc[i+1, 'value']
            
            dias_intervalo = (d2 - d1).days
            if dias_intervalo <= 0:
                continue
                
            passo_rni = (v2 - v1) / dias_intervalo
            
            for dia in range(dias_intervalo):
                rni_estimado = v1 + (passo_rni * dia)
                if min_alvo <= rni_estimado <= max_alvo:
                    dias_no_alvo += 1.0
                dias_totais += 1
                
        if dias_totais == 0:
            return 0.0
            
        return (dias_no_alvo / dias_totais) * 100.0
    except Exception:
        return 0.0

def calcular_ttr_direto(historico, min_alvo, max_alvo):
    """Calcula a proporção direta de exames dentro do alvo."""
    if not historico:
        return 0.0, 0, 0
    
    try:
        total_exames = len(historico)
        exames_na_faixa = sum(1 for e in historico if min_alvo <= float(e['value']) <= max_alvo)
        porcentagem = (exames_na_faixa / total_exames) * 100.0
        return porcentagem, exames_na_faixa, total_exames
    except Exception:
        return 0.0, 0, 0

def salvar_dados_json(dados):
    """Persiste as alterações no arquivo JSON."""
    with open("dados.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# ==============================================================================
# 3. CARREGAMENTO DE DADOS
# ==============================================================================
if "dados" not in st.session_state:
    if os.path.exists("dados.json"):
        with open("dados.json", "r", encoding="utf-8") as f:
            st.session_state.dados = json.load(f)
    else:
        st.session_state.dados = {"patients": [], "agenda": {}}

pacientes = st.session_state.dados.get("patients", [])
pacientes = sorted(pacientes, key=lambda x: (x.get('status') == 'Alta', x['name']))

# ==============================================================================
# 4. PAINEL ESQUERDO (SIDEBAR - LISTA DE PACIENTES E NOVO CADASTRO)
# ==============================================================================
st.sidebar.markdown("### 🩺 Ambulatório RNI")
st.sidebar.caption(f"Total: {len(pacientes)} pacientes cadastrados")

# Formulário Expansível para Adicionar Novo Paciente
with st.sidebar.expander("➕ Cadastrar Novo Paciente"):
    with st.form("form_add_paciente", clear_on_submit=True):
        novo_nome = st.text_input("Nome do Paciente:")
        nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=60)
        novo_contato = st.text_input("Contato/Telefone:")
        nova_indicacao = st.text_input("Indicação Clínica:", value="Fibrilação Atrial")
        nova_faixa = st.selectbox("Faixa Alvo RNI:", ["2.0-3.0", "2.5-3.5", "1.5-2.0"])
        nova_dose = st.number_input("Dose Semanal Inicial (mg):", value=35.0, step=2.5)
        
        btn_criar_paciente = st.form_submit_button("Cadastrar")
        
        if btn_criar_paciente and novo_nome:
            novo_paciente_obj = {
                "id": str(len(pacientes) + 1),
                "name": novo_nome,
                "age": nova_idade,
                "contact": novo_contato,
                "indication": nova_indicacao,
                "target": nova_faixa,
                "weeklyDose": nova_dose,
                "organizer": "Não",
                "level": "Médio",
                "status": "Ativo",
                "rniHistory": [],
                "evolution": ""
            }
            st.session_state.dados["patients"].append(novo_paciente_obj)
            salvar_dados_json(st.session_state.dados)
            st.success("Paciente cadastrado!")
            st.rerun()

st.sidebar.markdown("---")

if not pacientes:
    st.warning("Nenhum paciente cadastrado.")
    st.stop()

# Lista formatada com identificação visual dos pacientes em Alta (cinza)
opcoes_pacientes = []
for p in pacientes:
    label = f"⚪ {p['name']} (ALTA)" if p.get('status') == 'Alta' else f"🟢 {p['name']}"
    opcoes_pacientes.append(label)

paciente_sel_index = st.sidebar.radio(
    "Selecione o paciente:",
    range(len(opcoes_pacientes)),
    format_func=lambda i: opcoes_pacientes[i]
)

p = pacientes[paciente_sel_index]
em_alta = (p.get('status') == 'Alta')

# ==============================================================================
# 5. PAINEL PRINCIPAL (FICHA CLÍNICA DO PACIENTE)
# ==============================================================================
col_titulo, col_status = st.columns([4, 1])

with col_titulo:
    if em_alta:
        st.markdown(f"# <span style='color: #94A3B8;'>👤 {p['name']} (Alta Terapêutica)</span>", unsafe_allow_html=True)
    else:
        st.markdown(f"# 👤 {p['name']}")

with col_status:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Alternar Alta / Ativo", use_container_width=True):
        p['status'] = 'Ativo' if em_alta else 'Alta'
        salvar_dados_json(st.session_state.dados)
        st.rerun()

col_info1, col_info2, col_info3 = st.columns([2, 2, 2])

try:
    target_str = p.get('target', '2.0-3.0')
    min_alvo, max_alvo = map(float, target_str.split('-'))
except Exception:
    min_alvo, max_alvo = 2.0, 3.0

ttr_valor = calcular_ttr_rosendaal(p.get('rniHistory', []), min_alvo, max_alvo)
ttr_direto, exames_na_faixa, total_exames = calcular_ttr_direto(p.get('rniHistory', []), min_alvo, max_alvo)

if em_alta:
    cor_ttr = "#64748B"
    bg_badge = "#F1F5F9"
    status_ttr = "Alta TTR"
elif ttr_valor >= 70.0:
    cor_ttr = "#10B981"
    bg_badge = "#ECFDF5"
    status_ttr = "Estável"
elif ttr_valor >= 60.0:
    cor_ttr = "#F59E0B"
    bg_badge = "#FFFBEB"
    status_ttr = "Alerta"
else:
    cor_ttr = "#EF4444"
    bg_badge = "#FEF2F2"
    status_ttr = "Crítico"

level_class = "level-alta" if em_alta else ("level-baixo" if p.get('level') == "Baixo" else "level-alto" if p.get('level') == "Alto" else "level-medio")

with col_info1:
    st.markdown(f"""
    <div class="patient-card" style="{'background: #F8FAFC; border-color: #CBD5E1;' if em_alta else ''}">
        <div class="info-label">Dados Demográficos</div>
        <div class="info-value">Idade: {p.get('age', 'N/A')} anos</div>
        <div class="info-value">Contato: {p.get('contact', 'Não informado')}</div>
        <div class="info-label" style="margin-top: 10px;">Status / Complexidade</div>
        <div><span class="badge-level {level_class}">{ 'ALTA' if em_alta else p.get('level', 'Médio') }</span></div>
    </div>
    """, unsafe_allow_html=True)

with col_info2:
    st.markdown(f"""
    <div class="patient-card" style="{'background: #F8FAFC; border-color: #CBD5E1;' if em_alta else ''}">
        <div class="info-label">Manejo Terapêutico</div>
        <div class="info-value">Indicação: {p.get('indication', 'N/A')}</div>
        <div class="info-value">Dose Semanal: {p.get('weeklyDose', p.get('doseCurrent', 0))} mg</div>
        <div class="info-value">Organizador: {p.get('organizer', 'Não')}</div>
    </div>
    """, unsafe_allow_html=True)

with col_info3:
    card_html = f"""
    <div style="background: {'#F8FAFC' if em_alta else '#FFFFFF'}; border: 1px solid {'#CBD5E1' if em_alta else '#E2E8F0'}; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <span style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase;">
                TTR (Rosendaal)
            </span>
            <span style="font-size: 0.75rem; font-weight: 600; color: {cor_ttr}; background: {bg_badge}; padding: 2px 8px; border-radius: 9999px;">
                {status_ttr}
            </span>
        </div>
        <div style="font-size: 2.5rem; font-weight: 700; color: {cor_ttr}; line-height: 1; margin-bottom: 16px;">
            {ttr_valor:.1f}%
        </div>
        <div style="border-top: 1px solid #F1F5F9; margin-bottom: 12px;"></div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
            <div style="font-size: 0.8rem; color: #94A3B8; text-transform: uppercase; font-weight: 500;">
                Método Comparativo
            </div>
            <div style="font-size: 0.87rem; color: #334155;">
                TTR Direto: <b style="color: #0F172A;">{ttr_direto:.1f}%</b> 
                <span style="color: #64748B; font-size: 0.8rem; margin-left: 4px;">
                    ({exames_na_faixa}/{total_exames} exames)
                </span>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

st.markdown("---")

# ==============================================================================
# 6. GRÁFICO E REGISTRO DE RNI
# ==============================================================================
col_grafico, col_novo_rni = st.columns([2, 1])

with col_grafico:
    st.subheader("📈 Tendência do RNI")
    if p.get('rniHistory'):
        df_rni = pd.DataFrame(p['rniHistory'])
        df_rni['date'] = pd.to_datetime(df_rni['date'])
        df_rni['value'] = df_rni['value'].astype(float)
        df_rni = df_rni.sort_values('date')
        
        df_rni['Alvo Mínimo'] = min_alvo
        df_rni['Alvo Máximo'] = max_alvo
        
        st.line_chart(
            df_rni.set_index('date')[['value', 'Alvo Mínimo', 'Alvo Máximo']],
            color=["#2563EB", "#10B981", "#10B981"],
            height=300
        )
    else:
        st.info("Nenhum histórico de RNI para gerar o gráfico.")

with col_novo_rni:
    st.subheader("➕ Registrar Exame")
    with st.form("form_novo_rni", clear_on_submit=True):
        nova_data = st.date_input("Data da Coleta", value=datetime.today())
        novo_rni = st.number_input("Valor do RNI", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
        
        btn_adicionar = st.form_submit_button("Salvar Exame")
        
        if btn_adicionar:
            novo_registro = {"date": nova_data.strftime("%Y-%m-%d"), "value": float(novo_rni)}
            p['rniHistory'].insert(0, novo_registro)
            salvar_dados_json(st.session_state.dados)
            st.success("Exame salvo!")
            st.rerun()

st.markdown("---")

# ==============================================================================
# 7. ROTEIRO FARMACÊUTICO E EVOLUÇÃO SOAP (PADRÃO MV)
# ==============================================================================
tab_anamnese, tab_evolucao, tab_tabela, tab_meds = st.tabs([
    "🔍 Roteiro de Decisão & Consulta", 
    "📝 Evolução Farmacêutica (MV)", 
    "📋 Histórico de Coletas", 
    "💊 Medicamentos em Uso"
])

ultimo_rni = p['rniHistory'][0]['value'] if p.get('rniHistory') else "N/A"
data_ultimo_rni = p['rniHistory'][0]['date'] if p.get('rniHistory') else "N/A"

with tab_anamnese:
    st.markdown("### 📋 Questionário Norteador de Tomada de Decisão")
    st.caption("Preencha os pontos observados na consulta para gerar a Evolução SOAP.")
    
    with st.form("form_anamnese_soap"):
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**1. Segurança e Eventos Adversos**")
            sinais_sangramento = st.radio(
                "Sinais de sangramento recente:",
                ["Ausentes", "Leves (gengivorragia, pequenas equimoses)", "Moderados a Graves (epistaxe volumosa, hematúria, melena)"],
                index=0
            )
            sinais_trombose = st.radio(
                "Sinais/Sintomas de Tromboembolismo:",
                ["Ausentes", "Presentes (DNV, dor em MMII, assimetria, cefaleia)"],
                index=0
            )
            
            st.markdown("**2. Aderência e Posologia**")
            esquecimento = st.radio(
                "Relato de esquecimento ou erro de dose:",
                ["Nenhum esquecimento (Aderência 100%)", "1 a 2 esquecimentos/mês", "Frequentes erros/esquecimentos"],
                index=0
            )

        with c2:
            st.markdown("**3. Fatores Interferentes e Dieta**")
            alteracao_dieta = st.radio(
                "Consumo de Vitamina K (folhosos) ou Álcool:",
                ["Manutenção do hábito alimentar usual", "Aumento no consumo de Vitamina K", "Redução expressiva no consumo", "Uso recente de álcool"],
                index=0
            )
            interacao_med = st.radio(
                "Início ou alteração de outros medicamentos:",
                ["Sem alterações de medicamentos", "Início de novo medicamento (Potencial Interação)", "Suspensão de medicamento contínuo"],
                index=0
            )
            detalhe_interacao = st.text_input("Especifique interações se houver:", placeholder="Ex: Azitromicina por 5 dias")

        st.markdown("**4. Conduta Farmacêutica e Ajuste de Dose**")
        c3, c4 = st.columns(2)
        with c3:
            decisao_dose = st.selectbox(
                "Conduta de Ajuste Posológico:",
                [
                    "Manter dose semanal atual",
                    "Aumentar dose semanal total (5% a 15%)",
                    "Reduzir dose semanal total (5% a 15%)",
                    "Omitir 1 dose e ajustar dose semanal",
                    "Alta por estabilidade do TTR"
                ]
            )
            nova_dose_semanal = st.number_input(
                "Nova Dose Semanal Proposta (mg):", 
                value=float(p.get('weeklyDose', p.get('doseCurrent', 0))), 
                step=2.5
            )
        with c4:
            retorno_dias = st.select_slider(
                "Retorno Agendado em:",
                options=["7 dias", "14 dias", "21 dias", "30 dias", "60 dias", "Alta Terapêutica"],
                value="30 dias"
            )
            obs_clinicas = st.text_area("Observações Adicionais:", placeholder="Orientações específicas...")

        btn_gerar_soap = st.form_submit_button("💾 Salvar e Gerar Evolução SOAP (MV)")

        if btn_gerar_soap:
            data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            soap_texto = (
                f"CONSULTA FARMACÊUTICA AMBULATORIAL DE ANTICOAGULAÇÃO - {data_hoje}\n\n"
                f"S (SUBJETIVO): Paciente {p['name']}, {p.get('age', 'N/A')} anos, em acompanhamento para anticoagulação oral ({p.get('indication', 'N/A')}). "
                f"Sinais de sangramento: {sinais_sangramento}. Sinais tromboembólicos: {sinais_trombose}. "
                f"Aderência ao tratamento: {esquecimento}. "
                f"Hábito alimentar e Vitamina K: {alteracao_dieta}. Interações medicamentosas: {interacao_med}"
                f"{f' ({detalhe_interacao})' if detalhe_interacao else ''}. {f'Obs: {obs_clinicas}' if obs_clinicas else ''}\n\n"
                f"O (OBJETIVO): RNI Atual: {ultimo_rni} (coleta em {data_ultimo_rni}). "
                f"Faixa Alvo RNI: {p.get('target', '2.0-3.0')}. TTR Estimado (Rosendaal): {ttr_valor:.1f}%. "
                f"TTR Direto: {ttr_direto:.1f}% ({exames_na_faixa}/{total_exames} exames na faixa). "
                f"Dose semanal prévia: {p.get('weeklyDose', p.get('doseCurrent', 0))} mg.\n\n"
                f"A (AVALIAÇÃO): Controle da anticoagulação oral classificado como {status_ttr.upper()} "
                f"(TTR Rosendaal = {ttr_valor:.1f}%). RNI atual encontra-se "
                f"{'DENTRO DA FAIXA ALVO' if min_alvo <= float(ultimo_rni) <= max_alvo else 'FORA DA FAIXA ALVO' if ultimo_rni != 'N/A' else 'NÃO AVALIADO'}.\n\n"
                f"P (PLANO): {decisao_dose}. Nova dose semanal ajustada para {nova_dose_semanal} mg. "
                f"Orientação farmacêutica realizada quanto à posologia diária e sinais de alarme. "
                f"Retorno agendado para {retorno_dias}. Farmacêutico responsável."
            )
            
            p['evolution'] = soap_texto
            p['weeklyDose'] = nova_dose_semanal
            if decisao_dose == "Alta por estabilidade do TTR" or retorno_dias == "Alta Terapêutica":
                p['status'] = 'Alta'
                
            salvar_dados_json(st.session_state.dados)
            st.success("Evolução SOAP registrada com sucesso!")
            st.rerun()

with tab_evolucao:
    st.subheader("📝 Evolução Farmacêutica Registrada (Sistema MV PEP)")
    if p.get('evolution'):
        st.text_area("Texto SOAP para Prontuário:", p['evolution'], height=320)
    else:
        st.info("Nenhuma evolução registrada para este paciente.")

with tab_tabela:
    if p.get('rniHistory'):
        df_hist = pd.DataFrame(p['rniHistory'])
        df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d/%m/%Y')
        df_hist.columns = ['Data da Coleta', 'Valor do RNI']
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Sem registros no histórico.")

with tab_meds:
    st.write("**Farmacoterapia Habitual:**")
    st.info(p.get('meds') if p.get('meds') else "Nenhum medicamento adicional registrado.")
