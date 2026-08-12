import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta

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
    
    /* Badge do Status de Risco */
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
    
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES DE CÁLCULO DE TTR
# ==============================================================================
def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
    """Calcula o Time in Therapeutic Range (TTR) por Interpolação Linear."""
    if len(historico) < 2:
        return 0.0
    
    df = pd.DataFrame(historico)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    dias_no_alvo = 0
    dias_totais = 0
    
    for i in range(len(df) - 1):
        d1, v1 = df.loc[i, 'date'], float(df.loc[i, 'value'])
        d2, v2 = df.loc[i+1, 'date'], float(df.loc[i+1, 'value'])
        
        dias_intervalo = (d2 - d1).days
        if dias_intervalo <= 0:
            continue
            
        passo_rni = (v2 - v1) / dias_intervalo
        
        for dia in range(dias_intervalo):
            rni_estimado = v1 + (passo_rni * dia)
            if min_alvo <= rni_estimado <= max_alvo:
                dias_no_alvo += 1
            dias_totais += 1
            
    if dias_totais == 0:
        return 0.0
        
    return (dias_no_alvo / dias_totais) * 100

def calcular_ttr_direto(historico, min_alvo, max_alvo):
    """Calcula a proporção direta de exames dentro do alvo."""
    if not historico:
        return 0.0, 0, 0
    
    total_exames = len(historico)
    exames_na_faixa = sum(1 for e in historico if min_alvo <= float(e['value']) <= max_alvo)
    porcentagem = (exames_na_faixa / total_exames) * 100
    return porcentagem, exames_na_faixa, total_exames

# ==============================================================================
# 3. CARREGAMENTO E MANIPULAÇÃO DE DADOS (JSON)
# ==============================================================================
if "dados" not in st.session_state:
    if os.path.exists("dados.json"):
        with open("dados.json", "r", encoding="utf-8") as f:
            st.session_state.dados = json.load(f)
    else:
        st.session_state.dados = {"patients": [], "agenda": {}}

pacientes = st.session_state.dados.get("patients", [])
pacientes = sorted(pacientes, key=lambda x: x['name'])

# ==============================================================================
# 4. PAINEL ESQUERDO (SIDEBAR - SELEÇÃO DE PACIENTES)
# ==============================================================================
st.sidebar.markdown("### 🩺 Ambulatório RNI")
st.sidebar.caption(f"Total de {len(pacientes)} pacientes cadastrados")

nombres_pacientes = [p['name'] for p in pacientes]

if not nombres_pacientes:
    st.warning("Nenhum paciente cadastrado no arquivo dados.json.")
    st.stop()

paciente_nome_sel = st.sidebar.radio(
    "Selecione o paciente:",
    nombres_pacientes,
    index=0
)

# Recupera o objeto do paciente selecionado
p = next(item for item in pacientes if item["name"] == paciente_nome_sel)

# ==============================================================================
# 5. PAINEL PRINCIPAL (FICHA CLINICA DO PACIENTE)
# ==============================================================================
st.markdown(f"# 👤 {p['name']}")

col_info1, col_info2, col_info3 = st.columns([2, 2, 2])

# Faixa Alvo do Paciente
try:
    min_alvo, max_alvo = map(float, p['target'].split('-'))
except:
    min_alvo, max_alvo = 2.0, 3.0

# Cálculos de TTR
ttr_valor = calcular_ttr_rosendaal(p.get('rniHistory', []), min_alvo, max_alvo)
ttr_direto, exames_na_faixa, total_exames = calcular_ttr_direto(p.get('rniHistory', []), min_alvo, max_alvo)

# Lógica Dinâmica de Cores baseada no TTR
if ttr_valor >= 70.0:
    cor_ttr = "#10B981"      # Verde (Bom controle)
    bg_badge = "#ECFDF5"     # Fundo verde claro
    status_ttr = "Estável"
elif ttr_valor >= 60.0:
    cor_ttr = "#F59E0B"      # Amarelo/Laranja (Alerta)
    bg_badge = "#FFFBEB"     # Fundo amarelo claro
    status_ttr = "Alerta"
else:
    cor_ttr = "#EF4444"      # Vermelho (Crítico)
    bg_badge = "#FEF2F2"     # Fundo vermelho claro
    status_ttr = "Crítico"

# Classe do nível de complexidade
level_class = "level-baixo" if p.get('level') == "Baixo" else "level-alto" if p.get('level') == "Alto" else "level-medio"

with col_info1:
    st.markdown(f"""
    <div class="patient-card">
        <div class="info-label">Dados Demográficos</div>
        <div class="info-value">Idade: {p.get('age', 'N/A')} anos</div>
        <div class="info-value">Contato: {p.get('contact', 'Não informado')}</div>
        <div class="info-label" style="margin-top: 10px;">Complexidade</div>
        <div><span class="badge-level {level_class}">{p.get('level', 'Médio')}</span></div>
    </div>
    """, unsafe_allow_html=True)

with col_info2:
    st.markdown(f"""
    <div class="patient-card">
        <div class="info-label">Manejo Terapêutico</div>
        <div class="info-value">Indicação: {p.get('indication', 'N/A')}</div>
        <div class="info-value">Dose Semanal: {p.get('weeklyDose', p.get('doseCurrent', 0))} mg</div>
        <div class="info-value">Organizador de Cp.: {p.get('organizer', 'Não')}</div>
    </div>
    """, unsafe_allow_html=True)

# Renderização do Card Dinâmico de TTR na col_info3
with col_info3:
    st.markdown(f"""
    <div style="
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    ">
        <!-- Cabeçalho Principal -->
        <div style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        ">
            <span style="font-size: 0.85rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em;">
                TTR (Rosendaal)
            </span>
            <span style="
                font-size: 0.75rem; 
                font-weight: 600; 
                color: {cor_ttr}; 
                background: {bg_badge}; 
                padding: 2px 8px; 
                border-radius: 9999px;
            ">
                {status_ttr}
            </span>
        </div>

        <!-- Valor Principal Dinâmico -->
        <div style="
            font-size: 2.5rem; 
            font-weight: 700; 
            color: {cor_ttr}; 
            line-height: 1; 
            margin-bottom: 16px;
            letter-spacing: -0.02em;
        ">
            {ttr_valor:.1f}%
        </div>

        <!-- Divisor Sutil -->
        <div style="border-top: 1px solid #F1F5F9; margin-bottom: 12px;"></div>

        <!-- Métrica Secundária Inferior -->
        <div style="
            display: flex;
            flex-direction: column;
            gap: 4px;
        ">
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
    """, unsafe_allow_html=True)

st.markdown("---")

# ==============================================================================
# 6. GRÁFICO DE ACOMPANHAMENTO E LANÇAMENTO DE EXAMES
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
            novo_registro = {
                "date": nova_data.strftime("%Y-%m-%d"),
                "value": float(novo_rni)
            }
            
            p['rniHistory'].insert(0, novo_registro)
            
            with open("dados.json", "w", encoding="utf-8") as f:
                json.dump(st.session_state.dados, f, ensure_ascii=False, indent=2)
                
            st.success("RNI adicionado com sucesso!")
            st.rerun()

st.markdown("---")

# ==============================================================================
# 7. REGISTROS DETALHADOS E EVOLUÇÃO FARMACÊUTICA
# ==============================================================================
tab_tabela, tab_evolucao, tab_meds = st.tabs(["📋 Histórico de Coletas", "📝 Evolução Farmacêutica", "💊 Medicamentos em Uso"])

with tab_tabela:
    if p.get('rniHistory'):
        df_hist = pd.DataFrame(p['rniHistory'])
        df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d/%m/%Y')
        df_hist.columns = ['Data da Coleta', 'Valor do RNI']
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Sem registros no histórico.")

with tab_evolucao:
    if p.get('evolution'):
        st.text_area("Registro da Última Evolução:", p['evolution'], height=250)
    else:
        st.info("Nenhuma evolução registrada para este paciente.")

with tab_meds:
    st.write("**Farmacoterapia Habitual:**")
    st.info(p.get('meds') if p.get('meds') else "Nenhum medicamento adicional registrado.")
