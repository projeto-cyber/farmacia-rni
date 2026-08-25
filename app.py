import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import json
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile

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

class DatabaseError(Exception):
    """Erro personalizado para operações de banco de dados"""
    pass

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

def executar_query_segura(query, params=None):
    """Executa query com tratamento de erro e rollback"""
    conn = get_db_connection()
    try:
        if params:
            cursor = conn.execute(query, params)
        else:
            cursor = conn.execute(query)
        conn.commit()
        return cursor
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Erro no banco de dados: {str(e)}")
    finally:
        conn.close()

@st.cache_data(ttl=60)
def carregar_pacientes():
    """Carrega pacientes com cache para melhor performance"""
    conn = get_db_connection()
    pacientes = conn.execute("SELECT * FROM pacientes").fetchall()
    conn.close()
    return [dict(p) for p in pacientes]

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
# 6. FUNÇÕES DE SUGESTÃO DE DOSE E ALERTAS
# ==============================================================================
def sugerir_ajuste_dose(rni_atual, dose_atual, min_alvo, max_alvo):
    """
    Sugere ajuste de dose baseado no RNI atual
    Baseado nas diretrizes do ACCP (American College of Chest Physicians)
    """
    if rni_atual < 1.5:
        return {
            "acao": "Aumentar dose em 10-15%",
            "nova_dose": dose_atual * 1.15,
            "dose_extra": "Considerar dose de reforço",
            "retorno": "7 dias"
        }
    elif 1.5 <= rni_atual < min_alvo:
        return {
            "acao": "Aumentar dose em 5-10%",
            "nova_dose": dose_atual * 1.10,
            "dose_extra": None,
            "retorno": "14 dias"
        }
    elif min_alvo <= rni_atual <= max_alvo:
        return {
            "acao": "Manter dose atual",
            "nova_dose": dose_atual,
            "dose_extra": None,
            "retorno": "30 dias"
        }
    elif max_alvo < rni_atual <= 4.5:
        return {
            "acao": "Reduzir dose em 5-10%",
            "nova_dose": dose_atual * 0.90,
            "dose_extra": None,
            "retorno": "14 dias"
        }
    elif 4.5 < rni_atual <= 5.0:
        return {
            "acao": "Omitir 1 dose e reduzir 10%",
            "nova_dose": dose_atual * 0.90,
            "dose_extra": "Omitir próxima dose",
            "retorno": "7 dias"
        }
    else:  # RNI > 5.0
        return {
            "acao": "URGENTE - Avaliar suspensão temporária",
            "nova_dose": None,
            "dose_extra": "Contatar médico imediatamente",
            "retorno": "Imediato"
        }

def verificar_alertas_paciente(p, historico, min_alvo, max_alvo):
    """
    Verifica e retorna alertas importantes para o paciente
    """
    alertas = []
    
    # Verificar último RNI
    if historico and historico[0].get('value'):
        ultimo_rni = float(historico[0]['value'])
        
        if ultimo_rni > 5.0:
            alertas.append({
                "tipo": "critico",
                "mensagem": f"RNI CRÍTICO: {ultimo_rni} - Contatar médico imediatamente"
            })
        elif ultimo_rni > max_alvo + 1:
            alertas.append({
                "tipo": "alto",
                "mensagem": f"RNI elevado: {ultimo_rni} - Avaliar redução de dose"
            })
        elif ultimo_rni < min_alvo - 0.5:
            alertas.append({
                "tipo": "moderado",
                "mensagem": f"RNI abaixo do alvo: {ultimo_rni} - Risco de trombose"
            })
    
    # Verificar tempo desde última consulta
    if historico:
        ultima_data = datetime.strptime(historico[0]['date'], "%Y-%m-%d")
        dias_desde_ultima = (datetime.now() - ultima_data).days
        if dias_desde_ultima > 45:
            alertas.append({
                "tipo": "moderado",
                "mensagem": f"Paciente sem acompanhamento há {dias_desde_ultima} dias"
            })
    
    return alertas

# ==============================================================================
# 7. FUNÇÃO PARA GERAR RELATÓRIO PDF
# ==============================================================================
def gerar_relatorio_pdf(paciente, historico, ttr):
    """
    Gera relatório PDF do paciente para impressão
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        c = canvas.Canvas(tmp.name, pagesize=letter)
        width, height = letter
        
        # Cabeçalho
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"Relatório de Acompanhamento - {paciente['name']}")
        
        # Dados do paciente
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Idade: {paciente['age']} anos")
        c.drawString(50, height - 100, f"Indicação: {paciente['indication']}")
        c.drawString(50, height - 120, f"Faixa Alvo: {paciente['target']}")
        c.drawString(50, height - 140, f"TTR: {ttr:.1f}%")
        c.drawString(50, height - 160, f"Dose Semanal: {paciente['weekly_dose']} mg")
        
        # Histórico
        c.drawString(50, height - 200, "Histórico de RNI:")
        y_pos = height - 220
        for item in historico[:10]:  # últimos 10 exames
            if item.get('value'):
                c.drawString(70, y_pos, f"{item['date']}: RNI = {item['value']}")
            else:
                c.drawString(70, y_pos, f"{item['date']}: FALTA")
            y_pos -= 20
        
        c.save()
        return tmp.name

# ==============================================================================
# 8. SIDEBAR, NAVEGAÇÃO E EXPORTAR/IMPORTAR PROJETO
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
# 9. MODO 1: DASHBOARD POPULACIONAL
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
        fig_pie.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c_g2:
        st.subheader("⚠️ Top Fármacos de Uso Contínuo Interagentes")
        if interagentes_dict:
            df_inter = pd.DataFrame(list(interagentes_dict.items()), columns=['Medicamento', 'Pacientes']).sort_values('Pacientes', ascending=True)
            fig_bar_inter = px.bar(
                df_inter, x='Pacientes', y='Medicamento', orientation='h',
                color_discrete_sequence=['#EF4444'], text='Pacientes'
            )
            fig_bar_inter.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350, yaxis_title=None, xaxis_title="Número de Pacientes em Uso")
            st.plotly_chart(fig_bar_inter, use_container_width=True)
        else:
            st.info("Nenhum medicamento interagente registrado nos cadastros atuais.")

    st.markdown("---")

    # GRÁFICOS - LINHA 2 (FAIXAS ETÁRIAS)
    st.subheader("👥 Distribuição por Faixa Etária")
    c_g3, c_g4 = st.columns(2)
    
    with c_g3:
        # Gráfico de faixas etárias detalhado
        faixa_adultos = sum(1 for p in lista_pacientes if p['age'] < 60)
        faixa_idosos = sum(1 for p in lista_pacientes if 60 <= p['age'] < 80)
        faixa_muito_idosos = sum(1 for p in lista_pacientes if p['age'] >= 80)
        
        df_idade = pd.DataFrame({
            "Faixa Etária": ["Adultos (<60 anos)", "Idosos (60-79 anos)", "Idosos 80+ (≥80 anos)"],
            "Pacientes": [faixa_adultos, faixa_idosos, faixa_muito_idosos]
        })
        
        fig_idade = px.bar(
            df_idade, 
            x="Faixa Etária", 
            y="Pacientes", 
            color="Faixa Etária", 
            text="Pacientes",
            color_discrete_sequence=['#3B82F6', '#F59E0B', '#8B5CF6'],
            title="Distribuição por Faixa Etária"
        )
        fig_idade.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=350)
        st.plotly_chart(fig_idade, use_container_width=True)

    with c_g4:
        # Gráfico de pizza para faixas etárias
        fig_idade_pie = px.pie(
            df_idade, 
            names='Faixa Etária', 
            values='Pacientes',
            color='Faixa Etária',
            color_discrete_sequence=['#3B82F6', '#F59E0B', '#8B5CF6'],
            hole=0.4,
            title="Proporção por Faixa Etária"
        )
        fig_idade_pie.update_traces(textinfo='percent+label')
        fig_idade_pie.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=350)
        st.plotly_chart(fig_idade_pie, use_container_width=True)

    st.markdown("---")

    # GRÁFICOS - LINHA 3 (POLIFARMÁCIA E INTERAÇÕES)
    st.subheader("💊 Polifarmácia e Interações Medicamentosas")
    c_g5, c_g6 = st.columns(2)
    
    with c_g5:
        # Gráfico de polifarmácia
        nao_polimedicados = total_pacientes - polimedicados
        df_poli = pd.DataFrame({
            "Categoria": ["Polimedicados (≥5 meds)", "Não Polimedicados (<5 meds)"],
            "Pacientes": [polimedicados, nao_polimedicados]
        })
        
        fig_poli = px.pie(
            df_poli,
            names='Categoria',
            values='Pacientes',
            color='Categoria',
            color_discrete_sequence=['#EF4444', '#10B981'],
            hole=0.4,
            title="Distribuição de Polifarmácia"
        )
        fig_poli.update_traces(textinfo='percent+label')
        fig_poli.update_layout(showlegend=False, margin=dict(t=40, b=20, l=20, r=20), height=350)
        st.plotly_chart(fig_poli, use_container_width=True)

    with c_g6:
        # Gráfico de pacientes com interações medicamentosas
        pacientes_com_interacao
