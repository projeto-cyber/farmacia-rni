import streamlit as st
import pandas as pd
import plotly.express as px
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
    
    /* Cards Clínicos */
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
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES DE CÁLCULO E PERSISTÊNCIA DE DADOS
# ==============================================================================
def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
    """Calcula o TTR pelo Método de Rosendaal (Interpolação Linear)."""
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
    """Calcula a proporção de exames dentro da faixa alvo."""
    if not historico:
        return 0.0, 0, 0
    try:
        total_exames = len(historico)
        exames_na_faixa = sum(1 for e in historico if min_alvo <= float(e['value']) <= max_alvo)
        porcentagem = (exames_na_faixa / total_exames) * 100.0
        return porcentagem, exames_na_faixa, total_exames
    except Exception:
        return 0.0, 0, 0

def obter_status_paciente(p):
    """Retorna a categoria clínica do paciente para o Dashboard e filtros."""
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
# 4. PAINEL ESQUERDO (SIDEBAR - NAVEGAÇÃO E SELEÇÃO)
# ==============================================================================
st.sidebar.markdown("### 🩺 Ambulatório RNI")

# Menu de Navegação Principal
modo_visao = st.sidebar.radio(
    "Navegação:",
    ["🏠 Visão Geral (Dashboard)", "👤 Ficha do Paciente"],
    index=0
)

st.sidebar.markdown("---")

# Cadastro de Novo Paciente
with st.sidebar.expander("➕ Cadastrar Novo Paciente"):
    with st.form("form_add_paciente", clear_on_submit=True):
        novo_nome = st.text_input("Nome Completo:")
        nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=60)
        novo_contato = st.text_input("Telefone/Contato:")
        nova_indicacao = st.selectbox("Indicação Clínica:", ["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"])
        nova_faixa = st.selectbox("Faixa Alvo RNI:", ["2.0-3.0", "2.5-3.5", "1.5-2.0"])
        nova_dose = st.number_input("Dose Semanal Inicial (mg):", value=35.0, step=2.5)
        
        btn_criar = st.form_submit_button("Salvar Paciente")
        
        if btn_criar and novo_nome:
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
                "rniHistory": [],
                "evolution": ""
            }
            st.session_state.dados["patients"].append(novo_p)
            salvar_dados_json(st.session_state.dados)
            st.success("Paciente cadastrado com sucesso!")
            st.rerun()

# ==============================================================================
# 5. MODO 1: DASHBOARD DA PÁGINA INICIAL (VISÃO GERAL DO AMBULATÓRIO)
# ==============================================================================
if modo_visao == "🏠 Visão Geral (Dashboard)":
    st.title("📊 Painel Geral do Ambulatório de Anticoagulação")
    st.caption("Mapeamento populacional de estabilidade terapêutica e triagem clínica dos pacientes.")
    
    if not pacientes:
        st.warning("Nenhum paciente cadastrado no banco de dados.")
        st.stop()

    # Mapeamento dos Perfis
    categorias = [obter_status_paciente(pt) for pt in pacientes]
    df_dashboard = pd.DataFrame({"Paciente": [pt['name'] for pt in pacientes], "Categoria": categorias})
    
    col_dash1, col_dash2 = st.columns([1, 1])
    
    with col_dash1:
        st.subheader("📈 Distribuição do Controle do TTR")
        df_pizza = df_dashboard['Categoria'].value_counts().reset_index()
        df_pizza.columns = ['Status', 'Total']
        
        cores_map = {
            'Apto para Alta': '#10B981',
            'Em Melhora': '#F59E0B',
            'Precisa de Atenção': '#EF4444',
            'Em Alta Terapêutica': '#94A3B8'
        }
        
        fig_pizza = px.pie(
            df_pizza, 
            names='Status', 
            values='Total', 
            color='Status',
            color_discrete_map=cores_map,
            hole=0.4
        )
        fig_pizza.update_traces(textinfo='percent+label', hoverinfo='label+value+percent')
        fig_pizza.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pizza, use_container_width=True)

    with col_dash2:
        st.subheader("🎯 Triagem e Status Clínico")
        
        tab_aptos, tab_atencao = st.tabs(["✅ Aptos para Alta (TTR ≥ 70%)", "⚠️ RNI Instável / Atenção"])
        
        with tab_aptos:
            aptos_lista = [pt for pt in pacientes if obter_status_paciente(pt) == 'Apto para Alta']
            if aptos_lista:
                for pt in aptos_lista:
                    min_a, max_a = map(float, pt.get('target', '2.0-3.0').split('-'))
                    ttr = calcular_ttr_rosendaal(pt.get('rniHistory', []), min_a, max_a)
                    st.success(f"**{pt['name']}** — TTR: **{ttr:.1f}%** | Target: {pt.get('target')}")
            else:
                st.info("Nenhum paciente ativo com TTR ≥ 70% no momento.")
                
        with tab_atencao:
            atencao_lista = [pt for pt in pacientes if obter_status_paciente(pt) == 'Precisa de Atenção']
            if atencao_lista:
                for pt in atencao_lista:
                    min_a, max_a = map(float, pt.get('target', '2.0-3.0').split('-'))
                    ttr = calcular_ttr_rosendaal(pt.get('rniHistory', []), min_a, max_a)
                    ult_rni = pt['rniHistory'][0]['value'] if pt.get('rniHistory') else "N/A"
                    st.error(f"**{pt['name']}** — TTR: **{ttr:.1f}%** | Último RNI: **{ult_rni}**")
            else:
                st.info("Nenhum paciente classificado na zona crítica.")

# ==============================================================================
# 6. MODO 2: FICHA DO PACIENTE
# ==============================================================================
else:
    opcoes_pacientes = [f"⚪ {pt['name']} (ALTA)" if pt.get('status') == 'Alta' else f"🟢 {pt['name']}" for pt in pacientes]
    
    if not pacientes:
        st.warning("Cadastre um paciente na barra lateral.")
        st.stop()
        
    paciente_sel_index = st.sidebar.radio(
        "Selecione o paciente:",
        range(len(opcoes_pacientes)),
        format_func=lambda i: opcoes_pacientes[i]
    )

    p = pacientes[paciente_sel_index]
    em_alta = (p.get('status') == 'Alta')

    # Cabeçalho da Ficha
    col_titulo, col_status_btn = st.columns([4, 1])
    with col_titulo:
        if em_alta:
            st.markdown(f"# <span style='color: #94A3B8;'>👤 {p['name']} (Alta Terapêutica)</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"# 👤 {p['name']}")

    with col_status_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Alternar Alta / Ativo", use_container_width=True):
            p['status'] = 'Ativo' if em_alta else 'Alta'
            salvar_dados_json(st.session_state.dados)
            st.rerun()

    # Informações Rápidas e TTR
    col_info1, col_info2, col_info3 = st.columns([2, 2, 2])

    try:
        target_str = p.get('target', '2.0-3.0')
        min_alvo, max_alvo = map(float, target_str.split('-'))
    except Exception:
        min_alvo, max_alvo = 2.0, 3.0

    ttr_valor = calcular_ttr_rosendaal(p.get('rniHistory', []), min_alvo, max_alvo)
    ttr_direto, exames_na_faixa, total_exames = calcular_ttr_direto(p.get('rniHistory', []), min_alvo, max_alvo)

    if em_alta:
        cor_ttr, bg_badge, status_ttr = "#64748B", "#F1F5F9", "Alta TTR"
    elif ttr_valor >= 70.0:
        cor_ttr, bg_badge, status_ttr = "#10B981", "#ECFDF5", "Estável"
    elif ttr_valor >= 60.0:
        cor_ttr, bg_badge, status_ttr = "#F59E0B", "#FFFBEB", "Alerta"
    else:
        cor_ttr, bg_badge, status_ttr = "#EF4444", "#FEF2F2", "Crítico"

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
    # 7. GRÁFICO PLOTLY DE RNI & REGISTRO DE EXAMES
    # ==============================================================================
    col_grafico, col_novo_rni = st.columns([2, 1])

    with col_grafico:
        st.subheader("📈 Tendência Temporal do RNI (Plotly)")
        if p.get('rniHistory'):
            df_chart = pd.DataFrame(p['rniHistory'])
            df_chart['date'] = pd.to_datetime(df_chart['date'])
            df_chart['value'] = df_chart['value'].astype(float)
            df_chart = df_chart.sort_values('date')

            fig_rni = px.line(
                df_chart, 
                x='date', 
                y='value', 
                markers=True,
                labels={'date': 'Data da Coleta', 'value': 'Valor de RNI'},
                title=f"Histórico de RNI - Alvo ({min_alvo} - {max_alvo})"
            )
            
            fig_rni.add_hrect(
                y0=min_alvo, y1=max_alvo, 
                fillcolor="green", opacity=0.15, line_width=0,
                annotation_text="Faixa Alvo Terapêutica", annotation_position="top left"
            )
            
            fig_rni.update_traces(line_color='#2563EB', line_width=3, marker_size=8)
            fig_rni.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=320)
            
            st.plotly_chart(fig_rni, use_container_width=True)
        else:
            st.info("Nenhum histórico de RNI disponível para renderização do gráfico.")

    with col_novo_rni:
        st.subheader("➕ Registrar Novo RNI")
        with st.form("form_novo_rni_avulso", clear_on_submit=True):
            data_avulsa = st.date_input("Data do Exame", value=datetime.today())
            rni_avulso = st.number_input("Valor de RNI Obtido", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
            
            btn_add_avulso = st.form_submit_button("Salvar Exame")
            
            if btn_add_avulso:
                p['rniHistory'].insert(0, {"date": data_avulsa.strftime("%Y-%m-%d"), "value": float(rni_avulso)})
                salvar_dados_json(st.session_state.dados)
                st.success("RNI registrado no histórico!")
                st.rerun()

    st.markdown("---")

    # ==============================================================================
    # 8. ANAMNESE E GERADOR DE EVOLUÇÃO SOAP NARRATIVA (MV PEP)
    # ==============================================================================
    tab_anamnese, tab_evolucao, tab_tabela, tab_meds = st.tabs([
        "🔍 Roteiro de Decisão & Consulta", 
        "📝 Evolução Farmacêutica (MV PEP)", 
        "📋 Histórico de Coletas", 
        "💊 Medicamentos em Uso"
    ])

    with tab_anamnese:
        st.markdown("### 📋 Questionário Norteador & Lançamento da Consulta")
        
        with st.form("form_anamnese_soap"):
            st.markdown("**0. Lançar RNI do Dia da Consulta (Opcional)**")
            c_rni1, c_rni2 = st.columns(2)
            with c_rni1:
                registrar_rni_hoje = st.checkbox("Incluir novo valor de RNI coletado hoje", value=True)
            with c_rni2:
                rni_hoje_valor = st.number_input("Valor do RNI Coletado Hoje:", min_value=0.5, max_value=10.0, step=0.1, value=2.5)

            st.markdown("---")
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
                    ["Manutenção do hábito alimentar usual", "Aumento no consumo de Vitamina K", "Redução expressiva no consumo de Vitamina K", "Uso recente de álcool"],
                    index=0
                )
                interacao_med = st.radio(
                    "Início ou alteração de outros medicamentos:",
                    ["Sem alterações de medicamentos", "Início de novo medicamento (Potencial Interação)", "Suspensão de medicamento contínuo"],
                    index=0
                )
                detalhe_interacao = st.text_input("Especifique interações se houver:", placeholder="Ex: Uso recente de Azitromicina")

            st.markdown("---")
            st.markdown("**4. Conduta Farmacêutica e Ajuste de Dose**")
            c3, c4 = st.columns(2)
            with c3:
                decisao_dose = st.selectbox(
                    "Conduta Posológica:",
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
                    options=["7 dias", "14 dias", "21 dias", "30 dias", "37 dias", "Alta Terapêutica"],
                    value="30 dias"
                )
                obs_clinicas = st.text_area("Observações Adicionais:", placeholder="Orientações prestadas...")

            btn_gerar_soap = st.form_submit_button("💾 Finalizar Consulta e Gerar Evolução SOAP (MV PEP)")

            if btn_gerar_soap:
                data_hoje_str = datetime.now().strftime("%Y-%m-%d")
                data_hoje_fmt = datetime.now().strftime("%d/%m/%Y às %H:%M")
                
                if registrar_rni_hoje:
                    p['rniHistory'].insert(0, {"date": data_hoje_str, "value": float(rni_hoje_valor)})
                
                # Recálculo atualizado
                ttr_atual = calcular_ttr_rosendaal(p['rniHistory'], min_alvo, max_alvo)
                ttr_dir, ex_f, tot_ex = calcular_ttr_direto(p['rniHistory'], min_alvo, max_alvo)
                ult_rni_val = p['rniHistory'][0]['value'] if p['rniHistory'] else "N/A"
                
                # Texto Narrativo Fluido (Padrão MV PEP)
                soap_texto = (
                    f"Evolução Farmacêutica - Ambulatório de Anticoagulação Oral ({data_hoje_fmt}). "
                    f"Paciente {p['name']}, {p.get('age', 'N/A')} anos, em acompanhamento ambulatorial para manejo de anticoagulação oral por {p.get('indication', 'N/A')}. "
                    f"Ao interrogatório clínico, nega intercorrências graves, relatando em relação a sangramentos: {sinais_sangramento.lower()} e sobre sintomas tromboembólicos: {sinais_trombose.lower()}. "
                    f"Quanto ao perfil de adesão farmacoterapêutica, refere {esquecimento.lower()}, associado à {alteracao_dieta.lower()} no padrão alimentar recente. "
                    f"Em relação à farmacoterapia concomitante, observa-se {interacao_med.lower()}{f' ({detalhe_interacao})' if detalhe_interacao else ''}. "
                    f"{f'Notas adicionais do relato: {obs_clinicas}. ' if obs_clinicas else ''}"
                    f"Ao exame objetivo e dados laboratoriais, aponta-se RNI atual de {ult_rni_val} para uma faixa alvo terapêutica estabelecida de {p.get('target', '2.0-3.0')}. "
                    f"O cálculo de controle de estabilidade indica Time in Therapeutic Range (TTR) pelo Método de Rosendaal de {ttr_atual:.1f}% e TTR Direto de {ttr_dir:.1f}% ({ex_f} de {tot_ex} exames na faixa). "
                    f"A dose semanal total prévia utilizada pelo paciente era de {p.get('weeklyDose', p.get('doseCurrent', 0))} mg. "
                    f"Em avaliação farmacêutica clínica, o controle da anticoagulação é classificado como {status_ttr.upper()}, estando o RNI atual "
                    f"{'adequado e dentro do intervalo alvo' if min_alvo <= float(ult_rni_val) <= max_alvo else 'fora da faixa ideal recomendada'}. "
                    f"Frente aos achados e perfil de segurança, adota-se como plano de conduta: {decisao_dose.lower()}, fixando a nova dose semanal ajustada em {nova_dose_semanal} mg. "
                    f"O paciente foi devidamente orientado quanto à correta distribuição diária da dose, reconhecimento de sinais de alarme para sangramentos ou trombose, e agendamento de retorno ambulatorial pactuado para {retorno_dias}. "
                    f"Atendimento finalizado e registrado por Farmacêutico Clínico."
                )
                
                p['evolution'] = soap_texto
                p['weeklyDose'] = nova_dose_semanal
                if decisao_dose == "Alta por estabilidade do TTR" or retorno_dias == "Alta Terapêutica":
                    p['status'] = 'Alta'
                    
                salvar_dados_json(st.session_state.dados)
                st.success("Consulta registrada! Evolução gerada no formato MV PEP.")
                st.rerun()

    with tab_evolucao:
        st.subheader("📝 Evolução Farmacêutica Registrada (Padrão MV PEP)")
        if p.get('evolution'):
            st.text_area("Texto Corrido Completo:", p['evolution'], height=350)
            st.info("💡 Você pode copiar o parágrafo acima e colar diretamente no Prontuário Eletrônico MV.")
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
