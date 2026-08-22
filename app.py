import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
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
    
    [data-testid="stSidebar"] {
        background-color: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    
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
    
    .alert-card {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 12px;
        border-left: 4px solid;
    }
    .alert-high { background-color: #FEF2F2; border-color: #EF4444; color: #991B1B; }
    .alert-mod { background-color: #FFFBEB; border-color: #F59E0B; color: #92400E; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. BANCO DE INTERAÇÕES MEDICAMENTOSAS COM A VARFARINA
# ==============================================================================
INTERACOES_VARFARINA = {
    "AMIODARONA": {"risco": "Alta", "efeito": "Inibe CYP2C9/3A4. Aumenta expressivamente o RNI.", "conduta": "Reduzir dose da Varfarina em 30% a 50% e monitorar RNI semanalmente."},
    "AZITROMICINA": {"risco": "Moderada", "efeito": "Alteração da flora intestinal e/ou clearance.", "conduta": "Monitorar RNI em 3 a 5 dias após início do antibiótico."},
    "CIPROFLOXACINO": {"risco": "Alta", "efeito": "Inibição de metabolização hepática. Risco elevado de sangramento.", "conduta": "Monitorar RNI frequente ou ajustar dose provisoriamente."},
    "SULFAMETOXAZOL": {"risco": "Alta", "efeito": "Deslocamento proteico e inibição da CYP2C9.", "conduta": "Potencialização severa. Reduzir dose e monitorar RNI precocemente."},
    "TRIMETOPRIMA": {"risco": "Alta", "efeito": "Potencializa efeito anticoagulante.", "conduta": "Reduzir dose e monitorar RNI em 3 dias."},
    "FLUCONAZOL": {"risco": "Alta", "efeito": "Inibidor potente da CYP2C9. Eleva RNI acentuadamente.", "conduta": "Reduzir dose em até 50% e acompanhar RNI estritamente."},
    "CETOCONAZOL": {"risco": "Alta", "efeito": "Inibição enzimática. Aumento do risco hemorrágico.", "conduta": "Acompanhamento rigoroso de RNI."},
    "OMEPRAZOL": {"risco": "Moderada", "efeito": "Discreta inibição CYP2C19. Pode elevar RNI discretamente.", "conduta": "Monitorar se houver alteração de dosagem."},
    "SIMVASTATINA": {"risco": "Moderada", "efeito": "Aumento do efeito anticoagulante e risco de rabdomiólise.", "conduta": "Avaliar RNI e sintomas musculares."},
    "PARACETAMOL": {"risco": "Moderada", "efeito": "Uso contínuo (>2g/dia) pode inibir fatores de coagulação.", "conduta": "Preferir doses baixas e esporádicas. Se uso contínuo, checar RNI."},
    "IBUPROFENO": {"risco": "Alta", "efeito": "Gastrolesividade e inibição plaquetária. Alto risco de sangramento.", "conduta": "Evitar AINEs. Se indispensável, associar gastroproteção e monitorar."},
    "NIMESULIDA": {"risco": "Alta", "efeito": "Aumento do risco de sangramento gastrointestinal.", "conduta": "Evitar coadministração."},
    "DICLOFENACO": {"risco": "Alta", "efeito": "Antiagregação e irritação gástrica associada.", "conduta": "Substituir por analgésico sem ação plaquetária."},
    "AAS": {"risco": "Alta", "efeito": "Sinergismo hemorrágico expressivo.", "conduta": "Uso apenas sob indicação formal (ex: prótese). Monitorar estritamente."},
    "ASPIRINA": {"risco": "Alta", "efeito": "Inibição irreversível das plaquetas + dano de mucosa.", "conduta": "Verificar indicação formal da dupla terapia."},
    "CARBAMAZEPINA": {"risco": "Alta", "efeito": "Indutor enzimático potente (CYP3A4/2C9). Reduz RNI.", "conduta": "Pode necessitar de doses substancialmente maiores de Varfarina."},
    "FENITOINA": {"risco": "Alta", "efeito": "Efeito bifásico (pode aumentar ou diminuir RNI).", "conduta": "Monitorar RNI e níveis de fenitoína com frequência."},
    "RIFAMPECINA": {"risco": "Alta", "efeito": "Indutor enzimático potente. Reduz acentuadamente o RNI.", "conduta": "Poderá exigir aumento expressivo da dose da Varfarina."},
    "SERTRALINA": {"risco": "Moderada", "efeito": "ISRSs alteram função plaquetária e aumentam risco de sangramento.", "conduta": "Acompanhar sinais clínicos de sangramento."},
    "FLUOXETINA": {"risco": "Moderada", "efeito": "Inibição metabólica e alteração de adesão plaquetária.", "conduta": "Monitorar RNI após início/ajuste."}
}

def checar_interacoes(texto_meds):
    if not texto_meds:
        return []
    encontradas = []
    texto_upper = texto_meds.upper()
    for med, info in INTERACOES_VARFARINA.items():
        if med in texto_upper:
            encontradas.append({"medicamento": med, **info})
    return encontradas

# ==============================================================================
# 3. CÁLCULOS E PERSISTÊNCIA DE DADOS
# ==============================================================================
def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
    # Filtra apenas registros válidos com valor numérico de RNI
    historico_rni = [e for e in historico if e.get('value') is not None]
    if not historico_rni or len(historico_rni) < 2:
        return 0.0
    try:
        df = pd.DataFrame(historico_rni)
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
                
        return (dias_no_alvo / dias_totais) * 100.0 if dias_totais > 0 else 0.0
    except Exception:
        return 0.0

def calcular_ttr_direto(historico, min_alvo, max_alvo):
    historico_rni = [e for e in historico if e.get('value') is not None]
    if not historico_rni:
        return 0.0, 0, 0
    try:
        total = len(historico_rni)
        na_faixa = sum(1 for e in historico_rni if min_alvo <= float(e['value']) <= max_alvo)
        return (na_faixa / total) * 100.0, na_faixa, total
    except Exception:
        return 0.0, 0, 0

def obter_status_paciente(p):
    if p.get('status') == 'Alta':
        return 'Em Alta Terapêutica'
    try:
        min_a, max_a = map(float, p.get('target', '2.0-3.0').split('-'))
    except Exception:
        min_a, max_a = 2.0, 3.0
    ttr = calcular_ttr_rosendaal(p.get('rniHistory', []), min_a, max_a)
    if ttr >= 70.0:
        return 'Apto para Alta'
    elif ttr >= 60.0:
        return 'Em Melhora'
    else:
        return 'Precisa de Atenção'

def salvar_dados_json(dados):
    with open("dados.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# ==============================================================================
# 4. CARREGAMENTO INICIAL
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
# 5. SIDEBAR E NAVEGAÇÃO
# ==============================================================================
st.sidebar.markdown("### 🩺 Ambulatório RNI")

modo_visao = st.sidebar.radio("Navegação:", ["🏠 Visão Geral (Dashboard)", "👤 Ficha do Paciente"], index=0)
st.sidebar.markdown("---")

with st.sidebar.expander("➕ Cadastrar Novo Paciente"):
    with st.form("form_add_paciente", clear_on_submit=True):
        novo_nome = st.text_input("Nome Completo:")
        nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=60)
        novo_contato = st.text_input("Telefone/Contato:")
        nova_indicacao = st.selectbox("Indicação Clínica:", ["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"])
        nova_faixa = st.selectbox("Faixa Alvo RNI:", ["2.0-3.0", "2.5-3.5", "1.5-2.0"])
        nova_dose = st.number_input("Dose Semanal Inicial (mg):", value=35.0, step=2.5)
        meds_iniciais = st.text_area("Medicamentos em Casa:", placeholder="Ex: Amiodarona 200mg, Omeprazol 20mg...")
        
        if st.form_submit_button("Salvar Paciente") and novo_nome:
            novo_p = {
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
                "meds": meds_iniciais,
                "rniHistory": [],
                "evolution": ""
            }
            st.session_state.dados["patients"].append(novo_p)
            salvar_dados_json(st.session_state.dados)
            st.success("Paciente cadastrado!")
            st.rerun()

# ==============================================================================
# 6. MODO 1: DASHBOARD
# ==============================================================================
if modo_visao == "🏠 Visão Geral (Dashboard)":
    st.title("📊 Painel Geral do Ambulatório de Anticoagulação")
    st.caption("Mapeamento populacional de estabilidade terapêutica e triagem clínica dos pacientes.")
    
    if not pacientes:
        st.warning("Nenhum paciente cadastrado.")
        st.stop()

    categorias = [obter_status_paciente(pt) for pt in pacientes]
    df_dashboard = pd.DataFrame({"Paciente": [pt['name'] for pt in pacientes], "Categoria": categorias})
    
    col_dash1, col_dash2 = st.columns([1, 1])
    
    with col_dash1:
        st.subheader("📈 Distribuição do Controle do TTR")
        df_pizza = df_dashboard['Categoria'].value_counts().reset_index()
        df_pizza.columns = ['Status', 'Total']
        
        fig_pizza = px.pie(
            df_pizza, names='Status', values='Total', color='Status',
            color_discrete_map={'Apto para Alta': '#10B981', 'Em Melhora': '#F59E0B', 'Precisa de Atenção': '#EF4444', 'Em Alta Terapêutica': '#94A3B8'},
            hole=0.4
        )
        fig_pizza.update_traces(textinfo='percent+label')
        fig_pizza.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pizza, use_container_width=True)

    with col_dash2:
        st.subheader("🎯 Triagem e Status Clínico")
        tab_aptos, tab_atencao = st.tabs(["✅ Aptos para Alta (TTR ≥ 70%)", "⚠️ RNI Instável / Atenção"])
        
        with tab_aptos:
            aptos = [pt for pt in pacientes if obter_status_paciente(pt) == 'Apto para Alta']
            if aptos:
                for pt in aptos:
                    min_a, max_a = map(float, pt.get('target', '2.0-3.0').split('-'))
                    ttr = calcular_ttr_rosendaal(pt.get('rniHistory', []), min_a, max_a)
                    st.success(f"**{pt['name']}** — TTR: **{ttr:.1f}%** | Target: {pt.get('target')}")
            else:
                st.info("Nenhum paciente com TTR ≥ 70%.")
                
        with tab_atencao:
            atencao = [pt for pt in pacientes if obter_status_paciente(pt) == 'Precisa de Atenção']
            if atencao:
                for pt in atencao:
                    min_a, max_a = map(float, pt.get('target', '2.0-3.0').split('-'))
                    ttr = calcular_ttr_rosendaal(pt.get('rniHistory', []), min_a, max_a)
                    rni_validos = [e for e in pt.get('rniHistory', []) if e.get('value') is not None]
                    ult_rni = rni_validos[0]['value'] if rni_validos else "N/A"
                    st.error(f"**{pt['name']}** — TTR: **{ttr:.1f}%** | Último RNI: **{ult_rni}**")
            else:
                st.info("Nenhum paciente na zona crítica.")

# ==============================================================================
# 7. MODO 2: FICHA DO PACIENTE
# ==============================================================================
else:
    opcoes_pacientes = [f"⚪ {pt['name']} (ALTA)" if pt.get('status') == 'Alta' else f"🟢 {pt['name']}" for pt in pacientes]
    if not pacientes:
        st.warning("Cadastre um paciente na barra lateral.")
        st.stop()
        
    paciente_sel_index = st.sidebar.radio("Selecione o paciente:", range(len(opcoes_pacientes)), format_func=lambda i: opcoes_pacientes[i])
    p = pacientes[paciente_sel_index]
    em_alta = (p.get('status') == 'Alta')

    # CABEÇALHO E ALTERAÇÃO DE DADOS DO PACIENTE
    col_titulo, col_edit_btn, col_status_btn = st.columns([3, 1, 1])
    with col_titulo:
        st.markdown(f"# {'<span style=\"color: #94A3B8;\">👤 ' + p['name'] + ' (Alta Terapêutica)</span>' if em_alta else '👤 ' + p['name']}", unsafe_allow_html=True)

    with col_edit_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.popover("✏️ Editar Paciente", use_container_width=True):
            st.markdown("### Alterar Dados do Paciente")
            with st.form("form_edit_paciente"):
                edit_nome = st.text_input("Nome:", value=p.get('name'))
                edit_idade = st.number_input("Idade:", value=int(p.get('age', 60)))
                edit_contato = st.text_input("Contato:", value=p.get('contact', ''))
                edit_indicacao = st.selectbox("Indicação:", ["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"], index=0)
                edit_target = st.selectbox("Faixa Alvo:", ["2.0-3.0", "2.5-3.5", "1.5-2.0"], index=["2.0-3.0", "2.5-3.5", "1.5-2.0"].index(p.get('target', '2.0-3.0')))
                edit_level = st.selectbox("Complexidade:", ["Baixo", "Médio", "Alto"], index=["Baixo", "Médio", "Alto"].index(p.get('level', 'Médio')))
                edit_dose = st.number_input("Dose Semanal Total (mg):", value=float(p.get('weeklyDose', 35.0)), step=2.5)
                
                if st.form_submit_button("Atualizar Cadastro"):
                    p['name'] = edit_nome
                    p['age'] = edit_idade
                    p['contact'] = edit_contato
                    p['indication'] = edit_indicacao
                    p['target'] = edit_target
                    p['level'] = edit_level
                    p['weeklyDose'] = edit_dose
                    salvar_dados_json(st.session_state.dados)
                    st.success("Dados atualizados!")
                    st.rerun()

    with col_status_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Alternar Status", use_container_width=True):
            p['status'] = 'Ativo' if em_alta else 'Alta'
            salvar_dados_json(st.session_state.dados)
            st.rerun()

    # INFOS RÁPIDAS
    col_info1, col_info2, col_info3 = st.columns([2, 2, 2])
    try:
        min_alvo, max_alvo = map(float, p.get('target', '2.0-3.0').split('-'))
    except Exception:
        min_alvo, max_alvo = 2.0, 3.0

    ttr_valor = calcular_ttr_rosendaal(p.get('rniHistory', []), min_alvo, max_alvo)
    ttr_direto, exames_na_faixa, total_exames = calcular_ttr_direto(p.get('rniHistory', []), min_alvo, max_alvo)

    cor_ttr, bg_badge, status_ttr = ("#64748B", "#F1F5F9", "Alta") if em_alta else (("#10B981", "#ECFDF5", "Estável") if ttr_valor >= 70.0 else (("#F59E0B", "#FFFBEB", "Alerta") if ttr_valor >= 60.0 else ("#EF4444", "#FEF2F2", "Crítico")))
    level_class = "level-alta" if em_alta else ("level-baixo" if p.get('level') == "Baixo" else "level-alto" if p.get('level') == "Alto" else "level-medio")

    with col_info1:
        st.markdown(f"""
        <div class="patient-card">
            <div class="info-label">Dados Demográficos</div>
            <div class="info-value">Idade: {p.get('age', 'N/A')} anos</div>
            <div class="info-value">Contato: {p.get('contact', 'Não informado')}</div>
            <div class="info-label" style="margin-top: 8px;">Complexidade</div>
            <div><span class="badge-level {level_class}">{ 'ALTA' if em_alta else p.get('level', 'Médio') }</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_info2:
        st.markdown(f"""
        <div class="patient-card">
            <div class="info-label">Manejo Terapêutico</div>
            <div class="info-value">Indicação: {p.get('indication', 'N/A')}</div>
            <div class="info-value">Faixa Alvo: {p.get('target', '2.0-3.0')}</div>
            <div class="info-value">Dose Semanal: {p.get('weeklyDose', 0)} mg</div>
        </div>
        """, unsafe_allow_html=True)

    with col_info3:
        st.markdown(f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span class="info-label">TTR (Rosendaal)</span>
                <span style="font-size: 0.75rem; font-weight: 600; color: {cor_ttr}; background: {bg_badge}; padding: 2px 8px; border-radius: 9999px;">{status_ttr}</span>
            </div>
            <div style="font-size: 2.2rem; font-weight: 700; color: {cor_ttr}; line-height: 1; margin-bottom: 12px;">{ttr_valor:.1f}%</div>
            <div style="font-size: 0.85rem; color: #475569;">TTR Direto: <b>{ttr_direto:.1f}%</b> ({exames_na_faixa}/{total_exames} exames)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ==============================================================================
    # GRÁFICO DE TENDÊNCIA EM ALTA QUALIDADE USANDO JSON CONFIGURAÇÃO NO PLOTLY
    # ==============================================================================
    col_grafico, col_novo_rni = st.columns([2, 1])
    with col_grafico:
        st.subheader("📈 Tendência Temporal do RNI (Alta Definção)")
        
        # Filtra histórico apenas para exames com RNI válido
        historico_rni_validos = [e for e in p.get('rniHistory', []) if e.get('value') is not None]
        
        if historico_rni_validos:
            df_chart = pd.DataFrame(historico_rni_validos)
            df_chart['date'] = pd.to_datetime(df_chart['date'])
            df_chart['value'] = df_chart['value'].astype(float)
            df_chart = df_chart.sort_values('date')

            fig_rni = px.line(
                df_chart, 
                x='date', 
                y='value', 
                markers=True, 
                labels={'date': 'Data da Coleta', 'value': 'Resultado do RNI'}
            )

            # ESTILIZAÇÃO AVANÇADA VIA DICIONÁRIO / CONFIGURAÇÃO JSON
            plotly_json_config = {
                "layout": {
                    "template": "plotly_white",
                    "font": {"family": "Inter, sans-serif", "size": 12, "color": "#1E293B"},
                    "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
                    "height": 300,
                    "hovermode": "x unified",
                    "xaxis": {
                        "showgrid": True,
                        "gridcolor": "#F1F5F9",
                        "linecolor": "#CBD5E1",
                        "ticks": "outside"
                    },
                    "yaxis": {
                        "showgrid": True,
                        "gridcolor": "#F1F5F9",
                        "linecolor": "#CBD5E1",
                        "zeroline": False,
                        "range": [max(0.0, df_chart['value'].min() - 0.5), df_chart['value'].max() + 0.8]
                    },
                    "shapes": [
                        # Faixa verde de Alvo Alvo RNI
                        {
                            "type": "rect",
                            "xref": "paper",
                            "yref": "y",
                            "x0": 0,
                            "x1": 1,
                            "y0": min_alvo,
                            "y1": max_alvo,
                            "fillcolor": "rgba(16, 185, 129, 0.12)",
                            "line": {"width": 0},
                            "layer": "below"
                        },
                        # Linha Limite Inferior
                        {
                            "type": "line", "xref": "paper", "yref": "y", "x0": 0, "x1": 1,
                            "y0": min_alvo, "y1": min_alvo,
                            "line": {"color": "#10B981", "width": 1.5, "dash": "dot"}
                        },
                        # Linha Limite Superior
                        {
                            "type": "line", "xref": "paper", "yref": "y", "x0": 0, "x1": 1,
                            "y0": max_alvo, "y1": max_alvo,
                            "line": {"color": "#10B981", "width": 1.5, "dash": "dot"}
                        }
                    ]
                }
            }

            fig_rni.update_traces(
                line=dict(color='#2563EB', width=3, shape='linear'),
                marker=dict(size=9, color='#1D4ED8', symbol='circle', line=dict(width=2, color='#FFFFFF'))
            )
            fig_rni.update_layout(plotly_json_config["layout"])

            st.plotly_chart(fig_rni, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Nenhum histórico numérico de RNI registrado até o momento.")

    with col_novo_rni:
        st.subheader("➕ Registrar RNI")
        with st.form("form_novo_rni_avulso", clear_on_submit=True):
            data_avulsa = st.date_input("Data do Exame", value=datetime.today())
            rni_avulso = st.number_input("Valor de RNI", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
            if st.form_submit_button("Salvar Exame"):
                p['rniHistory'].insert(0, {"date": data_avulsa.strftime("%Y-%m-%d"), "value": float(rni_avulso)})
                salvar_dados_json(st.session_state.dados)
                st.success("RNI registrado!")
                st.rerun()

    st.markdown("---")

    # ABAS DA FICHA
    tab_anamnese, tab_evolucao, tab_tabela, tab_meds = st.tabs([
        "🔍 Roteiro de Decisão & Consulta", 
        "📝 Evolução Farmacêutica (MV PEP)", 
        "📋 Histórico & Edição de RNI", 
        "💊 Medicamentos em Casa & Alertas"
    ])

    # 1. ANAMNESE E GERADOR DE EVOLUÇÃO
    with tab_anamnese:
        st.markdown("### 📋 Lançamento da Consulta Ambulatorial")
        with st.form("form_anamnese_soap"):
            c_rni1, c_rni2 = st.columns(2)
            with c_rni1:
                registrar_rni_hoje = st.checkbox("Incluir RNI coletado hoje na consulta", value=True)
            with c_rni2:
                rni_hoje_valor = st.number_input("RNI Coletado Hoje:", min_value=0.5, max_value=10.0, step=0.1, value=2.5)

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**1. Segurança e Eventos Adversos**")
                sinais_sangramento = st.radio("Sangramentos recentes:", ["Ausentes", "Leves (gengivorragia, pequenas equimoses)", "Moderados a Graves (epistaxe volumosa, hematúria, melena)"])
                sinais_trombose = st.radio("Sintomas Tromboembólicos:", ["Ausentes", "Presentes (DNV, dor em MMII, assimetria, cefaleia)"])
                st.markdown("**2. Aderência**")
                esquecimento = st.radio("Relato de esquecimento:", ["Nenhum esquecimento (Aderência 100%)", "1 a 2 esquecimentos/mês", "Frequentes erros/esquecimentos"])

            with c2:
                st.markdown("**3. Fatores Interferentes e Dieta**")
                alteracao_dieta = st.radio("Vitamina K / Álcool:", ["Manutenção do hábito alimentar usual", "Aumento no consumo de Vitamina K", "Redução expressiva de Vitamina K", "Uso recente de álcool"])
                interacao_med = st.radio("Medicamentos Concomitantes:", ["Sem alterações de medicamentos", "Início de novo medicamento (Potencial Interação)", "Suspensão de medicamento contínuo"])
                detalhe_interacao = st.text_input("Especifique novos medicamentos se houver:", placeholder="Ex: Azitromicina")

            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                decisao_dose = st.selectbox("Conduta Posológica:", ["Manter dose semanal atual", "Aumentar dose semanal total (5% a 15%)", "Reduzir dose semanal total (5% a 15%)", "Omitir 1 dose e ajustar dose semanal", "Alta por estabilidade do TTR"])
                nova_dose_semanal = st.number_input("Nova Dose Semanal Total (mg):", value=float(p.get('weeklyDose', 35.0)), step=2.5)
            with c4:
                retorno_dias = st.select_slider("Retorno Agendado:", options=["7 dias", "14 dias", "21 dias", "30 dias", "37 dias", "Alta Terapêutica"], value="30 dias")
                obs_clinicas = st.text_area("Observações Adicionais:", placeholder="Orientações e detalhes adicionais...")

            if st.form_submit_button("💾 Gerar Evolução Narrativa em Texto Corrido"):
                data_hoje_str = datetime.now().strftime("%Y-%m-%d")
                data_hoje_fmt = datetime.now().strftime("%d/%m/%Y às %H:%M")
                
                if registrar_rni_hoje:
                    p['rniHistory'].insert(0, {"date": data_hoje_str, "value": float(rni_hoje_valor)})
                
                ttr_atual = calcular_ttr_rosendaal(p['rniHistory'], min_alvo, max_alvo)
                ttr_dir, ex_f, tot_ex = calcular_ttr_direto(p['rniHistory'], min_alvo, max_alvo)
                rni_validos = [e for e in p['rniHistory'] if e.get('value') is not None]
                ult_rni_val = rni_validos[0]['value'] if rni_validos else "N/A"
                
                # NARRATIVA DIRETA E CONTINUA EM TEXTO CORRIDO
                soap_texto = (
                    f"Evolução Farmacêutica - Ambulatório de Anticoagulação Oral ({data_hoje_fmt}). "
                    f"Paciente {p['name']}, {p.get('age', 'N/A')} anos, em acompanhamento ambulatorial para manejo de anticoagulação por {p.get('indication', 'N/A')}. "
                    f"Ao interrogatório clínico, nega intercorrências graves, relatando em relação a sangramentos: {sinais_sangramento.lower()} e sobre sintomas tromboembólicos: {sinais_trombose.lower()}. "
                    f"Quanto ao perfil de adesão farmacoterapêutica, refere {esquecimento.lower()}, associado a {alteracao_dieta.lower()} no padrão alimentar habitual. "
                    f"Em relação à farmacoterapia concomitante, observa-se {interacao_med.lower()}{f' ({detalhe_interacao})' if detalhe_interacao else ''}. "
                    f"{f'Informações complementares relatadas: {obs_clinicas}. ' if obs_clinicas else ''}"
                    f"Ao exame objetivo e dados laboratoriais, aponta-se RNI atual de {ult_rni_val} para uma faixa alvo terapêutica estabelecida de {p.get('target', '2.0-3.0')}. "
                    f"O cálculo de controle de estabilidade indica Time in Therapeutic Range (TTR) pelo Método de Rosendaal de {ttr_atual:.1f}% e TTR Direto de {ttr_dir:.1f}% ({ex_f} de {tot_ex} exames na faixa). "
                    f"A dose semanal total prévia utilizada pelo paciente era de {p.get('weeklyDose', 0)} mg. "
                    f"Em avaliação farmacêutica clínica, o controle da anticoagulação é classificado como {status_ttr.upper()}, estando o RNI "
                    f"{'adequado e dentro do intervalo alvo' if (ult_rni_val != 'N/A' and min_alvo <= float(ult_rni_val) <= max_alvo) else 'fora da faixa ideal recomendada'}. "
                    f"Frente aos achados e perfil de segurança, adota-se como plano de conduta: {decisao_dose.lower()}, fixando a nova dose semanal ajustada em {nova_dose_semanal} mg. "
                    f"O paciente foi devidamente orientado quanto à correta distribuição diária da dose, reconhecimento de sinais de alarme para sangramentos ou trombose, e agendamento de retorno ambulatorial pactuado para {retorno_dias}. "
                    f"Atendimento finalizado e registrado por Farmacêutico Clínico."
                )
                
                p['evolution'] = soap_texto
                p['weeklyDose'] = nova_dose_semanal
                if decisao_dose == "Alta por estabilidade do TTR" or retorno_dias == "Alta Terapêutica":
                    p['status'] = 'Alta'
                    
                salvar_dados_json(st.session_state.dados)
                st.success("Evolução gerada! Disponível na aba 'Evolução Farmacêutica'.")
                st.rerun()

    # 2. EVOLUÇÃO EDITÁVEL
    with tab_evolucao:
        st.subheader("📝 Evolução Farmacêutica Narrativa (Padrão MV PEP)")
        st.caption("Você pode editar o texto abaixo diretamente para acrescentar dados antes de copiar para o prontuário eletrônico.")
        
        texto_evol_atual = p.get('evolution', '')
        novo_texto_editado = st.text_area("Texto Corrido Editável:", value=texto_evol_atual, height=350)
        
        c_btn1, c_btn2 = st.columns([1, 4])
        with c_btn1:
            if st.button("💾 Salvar Alterações no Texto"):
                p['evolution'] = novo_texto_editado
                salvar_dados_json(st.session_state.dados)
                st.success("Texto da evolução atualizado!")

    # 3. HISTÓRICO, EDIÇÃO E EXCLUSÃO DE RNI + OPÇÃO DE REGISTRO DE FALTA
    with tab_tabela:
        st.subheader("📋 Histórico de Coletas - Edição e Gestão")
        
        # BOTÃO PARA REGISTRAR FALTA
        with st.expander("🚨 Registrar Ausência / Paciente Faltou à Consulta", expanded=False):
            with st.form("form_registra_falta"):
                data_falta = st.date_input("Data da Consulta Não Comparecida:", value=datetime.today())
                obs_falta = st.text_input("Observação da Falta:", value="Paciente faltou à consulta agendada. Sem justificativa prévia.")
                if st.form_submit_button("Registrar Ausência"):
                    p['rniHistory'].insert(0, {
                        "date": data_falta.strftime("%Y-%m-%d"),
                        "value": None,
                        "status": "Falta",
                        "obs": obs_falta
                    })
                    salvar_dados_json(st.session_state.dados)
                    st.warning("Falta registrada no histórico!")
                    st.rerun()

        st.markdown("---")

        if p.get('rniHistory'):
            for idx, item in enumerate(p['rniHistory']):
                c_data, c_val, c_edit, c_del = st.columns([2, 3, 1, 1])
                with c_data:
                    st.write(f"📅 **{item['date']}**")
                with c_val:
                    if item.get('status') == 'Falta' or item.get('value') is None:
                        st.markdown(f"⚠️ <span style='color: #DC2626; font-weight: 600;'>PACIENTE FALTOU À CONSULTA</span><br><small style='color: #64748B;'>Obs: {item.get('obs', 'Sem registro')}</small>", unsafe_allow_html=True)
                    else:
                        st.write(f"🩸 **RNI: {item['value']}**")
                with c_edit:
                    if item.get('value') is not None:
                        with st.popover("✏️ Editar"):
                            with st.form(f"form_edit_rni_{idx}"):
                                nova_d = st.date_input("Data:", value=datetime.strptime(item['date'], "%Y-%m-%d"))
                                novo_v = st.number_input("Valor RNI:", value=float(item['value']), step=0.1)
                                if st.form_submit_button("Atualizar"):
                                    p['rniHistory'][idx] = {"date": nova_d.strftime("%Y-%m-%d"), "value": float(novo_v)}
                                    salvar_dados_json(st.session_state.dados)
                                    st.success("Atualizado!")
                                    st.rerun()
                with c_del:
                    if st.button("🗑️ Excluir", key=f"btn_del_rni_{idx}"):
                        p['rniHistory'].pop(idx)
                        salvar_dados_json(st.session_state.dados)
                        st.success("Registro removido!")
                        st.rerun()
                st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
        else:
            st.info("Sem exames ou ausências registradas.")

    # 4. MEDICAMENTOS EM CASA E ALERTAS DE INTERAÇÃO
    with tab_meds:
        st.subheader("💊 Medicamentos de Uso Domiciliar e Alertas Clínicos")
        
        with st.form("form_edit_meds"):
            meds_texto = st.text_area("Relação de Medicamentos em Uso em Casa:", value=p.get('meds', ''), height=120, placeholder="Ex: Amiodarona 200mg, Omeprazol 20mg, Paracetamol 750mg...")
            if st.form_submit_button("💾 Salvar Relação de Medicamentos"):
                p['meds'] = meds_texto
                salvar_dados_json(st.session_state.dados)
                st.success("Medicamentos atualizados!")
                st.rerun()

        st.markdown("---")
        st.markdown("### ⚠️ Rastreio Automático de Interações com a Varfarina")
        
        interacoes = checar_interacoes(p.get('meds', ''))
        if interacoes:
            for inter in interacoes:
                classe_card = "alert-high" if inter['risco'] == "Alta" else "alert-mod"
                st.markdown(f"""
                <div class="alert-card {classe_card}">
                    <div style="font-size: 1rem; font-weight: 700;">🚨 {inter['medicamento']} — Risco de Interação {inter['risco'].upper()}</div>
                    <div style="margin-top: 4px; font-size: 0.9rem;"><b>Efeito Clínico:</b> {inter['efeito']}</div>
                    <div style="margin-top: 2px; font-size: 0.9rem;"><b>Recomendação / Conduta:</b> {inter['conduta']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ Nenhuma interação medicamentosa de alto risco identificada na lista atual.")

    # ==============================================================================
    # 8. ÁREA DE SEGURANÇA: EXCLUSÃO DEFINITIVA DO PACIENTE
    # ==============================================================================
    st.markdown("---")
    with st.expander("⚙️ Opções Avançadas / Excluir Paciente do Serviço"):
        st.warning("⚠️ **Atenção:** A exclusão do paciente removerá todos os registros de RNI, evoluções e histórico ambulatorial associados de forma irreversível.")
        col_del_txt, col_del_btn = st.columns([3, 1])
        with col_del_txt:
            confirma_exclusao = st.checkbox(f"Estou ciente e desejo excluir o paciente {p['name']} do sistema.")
        with col_del_btn:
            if st.button("🗑️ Excluir Paciente", type="primary", disabled=not confirma_exclusao, use_container_width=True):
                st.session_state.dados["patients"].pop(paciente_sel_index)
                salvar_dados_json(st.session_state.dados)
                st.success("Paciente excluído com sucesso!")
                st.rerun()
