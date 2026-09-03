"""
Sistema de Controle de RNI - Ambulatório de Anticoagulação
==========================================================
Sistema simplificado para acompanhamento individual de pacientes
em uso de varfarina.

Versão: 4.0
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
APP_VERSION = "4.0"

# Cores do tema
COR_PRIMARIA = "#7A2331"
COR_SECUNDARIA = "#0F6E6A"
COR_ALERTA = "#C9821A"
COR_TEXTO = "#14181F"
COR_TEXTO_SUAVE = "#4B5563"

st.set_page_config(
    page_title="Controle de RNI - Pacientes",
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
        background-color: #F7F9FA;
        border-right: 1px solid #E4E7EB;
    }}
    
    .flash-card {{
        background: #FFFFFF;
        border: 1px solid #E4E7EB;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 15px;
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
    "Fibrilação Atrial",
    "Flutter Atrial",
    "TVP/EP (Tromboembolismo Venoso)",
    "Prótese Valvar Metálica",
    "Prótese Valvar Biológica",
    "Trombose Venosa Profunda (TVP)",
    "Embolia Pulmonar (EP)",
    "AVC Cardioembólico",
    "Tromboembolismo Recorrente",
    "Síndrome Antifosfolípide (SAF)",
    "Trombofilia Hereditária",
    "Cardiomiopatia Dilatada",
    "IAM com Trombo",
    "Aneurisma de Ventrículo Esquerdo",
    "Trombo Intracardíaco",
    "Valvopatia Reumática",
    "Estenose Mitral",
    "Trombose de Prótese Valvar",
    "Trombose Arterial",
    "Trombose Venosa Cerebral",
    "Trombose de Veia Porta",
    "Trombose de Veia Mesentérica",
    "Trombose de Veia Renal",
    "Síndrome de Budd-Chiari",
    "Prevenção em Cirurgia Cardíaca",
    "Prevenção em Cirurgia Ortopédica",
    "Embolia Sistêmica",
    "Trombose de Acesso Vascular",
    "Outra"
]

FAIXAS_TERAPEUTICAS = ["2.0-3.0", "2.5-3.5", "1.5-2.0"]

INTERACOES_VARFARINA = {
    "AMIODARONA": {"risco": "Alta", "efeito": "Inibe CYP2C9/3A4 e aumenta RNI", "conduta": "Reduzir dose 30-50% e monitorar semanalmente"},
    "AZITROMICINA": {"risco": "Moderada", "efeito": "Altera flora intestinal e pode aumentar RNI", "conduta": "Monitorar RNI em 3-5 dias"},
    "CIPROFLOXACINO": {"risco": "Alta", "efeito": "Inibe metabolização hepática", "conduta": "Monitorar RNI com frequência"},
    "SULFAMETOXAZOL": {"risco": "Alta", "efeito": "Potencializa fortemente a Varfarina", "conduta": "Reduzir dose e monitorar precocemente"},
    "TRIMETOPRIMA": {"risco": "Alta", "efeito": "Potencializa efeito anticoagulante", "conduta": "Reduzir dose e monitorar em 3 dias"},
    "FLUCONAZOL": {"risco": "Alta", "efeito": "Inibidor potente da CYP2C9", "conduta": "Reduzir dose até 50%"},
    "OMEPRAZOL": {"risco": "Moderada", "efeito": "Inibição discreta da CYP2C19", "conduta": "Monitorar se houver alteração"},
    "PARACETAMOL": {"risco": "Moderada", "efeito": "Uso contínuo >2g/dia eleva RNI", "conduta": "Preferir doses baixas"},
    "IBUPROFENO": {"risco": "Alta", "efeito": "Risco hemorrágico alto", "conduta": "Evitar AINEs"},
    "AAS": {"risco": "Alta", "efeito": "Sinergismo hemorrágico", "conduta": "Uso apenas sob indicação formal"},
    "CARBAMAZEPINA": {"risco": "Alta", "efeito": "Indutor enzimático potente", "conduta": "Pode necessitar doses maiores"},
    "RIFAMPECINA": {"risco": "Alta", "efeito": "Indutor enzimático potente", "conduta": "Aumento expressivo da dose"},
    "SERTRALINA": {"risco": "Moderada", "efeito": "Altera função plaquetária", "conduta": "Acompanhar sangramentos"},
    "FLUOXETINA": {"risco": "Moderada", "efeito": "Inibição metabólica", "conduta": "Monitorar RNI"}
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
    """Calcula TTR (Rosendaal e Direto)"""
    historico_validos = [e for e in historico if e.get('value') is not None]
    
    # TTR Direto
    if historico_validos:
        total = len(historico_validos)
        na_faixa = sum(1 for e in historico_validos if min_alvo <= float(e['value']) <= max_alvo)
        ttr_direto = (na_faixa / total) * 100.0
    else:
        ttr_direto = 0.0
        na_faixa = 0
        total = 0
    
    # TTR Rosendaal
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

# ==============================================================================
# SIDEBAR - CADASTRO DE PACIENTE
# ==============================================================================
with st.sidebar:
    st.markdown("### 🩺 Controle de RNI")
    
    # Seleção do paciente
    conn = get_connection()
    pacientes_raw = conn.execute("SELECT * FROM pacientes ORDER BY name").fetchall()
    conn.close()
    
    if pacientes_raw:
        pacientes = [dict(p) for p in pacientes_raw]
        opcoes = [p['name'] for p in pacientes]
        paciente_selecionado = st.selectbox("Paciente:", opcoes)
        paciente = pacientes[opcoes.index(paciente_selecionado)]
    else:
        paciente = None
        st.info("Cadastre um paciente abaixo.")
    
    st.markdown("---")
    
    # Cadastro de novo paciente
    with st.expander("➕ Cadastrar Novo Paciente"):
        with st.form("form_add_paciente", clear_on_submit=True):
            novo_nome = st.text_input("Nome Completo:")
            nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=65)
            
            nova_indicacao = st.selectbox("Indicação Clínica:", INDICACOES_CLINICAS)
            if nova_indicacao == "Outra":
                nova_indicacao_personalizada = st.text_input("Especifique:")
                nova_indicacao_final = nova_indicacao_personalizada or "Outra"
            else:
                nova_indicacao_final = nova_indicacao
            
            nova_faixa = st.selectbox("Faixa Alvo RNI:", FAIXAS_TERAPEUTICAS)
            nova_dose = st.number_input("Dose Semanal (mg):", value=35.0, step=2.5)
            meds_iniciais = st.text_area("Medicamentos em Uso:", placeholder="Ex: Amiodarona 200mg, Omeprazol 20mg...")
            
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
    
    # Registrar RNI
    if paciente:
        st.markdown("---")
        with st.expander("➕ Registrar RNI"):
            with st.form("form_add_rni", clear_on_submit=True):
                data_rni = st.date_input("Data do Exame", value=datetime.today())
                valor_rni = st.number_input("Valor RNI", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
                obs_rni = st.text_input("Observação:", placeholder="Ex: Após ajuste de dose")
                
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

# ==============================================================================
# ÁREA PRINCIPAL - FICHA DO PACIENTE
# ==============================================================================
if paciente:
    # Dados do paciente
    conn = get_connection()
    historico_rni = [dict(r) for r in conn.execute(
        "SELECT * FROM historico_rni WHERE patient_id = ? ORDER BY date DESC",
        (paciente['id'],)
    ).fetchall()]
    conn.close()
    
    # Parse faixa alvo
    try:
        min_alvo, max_alvo = map(float, paciente['target'].split('-'))
    except Exception:
        min_alvo, max_alvo = 2.0, 3.0
    
    # Cálculos
    ttr_rosendaal, ttr_direto, exames_na_faixa, total_exames = calcular_ttr(historico_rni, min_alvo, max_alvo)
    interacoes = checar_interacoes(paciente['meds'] or "")
    qtd_meds = contar_medicamentos(paciente['meds'] or "")
    
    # Cabeçalho
    st.markdown(f"# 👤 {paciente['name']}")
    
    # CARDS DE INFORMAÇÕES
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="flash-card">
            <div class="info-label">Idade</div>
            <div class="info-value">{paciente['age']} anos</div>
            <div class="info-label">Indicação da Varfarina</div>
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
            <div class="info-value">{ttr_direto:.1f}% ({exames_na_faixa}/{total_exames} exames na faixa)</div>
            <div class="info-label">Faixa Alvo</div>
            <div class="info-value">{paciente['target']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="flash-card">
            <div class="info-label">Medicamentos em Uso</div>
            <div class="info-value">{qtd_meds} medicamento(s)</div>
            <div class="info-label">Interações com Varfarina</div>
            <div class="info-value" style="color: {COR_PRIMARIA if interacoes else COR_SECUNDARIA};">{len(interacoes)} encontrada(s)</div>
            <div class="info-label">Último RNI</div>
            <div class="info-value">{historico_rni[0]['value'] if historico_rni and historico_rni[0]['value'] else 'N/A'}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # GRÁFICO DE EVOLUÇÃO DO RNI
    st.subheader("📈 Evolução do RNI")
    
    historico_validos = [e for e in historico_rni if e.get('value') is not None]
    
    if historico_validos:
        df_chart = pd.DataFrame(historico_validos)
        df_chart['date'] = pd.to_datetime(df_chart['date'])
        df_chart['value'] = df_chart['value'].astype(float)
        df_chart = df_chart.sort_values('date')
        
        def classificar_ponto(v):
            if min_alvo <= v <= max_alvo:
                return COR_SECUNDARIA
            elif v < min_alvo:
                return COR_ALERTA
            else:
                return COR_PRIMARIA
        
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
        
        fig_rni.update_layout(
            template="plotly_white",
            font={"family": "Inter, sans-serif", "size": 13, "color": COR_TEXTO},
            margin={"l": 40, "r": 20, "t": 30, "b": 40},
            height=350,
            hovermode="x unified",
            xaxis={"showgrid": True, "gridcolor": "#F1F5F9"},
            yaxis={"showgrid": True, "gridcolor": "#F1F5F9"},
            shapes=[
                {"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, 
                 "y0": min_alvo, "y1": max_alvo, "fillcolor": f"rgba(15, 110, 106, 0.15)", 
                 "line": {"width": 0}, "layer": "below"},
                {"type": "line", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, 
                 "y0": min_alvo, "y1": min_alvo, "line": {"color": COR_SECUNDARIA, "width": 1.5, "dash": "dot"}},
                {"type": "line", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, 
                 "y0": max_alvo, "y1": max_alvo, "line": {"color": COR_SECUNDARIA, "width": 1.5, "dash": "dot"}}
            ]
        )
        st.plotly_chart(fig_rni, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("Nenhum exame de RNI registrado.")
    
    st.markdown("---")
    
    # MEDICAMENTOS E INTERAÇÕES
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💊 Medicamentos em Uso")
        if paciente['meds']:
            st.text_area("Lista de Medicamentos:", value=paciente['meds'], height=150, disabled=True, label_visibility="collapsed")
        else:
            st.info("Nenhum medicamento registrado.")
        
        st.caption(f"Total: {qtd_meds} medicamento(s)")
    
    with col2:
        st.subheader("⚠️ Interações Medicamentosas")
        if interacoes:
            for inter in interacoes:
                classe = "alert-high" if inter['risco'] == "Alta" else "alert-mod"
                st.markdown(f"""
                <div class="alert-card {classe}">
                    <div style="font-weight: 700;">🚨 {inter['medicamento']} — Risco {inter['risco']}</div>
                    <div style="font-size: 0.9rem;"><b>Efeito:</b> {inter['efeito']}</div>
                    <div style="font-size: 0.9rem;"><b>Conduta:</b> {inter['conduta']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ Nenhuma interação medicamentosa identificada.")
    
    # HISTÓRICO DE RNI
    st.markdown("---")
    st.subheader("📋 Histórico de Exames")
    
    if historico_rni:
        df_historico = pd.DataFrame(historico_rni)
        df_historico = df_historico[['date', 'value', 'obs']]
        df_historico.columns = ['Data', 'RNI', 'Observação']
        st.dataframe(df_historico, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum exame registrado.")

else:
    st.title("🩸 Controle de RNI")
    st.info("👈 Cadastre um paciente na barra lateral para começar.")
