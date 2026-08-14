import streamlit as st
import pandas as pd
import sqlite3
import datetime

# -----------------------------------------------------------------------------
# 1. Configuração Inicial da Página
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Controle de RNI - Anticoagulação",
    page_icon="🩸",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. Funções de Banco de Dados (SQLite Local)
# -----------------------------------------------------------------------------
def init_db():
    """Inicializa o banco de dados e cria a tabela se não existir."""
    conn = sqlite3.connect("rni_pacientes.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS exames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente TEXT NOT NULL,
            indicacao TEXT NOT NULL,
            data_coleta TEXT NOT NULL,
            rni_atual REAL NOT NULL,
            meta_min REAL NOT NULL,
            meta_max REAL NOT NULL,
            dose_semanal REAL NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def salvar_exame(paciente, indicacao, data_coleta, rni_atual, meta_min, meta_max, dose_semanal, status):
    """Salva um novo registro no banco de dados local."""
    conn = sqlite3.connect("rni_pacientes.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO exames (paciente, indicacao, data_coleta, rni_atual, meta_min, meta_max, dose_semanal, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (paciente, indicacao, str(data_coleta), rni_atual, meta_min, meta_max, dose_semanal, status))
    conn.commit()
    conn.close()

def carregar_dados():
    """Lê todos os dados salvos do SQLite e retorna como DataFrame do Pandas."""
    conn = sqlite3.connect("rni_pacientes.db")
    df = pd.read_sql_query("SELECT * FROM exames ORDER BY data_coleta DESC", conn)
    conn.close()
    return df

# Garante que a estrutura do banco de dados exista ao iniciar o app
init_db()

# -----------------------------------------------------------------------------
# 3. Interface Principal e Barra Lateral
# -----------------------------------------------------------------------------
st.title("🩸 Sistema de Acompanhamento e Manejo de RNI")
st.caption("Ferramenta de Acompanhamento Clínico de Anticoagulação Oral | TCR Farmácia Hospitalar")

st.sidebar.header("📝 Novo Registro de Exame")

# Formulário de Entrada
nome_paciente = st.sidebar.text_input("Nome / Prontuário do Paciente", placeholder="Ex: Paciente 01")
indicacao = st.sidebar.selectbox("Indicação Primária", ["Fibrilação Atrial", "Prótese Valvular Mecânica", "TEV / TVP", "Outra"])

st.sidebar.subheader("🎯 Meta Terapêutica")
col_m1, col_m2 = st.sidebar.columns(2)
meta_min = col_m1.number_input("RNI Mín", value=2.0, step=0.1)
meta_max = col_m2.number_input("RNI Máx", value=3.0, step=0.1)

st.sidebar.subheader("📊 Exame Atual")
data_exame = st.sidebar.date_input("Data da Coleta", datetime.date.today())
rni_atual = st.sidebar.number_input("Valor do RNI", min_value=0.5, max_value=15.0, value=2.5, step=0.1)
dose_semanal = st.sidebar.number_input("Dose Semanal Atual (mg)", value=35.0, step=2.5)

# Lógica de Avaliação Clínica
if rni_atual < meta_min:
    status_clinico = "Subterapêutico (Risco Trombótico)"
    delta_msg = f"Abaixo do alvo ({meta_min})"
elif rni_atual > meta_max:
    status_clinico = "Supraterapêutico (Risco Hemorrágico)"
    delta_msg = f"Acima do alvo ({meta_max})"
else:
    status_clinico = "Na Faixa Terapêutica"
    delta_msg = "Dentro da meta"

# Botão para salvar no banco
if st.sidebar.button("💾 Salvar Exame no Banco de Dados", type="primary"):
    if nome_paciente.strip() == "":
        st.sidebar.error("Por favor, preencha o identificador do paciente.")
    else:
        salvar_exame(
            nome_paciente, indicacao, data_exame, rni_atual,
            meta_min, meta_max, dose_semanal, status_clinico
        )
        st.sidebar.success(f"Exame registrado com sucesso para {nome_paciente}!")
        st.rerun()

# -----------------------------------------------------------------------------
# 4. Painel de Exibição dos Dados Atual
# -----------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("RNI Informado", f"{rni_atual:.1f}", delta=delta_msg)
c2.metric("Faixa Alvo", f"{meta_min:.1f} - {meta_max:.1f}")
c3.metric("Dose Semanal", f"{dose_semanal} mg")

if rni_atual < meta_min:
    st.warning(f"⚠️ **Atenção:** Paciente em nível **{status_clinico}**. Avaliar adesão posológica ou interações medicamentosas.")
elif rni_atual > meta_max:
    st.error(f"🚨 **Alerta de Risco:** Paciente em nível **{status_clinico}**. Avaliar suspensão temporária, Vitamina K ou conduta de urgência.")
else:
    st.success(f"✅ **Faixa Adequada:** Paciente mantido dentro do alvo terapêutico.")

st.divider()

# -----------------------------------------------------------------------------
# 5. Consulta e Histórico Salvo (Pandas + SQLite)
# -----------------------------------------------------------------------------
st.subheader("📚 Banco de Exames Registrados")

df_banco = carregar_dados()

if df_banco.empty:
    st.info("Nenhum exame cadastrado até o momento. Utilise o menu lateral para realizar o primeiro registro.")
else:
    # Filtro por Paciente
    lista_pacientes = ["Todos os Pacientes"] + sorted(list(df_banco["paciente"].unique()))
    paciente_selecionado = st.selectbox("🔍 Selecionar Paciente para Visualização de Histórico", lista_pacientes)

    if paciente_selecionado != "Todos os Pacientes":
        df_filtrado = df_banco[df_banco["paciente"] == paciente_selecionado].copy()
    else:
        df_filtrado = df_banco.copy()

    aba_tabela, aba_grafico = st.tabs(["📑 Histórico Geral / Registros", "📈 Evolução Temporal de RNI"])

    with aba_tabela:
        st.dataframe(
            df_filtrado,
            column_config={
                "id": "ID",
                "paciente": "Paciente / Prontuário",
                "indicacao": "Indicação",
                "data_coleta": "Data da Coleta",
                "rni_atual": "RNI",
                "meta_min": "Meta Mín.",
                "meta_max": "Meta Máx.",
                "dose_semanal": "Dose Semanal (mg)",
                "status": "Status Clínico"
            },
            use_container_width=True,
            hide_index=True
        )

    with aba_grafico:
        if paciente_selecionado == "Todos os Pacientes":
            st.warning("Selecione um paciente específico no campo acima para gerar o gráfico temporal individual.")
        else:
            # Ordena por data para exibição correta no gráfico
            df_grafico = df_filtrado.sort_values(by="data_coleta")
            st.line_chart(df_grafico, x="data_coleta", y="rni_atual")
            st.caption(f"Evolução temporal do RNI do paciente: **{paciente_selecionado}**")
