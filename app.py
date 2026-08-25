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
        
        # Limpa as tabelas atuais para substituir pelos dados importados
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
    
    # 1. Exportar
    json_backup = exportar_projeto_json()
    nome_arq_backup = f"backup_ambulatorio_rni_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    st.download_button(
        label="📥 Exportar Backup do Projeto",
        data=json_backup,
        file_name=nome_arq_backup,
        mime="application/json",
        use_container_width=True,
        help="Baixa um arquivo com todos os dados atuais do sistema para guardar no seu computador/Documentos."
    )
    
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    
    # 2. Importar
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
        st.warning("Nenhum paciente cadastrado no banco de dados. Utilize a opção na barra lateral ou importe um projeto salvo.")
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
    
    # Contar indicações
    indicacoes_dict = {}
    for p in lista_pacientes:
        ind = p['indication'] or "Não especificada"
        indicacoes_dict[ind] = indicacoes_dict.get(ind, 0) + 1
    
    # Mostrar total de indicações diferentes
    m5.metric("Indicações Clínicas", f"{len(indicacoes_dict)} tipos")

    st.markdown("---")

    # GRÁFICO DE INDICAÇÕES CLÍNICAS
    st.subheader("🏥 Indicações Clínicas dos Pacientes")
    
    df_indicacoes = pd.DataFrame(list(indicacoes_dict.items()), columns=['Indicação', 'Pacientes'])
    df_indicacoes = df_indicacoes.sort_values('Pacientes', ascending=False)
    
    col_ind1, col_ind2 = st.columns(2)
    
    with col_ind1:
        # Gráfico de barras
        fig_ind = px.bar(
            df_indicacoes,
            x='Indicação',
            y='Pacientes',
            color='Indicação',
            text='Pacientes',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_ind.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            yaxis_title="Número de Pacientes",
            xaxis_title=""
        )
        st.plotly_chart(fig_ind, use_container_width=True)
    
    with col_ind2:
        # Gráfico de pizza
        fig_ind_pie = px.pie(
            df_indicacoes,
            names='Indicação',
            values='Pacientes',
            color='Indicação',
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.4
        )
        fig_ind_pie.update_traces(textinfo='percent+label')
        fig_ind_pie.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=300
        )
        st.plotly_chart(fig_ind_pie, use_container_width=True)

    st.markdown("---")
    
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
        st.subheader("💊 Distribuição por Quantidade de Medicamentos")
        
        # Contar pacientes por quantidade de medicamentos
        pacientes_1_med = 0
        pacientes_2_meds = 0
        pacientes_3_meds = 0
        pacientes_4_meds = 0
        pacientes_5_ou_mais = 0
        
        for p in lista_pacientes:
            qtd_meds_paciente = contar_medicamentos(p['meds'] or "")
            if qtd_meds_paciente == 1:
                pacientes_1_med += 1
            elif qtd_meds_paciente == 2:
                pacientes_2_meds += 1
            elif qtd_meds_paciente == 3:
                pacientes_3_meds += 1
            elif qtd_meds_paciente == 4:
                pacientes_4_meds += 1
            elif qtd_meds_paciente >= 5:
                pacientes_5_ou_mais += 1
        
        df_distribuicao_meds = pd.DataFrame({
            "Quantidade de Medicamentos": ["1 medicamento", "2 medicamentos", "3 medicamentos", "4 medicamentos", "5 ou mais medicamentos"],
            "Pacientes": [pacientes_1_med, pacientes_2_meds, pacientes_3_meds, pacientes_4_meds, pacientes_5_ou_mais]
        })
        
        fig_distribuicao_meds = px.bar(
            df_distribuicao_meds, 
            x="Quantidade de Medicamentos", 
            y="Pacientes", 
            color="Quantidade de Medicamentos", 
            text="Pacientes",
            color_discrete_sequence=['#10B981', '#3B82F6', '#F59E0B', '#EC4899', '#EF4444']
        )
        fig_distribuicao_meds.update_layout(
            showlegend=False, 
            margin=dict(t=20, b=20, l=20, r=20), 
            height=300,
            yaxis_title="Número de Pacientes",
            xaxis_title=""
        )
        st.plotly_chart(fig_distribuicao_meds, use_container_width=True)

     with c_g5:
        st.markdown("---")
            st.subheader("♥️ Indicação Clínicas")
         df_indicacoes = pd.DataFrame(list(indicacoes_dict.items()), columns=['Indicação', 'Pacientes'])
    df_indicacoes = df_indicacoes.sort_values('Pacientes', ascending=False)
    
    col_ind1, col_ind2 = st.columns(2)
    
    with col_ind1:
        # Gráfico de barras
        fig_ind = px.bar(
            df_indicacoes,
            x='Indicação',
            y='Pacientes',
            color='Indicação',
            text='Pacientes',
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_ind.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            yaxis_title="Número de Pacientes",
            xaxis_title=""
        )
        st.plotly_chart(fig_ind, use_container_width=True)
    
    with col_ind2:
        # Gráfico de pizza
        fig_ind_pie = px.pie(
            df_indicacoes,
            names='Indicação',
            values='Pacientes',
            color='Indicação',
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.4
        )
        fig_ind_pie.update_traces(textinfo='percent+label')
        fig_ind_pie.update_layout(
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20),
            height=300
        )
        st.plotly_chart(fig_ind_pie, use_container_width=True)
         
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
                nova_dose_semanal = st.number_input("Nova Dose Semanal Total (mg):", value=float(p['weekly_dose']), step=2.5)
            with c4:
                retorno_dias = st.select_slider("Retorno Agendado:", options=["7 dias", "14 dias", "21 dias", "30 dias", "37 dias", "Alta Terapêutica"], value="30 dias")
                obs_clinicas = st.text_area("Observações Adicionais:", placeholder="Orientações e detalhes adicionais...")

            if st.form_submit_button("💾 Gerar Evolução Narrativa em Texto Corrido"):
                data_hoje_str = datetime.now().strftime("%Y-%m-%d")
                data_hoje_fmt = datetime.now().strftime("%d/%m/%Y às %H:%M")
                
                if registrar_rni_hoje:
                    conn.execute("""
                        INSERT INTO historico_rni (patient_id, date, value, status, obs)
                        VALUES (?, ?, ?, ?, ?)
                    """, (p['id'], data_hoje_str, float(rni_hoje_valor), "Normal", ""))
                    conn.commit()
                
                rni_rows_updated = conn.execute("SELECT * FROM historico_rni WHERE patient_id = ? ORDER BY date DESC", (p['id'],)).fetchall()
                historico_rni_up = [dict(r) for r in rni_rows_updated]
                
                ttr_atual = calcular_ttr_rosendaal(historico_rni_up, min_alvo, max_alvo)
                ttr_dir, ex_f, tot_ex = calcular_ttr_direto(historico_rni_up, min_alvo, max_alvo)
                rni_validos = [e for e in historico_rni_up if e.get('value') is not None]
                ult_rni_val = rni_validos[0]['value'] if rni_validos else "N/A"
                
                interacoes_casa = checar_interacoes(p['meds'] or "")
                texto_interacoes_casa = ""
                if interacoes_casa:
                    meds_alerta = [f"{item['medicamento']} ({item['efeito']})" for item in interacoes_casa]
                    texto_interacoes_casa = (
                        f" Em análise da farmacoterapia de uso domiciliário, identificou-se o uso de medicamento(s) com potencial de alterar o valor do RNI: "
                        f"{'; '.join(meds_alerta)}. Foi reforçada a necessidade de monitorização e alinhada a conduta recomendada: "
                        f"{'; '.join([item['conduta'] for item in interacoes_casa])}."
                    )
                
                apoio_txt = "necessita de apoio/cuidador para tomada de medicamentos" if p['needs_support'] == "Sim" else "possui autonomia para tomada de medicamentos"
                soap_texto = (
                    f"Evolução Farmacêutica - Ambulatório de Anticoagulação Oral ({data_hoje_fmt}). "
                    f"Paciente {p['name']}, {p['age']} anos ({'idoso' if p['age']>=60 else 'adulto'}), que {apoio_txt}, em acompanhamento ambulatorial para manejo de anticoagulação por {p['indication']}. "
                    f"Ao interrogatório clínico, nega intercorrências graves, relatando em relação a sangramentos: {sinais_sangramento.lower()} e sobre sintomas tromboembólicos: {sinais_trombose.lower()}. "
                    f"Quanto ao perfil de adesão farmacoterapêutica, refere {esquecimento.lower()}, associado a {alteracao_dieta.lower()} no padrão alimentar habitual. "
                    f"Em relação à farmacoterapia concomitante, observa-se {interacao_med.lower()}{f' ({detalhe_interacao})' if detalhe_interacao else ''}.{texto_interacoes_casa} "
                    f"{f'Informações complementares relatadas: {obs_clinicas}. ' if obs_clinicas else ''}"
                    f"Ao exame objetivo e dados laboratoriais, aponta-se RNI atual de {ult_rni_val} para uma faixa alvo terapêutica estabelecida de {p['target']}. "
                    f"O cálculo de controle de estabilidade indica Time in Therapeutic Range (TTR) pelo Método de Rosendaal de {ttr_atual:.1f}% e TTR Direto de {ttr_dir:.1f}% ({ex_f} de {tot_ex} exames na faixa). "
                    f"A dose semanal total prévia utilizada pelo paciente era de {p['weekly_dose']} mg. "
                    f"Em avaliação farmacêutica clínica, o controle da anticoagulação é classificado como {status_ttr.upper()}, estando o RNI "
                    f"{'adequado e dentro do intervalo alvo' if (ult_rni_val != 'N/A' and min_alvo <= float(ult_rni_val) <= max_alvo) else 'fora da faixa ideal recomendada'}. "
                    f"Frente aos achados e perfil de segurança, adota-se como plano de conduta: {decisao_dose.lower()}, fixando a nova dose semanal ajustada em {nova_dose_semanal} mg. "
                    f"O paciente foi devidamente orientado quanto à correta distribuição diária da dose, reconhecimento de sinais de alarme para sangramentos ou trombose, e agendamento de retorno ambulatorial pactuado para {retorno_dias}. "
                    f"Atendimento finalizado e registrado por Farmacêutico Clínico."
                )
                
                novo_st = 'Alta' if (decisao_dose == "Alta por estabilidade do TTR" or retorno_dias == "Alta Terapêutica") else p['status']
                
                conn.execute("""
                    UPDATE pacientes SET evolution=?, weekly_dose=?, status=? WHERE id=?
                """, (soap_texto, nova_dose_semanal, novo_st, p['id']))
                conn.commit()
                conn.close()
                st.success("Evolução gerada com sucesso!")
                st.rerun()

    # 2. HISTÓRICO DE COLETAS
    with tab_tabela:
        st.subheader("📋 Histórico de Coletas - Edição e Gestão")
        
        with st.expander("🚨 Registrar Ausência / Paciente Faltou à Consulta", expanded=False):
            with st.form("form_registra_falta"):
                data_falta = st.date_input("Data da Consulta Não Comparecida:", value=datetime.today())
                obs_falta = st.text_input("Observação da Falta:", value="Paciente faltou à consulta agendada. Sem justificativa prévia.")
                if st.form_submit_button("Registrar Ausência"):
                    conn.execute("""
                        INSERT INTO historico_rni (patient_id, date, value, status, obs)
                        VALUES (?, ?, NULL, ?, ?)
                    """, (p['id'], data_falta.strftime("%Y-%m-%d"), "Falta", obs_falta))
                    conn.commit()
                    conn.close()
                    st.warning("Falta registrada no histórico!")
                    st.rerun()

        st.markdown("---")

        if historico_rni:
            for item in historico_rni:
                c_data, c_val, c_edit, c_del = st.columns([2, 3, 1, 1])
                with c_data:
                    st.write(f"📅 **{item['date']}**")
                with c_val:
                    if item['status'] == 'Falta' or item['value'] is None:
                        st.markdown(f"⚠️ <span style='color: #DC2626; font-weight: 600;'>PACIENTE FALTOU À CONSULTA</span><br><small style='color: #64748B;'>Obs: {item['obs'] or 'Sem registro'}</small>", unsafe_allow_html=True)
                    else:
                        st.write(f"🩸 **RNI: {item['value']}**")
                with c_edit:
                    if item['value'] is not None:
                        with st.popover("✏️ Editar"):
                            with st.form(f"form_edit_rni_{item['id']}"):
                                nova_d = st.date_input("Data:", value=datetime.strptime(item['date'], "%Y-%m-%d"))
                                novo_v = st.number_input("Valor RNI:", value=float(item['value']), step=0.1)
                                if st.form_submit_button("Atualizar"):
                                    conn.execute("UPDATE historico_rni SET date=?, value=? WHERE id=?", (nova_d.strftime("%Y-%m-%d"), float(novo_v), item['id']))
                                    conn.commit()
                                    conn.close()
                                    st.success("Atualizado!")
                                    st.rerun()
                with c_del:
                    if st.button("🗑️ Excluir", key=f"btn_del_rni_{item['id']}"):
                        conn.execute("DELETE FROM historico_rni WHERE id=?", (item['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Registro removido!")
                        st.rerun()
                st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
        else:
            st.info("Sem exames ou ausências registradas.")

    # 3. MEDICAMENTOS EM CASA E ALERTAS
    with tab_meds:
        st.subheader("💊 Medicamentos de Uso Domiciliar e Alertas Clínicos")
        st.caption("Cadastre os medicamentos de uso contínuo. Separe os nomes por vírgula para possibilitar a contagem de Polifarmácia e detecção automática de interações.")
        
        with st.form("form_edit_meds"):
            meds_texto = st.text_area("Relação de Medicamentos em Uso em Casa:", value=p['meds'] or '', height=120, placeholder="Ex: Amiodarona 200mg, Omeprazol 20mg, Losartana 50mg, Paracetamol 750mg...")
            if st.form_submit_button("💾 Salvar Relação de Medicamentos"):
                conn.execute("UPDATE pacientes SET meds=? WHERE id=?", (meds_texto, p['id']))
                conn.commit()
                conn.close()
                st.success("Medicamentos atualizados!")
                st.rerun()

        st.markdown("---")
        st.markdown("### ⚠️ Rastreio Automático de Interações com a Varfarina")
        
        interacoes = checar_interacoes(p['meds'] or '')
        if interacoes:
            for inter in interacoes:
                classe_card = "alert-high" if inter['risco'] == "Alta" else "alert-mod"
                st.markdown(f"""
                <div class="alert-card {classe_card}">
                    <div style="font-size: 1rem; font-weight: 700;">🚨 {inter['medicamento']} — Risco de Interação {inter['risco'].upper()}</div>
                    <div style="margin-top: 4px; font-size: 0.9rem;"><b>Efeito no RNI / Clínico:</b> {inter['efeito']}</div>
                    <div style="margin-top: 2px; font-size: 0.9rem;"><b>Recomendação / Conduta:</b> {inter['conduta']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ Nenhuma interação medicamentosa de alto risco identificada na lista atual.")

    # 4. EVOLUÇÃO FARMACÊUTICA (MV PEP)
    with tab_evolucao:
        st.subheader("📝 Evolução Farmacêutica Narrativa (Padrão MV PEP)")
        st.caption("Você pode editar o texto abaixo diretamente para acrescentar dados antes de copiar para o prontuário eletrônico.")
        
        texto_evol_atual = p['evolution'] or ''
        novo_texto_editado = st.text_area("Texto Corrido Editável:", value=texto_evol_atual, height=350)
        
        if st.button("💾 Salvar Alterações no Texto"):
            conn.execute("UPDATE pacientes SET evolution=? WHERE id=?", (novo_texto_editado, p['id']))
            conn.commit()
            conn.close()
            st.success("Texto da evolução atualizado!")

        # EXCLUSÃO DO PACIENTE
        st.markdown("<br><br><hr>", unsafe_allow_html=True)
        st.markdown("### ⚙️ Gestão do Paciente")
        with st.expander("🚨 Excluir Paciente do Serviço de Farmácia Clínica", expanded=False):
            st.warning("⚠️ **Atenção:** A exclusão do paciente removerá todos os registros de RNI, evoluções e histórico ambulatorial de forma irreversível.")
            col_del_txt, col_del_btn = st.columns([3, 1])
            with col_del_txt:
                confirma_exclusao = st.checkbox(f"Estou ciente e desejo excluir o paciente {p['name']} definitivamente.")
            with col_del_btn:
                if st.button("🗑️ Excluir Paciente", type="primary", disabled=not confirma_exclusao, use_container_width=True):
                    conn.execute("DELETE FROM pacientes WHERE id=?", (p['id'],))
                    conn.commit()
                    conn.close()
                    st.success("Paciente excluído com sucesso!")
                    st.rerun()

    conn.close()
