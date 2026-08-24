import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
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
# 2. BANCO DE DADOS SQLITE (INICIALIZAÇÃO & MIGRAÇÃO)
# ==============================================================================
DB_NAME = "ambulatorio_rni.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            contact TEXT,
            indication TEXT,
            target TEXT,
            weekly_dose REAL,
            level TEXT,
            status TEXT,
            meds TEXT,
            needs_support TEXT,
            evolution TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_rni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            date TEXT NOT NULL,
            value REAL,
            status TEXT,
            obs TEXT,
            FOREIGN KEY (patient_id) REFERENCES pacientes (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==============================================================================
# 3. FUNÇÕES DE EXPORTAR E IMPORTAR PROJETO (BACKUP / RESTORE)
# ==============================================================================
def exportar_projeto_json():
    conn = get_db_connection()
    pacientes = [dict(p) for p in conn.execute("SELECT * FROM pacientes").fetchall()]
    historico = [dict(h) for h in conn.execute("SELECT * FROM historico_rni").fetchall()]
    conn.close()
    
    dados_exportacao = {
        "versao": "2.0",
        "data_backup": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pacientes": pacientes,
        "historico_rni": historico
    }
    return json.dumps(dados_exportacao, ensure_ascii=False, indent=2)

def importar_projeto_json(conteudo_json):
    try:
        dados = json.loads(conteudo_json)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM historico_rni")
        cursor.execute("DELETE FROM pacientes")
        
        for p in dados.get("pacientes", []):
            cursor.execute("""
                INSERT INTO pacientes (id, name, age, contact, indication, target, weekly_dose, level, status, meds, needs_support, evolution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p.get("id"), p.get("name"), p.get("age"), p.get("contact"), p.get("indication"),
                p.get("target"), p.get("weekly_dose"), p.get("level"), p.get("status"),
                p.get("meds"), p.get("needs_support"), p.get("evolution")
            ))
            
        for h in dados.get("historico_rni", []):
            cursor.execute("""
                INSERT INTO historico_rni (id, patient_id, date, value, status, obs)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                h.get("id"), h.get("patient_id"), h.get("date"), h.get("value"), h.get("status"), h.get("obs")
            ))
            
        conn.commit()
        conn.close()
        return True, "Projeto importado e restaurado com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar arquivo: {str(e)}"

# ==============================================================================
# 4. BANCO DE INTERAÇÕES MEDICAMENTOSAS COM A VARFARINA
# ==============================================================================
INTERACOES_VARFARINA = {
    "AMIODARONA": {"risco": "Alta", "efeito": "Inibe CYP2C9/3A4 e aumenta expressivamente o RNI com risco de hemorragia.", "conduta": "Reduzir dose da Varfarina em 30% a 50% e monitorar RNI semanalmente."},
    "AZITROMICINA": {"risco": "Moderada", "efeito": "Altera flora intestinal/clearance e pode aumentar o RNI.", "conduta": "Monitorar RNI em 3 a 5 dias após início do antibiótico."},
    "CIPROFLOXACINO": {"risco": "Alta", "efeito": "Inibe metabolização hepática e eleva o RNI (risco de sangramento).", "conduta": "Monitorar RNI com frequência ou ajustar dose provisoriamente."},
    "SULFAMETOXAZOL": {"risco": "Alta", "efeito": "Potencializa fortemente a Varfarina aumentando o RNI.", "conduta": "Reduzir dose e monitorar RNI precocemente."},
    "TRIMETOPRIMA": {"risco": "Alta", "efeito": "Potencializa o efeito anticoagulante e eleva RNI.", "conduta": "Reduzir dose e monitorar RNI em 3 dias."},
    "FLUCONAZOL": {"risco": "Alta", "efeito": "Inibidor potente da CYP2C9, eleva o RNI acentuadamente.", "conduta": "Reduzir dose em até 50% e acompanhar RNI estritamente."},
    "CETOCONAZOL": {"risco": "Alta", "efeito": "Inibição enzimática com elevação do RNI e risco hemorrágico.", "conduta": "Acompanhamento rigoroso de RNI."},
    "OMEPRAZOL": {"risco": "Moderada", "efeito": "Inibição discreta da CYP2C19, podendo elevar levemente o RNI.", "conduta": "Monitorar se houver alteração de dosagem."},
    "SIMVASTATINA": {"risco": "Moderada", "efeito": "Aumenta o efeito anticoagulante e o RNI.", "conduta": "Avaliar RNI e sintomas musculares."},
    "PARACETAMOL": {"risco": "Moderada", "efeito": "Uso contínuo (>2g/dia) inibe fatores de coagulação e eleva RNI.", "conduta": "Preferir doses baixas e esporádicas. Se uso contínuo, checar RNI."},
    "IBUPROFENO": {"risco": "Alta", "efeito": "Gastrolesividade e inibição plaquetária (risco hemorrágico alto).", "conduta": "Evitar AINEs. Se indispensável, associar gastroproteção e monitorar."},
    "NIMESULIDA": {"risco": "Alta", "efeito": "Risco elevado de sangramento gastrointestinal.", "conduta": "Evitar coadministração."},
    "DICLOFENACO": {"risco": "Alta", "efeito": "Antiagregação plaquetária e risco de sangramento.", "conduta": "Substituir por analgésico sem ação plaquetária."},
    "AAS": {"risco": "Alta", "efeito": "Sinergismo hemorrágico expressivo.", "conduta": "Uso apenas sob indicação formal (ex: prótese). Monitorar estritamente."},
    "ASPIRINA": {"risco": "Alta", "efeito": "Inibição irreversível das plaquetas e aumento do risco hemorrágico.", "conduta": "Verificar indicação formal da dupla terapia."},
    "CARBAMAZEPINA": {"risco": "Alta", "efeito": "Indutor enzimático potente (CYP3A4/2C9), reduz o RNI (risco de trombose).", "conduta": "Pode necessitar de doses maiores de Varfarina."},
    "FENITOINA": {"risco": "Alta", "efeito": "Efeito bifásico (pode elevar ou reduzir o RNI).", "conduta": "Monitorar RNI e níveis de fenitoína com frequência."},
    "RIFAMPECINA": {"risco": "Alta", "efeito": "Indutor enzimático potente, reduz acentuadamente o RNI (risco de trombose).", "conduta": "Poderá exigir aumento expressivo da dose de Varfarina."},
    "SERTRALINA": {"risco": "Moderada", "efeito": "Altera função plaquetária e aumenta risco de sangramento.", "conduta": "Acompanhar sinais clínicos de sangramento."},
    "FLUOXETINA": {"risco": "Moderada", "efeito": "Inibição metabólica e alteração da adesão plaquetária.", "conduta": "Monitorar RNI após início/ajuste."}
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

def contar_medicamentos(texto_meds):
    if not texto_meds or not texto_meds.strip():
        return 0
    itens = [m.strip() for m in texto_meds.replace('\n', ',').replace(';', ',').split(',') if m.strip()]
    return len(itens)

# ==============================================================================
# 5. CÁLCULOS TTR E UTILITÁRIOS
# ==============================================================================
def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
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

def obter_status_paciente(p, historico):
    if p['status'] == 'Alta':
        return 'Em Alta Terapêutica'
    try:
        min_a, max_a = map(float, p['target'].split('-'))
    except Exception:
        min_a, max_a = 2.0, 3.0
    ttr = calcular_ttr_rosendaal(historico, min_a, max_a)
    if ttr >= 70.0:
        return 'Apto para Alta'
    elif ttr >= 60.0:
        return 'Em Melhora'
    else:
        return 'Precisa de Atenção'

# ==============================================================================
# 6. SIDEBAR, NAVEGAÇÃO E EXPORTAR/IMPORTAR PROJETO
# ==============================================================================
st.sidebar.markdown("### 🩺 Ambulatório RNI")

modo_visao = st.sidebar.radio("Navegação:", ["🏠 Visão Geral (Dashboard)", "👤 Ficha do Paciente"], index=0)
st.sidebar.markdown("---")

# GERENCIAMENTO DE CADASTRO
with st.sidebar.expander("➕ Cadastrar Novo Paciente"):
    with st.form("form_add_paciente", clear_on_submit=True):
        novo_nome = st.text_input("Nome Completo:")
        nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=65)
        novo_contato = st.text_input("Telefone/Contato:")
        nova_indicacao = st.selectbox("Indicação Clínica:", ["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"])
        nova_faixa = st.selectbox("Faixa Alvo RNI:", ["2.0-3.0", "2.5-3.5", "1.5-2.0"])
        nova_dose = st.number_input("Dose Semanal Inicial (mg):", value=35.0, step=2.5)
        novo_apoio = st.selectbox("Necessita de Apoio/Cuidador?", ["Não", "Sim"])
        meds_iniciais = st.text_area("Medicamentos de Uso Contínuo:", placeholder="Ex: Amiodarona 200mg, Omeprazol 20mg, Losartana 50mg, AAS 100mg...")
        
        if st.form_submit_button("Salvar Paciente") and novo_nome:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pacientes (name, age, contact, indication, target, weekly_dose, level, status, meds, needs_support, evolution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (novo_nome, nova_idade, novo_contato, nova_indicacao, nova_faixa, nova_dose, "Médio", "Ativo", meds_iniciais, novo_apoio, ""))
            conn.commit()
            conn.close()
            st.success("Paciente cadastrado!")
            st.rerun()

st.sidebar.markdown("---")

# EXPORTAÇÃO E IMPORTAÇÃO COMPLETA DO PROJETO (BACKUP / RESTORE)
with st.sidebar.expander("💾 Gestão de Dados do Projeto"):
    st.caption("Salve ou restaure todo o projeto (pacientes, histórico de RNI e evoluções).")
    
    json_backup = exportar_projeto_json()
    nome_arq_backup = f"backup_ambulatorio_rni_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    st.download_button(
        label="📥 Exportar Backup do Projeto",
        data=json_backup,
        file_name=nome_arq_backup,
        mime="application/json",
        use_container_width=True,
        help="Baixa um arquivo com todos os dados atuais do sistema."
    )
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    
    arquivo_upload = st.file_uploader("📤 Importar Backup do Projeto", type=["json"], help="Selecione um arquivo de backup previamente exportado.")
    if arquivo_upload is not None:
        if st.button("🔄 Restaurar Dados do Arquivo", use_container_width=True, type="primary"):
            conteudo = arquivo_upload.read().decode("utf-8")
            sucesso, msg = importar_projeto_json(conteudo)
            if sucesso:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

# ==============================================================================
# 7. MODO 1: DASHBOARD POPULACIONAL
# ==============================================================================
if modo_visao == "🏠 Visão Geral (Dashboard)":
    st.title("📊 Painel Geral do Ambulatório de Anticoagulação")
    st.caption("Mapeamento da população, perfis de complexidade, idosos, polifarmácia e interações.")
    
    conn = get_db_connection()
    pacientes_raw = conn.execute("SELECT * FROM pacientes").fetchall()
    
    if not pacientes_raw:
        st.warning("Nenhum paciente cadastrado no banco de dados. Utilize a opção na barra lateral para cadastrar ou importar um backup.")
        conn.close()
        st.stop()

    lista_pacientes = [dict(p) for p in pacientes_raw]
    
    total_pacientes = len(lista_pacientes)
    idosos = sum(1 for p in lista_pacientes if p['age'] >= 60)
    idosos_mais_velhos = sum(1 for p in lista_pacientes if p['age'] >= 80)
    com_apoio = sum(1 for p in lista_pacientes if p['needs_support'] == "Sim")
    
    polimedicados = 0
    interagentes_dict = {}
    status_categorias = []
    
    for p in lista_pacientes:
        rni_rows = conn.execute("SELECT * FROM historico_rni WHERE patient_id = ? ORDER BY date DESC", (p['id'],)).fetchall()
        rni_hist = [dict(r) for r in rni_rows]
        
        cat = obter_status_paciente(p, rni_hist)
        status_categorias.append(cat)
        
        meds_texto = p['meds'] or ""
        qtd_meds = contar_medicamentos(meds_texto)
        if qtd_meds >= 5:
            polimedicados += 1
            
        interacoes = checar_interacoes(meds_texto)
        for inter in interacoes:
            med_nome = inter['medicamento']
            interagentes_dict[med_nome] = interagentes_dict.get(med_nome, 0) + 1

    conn.close()

    # METRICAS RÁPIDAS
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total de Pacientes", total_pacientes)
    m2.metric("Idosos (≥ 60 anos)", f"{idosos} ({idosos/total_pacientes*100:.0f}%)")
    m3.metric("Very Elderly (≥ 80 anos)", f"{idosos_mais_velhos} ({idosos_mais_velhos/total_pacientes*100:.0f}%)")
    m4.metric("Polimedicados (≥ 5 meds)", f"{polimedicados} ({polimedicados/total_pacientes*100:.0f}%)")
    m5.metric("Necessitam de Apoio", f"{com_apoio} ({com_apoio/total_pacientes*100:.0f}%)")

    st.markdown("---")

    # GRÁFICOS - LINHA 1
    c_g1, c_g2 = st.columns(2)
    
    with c_g1:
        st.subheader("🎯 Controle Terapêutico (TTR Populacional)")
        df_status = pd.DataFrame({"Categoria": status_categorias}).value_counts().reset_index()
        df_status.columns = ['Status', 'Total']
        fig_pie = px.pie(
            df_status, names='Status', values='Total', color='Status',
            color_discrete_map={'Apto para Alta': '#10B981', 'Em Melhora': '#F59E0B', 'Precisa de Atenção': '#EF4444', 'Em Alta Terapêutica': '#94A3B8'},
            hole=0.4
        )
        fig_pie.update_traces(textinfo='percent+label')
        fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=300)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c_g2:
        st.subheader("⚠️ Top Fármacos de Uso Contínuo Interagentes")
        if interagentes_dict:
            df_inter = pd.DataFrame(list(interagentes_dict.items()), columns=['Medicamento', 'Pacientes']).sort_values('Pacientes', ascending=True)
            fig_bar_inter = px.bar(
                df_inter, x='Pacientes', y='Medicamento', orientation='h',
                color_discrete_sequence=['#EF4444'], text='Pacientes'
            )
            fig_bar_inter.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300, yaxis_title=None, xaxis_title="Número de Pacientes em Uso")
            st.plotly_chart(fig_bar_inter, use_container_width=True)
        else:
            st.info("Nenhum medicamento interagente registrado nos cadastros atuais.")

    # GRÁFICOS - LINHA 2
    c_g3, c_g4 = st.columns(2)
    
    with c_g3:
        st.subheader("👴 Faixas Etárias Populacionais")
        faixa_nao_idoso = sum(1 for p in lista_pacientes if p['age'] < 60)
        faixa_idoso = sum(1 for p in lista_pacientes if 60 <= p['age'] < 80)
        faixa_muito_idoso = sum(1 for p in lista_pacientes if p['age'] >= 80)
        
        df_idade = pd.DataFrame({
            "Faixa Etária": ["Adultos (<60 anos)", "Idosos (60-79 anos)", "Idosos Mais Velhos (80+ anos)"],
            "Pacientes": [faixa_nao_idoso, faixa_idoso, faixa_muito_idoso]
        })
        fig_idade = px.bar(df_idade, x="Faixa Etária", y="Pacientes", color="Faixa Etária", text="Pacientes", color_discrete_sequence=['#3B82F6', '#F59E0B', '#8B5CF6'])
        fig_idade.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=300)
        st.plotly_chart(fig_idade, use_container_width=True)

    with c_g4:
        st.subheader("💊 Polifarmácia e Necessidade de Apoio")
        df_poli = pd.DataFrame({
            "Indicador": ["Polimedicados (≥5 meds)", "Uso de 1 a 4 meds", "Necessitam de Cuidador/Apoio"],
            "Quantidade": [polimedicados, total_pacientes - polimedicados, com_apoio]
        })
        fig_poli = px.bar(df_poli, x="Indicador", y="Quantidade", color="Indicador", text="Quantidade", color_discrete_sequence=['#EC4899', '#10B981', '#6366F1'])
        fig_poli.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=300)
        st.plotly_chart(fig_poli, use_container_width=True)

# ==============================================================================
# 8. MODO 2: FICHA DO PACIENTE
# ==============================================================================
else:
    conn = get_db_connection()
    pacientes_raw = conn.execute("SELECT * FROM pacientes ORDER BY status ASC, name ASC").fetchall()
    
    if not pacientes_raw:
        st.warning("Cadastre um paciente na barra lateral ou importe os dados do projeto.")
        conn.close()
        st.stop()

    lista_pacientes = [dict(p) for p in pacientes_raw]
    opcoes_pacientes = [f"⚪ {pt['name']} (ALTA)" if pt['status'] == 'Alta' else f"🟢 {pt['name']}" for pt in lista_pacientes]
    
    paciente_sel_index = st.sidebar.radio("Selecione o paciente:", range(len(opcoes_pacientes)), format_func=lambda i: opcoes_pacientes[i])
    p = lista_pacientes[paciente_sel_index]
    
    rni_rows = conn.execute("SELECT * FROM historico_rni WHERE patient_id = ? ORDER BY date DESC", (p['id'],)).fetchall()
    historico_rni = [dict(r) for r in rni_rows]
    
    em_alta = (p['status'] == 'Alta')

    # CABEÇALHO E EDIÇÃO DOS DADOS
    col_titulo, col_edit_btn, col_status_btn = st.columns([3, 1, 1])
    with col_titulo:
        st.markdown(f"# {'<span style=\"color: #94A3B8;\">👤 ' + p['name'] + ' (Alta Terapêutica)</span>' if em_alta else '👤 ' + p['name']}", unsafe_allow_html=True)

    with col_edit_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.popover("✏️ Editar Paciente", use_container_width=True):
            st.markdown("### Alterar Dados do Paciente")
            with st.form("form_edit_paciente"):
                edit_nome = st.text_input("Nome:", value=p['name'])
                edit_idade = st.number_input("Idade:", value=int(p['age']))
                edit_contato = st.text_input("Contato:", value=p['contact'])
                edit_indicacao = st.selectbox("Indicação:", ["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"], index=["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"].index(p['indication']) if p['indication'] in ["Fibrilação Atrial", "TVP/EP", "Prótese Valvar Metálica", "Outra"] else 0)
                edit_target = st.selectbox("Faixa Alvo:", ["2.0-3.0", "2.5-3.5", "1.5-2.0"], index=["2.0-3.0", "2.5-3.5", "1.5-2.0"].index(p['target']))
                edit_level = st.selectbox("Complexidade:", ["Baixo", "Médio", "Alto"], index=["Baixo", "Médio", "Alto"].index(p['level']))
                edit_dose = st.number_input("Dose Semanal Total (mg):", value=float(p['weekly_dose']), step=2.5)
                edit_apoio = st.selectbox("Necessita de Apoio/Cuidador?", ["Não", "Sim"], index=0 if p['needs_support'] == "Não" else 1)
                
                if st.form_submit_button("Atualizar Cadastro"):
                    conn.execute("""
                        UPDATE pacientes SET name=?, age=?, contact=?, indication=?, target=?, level=?, weekly_dose=?, needs_support=?
                        WHERE id=?
                    """, (edit_nome, edit_idade, edit_contato, edit_indicacao, edit_target, edit_level, edit_dose, edit_apoio, p['id']))
                    conn.commit()
                    conn.close()
                    st.success("Dados atualizados!")
                    st.rerun()

    with col_status_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Alternar Status", use_container_width=True):
            novo_st = 'Ativo' if em_alta else 'Alta'
            conn.execute("UPDATE pacientes SET status=? WHERE id=?", (novo_st, p['id']))
            conn.commit()
            conn.close()
            st.rerun()

    # CARTÕES DE INFORMAÇÕES
    col_info1, col_info2, col_info3 = st.columns([2, 2, 2])
    try:
        min_alvo, max_alvo = map(float, p['target'].split('-'))
    except Exception:
        min_alvo, max_alvo = 2.0, 3.0

    ttr_valor = calcular_ttr_rosendaal(historico_rni, min_alvo, max_alvo)
    ttr_direto, exames_na_faixa, total_exames = calcular_ttr_direto(historico_rni, min_alvo, max_alvo)

    cor_ttr, bg_badge, status_ttr = ("#64748B", "#F1F5F9", "Alta") if em_alta else (("#10B981", "#ECFDF5", "Estável") if ttr_valor >= 70.0 else (("#F59E0B", "#FFFBEB", "Alerta") if ttr_valor >= 60.0 else ("#EF4444", "#FEF2F2", "Crítico")))
    level_class = "level-alta" if em_alta else ("level-baixo" if p['level'] == "Baixo" else "level-alto" if p['level'] == "Alto" else "level-medio")

    tag_idoso = " (Idoso 80+)" if p['age'] >= 80 else (" (Idoso 60+)" if p['age'] >= 60 else "")

    with col_info1:
        st.markdown(f"""
        <div class="patient-card">
            <div class="info-label">Dados Demográficos</div>
            <div class="info-value">Idade: {p['age']} anos{tag_idoso}</div>
            <div class="info-value">Contato: {p['contact'] or 'Não informado'}</div>
            <div class="info-value">Necessita Apoio: <b>{p['needs_support']}</b></div>
            <div class="info-label" style="margin-top: 8px;">Complexidade</div>
            <div><span class="badge-level {level_class}">{ 'ALTA' if em_alta else p['level'] }</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_info2:
        qtd_m = contar_medicamentos(p['meds'])
        st.markdown(f"""
        <div class="patient-card">
            <div class="info-label">Manejo Terapêutico</div>
            <div class="info-value">Indicação: {p['indication']}</div>
            <div class="info-value">Faixa Alvo: {p['target']}</div>
            <div class="info-value">Dose Semanal: {p['weekly_dose']} mg</div>
            <div class="info-value">Polifarmácia: <b>{'Sim (' + str(qtd_m) + ' meds)' if qtd_m >= 5 else 'Não (' + str(qtd_m) + ' meds)'}</b></div>
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

    # GRÁFICO DE TENDÊNCIA DE RNI
    col_grafico, col_novo_rni = st.columns([2, 1])
    with col_grafico:
        st.subheader("📈 Tendência Temporal do RNI")
        historico_rni_validos = [e for e in historico_rni if e.get('value') is not None]
        
        if historico_rni_validos:
            df_chart = pd.DataFrame(historico_rni_validos)
            df_chart['date'] = pd.to_datetime(df_chart['date'])
            df_chart['value'] = df_chart['value'].astype(float)
            df_chart = df_chart.sort_values('date')

            def classificar_ponto(v):
                if min_alvo <= v <= max_alvo:
                    return '#10B981'
                elif v < min_alvo:
                    return '#EF4444'
                else:
                    return '#991B1B'

            colors = [classificar_ponto(v) for v in df_chart['value']]

            fig_rni = go.Figure()
            fig_rni.add_trace(go.Scatter(
                x=df_chart['date'],
                y=df_chart['value'],
                mode='lines+markers',
                line=dict(color='#64748B', width=2),
                marker=dict(size=10, color=colors, line=dict(width=1.5, color='#FFFFFF')),
                name='RNI'
            ))

            layout_config = {
                "template": "plotly_white",
                "font": {"family": "Inter, sans-serif", "size": 12, "color": "#1E293B"},
                "margin": {"l": 40, "r": 20, "t": 30, "b": 40},
                "height": 300,
                "hovermode": "x unified",
                "xaxis": {"showgrid": True, "gridcolor": "#F1F5F9", "linecolor": "#CBD5E1"},
                "yaxis": {"showgrid": True, "gridcolor": "#F1F5F9", "linecolor": "#CBD5E1", "zeroline": False},
                "shapes": [
                    {"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": min_alvo, "y1": max_alvo, "fillcolor": "rgba(16, 185, 129, 0.20)", "line": {"width": 0}, "layer": "below"},
                    {"type": "line", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": min_alvo, "y1": min_alvo, "line": {"color": "#10B981", "width": 1.5, "dash": "dot"}},
                    {"type": "line", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": max_alvo, "y1": max_alvo, "line": {"color": "#10B981", "width": 1.5, "dash": "dot"}}
                ]
            }

            fig_rni.update_layout(layout_config)
            st.plotly_chart(fig_rni, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Nenhum histórico numérico de RNI registrado.")

    with col_novo_rni:
        st.subheader("➕ Registrar RNI")
        with st.form("form_novo_rni_avulso", clear_on_submit=True):
            data_avulsa = st.date_input("Data do Exame", value=datetime.today())
            rni_avulso = st.number_input("Valor de RNI", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
            if st.form_submit_button("Salvar Exame"):
                conn.execute("""
                    INSERT INTO historico_rni (patient_id, date, value, status, obs)
                    VALUES (?, ?, ?, ?, ?)
                """, (p['id'], data_avulsa.strftime("%Y-%m-%d"), float(rni_avulso), "Normal", ""))
                conn.commit()
                conn.close()
                st.success("RNI registrado!")
                st.rerun()

    st.markdown("---")

    # ABAS DO PACIENTE
    tab_anamnese, tab_tabela, tab_meds, tab_evolucao = st.tabs([
        "🔍 Roteiro de Decisão & Consulta", 
        "📋 Histórico & Edição de RNI", 
        "💊 Medicamentos em Casa & Alertas",
        "📝 Evolução Farmacêutica (MV PEP)"
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
                sinais_sangramento = st.multiselect("Sinais de Sangramento Notados:", ["Nenhum", "Gengivorragia", "Epistaxe", "Equimoses/Hematomas", "Hematúria", "Melena/Hematoquezia", "Outros"])
                esquecimento = st.selectbox("Omitiu ou esqueceu doses recentemente?", ["Não", "Sim (1 dose)", "Sim (2 ou mais doses)"])
                mudanca_diet = st.selectbox("Alteração expressiva na dieta (folhas verdes/chás)?", ["Não", "Sim - Aumentou consumo", "Sim - Reduziu consumo"])
                
            with c2:
                st.markdown("**2. Mudanças na Farmacoterapia e Conduta**")
                novos_meds = st.text_input("Novos medicamentos iniciados por outros médicos:", value="Nenhum")
                nova_dose_semanal = st.number_input("Nova Dose Semanal Proposta (mg):", value=float(p['weekly_dose']), step=2.5)
                retorno_dias = st.selectbox("Aprazamento do Retorno:", ["7 dias", "14 dias", "21 dias", "30 dias", "60 dias", "90 dias"])
                orientacoes_obs = st.text_area("Orientações Clínicas e Observações Adicionais:", placeholder="Escreva observações específicas para o plano de cuidado...")

            if st.form_submit_button("Gerar e Salvar Evolução Farmacêutica"):
                data_hoje_str = datetime.today().strftime("%Y-%m-%d")
                
                # Salva RNI caso checado
                if registrar_rni_hoje:
                    conn.execute("""
                        INSERT INTO historico_rni (patient_id, date, value, status, obs)
                        VALUES (?, ?, ?, ?, ?)
                    """, (p['id'], data_hoje_str, float(rni_hoje_valor), "Consulta", "Registrado via Anamnese"))
                    conn.commit()

                # Atualiza dose no cadastro do paciente
                conn.execute("UPDATE pacientes SET weekly_dose=? WHERE id=?", (nova_dose_semanal, p['id']))
                conn.commit()

                # Estrutura do Texto SOAP para Prontuário
                sang_texto = ", ".join(sinais_sangramento) if sinais_sangramento else "Nenhum"
                
                texto_soap = f"""[EVOLUÇÃO FARMA CÊUTICA - AMBULATÓRIO DE ANTICOAGULAÇÃO]
Data: {datetime.today().strftime('%d/%m/%Y')}

S (SUBJETIVO):
- Adesão/Esquecimento: {esquecimento}
- Sinais de Sangramento Relatados: {sang_texto}
- Alterações Diéticas Recentes: {mudanca_diet}
- Introdução de Novos Medicamentos: {novos_meds}

O (OBJETIVO):
- Paciente em uso de Varfarina para {p['indication']}. Faixa Alvo RNI: {p['target']}.
- Dose Semanal Anterior: {p['weekly_dose']} mg.
- RNI Atual ({data_hoje_str}): {rni_hoje_valor if registrar_rni_hoje else 'Não informado/Coletado em outro serviço'}.
- TTR Acumulado (Rosendaal): {ttr_valor:.1f}%.

A (AVALIAÇÃO):
- Controle do RNI: {'Adequado/Na faixa alvo' if min_alvo <= (rni_hoje_valor if registrar_rni_hoje else 2.5) <= max_alvo else 'Fora do Alvo Terapêutico'}.
- Análise de Riscos: Interações e sinais de segurança avaliados na consulta.

P (PLANO / CONDUTA):
- Nova Dose Semanal Ajustada/Mantida: {nova_dose_semanal} mg/semana.
- Orientações de Adesão e Sinais de Alerta Reforçados com o Paciente/Cuidador.
- Observações: {orientacoes_obs if orientacoes_obs else 'Sem observações adicionais.'}
- Retorno Agendado: Em {retorno_dias}.
"""
                conn.execute("UPDATE pacientes SET evolution=? WHERE id=?", (texto_soap, p['id']))
                conn.commit()
                conn.close()
                st.success("Evolução gerada e armazenada no histórico!")
                st.rerun()

    # 2. TABELA DE HISTÓRICO DE RNI
    with tab_tabela:
        st.markdown("### 📋 Histórico Registrado de Exames de RNI")
        if historico_rni:
            df_tab = pd.DataFrame(historico_rni)
            st.dataframe(df_tab[['id', 'date', 'value', 'status', 'obs']], use_container_width=True)
            
            with st.expander("🗑️ Excluir Registro de RNI"):
                id_excluir = st.number_input("Digite o ID do exame a remover:", min_value=1, step=1)
                if st.button("Confirmar Exclusão"):
                    conn.execute("DELETE FROM historico_rni WHERE id=? AND patient_id=?", (id_excluir, p['id']))
                    conn.commit()
                    conn.close()
                    st.success("Exame excluído com sucesso.")
                    st.rerun()
        else:
            st.info("Nenhum histórico cadastrado para este paciente.")

    # 3. MEDICAMENTOS EM CASA E ALERTAS
    with tab_meds:
        st.markdown("### 💊 Lista de Medicamentos & Interações com Varfarina")
        
        with st.form("form_update_meds"):
            novos_meds_texto = st.text_area("Editar Lista de Medicamentos (separados por vírgula ou linha):", value=p['meds'] or "", height=120)
            if st.form_submit_button("Atualizar Lista de Medicamentos"):
                conn.execute("UPDATE pacientes SET meds=? WHERE id=?", (novos_meds_texto, p['id']))
                conn.commit()
                conn.close()
                st.success("Lista de medicamentos atualizada!")
                st.rerun()

        interacoes_detectadas = checar_interacoes(p['meds'])
        if interacoes_detectadas:
            st.markdown("#### ⚠️ Interações Relevantes Identificadas")
            for inter in interacoes_detectadas:
                classe_alert = "alert-high" if inter['risco'] == "Alta" else "alert-mod"
                st.markdown(f"""
                <div class="alert-card {classe_alert}">
                    <b>Fármaco:</b> {inter['medicamento']} (Risco: {inter['risco']})<br>
                    <b>Efeito Terapêutico:</b> {inter['efeito']}<br>
                    <b>Conduta Clínica Recomendada:</b> {inter['conduta']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("Nenhuma interação clássica de alto risco detectada na lista informada.")

    # 4. EVOLUÇÃO FARMA CÊUTICA (PRONTUÁRIO)
    with tab_evolucao:
        st.markdown("### 📝 Registro de Evolução (Copiar para MV PEP)")
        if p['evolution']:
            st.text_area("Texto da Última Consulta:", value=p['evolution'], height=350)
        else:
            st.info("Nenhuma evolução registrada recentemente. Preencha a aba 'Roteiro de Decisão & Consulta' para gerar o texto do prontuário.")

    conn.close()
