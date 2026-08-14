import streamlit as st
import pandas as pd
import json
import os
import random
import string
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTILO
# ==============================================================================
st.set_page_config(
    page_title="Ambulatório de Anticoagulação - RNI",
    page_icon="🩸",
    layout="wide"
)

DB_FILE = "dados.json"

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

    .badge-status {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES DE BANCO DE DADOS (JSON local = nosso "banco de pacientes")
# ==============================================================================
def carregar_dados():
    """Lê o arquivo dados.json do disco. Se não existir, começa vazio."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"patients": [], "agenda": {}}


def salvar_dados():
    """Grava o estado atual (st.session_state.dados) de volta no arquivo."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.dados, f, ensure_ascii=False, indent=2)


def gerar_id():
    """Gera um id único no mesmo padrão do arquivo original (ex: _nlsiy8a8s)."""
    return "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))


# Carrega o banco uma única vez por sessão
if "dados" not in st.session_state:
    st.session_state.dados = carregar_dados()

pacientes = st.session_state.dados.get("patients", [])

# ==============================================================================
# 3. FUNÇÕES DE CÁLCULO CLÍNICO (TTR)
# ==============================================================================
def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
    """TTR pelo método de Rosendaal (interpolação linear entre exames)."""
    if not historico or len(historico) < 2:
        return 0.0
    try:
        df = pd.DataFrame(historico)
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = df["value"].astype(float)
        df = df.sort_values("date").reset_index(drop=True)

        dias_no_alvo = 0.0
        dias_totais = 0

        for i in range(len(df) - 1):
            d1, v1 = df.loc[i, "date"], df.loc[i, "value"]
            d2, v2 = df.loc[i + 1, "date"], df.loc[i + 1, "value"]

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
    """Proporção simples de exames que caíram dentro da faixa alvo."""
    if not historico:
        return 0.0, 0, 0
    try:
        total = len(historico)
        na_faixa = sum(1 for e in historico if min_alvo <= float(e["value"]) <= max_alvo)
        return (na_faixa / total) * 100.0, na_faixa, total
    except Exception:
        return 0.0, 0, 0


def faixa_alvo(paciente):
    """Extrai (min, max) do campo 'target' (ex: '2.0-3.0'), com fallback seguro."""
    try:
        lo, hi = map(float, paciente.get("target", "2.0-3.0").split("-"))
        return lo, hi
    except Exception:
        return 2.0, 3.0


def status_ttr(valor):
    """Retorna (cor, cor_fundo, rótulo) conforme o valor de TTR."""
    if valor >= 70.0:
        return "#10B981", "#ECFDF5", "Estável"
    elif valor >= 60.0:
        return "#F59E0B", "#FFFBEB", "Alerta"
    else:
        return "#EF4444", "#FEF2F2", "Crítico"


# ==============================================================================
# 4. NAVEGAÇÃO PRINCIPAL (menu fica no topo, em abas)
# ==============================================================================
st.title("🩸 Ambulatório de Anticoagulação")
st.caption("Acompanhamento clínico de pacientes em uso de anticoagulante oral (RNI / TTR)")

aba_visao_geral, aba_ficha, aba_novo_paciente = st.tabs(
    ["📊 Visão Geral", "👤 Ficha do Paciente", "➕ Adicionar Paciente"]
)

# ------------------------------------------------------------------------------
# 4.1 ABA: VISÃO GERAL — painel com todos os pacientes de uma vez
# ------------------------------------------------------------------------------
with aba_visao_geral:
    if not pacientes:
        st.info("Nenhum paciente cadastrado ainda. Use a aba **➕ Adicionar Paciente**.")
    else:
        linhas = []
        for p in pacientes:
            lo, hi = faixa_alvo(p)
            ttr = calcular_ttr_rosendaal(p.get("rniHistory", []), lo, hi)
            hist = p.get("rniHistory", [])
            ultimo_rni = hist[0]["value"] if hist else None
            _, _, rotulo = status_ttr(ttr)
            linhas.append({
                "Paciente": p["name"],
                "Indicação": p.get("indication", "N/A"),
                "Faixa Alvo": p.get("target", "N/A"),
                "Último RNI": ultimo_rni,
                "TTR (Rosendaal)": round(ttr, 1),
                "Status": rotulo,
                "Complexidade": p.get("level", "Médio"),
            })

        df_geral = pd.DataFrame(linhas)

        c1, c2, c3 = st.columns(3)
        c1.metric("Pacientes cadastrados", len(pacientes))
        c2.metric("TTR médio do grupo", f"{df_geral['TTR (Rosendaal)'].mean():.1f}%")
        c3.metric("Pacientes críticos (TTR < 60%)", int((df_geral["TTR (Rosendaal)"] < 60).sum()))

        st.markdown("#### Todos os pacientes")
        st.dataframe(df_geral, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# 4.2 ABA: FICHA DO PACIENTE — detalhe individual (gráfico, TTR, meds...)
# ------------------------------------------------------------------------------
with aba_ficha:
    if not pacientes:
        st.info("Cadastre um paciente primeiro na aba **➕ Adicionar Paciente**.")
    else:
        nomes = sorted([p["name"] for p in pacientes])
        nome_sel = st.selectbox("Selecione o paciente", nomes, key="select_paciente")
        p = next(item for item in pacientes if item["name"] == nome_sel)

        min_alvo, max_alvo = faixa_alvo(p)
        ttr_valor = calcular_ttr_rosendaal(p.get("rniHistory", []), min_alvo, max_alvo)
        ttr_direto, na_faixa, total = calcular_ttr_direto(p.get("rniHistory", []), min_alvo, max_alvo)
        cor_ttr, bg_badge, rotulo_ttr = status_ttr(ttr_valor)

        level_class = (
            "level-baixo" if p.get("level") == "Baixo"
            else "level-alto" if p.get("level") == "Alto"
            else "level-medio"
        )

        st.markdown(f"## 👤 {p['name']}")

        col_info1, col_info2, col_info3 = st.columns(3)

        with col_info1:
            st.markdown(f"""
            <div class="patient-card">
                <div class="info-label">Dados Demográficos</div>
                <div class="info-value">Idade: {p.get('age', 'N/A')} anos</div>
                <div class="info-value">Contato: {p.get('contact') or 'Não informado'}</div>
                <div class="info-label" style="margin-top: 10px;">Complexidade</div>
                <div><span class="badge-level {level_class}">{p.get('level', 'Médio')}</span></div>
            </div>
            """, unsafe_allow_html=True)

        with col_info2:
            st.markdown(f"""
            <div class="patient-card">
                <div class="info-label">Manejo Terapêutico</div>
                <div class="info-value">Indicação: {p.get('indication', 'N/A')}</div>
                <div class="info-value">Faixa Alvo (RNI): {p.get('target', 'N/A')}</div>
                <div class="info-value">Dose Semanal: {p.get('weeklyDose', 0)} mg</div>
                <div class="info-value">Organizador de Cp.: {p.get('organizer', 'Não')}</div>
            </div>
            """, unsafe_allow_html=True)

        with col_info3:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;padding:20px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                    <span style="font-size:0.85rem;font-weight:600;color:#64748B;text-transform:uppercase;">TTR (Rosendaal)</span>
                    <span class="badge-status" style="color:{cor_ttr};background:{bg_badge};">{rotulo_ttr}</span>
                </div>
                <div style="font-size:2.5rem;font-weight:700;color:{cor_ttr};line-height:1;margin-bottom:16px;">
                    {ttr_valor:.1f}%
                </div>
                <div style="border-top:1px solid #F1F5F9;margin-bottom:12px;"></div>
                <div style="font-size:0.8rem;color:#94A3B8;text-transform:uppercase;font-weight:500;">Método Comparativo</div>
                <div style="font-size:0.87rem;color:#334155;">
                    TTR Direto: <b style="color:#0F172A;">{ttr_direto:.1f}%</b>
                    <span style="color:#64748B;font-size:0.8rem;margin-left:4px;">({na_faixa}/{total} exames)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        col_grafico, col_novo_rni = st.columns([2, 1])

        with col_grafico:
            st.subheader("📈 Tendência do RNI")
            if p.get("rniHistory"):
                df_rni = pd.DataFrame(p["rniHistory"])
                df_rni["date"] = pd.to_datetime(df_rni["date"])
                df_rni["value"] = df_rni["value"].astype(float)
                df_rni = df_rni.sort_values("date")
                df_rni["Alvo Mínimo"] = min_alvo
                df_rni["Alvo Máximo"] = max_alvo

                st.line_chart(
                    df_rni.set_index("date")[["value", "Alvo Mínimo", "Alvo Máximo"]],
                    color=["#2563EB", "#10B981", "#10B981"],
                    height=300
                )
            else:
                st.info("Nenhum histórico de RNI para gerar o gráfico.")

        with col_novo_rni:
            st.subheader("➕ Registrar Exame")
            with st.form(f"form_novo_rni_{p['id']}", clear_on_submit=True):
                nova_data = st.date_input("Data da Coleta", value=datetime.today())
                novo_rni = st.number_input("Valor do RNI", min_value=0.5, max_value=10.0, step=0.1, value=2.5)
                btn_adicionar = st.form_submit_button("Salvar Exame")

                if btn_adicionar:
                    p.setdefault("rniHistory", []).insert(0, {
                        "date": nova_data.strftime("%Y-%m-%d"),
                        "value": float(novo_rni),
                    })
                    salvar_dados()
                    st.success("RNI adicionado com sucesso!")
                    st.rerun()

        st.markdown("---")

        tab_tabela, tab_evolucao, tab_meds = st.tabs(
            ["📋 Histórico de Coletas", "📝 Evolução Farmacêutica", "💊 Medicamentos em Uso"]
        )

        with tab_tabela:
            if p.get("rniHistory"):
                df_hist = pd.DataFrame(p["rniHistory"])
                df_hist["date"] = pd.to_datetime(df_hist["date"]).dt.strftime("%d/%m/%Y")
                df_hist.columns = ["Data da Coleta", "Valor do RNI"]
                st.dataframe(df_hist, use_container_width=True, hide_index=True)
            else:
                st.info("Sem registros no histórico.")

        with tab_evolucao:
            if p.get("evolution"):
                st.text_area("Registro da Última Evolução:", p["evolution"], height=250, disabled=True)
            else:
                st.info("Nenhuma evolução registrada para este paciente.")

        with tab_meds:
            st.write("**Farmacoterapia Habitual:**")
            st.info(p.get("meds") or "Nenhum medicamento adicional registrado.")

# ------------------------------------------------------------------------------
# 4.3 ABA: ADICIONAR PACIENTE — formulário de cadastro
# ------------------------------------------------------------------------------
with aba_novo_paciente:
    st.subheader("➕ Cadastrar novo paciente")

    with st.form("form_novo_paciente", clear_on_submit=True):
        col_a, col_b = st.columns(2)

        with col_a:
            novo_nome = st.text_input("Nome completo *")
            novo_contato = st.text_input("Contato (telefone)")
            nova_idade = st.number_input("Idade", min_value=0, max_value=120, value=60)
            nova_admissao = st.date_input("Data de admissão", value=datetime.today())
            novo_nivel = st.selectbox("Complexidade", ["Baixo", "Médio", "Alto"], index=1)
            novo_organizador = st.selectbox("Usa organizador de comprimidos?", ["Não", "Sim"])

        with col_b:
            nova_indicacao = st.selectbox(
                "Indicação da anticoagulação",
                ["Fibrilação Atrial", "Prótese Mecânica Mitral", "Prótese Mecânica Aórtica",
                 "TVP/TEP", "Valvulopatia Reumática", "Outra"]
            )
            col_alvo1, col_alvo2 = st.columns(2)
            alvo_min = col_alvo1.number_input("RNI alvo mínimo", value=2.0, step=0.1)
            alvo_max = col_alvo2.number_input("RNI alvo máximo", value=3.0, step=0.1)
            nova_dose = st.number_input("Dose semanal (mg)", min_value=0.0, value=35.0, step=2.5)
            novos_meds = st.text_area("Medicamentos em uso", placeholder="Ex: Varfarina 5mg 1-0-0, ...")

        st.markdown("**Primeiro exame de RNI (opcional)**")
        col_rni1, col_rni2 = st.columns(2)
        primeira_data = col_rni1.date_input("Data do exame", value=datetime.today(), key="primeira_data")
        primeiro_rni = col_rni2.number_input("Valor do RNI", min_value=0.0, max_value=10.0, value=0.0, step=0.1, key="primeiro_rni")

        enviado = st.form_submit_button("💾 Cadastrar Paciente", type="primary")

        if enviado:
            if not novo_nome.strip():
                st.error("O nome do paciente é obrigatório.")
            else:
                historico_inicial = []
                if primeiro_rni > 0:
                    historico_inicial.append({
                        "date": primeira_data.strftime("%Y-%m-%d"),
                        "value": float(primeiro_rni),
                    })

                novo_paciente = {
                    "id": gerar_id(),
                    "name": novo_nome.strip(),
                    "contact": novo_contato.strip(),
                    "age": nova_idade,
                    "admission": nova_admissao.strftime("%Y-%m-%d"),
                    "level": novo_nivel,
                    "organizer": novo_organizador,
                    "indication": nova_indicacao,
                    "target": f"{alvo_min}-{alvo_max}",
                    "weeklyDose": nova_dose,
                    "meds": novos_meds.strip(),
                    "rniHistory": historico_inicial,
                }

                st.session_state.dados.setdefault("patients", []).append(novo_paciente)
                salvar_dados()
                st.success(f"Paciente **{novo_nome}** cadastrado com sucesso!")
                st.rerun()
