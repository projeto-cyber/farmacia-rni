"""
Sistema de Controle de RNI - Ambulatório de Anticoagulação
==========================================================
Sistema para gerenciamento de pacientes em acompanhamento ambulatorial
de anticoagulação oral com varfarina.

Versão: 6.0
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
DB_NAME = "ambulatorio_rni.db"
APP_VERSION = "6.0"

# Cores do tema
COR_PRIMARIA = "#7A2331"
COR_SECUNDARIA = "#0F6E6A"
COR_ALERTA = "#C9821A"
COR_TEXTO = "#14181F"
COR_TEXTO_SUAVE = "#4B5563"
COR_FUNDO = "#F7F9FA"
COR_BORDA = "#E4E7EB"

st.set_page_config(
    page_title="Controle de RNI - Ambulatório",
    page_icon="🩸",
    layout="wide"
)

# ==============================================================================
# ESTILIZAÇÃO CSS
# ==============================================================================
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        font-size: 16px;
        color: {COR_TEXTO};
    }}
    
    [data-testid="stSidebar"] {{
        background-color: {COR_FUNDO};
        border-right: 1px solid {COR_BORDA};
    }}
    
    .flash-card {{
        background: #FFFFFF;
        border: 1px solid {COR_BORDA};
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 15px;
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    .flash-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.12);
    }}
    
    .patient-card {{
        background: #FFFFFF;
        border: 2px solid {COR_BORDA};
        border-radius: 12px;
        padding: 15px 20px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.2s;
    }}
    .patient-card:hover {{
        border-color: {COR_SECUNDARIA};
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transform: translateX(5px);
    }}
    .patient-card.active {{
        border-color: {COR_SECUNDARIA};
        background-color: #E6F5F4;
    }}
    
    .info-label {{
        font-size: 0.75rem;
        font-weight: 600;
        color: {COR_TEXTO_SUAVE};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }}
    
    .info-value {{
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 8px;
    }}
    
    .alert-card {{
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid;
    }}
    .alert-high {{ background-color: #FBEAEC; border-color: {COR_PRIMARIA}; }}
    .alert-mod {{ background-color: #FFF6E9; border-color: {COR_ALERTA}; }}
    
    .badge-poli {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }}
    .poli-sim {{ background-color: #FBEAEC; color: {COR_PRIMARIA}; }}
    .poli-nao {{ background-color: #E3F2EF; color: {COR_SECUNDARIA}; }}
    .poli-varfarina {{ background-color: #EEF1F4; color: #475569; }}
    
    .stButton > button[kind="primary"] {{
        background-color: {COR_PRIMARIA} !important;
        border-color: {COR_PRIMARIA} !important;
    }}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# CONSTANTES
# ==============================================================================
INDICACOES_CLINICAS = [
    "Fibrilação Atrial", "Flutter Atrial", "TVP/EP", "Prótese Valvar Metálica",
    "Prótese Valvar Biológica", "Trombose Venosa Profunda (TVP)", "Embolia Pulmonar (EP)",
    "AVC Cardioembólico", "Tromboembolismo Recorrente", "Síndrome Antifosfolípide (SAF)",
    "Trombofilia Hereditária", "Cardiomiopatia Dilatada", "IAM com Trombo",
    "Aneurisma de Ventrículo Esquerdo", "Trombo Intracardíaco", "Valvopatia Reumática",
    "Estenose Mitral", "Trombose de Prótese Valvar", "Trombose Arterial",
    "Trombose Venosa Cerebral", "Trombose de Veia Porta", "Trombose de Veia Mesentérica",
    "Trombose de Veia Renal", "Síndrome de Budd-Chiari", "Prevenção em Cirurgia Cardíaca",
    "Prevenção em Cirurgia Ortopédica", "Embolia Sistêmica", "Trombose de Acesso Vascular",
    "Outra"
]

FAIXAS_TERAPEUTICAS = ["2.0-3.0", "2.5-3.5", "1.5-2.0"]

INTERACOES_VARFARINA = {
    "AMIODARONA": {"risco": "Alta", "efeito": "Inibe CYP2C9/3A4 e aumenta RNI", "conduta": "Reduzir dose 30-50%"},
    "AZITROMICINA": {"risco": "Moderada", "efeito": "Altera flora intestinal", "conduta": "Monitorar RNI em 3-5 dias"},
    "CIPROFLOXACINO": {"risco": "Alta", "efeito": "Inibe metabolização hepática", "conduta": "Monitorar RNI"},
    "SULFAMETOXAZOL": {"risco": "Alta", "efeito": "Potencializa Varfarina", "conduta": "Reduzir dose"},
    "TRIMETOPRIMA": {"risco": "Alta", "efeito": "Potencializa anticoagulação", "conduta": "Reduzir dose"},
    "FLUCONAZOL": {"risco": "Alta", "efeito": "Inibidor CYP2C9", "conduta": "Reduzir dose 50%"},
    "OMEPRAZOL": {"risco": "Moderada", "efeito": "Inibição CYP2C19", "conduta": "Monitorar"},
    "PARACETAMOL": {"risco": "Moderada", "efeito": "Uso >2g/dia eleva RNI", "conduta": "Doses baixas"},
    "IBUPROFENO": {"risco": "Alta", "efeito": "Risco hemorrágico", "conduta": "Evitar AINEs"},
    "AAS": {"risco": "Alta", "efeito": "Sinergismo hemorrágico", "conduta": "Uso sob indicação"},
    "CARBAMAZEPINA": {"risco": "Alta", "efeito": "Indutor enzimático", "conduta": "Aumentar dose"},
    "RIFAMPECINA": {"risco": "Alta", "efeito": "Indutor enzimático", "conduta": "Aumentar dose"},
    "SERTRALINA": {"risco": "Moderada", "efeito": "Altera plaquetas", "conduta": "Monitorar"},
    "FLUOXETINA": {"risco": "Moderada", "efeito": "Inibição metabólica", "conduta": "Monitorar"}
}

# ==============================================================================
# BANCO DE DADOS
# ==============================================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            age INTEGER,
            contact TEXT,
            indication TEXT,
            target TEXT,
            weekly_dose REAL,
            meds TEXT,
            needs_support TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_rni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            date TEXT NOT NULL,
            value REAL,
            obs TEXT,
            FOREIGN KEY (patient_id) REFERENCES pacientes (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==============================================================================
# FUNÇÕES UTILITÁRIAS
# ==============================================================================
def contar_medicamentos(texto_meds: str) -> int:
    if not texto_meds or not texto_meds.strip():
        return 0
    itens = [m.strip() for m in texto_meds.replace('\n', ',').replace(';', ',').split(',') if m.strip()]
    return len(itens)

def classificar_polifarmacia(qtd_meds: int) -> Tuple[str, str]:
    """Classifica paciente quanto à polifarmácia."""
    if qtd_meds == 0:
        return "Apenas Varfarina", "poli-varfarina"
    elif qtd_meds <= 4:
        return f"{qtd_meds} medicamento(s)", "poli-nao"
    else:
        return "Polifarmácia (5+)", "poli-sim"

def checar_interacoes(texto_meds: str) -> List[Dict]:
    if not texto_meds:
        return []
    encontradas = []
    texto_upper = texto_meds.upper()
    for med, info in INTERACOES_VARFARINA.items():
        if med in texto_upper:
            encontradas.append({"medicamento": med, **info})
    return encontradas

def calcular_ttr(historico: List[Dict], min_alvo: float, max_alvo: float) -> Tuple[float, float, int, int]:
    historico_validos = [e for e in historico if e.get('value') is not None]
    
    if historico_validos:
        total = len(historico_validos)
        na_faixa = sum(1 for e in historico_validos if min_alvo <= float(e['value']) <= max_alvo)
        ttr_direto = (na_faixa / total) * 100.0
    else:
        ttr_direto = 0.0
        na_faixa = 0
        total = 0
    
    if len(historico_validos) < 2:
        ttr_rosendaal = 0.0
    else:
        try:
            df = pd.DataFrame(historico_validos)
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
            
            ttr_rosendaal = (dias_no_alvo / dias_totais) * 100.0 if dias_totais > 0 else 0.0
        except Exception:
            ttr_rosendaal = 0.0
    
    return ttr_rosendaal, ttr_direto, na_faixa, total

def exportar_backup() -> str:
    conn = get_connection()
    pacientes = [dict(p) for p in conn.execute("SELECT * FROM pacientes").fetchall()]
    historico = [dict(h) for h in conn.execute("SELECT * FROM historico_rni").fetchall()]
    conn.close()
    
    dados = {
        "versao": APP_VERSION,
        "data_backup": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pacientes": pacientes,
        "historico_rni": historico
    }
    return json.dumps(dados, ensure_ascii=False, indent=2)

def importar_backup(conteudo_json: str) -> Tuple[bool, str]:
    try:
        dados = json.loads(conteudo_json)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM historico_rni")
        cursor.execute("DELETE FROM pacientes")
        
        for p in dados.get("pacientes", []):
            cursor.execute("""
                INSERT INTO pacientes (id, name, age, contact, indication, target, weekly_dose, meds, needs_support)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p.get("id"), p.get("name"), p.get("age"), p.get("contact"),
                p.get("indication"), p.get("target"), p.get("weekly_dose"),
                p.get("meds"), p.get("needs_support")
            ))
        
        for h in dados.get("historico_rni", []):
            cursor.execute("""
                INSERT INTO historico_rni (id, patient_id, date, value, obs)
                VALUES (?, ?, ?, ?, ?)
            """, (
                h.get("id"), h.get("patient_id"), h.get("date"),
                h.get("value"), h.get("obs")
            ))
        
        conn.commit()
        conn.close()
        return True, "Backup importado com sucesso!"
    except Exception as e:
        return False, f"Erro ao importar: {str(e)}"

# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("### 🩺 Ambulatório RNI")
    
    # Navegação
    pagina = st.radio("", ["📊 Dashboard", "👤 Pacientes"], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Cadastro de paciente
    with st.expander("➕ Cadastrar Paciente"):
        with st.form("form_add_paciente", clear_on_submit=True):
            novo_nome = st.text_input("Nome Completo:")
            nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=65)
            
            nova_indicacao = st.selectbox("Indicação:", INDICACOES_CLINICAS)
            if nova_indicacao == "Outra":
                nova_indicacao_final = st.text_input("Especifique:") or "Outra"
            else:
                nova_indicacao_final = nova_indicacao
            
            nova_faixa = st.selectbox("Faixa Alvo:", FAIXAS_TERAPEUTICAS)
            nova_dose = st.number_input("Dose Semanal (mg):", value=35.0, step=2.5)
            meds_iniciais = st.text_area("Medicamentos:", placeholder="Ex: Amiodarona, Omeprazol...")
            
            if st.form_submit_button("Salvar") and novo_nome:
                conn = get_connection()
                try:
                    conn.execute("""
                        INSERT INTO pacientes (name, age, indication, target, weekly_dose, meds)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (novo_nome.strip(), nova_idade, nova_indicacao_final, nova_faixa, nova_dose, meds_iniciais))
                    conn.commit()
                    st.success("✅ Paciente cadastrado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(f"⚠️ Paciente '{novo_nome}' já existe!")
                finally:
                    conn.close()
    
    st.markdown("---")
    
    # Backup
    with st.expander("💾 Backup de Dados"):
        json_backup = exportar_backup()
        st.download_button(
            "📥 Exportar Backup",
            data=json_backup,
            file_name=f"backup_rni_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
        
        arquivo_upload = st.file_uploader("📤 Importar Backup", type=["json"])
        if arquivo_upload and st.button("🔄 Restaurar", use_container_width=True, type="primary"):
            sucesso, msg = importar_backup(arquivo_upload.read().decode("utf-8"))
            if sucesso:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

# ==============================================================================
# CARREGAR DADOS
# ==============================================================================
conn = get_connection()
pacientes_raw = conn.execute("SELECT * FROM pacientes ORDER BY name").fetchall()
conn.close()

pacientes = [dict(p) for p in pacientes_raw]

# ==============================================================================
# DASHBOARD
# ==============================================================================
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard - Visão Geral")
    st.caption("Análise populacional dos pacientes em acompanhamento")
    
    if not pacientes:
        st.warning("Nenhum paciente cadastrado.")
        st.stop()
    
    # Coletar dados
    total = len(pacientes)
    idades = [p['age'] for p in pacientes]
    indicacoes = {}
    interacoes_total = {}
    ttrs = []
    polifarmacia_counts = {"Apenas Varfarina": 0, "2-4 medicamentos": 0, "Polifarmácia (5+)": 0}
    
    for p in pacientes:
        conn = get_connection()
        historico = [dict(h) for h in conn.execute(
            "SELECT * FROM historico_rni WHERE patient_id = ?", (p['id'],)
        ).fetchall()]
        conn.close()
        
        try:
            min_alvo, max_alvo = map(float, p['target'].split('-'))
        except:
            min_alvo, max_alvo = 2.0, 3.0
        
        ttr, _, _, _ = calcular_ttr(historico, min_alvo, max_alvo)
        ttrs.append(ttr)
        
        indicacoes[p['indication'] or "Não especificada"] = indicacoes.get(p['indication'] or "Não especificada", 0) + 1
        
        for inter in checar_interacoes(p['meds'] or ""):
            interacoes_total[inter['medicamento']] = interacoes_total.get(inter['medicamento'], 0) + 1
        
        qtd_meds = contar_medicamentos(p['meds'] or "")
        if qtd_meds == 0:
            polifarmacia_counts["Apenas Varfarina"] += 1
        elif qtd_meds <= 4:
            polifarmacia_counts["2-4 medicamentos"] += 1
        else:
            polifarmacia_counts["Polifarmácia (5+)"] += 1
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Pacientes", total)
    col2.metric("Média de TTR", f"{sum(ttrs)/len(ttrs):.1f}%" if ttrs else "N/A")
    col3.metric("Faixa Etária", f"{min(idades)}-{max(idades)} anos")
    col4.metric("Polifarmácia", f"{polifarmacia_counts['Polifarmácia (5+)']} pacientes")
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👴 Distribuição por Faixa Etária")
        df_idade = pd.DataFrame({
            "Faixa": ["<60", "60-69", "70-79", "80+"],
            "Total": [
                sum(1 for a in idades if a < 60),
                sum(1 for a in idades if 60 <= a < 70),
                sum(1 for a in idades if 70 <= a < 80),
                sum(1 for a in idades if a >= 80)
            ]
        })
        fig = px.bar(df_idade, x='Faixa', y='Total', color='Faixa', text='Total',
                     color_discrete_sequence=['#0F6E6A', '#C9821A', '#7A2331', '#3B6E91'])
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("💊 Polifarmácia")
        df_poli = pd.DataFrame(list(polifarmacia_counts.items()), columns=['Categoria', 'Total'])
        fig = px.pie(df_poli, names='Categoria', values='Total', hole=0.4,
                     color_discrete_sequence=['#94A3B8', '#0F6E6A', '#7A2331'])
        fig.update_traces(textinfo='percent+label')
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏥 Indicações Clínicas")
        df_ind = pd.DataFrame(list(indicacoes.items()), columns=['Indicação', 'Total'])
        df_ind = df_ind.sort_values('Total', ascending=False)
        fig = px.bar(df_ind, x='Indicação', y='Total', color='Indicação', text='Total',
                     color_discrete_sequence=px.colors.qualitative.Set3)
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Distribuição de TTR")
        df_ttr = pd.DataFrame({
            "Controle": ["Ótimo (≥70%)", "Bom (60-69%)", "Regular (50-59%)", "Ruim (<50%)"],
            "Total": [
                sum(1 for t in ttrs if t >= 70),
                sum(1 for t in ttrs if 60 <= t < 70),
                sum(1 for t in ttrs if 50 <= t < 60),
                sum(1 for t in ttrs if t < 50)
            ]
        })
        fig = px.bar(df_ttr, x='Controle', y='Total', color='Controle', text='Total',
                     color_discrete_sequence=['#0F6E6A', '#C9821A', '#E67E22', '#7A2331'])
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Interações
    st.subheader("⚠️ Medicamentos Interagentes")
    if interacoes_total:
        df_inter = pd.DataFrame(list(interacoes_total.items()), columns=['Medicamento', 'Pacientes'])
        df_inter = df_inter.sort_values('Pacientes', ascending=True)
        fig = px.bar(df_inter, x='Pacientes', y='Medicamento', orientation='h',
                     text='Pacientes', color_discrete_sequence=['#7A2331'])
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma interação registrada.")

# ==============================================================================
# PÁGINA DE PACIENTES
# ==============================================================================
else:
    st.title("👤 Pacientes")
    
    if not pacientes:
        st.info("Cadastre um paciente na barra lateral.")
        st.stop()
    
    # Lista de pacientes clicáveis
    st.subheader("Selecione um paciente:")
    
    # Inicializar estado
    if 'paciente_selecionado' not in st.session_state:
        st.session_state['paciente_selecionado'] = None
    
    # Exibir cards de pacientes em grid
    cols = st.columns(3)
    
    for i, p in enumerate(pacientes):
        col_idx = i % 3
        with cols[col_idx]:
            qtd_meds = contar_medicamentos(p['meds'] or "")
            classificacao, classe_badge = classificar_polifarmacia(qtd_meds)
            
            is_active = st.session_state['paciente_selecionado'] == p['id']
            card_class = "patient-card active" if is_active else "patient-card"
            
            # Card clicável
            if st.button(
                f"**{p['name']}**\n\n{p['age']} anos | {p['indication']}\n\n<span class='badge-poli {classe_badge}'>{classificacao}</span>",
                key=f"paciente_{p['id']}",
                use_container_width=True,
                help="Clique para selecionar"
            ):
                st.session_state['paciente_selecionado'] = p['id']
                st.rerun()
    
    st.markdown("---")
    
    # Mostrar ficha do paciente selecionado
    if st.session_state['paciente_selecionado']:
        paciente = next((p for p in pacientes if p['id'] == st.session_state['paciente_selecionado']), None)
        
        if paciente:
            # Carregar histórico
            conn = get_connection()
            historico = [dict(h) for h in conn.execute(
                "SELECT * FROM historico_rni WHERE patient_id = ? ORDER BY date DESC",
                (paciente['id'],)
            ).fetchall()]
            conn.close()
            
            try:
                min_alvo, max_alvo = map(float, paciente['target'].split('-'))
            except:
                min_alvo, max_alvo = 2.0, 3.0
            
            ttr_rosendaal, ttr_direto, exames_na_faixa, total_exames = calcular_ttr(historico, min_alvo, max_alvo)
            interacoes = checar_interacoes(paciente['meds'] or "")
            qtd_meds = contar_medicamentos(paciente['meds'] or "")
            classificacao, classe_badge = classificar_polifarmacia(qtd_meds)
            
            # Cabeçalho
            st.markdown(f"## 📋 Ficha de {paciente['name']}")
            
            # Botões de ação
            col_editar, col_excluir = st.columns(2)
            with col_editar:
                if st.button("✏️ Editar Dados", use_container_width=True):
                    st.session_state['editando'] = True
            with col_excluir:
                if st.button("🗑️ Excluir Paciente", use_container_width=True, type="primary"):
                    if st.session_state.get('confirmar_exclusao', False):
                        conn = get_connection()
                        conn.execute("DELETE FROM pacientes WHERE id=?", (paciente['id'],))
                        conn.commit()
                        conn.close()
                        st.session_state['paciente_selecionado'] = None
                        st.session_state['confirmar_exclusao'] = False
                        st.success("Paciente excluído!")
                        st.rerun()
                    else:
                        st.session_state['confirmar_exclusao'] = True
                        st.warning("Clique novamente para confirmar!")
            
            # Formulário de edição
            if st.session_state.get('editando', False):
                with st.form("form_editar_paciente"):
                    st.markdown("### Editar Dados")
                    edit_nome = st.text_input("Nome:", value=paciente['name'])
                    edit_idade = st.number_input("Idade:", value=int(paciente['age']))
                    
                    lista_ind = INDICACOES_CLINICAS.copy()
                    if paciente['indication'] not in lista_ind:
                        lista_ind.insert(0, paciente['indication'])
                    edit_indicacao = st.selectbox("Indicação:", lista_ind, index=0)
                    
                    edit_target = st.selectbox("Faixa Alvo:", FAIXAS_TERAPEUTICAS,
                                               index=FAIXAS_TERAPEUTICAS.index(paciente['target']))
                    edit_dose = st.number_input("Dose Semanal:", value=float(paciente['weekly_dose']), step=2.5)
                    edit_meds = st.text_area("Medicamentos:", value=paciente['meds'] or "")
                    
                    col_salvar, col_cancelar = st.columns(2)
                    with col_salvar:
                        if st.form_submit_button("💾 Salvar", use_container_width=True):
                            conn = get_connection()
                            conn.execute("""
                                UPDATE pacientes SET name=?, age=?, indication=?, target=?, weekly_dose=?, meds=?
                                WHERE id=?
                            """, (edit_nome, edit_idade, edit_indicacao, edit_target, edit_dose, edit_meds, paciente['id']))
                            conn.commit()
                            conn.close()
                            st.session_state['editando'] = False
                            st.success("✅ Dados atualizados!")
                            st.rerun()
            
            st.markdown("---")
            
            # Cards de informações
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="flash-card">
                    <div class="info-label">Idade</div>
                    <div class="info-value">{paciente['age']} anos</div>
                    <div class="info-label">Indicação</div>
                    <div class="info-value">{paciente['indication']}</div>
                    <div class="info-label">Dose Semanal</div>
                    <div class="info-value">{paciente['weekly_dose']} mg</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="flash-card">
                    <div class="info-label">TTR (Rosendaal)</div>
                    <div class="info-value" style="font-size: 2rem; color: {COR_SECUNDARIA if ttr_rosendaal >= 60 else COR_ALERTA};">{ttr_rosendaal:.1f}%</div>
                    <div class="info-label">TTR Direto</div>
                    <div class="info-value">{ttr_direto:.1f}% ({exames_na_faixa}/{total_exames})</div>
                    <div class="info-label">Faixa Alvo</div>
                    <div class="info-value">{paciente['target']}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="flash-card">
                    <div class="info-label">Polifarmácia</div>
                    <div class="info-value"><span class="badge-poli {classe_badge}">{classificacao}</span></div>
                    <div class="info-label">Interações</div>
                    <div class="info-value" style="color: {COR_PRIMARIA if interacoes else COR_SECUNDARIA};">{len(interacoes)} encontrada(s)</div>
                    <div class="info-label">Último RNI</div>
                    <div class="info-value">{historico[0]['value'] if historico and historico[0]['value'] else 'N/A'}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Gráfico de evolução
            st.subheader("📈 Evolução do RNI")
            historico_validos = [e for e in historico if e.get('value') is not None]
            
            if historico_validos:
                df_chart = pd.DataFrame(historico_validos)
                df_chart['date'] = pd.to_datetime(df_chart['date'])
                df_chart['value'] = df_chart['value'].astype(float)
                df_chart = df_chart.sort_values('date')
                
                colors = [COR_SECUNDARIA if min_alvo <= v <= max_alvo else (COR_ALERTA if v < min_alvo else COR_PRIMARIA) for v in df_chart['value']]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_chart['date'], y=df_chart['value'],
                    mode='lines+markers',
                    line=dict(color='#64748B', width=2),
                    marker=dict(size=10, color=colors)
                ))
                fig.update_layout(
                    template="plotly_white", height=350, hovermode="x unified",
                    shapes=[
                        {"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1,
                         "y0": min_alvo, "y1": max_alvo, "fillcolor": "rgba(15,110,106,0.15)",
                         "line": {"width": 0}, "layer": "below"}
                    ]
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Nenhum exame registrado.")
            
            st.markdown("---")
            
            # Registrar RNI e Medicamentos
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("➕ Registrar RNI")
                with st.form("form_add_rni", clear_on_submit=True):
                    data_rni = st.date_input("Data do Exame", value=datetime.today())
                    valor_rni = st.number_input("Valor RNI", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
                    obs_rni = st.text_input("Observação:")
                    if st.form_submit_button("Salvar RNI"):
                        conn = get_connection()
                        conn.execute("""
                            INSERT INTO historico_rni (patient_id, date, value, obs)
                            VALUES (?, ?, ?, ?)
                        """, (paciente['id'], data_rni.strftime("%Y-%m-%d"), float(valor_rni), obs_rni))
                        conn.commit()
                        conn.close()
                        st.success("✅ RNI registrado!")
                        st.rerun()
            
            with col2:
                st.subheader("💊 Medicamentos e Interações")
                st.text_area("Medicamentos:", value=paciente['meds'] or "", height=100, disabled=True, label_visibility="collapsed")
                
                if interacoes:
                    for inter in interacoes:
                        classe = "alert-high" if inter['risco'] == "Alta" else "alert-mod"
                        st.markdown(f"""
                        <div class="alert-card {classe}">
                            <b>🚨 {inter['medicamento']} — {inter['risco']}</b><br>
                            <small>{inter['efeito']} | {inter['conduta']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.success("✅ Sem interações.")
            
            st.markdown("---")
            
            # Histórico
            st.subheader("📋 Histórico de Exames")
            
            if historico:
                for item in historico:
                    col_data, col_valor, col_obs, col_edit, col_del = st.columns([1, 1, 2, 1, 1])
                    
                    with col_data:
                        st.write(f"📅 {item['date']}")
                    with col_valor:
                        st.write(f"🩸 **{item['value'] if item['value'] else 'Falta'}**")
                    with col_obs:
                        st.write(item['obs'] or "")
                    with col_edit:
                        if item['value']:
                            with st.popover("✏️"):
                                with st.form(f"edit_rni_{item['id']}"):
                                    nova_data = st.date_input("Data:", value=datetime.strptime(item['date'], "%Y-%m-%d"))
                                    novo_valor = st.number_input("RNI:", value=float(item['value']), step=0.1)
                                    if st.form_submit_button("Atualizar"):
                                        conn = get_connection()
                                        conn.execute("UPDATE historico_rni SET date=?, value=? WHERE id=?",
                                                    (nova_data.strftime("%Y-%m-%d"), float(novo_valor), item['id']))
                                        conn.commit()
                                        conn.close()
                                        st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"del_rni_{item['id']}"):
                            conn = get_connection()
                            conn.execute("DELETE FROM historico_rni WHERE id=?", (item['id'],))
                            conn.commit()
                            conn.close()
                            st.rerun()
                    
                    st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
            else:
                st.info("Nenhum exame registrado.")
