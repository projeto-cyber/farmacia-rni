import streamlit as st
import pandas as pd
import json
import os
import random
import string
from datetime import datetime
import plotly.graph_objects as go

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

    .card-categoria {
        border-left: 5px solid;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. FUNÇÕES DE BANCO DE DADOS (JSON local = nosso "banco de pacientes")
# ==============================================================================
def carregar_dados():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"patients": [], "agenda": {}}


def salvar_dados():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.dados, f, ensure_ascii=False, indent=2)


def gerar_id():
    return "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))


if "dados" not in st.session_state:
    st.session_state.dados = carregar_dados()

pacientes = st.session_state.dados.get("patients", [])

# ==============================================================================
# 3. FUNÇÕES CLÍNICAS (TTR, faixa alvo, status atual, tendência)
# ==============================================================================
def faixa_alvo(paciente):
    try:
        lo, hi = map(float, paciente.get("target", "2.0-3.0").split("-"))
        return lo, hi
    except Exception:
        return 2.0, 3.0


def historico_ordenado(paciente, decrescente=True):
    """Retorna o histórico de RNI como lista de dicts ordenada por data."""
    hist = paciente.get("rniHistory", [])
    if not hist:
        return []
    try:
        return sorted(hist, key=lambda e: e["date"], reverse=decrescente)
    except Exception:
        return hist


def calcular_ttr_rosendaal(historico, min_alvo, max_alvo):
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
    if not historico:
        return 0.0, 0, 0
    try:
        total = len(historico)
        na_faixa = sum(1 for e in historico if min_alvo <= float(e["value"]) <= max_alvo)
        return (na_faixa / total) * 100.0, na_faixa, total
    except Exception:
        return 0.0, 0, 0


def status_ttr(valor):
    if valor >= 70.0:
        return "#10B981", "#ECFDF5", "Estável"
    elif valor >= 60.0:
        return "#F59E0B", "#FFFBEB", "Alerta"
    else:
        return "#EF4444", "#FEF2F2", "Crítico"


def status_ultimo_rni(paciente):
    """Classifica o exame mais recente: 'abaixo', 'dentro' ou 'acima' da faixa alvo."""
    hist = historico_ordenado(paciente)
    if not hist:
        return None, None
    lo, hi = faixa_alvo(paciente)
    valor = float(hist[0]["value"])
    if valor < lo:
        return "abaixo", valor
    elif valor > hi:
        return "acima", valor
    return "dentro", valor


def tendencia_paciente(paciente):
    """Compara os 2 últimos exames para saber se o paciente está melhorando, piorando ou estável."""
    hist = historico_ordenado(paciente)
    if len(hist) < 2:
        return "sem_dados"
    lo, hi = faixa_alvo(paciente)
    centro = (lo + hi) / 2
    atual = float(hist[0]["value"])
    anterior = float(hist[1]["value"])
    dist_atual = abs(atual - centro)
    dist_anterior = abs(anterior - centro)
    if dist_atual < dist_anterior - 0.05:
        return "melhorando"
    elif dist_atual > dist_anterior + 0.05:
        return "piorando"
    return "estavel"


def conduta_protocolo(rni, lo, hi):
    """
    Sugestão de conduta e percentual de ajuste de dose com base na posição
    do RNI em relação à faixa terapêutica do paciente.

    ATENÇÃO: isto é um protocolo padrão de referência (ajustável). A decisão
    final de conduta é sempre do prescritor/farmacêutico responsável, conforme
    o protocolo institucional vigente.

    Retorna: (mensagem, percentual, cor, cor_fundo, rótulo_severidade)
    """
    if rni < lo:
        diferenca = lo - rni
        if diferenca <= 0.3:
            return ("Aumentar a dose semanal em 5–10%. Reavaliar RNI em 1–2 semanas.",
                    "+5% a +10%", "#F59E0B", "#FFFBEB", "Atenção")
        elif diferenca <= 0.7:
            return ("Aumentar a dose semanal em 10–15%. Reavaliar RNI em 1 semana.",
                    "+10% a +15%", "#F97316", "#FFF7ED", "Alerta")
        else:
            return ("Aumentar a dose semanal em 15–20%. Considerar dose adicional pontual. Reavaliar em 3–5 dias.",
                    "+15% a +20%", "#EF4444", "#FEF2F2", "Crítico — subterapêutico")
    elif rni > hi:
        diferenca = rni - hi
        if diferenca <= 0.5:
            return ("Reduzir a dose semanal em 5–10%. Reavaliar RNI em 1–2 semanas.",
                    "-5% a -10%", "#F59E0B", "#FFFBEB", "Atenção")
        elif diferenca <= 1.5:
            return ("Omitir 1 dose e reduzir a dose semanal em 10–20%. Reavaliar em 3–5 dias.",
                    "-10% a -20%", "#F97316", "#FFF7ED", "Alerta")
        else:
            return ("Suspender o anticoagulante, avaliar risco de sangramento e necessidade de vitamina K. Contatar o prescritor com urgência.",
                    "Suspender", "#EF4444", "#FEF2F2", "Crítico — supraterapêutico")
    else:
        return ("Manter a dose semanal atual. Reavaliar RNI em 4 semanas.",
                "Manter (0%)", "#10B981", "#ECFDF5", "Dentro da meta")


# ==============================================================================
# 4. GRÁFICOS (Plotly — visual em português, sem zoom, hover facilitado)
# ==============================================================================
def grafico_evolucao_rni(historico, lo, hi):
    df = pd.DataFrame(historico)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = df["value"].astype(float)
    df = df.sort_values("date")

    fig = go.Figure()

    fig.add_hrect(
        y0=lo, y1=hi,
        fillcolor="#10B981", opacity=0.13, line_width=0,
        annotation_text="Faixa Terapêutica", annotation_position="top left",
        annotation_font_color="#059669", annotation_font_size=12
    )
    fig.add_hline(y=lo, line_dash="dash", line_color="#10B981", line_width=1.6)
    fig.add_hline(y=hi, line_dash="dash", line_color="#10B981", line_width=1.6)

    cores_pontos = ["#EF4444" if (v < lo or v > hi) else "#2563EB" for v in df["value"]]

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["value"],
        mode="lines+markers",
        name="RNI",
        line=dict(color="#2563EB", width=3),
        marker=dict(size=9, color=cores_pontos, line=dict(width=2, color="white")),
        hovertemplate="<b>%{x|%d/%m/%Y}</b><br>RNI: <b>%{y:.2f}</b><extra></extra>",
    ))

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Data da Coleta",
        yaxis_title="Valor do RNI",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=40, b=10),
        height=350,
        showlegend=False,
        font=dict(family="Inter, sans-serif", size=13, color="#334155"),
        hoverlabel=dict(bgcolor="#0F172A", font_color="white", font_size=13),
    )
    fig.update_xaxes(fixedrange=True, showgrid=False, tickformat="%d/%m/%y")
    fig.update_yaxes(fixedrange=True, gridcolor="#F1F5F9", zeroline=False)

    return fig


def grafico_qualidade_ambulatorio(lista_pacientes, n_ultimos=5):
    """Barras empilhadas: qualidade do controle de RNI (últimos exames) por paciente."""
    linhas = []
    for p in lista_pacientes:
        hist = historico_ordenado(p)[:n_ultimos]
        if not hist:
            continue
        lo, hi = faixa_alvo(p)
        contagem = {"Abaixo da faixa": 0, "Dentro da faixa": 0, "Acima da faixa": 0}
        for e in hist:
            v = float(e["value"])
            if v < lo:
                contagem["Abaixo da faixa"] += 1
            elif v > hi:
                contagem["Acima da faixa"] += 1
            else:
                contagem["Dentro da faixa"] += 1
        linhas.append({"Paciente": p["name"], **contagem})

    if not linhas:
        return None

    df = pd.DataFrame(linhas)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Paciente"], y=df["Abaixo da faixa"], name="Abaixo da faixa",
        marker_color="#F59E0B",
        hovertemplate="<b>%{x}</b><br>Abaixo da faixa: %{y} exame(s)<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["Paciente"], y=df["Dentro da faixa"], name="Dentro da faixa",
        marker_color="#10B981",
        hovertemplate="<b>%{x}</b><br>Dentro da faixa: %{y} exame(s)<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["Paciente"], y=df["Acima da faixa"], name="Acima da faixa",
        marker_color="#EF4444",
        hovertemplate="<b>%{x}</b><br>Acima da faixa: %{y} exame(s)<extra></extra>",
    ))

    fig.update_layout(
        barmode="stack",
        title=dict(text=f"Qualidade do controle — últimos {n_ultimos} exames por paciente", font=dict(size=14)),
        xaxis_title="", yaxis_title="Nº de exames",
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
        height=380,
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        hoverlabel=dict(bgcolor="#0F172A", font_color="white"),
    )
    fig.update_xaxes(fixedrange=True, tickangle=-30)
    fig.update_yaxes(fixedrange=True, gridcolor="#F1F5F9")

    return fig


# ==============================================================================
# 5. NAVEGAÇÃO PRINCIPAL
# ==============================================================================
st.title("🩸 Ambulatório de Anticoagulação")
st.caption("Acompanhamento clínico de pacientes em uso de anticoagulante oral (RNI / TTR)")

aba_visao_geral, aba_ficha, aba_novo_paciente = st.tabs(
    ["📊 Visão Geral", "👤 Ficha do Paciente", "➕ Adicionar Paciente"]
)

# ------------------------------------------------------------------------------
# 5.1 VISÃO GERAL
# ------------------------------------------------------------------------------
with aba_visao_geral:
    if not pacientes:
        st.info("Nenhum paciente cadastrado ainda. Use a aba **➕ Adicionar Paciente**.")
    else:
        resumo = []
        for p in pacientes:
            lo, hi = faixa_alvo(p)
            ttr = calcular_ttr_rosendaal(p.get("rniHistory", []), lo, hi)
            status_atual, valor_atual = status_ultimo_rni(p)
            tendencia = tendencia_paciente(p)
            resumo.append({
                "paciente": p, "ttr": ttr,
                "status_atual": status_atual, "valor_atual": valor_atual,
                "tendencia": tendencia,
            })

        com_exame = [r for r in resumo if r["status_atual"] is not None]
        total_com_exame = len(com_exame) or 1

        adequados = [r for r in com_exame if r["ttr"] >= 60.0]
        abaixo = [r for r in com_exame if r["status_atual"] == "abaixo"]
        dentro = [r for r in com_exame if r["status_atual"] == "dentro"]
        acima = [r for r in com_exame if r["status_atual"] == "acima"]

        pct_adequado = len(adequados) / total_com_exame * 100
        pct_abaixo = len(abaixo) / total_com_exame * 100
        pct_dentro = len(dentro) / total_com_exame * 100
        pct_acima = len(acima) / total_com_exame * 100

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pacientes cadastrados", len(pacientes))
        m2.metric("TTR Adequado (≥60%)", f"{pct_adequado:.0f}%")
        m3.metric("Abaixo da faixa (último RNI)", f"{pct_abaixo:.0f}%")
        m4.metric("Acima da faixa (último RNI)", f"{pct_acima:.0f}%")

        st.markdown("#### 📑 Tabela explicativa")
        df_explicativo = pd.DataFrame([
            {"Categoria": "TTR Adequado (≥ 60%)", "Quantidade": len(adequados),
             "Percentual": f"{pct_adequado:.1f}%",
             "Descrição": "Pacientes com bom controle terapêutico ao longo do tempo"},
            {"Categoria": "RNI Abaixo da Faixa", "Quantidade": len(abaixo),
             "Percentual": f"{pct_abaixo:.1f}%",
             "Descrição": "Último exame indica risco trombótico (subterapêutico)"},
            {"Categoria": "RNI Dentro da Faixa", "Quantidade": len(dentro),
             "Percentual": f"{pct_dentro:.1f}%",
             "Descrição": "Último exame dentro da meta terapêutica"},
            {"Categoria": "RNI Acima da Faixa", "Quantidade": len(acima),
             "Percentual": f"{pct_acima:.1f}%",
             "Descrição": "Último exame indica risco hemorrágico (supraterapêutico)"},
        ])
        st.dataframe(df_explicativo, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 📊 Qualidade do controle no ambulatório")
        fig_qualidade = grafico_qualidade_ambulatorio(pacientes)
        if fig_qualidade:
            st.plotly_chart(fig_qualidade, use_container_width=True,
                             config={"displayModeBar": False, "scrollZoom": False})
        else:
            st.info("Ainda não há exames suficientes para montar o gráfico.")

        st.markdown("---")
        st.markdown("#### 🚦 Pacientes por situação clínica")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("##### 🔴 Fora da faixa terapêutica")
            criticos = [r for r in com_exame if r["status_atual"] in ("abaixo", "acima")]
            if not criticos:
                st.caption("Nenhum paciente fora da faixa no momento.")
            for r in criticos:
                p = r["paciente"]
                desc = "abaixo da faixa (risco trombótico)" if r["status_atual"] == "abaixo" else "acima da faixa (risco hemorrágico)"
                st.markdown(f"""
                <div class="card-categoria" style="border-color:#EF4444;background:#FEF2F2;">
                    <b style="color:#0F172A;">{p['name']}</b><br>
                    <span style="font-size:0.85rem;color:#7F1D1D;">Último RNI: {r['valor_atual']:.2f} — {desc}</span>
                </div>""", unsafe_allow_html=True)

        with col_b:
            st.markdown("##### 🟢 Aptos para alta (TTR ≥ 70%)")
            aptos = [r for r in com_exame if r["ttr"] >= 70.0]
            if not aptos:
                st.caption("Nenhum paciente nessa condição no momento.")
            for r in aptos:
                p = r["paciente"]
                st.markdown(f"""
                <div class="card-categoria" style="border-color:#10B981;background:#ECFDF5;">
                    <b style="color:#0F172A;">{p['name']}</b><br>
                    <span style="font-size:0.85rem;color:#065F46;">TTR: {r['ttr']:.1f}% — bem controlado na faixa terapêutica</span>
                </div>""", unsafe_allow_html=True)

        col_c, col_d = st.columns(2)

        with col_c:
            st.markdown("##### 📈 Em melhora")
            melhorando = [r for r in com_exame if r["tendencia"] == "melhorando"]
            if not melhorando:
                st.caption("Nenhum paciente com tendência de melhora identificada.")
            for r in melhorando:
                p = r["paciente"]
                st.markdown(f"""
                <div class="card-categoria" style="border-color:#2563EB;background:#EFF6FF;">
                    <b style="color:#0F172A;">{p['name']}</b><br>
                    <span style="font-size:0.85rem;color:#1E40AF;">Últimos exames aproximando-se da meta terapêutica</span>
                </div>""", unsafe_allow_html=True)

        with col_d:
            st.markdown("##### 🟡 Precisam de atenção (TTR entre 60% e 70%)")
            atencao = [r for r in com_exame if 60.0 <= r["ttr"] < 70.0]
            if not atencao:
                st.caption("Nenhum paciente nessa condição no momento.")
            for r in atencao:
                p = r["paciente"]
                st.markdown(f"""
                <div class="card-categoria" style="border-color:#F59E0B;background:#FFFBEB;">
                    <b style="color:#0F172A;">{p['name']}</b><br>
                    <span style="font-size:0.85rem;color:#92400E;">TTR: {r['ttr']:.1f}% — acompanhar de perto</span>
                </div>""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 5.2 FICHA DO PACIENTE — lista à direita, conteúdo à esquerda
# ------------------------------------------------------------------------------
with aba_ficha:
    if not pacientes:
        st.info("Cadastre um paciente primeiro na aba **➕ Adicionar Paciente**.")
    else:
        col_main, col_lista = st.columns([4, 1])

        # Usamos o "id" (estável) para controlar a seleção, e não o nome —
        # assim, editar o nome de um paciente não quebra a seleção atual.
        mapa_id_nome = {p.get("id", p["name"]): p["name"] for p in pacientes}
        ids_ordenados = sorted(mapa_id_nome.keys(), key=lambda pid: mapa_id_nome[pid])

        with col_lista:
            st.markdown("##### 🗂️ Pacientes")
            id_sel = st.radio(
                "Selecionar paciente", ids_ordenados,
                format_func=lambda pid: mapa_id_nome[pid],
                key="ficha_paciente_sel_id",
                label_visibility="collapsed"
            )

        p = next(item for item in pacientes if item.get("id", item["name"]) == id_sel)

        with col_main:
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
                st.subheader("📈 Evolução do RNI")
                if p.get("rniHistory"):
                    fig = grafico_evolucao_rni(p["rniHistory"], min_alvo, max_alvo)
                    st.plotly_chart(fig, use_container_width=True,
                                     config={"displayModeBar": False, "scrollZoom": False})
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
                        st.toast(f"Novo RNI ({novo_rni:.1f}) registrado e salvo automaticamente!", icon="🩸")
                        st.rerun()

            # --- Painel de conduta sugerida, atualizado sempre que o RNI muda ---
            st.markdown("---")
            st.subheader("🧭 Conduta Sugerida (Protocolo)")
            if p.get("rniHistory"):
                _, valor_atual_rni = status_ultimo_rni(p)
                mensagem, percentual, cor_c, bg_c, rotulo_c = conduta_protocolo(valor_atual_rni, min_alvo, max_alvo)
                st.markdown(f"""
                <div style="border-left:6px solid {cor_c}; background:{bg_c}; padding:16px 20px; border-radius:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                        <span style="font-weight:700;color:{cor_c};font-size:1rem;">⚠️ {rotulo_c}</span>
                        <span style="background:{cor_c};color:white;padding:3px 12px;border-radius:9999px;font-weight:700;font-size:0.85rem;">{percentual}</span>
                    </div>
                    <div style="margin-top:8px;color:#0F172A;font-size:0.95rem;">{mensagem}</div>
                    <div style="margin-top:10px;font-size:0.75rem;color:#64748B;">
                        Último RNI: <b>{valor_atual_rni:.2f}</b> · Faixa alvo: {min_alvo}-{max_alvo} ·
                        Sugestão baseada em protocolo padrão — validar sempre com o prescritor responsável.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Registre um exame de RNI para visualizar a conduta sugerida pelo protocolo.")

            st.markdown("---")

            tab_tabela, tab_dose, tab_evolucao, tab_meds, tab_editar = st.tabs(
                ["📋 Histórico de Coletas", "💉 Dose & Esquema Semanal", "📝 Evolução Farmacêutica",
                 "💊 Medicamentos em Uso", "✏️ Editar Dados"]
            )

            with tab_tabela:
                if p.get("rniHistory"):
                    df_hist = pd.DataFrame(p["rniHistory"])
                    df_hist["date"] = pd.to_datetime(df_hist["date"]).dt.strftime("%d/%m/%Y")
                    df_hist.columns = ["Data da Coleta", "Valor do RNI"]
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem registros no histórico.")

            with tab_dose:
                st.markdown("##### 💉 Dose Semanal Atual")
                st.markdown(f"<div class='info-value' style='font-size:1.3rem;'>{p.get('weeklyDose', 0)} mg / semana</div>", unsafe_allow_html=True)

                with st.form(f"form_dose_{p['id']}", clear_on_submit=True):
                    col_d1, col_d2 = st.columns(2)
                    nova_dose_semanal = col_d1.number_input(
                        "Nova dose semanal (mg)", min_value=0.0,
                        value=float(p.get("weeklyDose") or 0), step=2.5
                    )
                    data_dose = col_d2.date_input("Data de início desta dose", value=datetime.today())
                    btn_dose = st.form_submit_button("💾 Atualizar Dose Semanal")

                    if btn_dose:
                        p.setdefault("doseHistory", []).insert(0, {
                            "date": data_dose.strftime("%Y-%m-%d"),
                            "weeklyDose": float(nova_dose_semanal),
                        })
                        p["weeklyDose"] = float(nova_dose_semanal)
                        salvar_dados()
                        st.toast(f"Dose semanal atualizada para {nova_dose_semanal} mg", icon="💾")
                        st.rerun()

                st.markdown("##### 📜 Histórico de Doses")
                if p.get("doseHistory"):
                    df_dose = pd.DataFrame(p["doseHistory"])
                    df_dose["date"] = pd.to_datetime(df_dose["date"]).dt.strftime("%d/%m/%Y")
                    df_dose.columns = ["Data", "Dose Semanal (mg)"]
                    st.dataframe(df_dose, use_container_width=True, hide_index=True)
                else:
                    st.caption("Nenhuma alteração de dose registrada ainda. As próximas atualizações aparecerão aqui.")

                st.markdown("---")
                st.markdown("##### 🗓️ Esquema Semanal de Doses (Reloginho)")
                st.caption("Informe a dose a ser tomada em cada dia da semana, conforme o esquema posológico do paciente.")

                reloginho_atual = p.get("reloginho", {})
                dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

                with st.form(f"form_reloginho_{p['id']}"):
                    cols_dias = st.columns(7)
                    valores_dias = {}
                    for i, dia in enumerate(dias_semana):
                        with cols_dias[i]:
                            valores_dias[dia] = st.text_input(
                                dia, value=reloginho_atual.get(dia, ""),
                                key=f"reloginho_{p['id']}_{dia}", placeholder="ex: 5mg"
                            )
                    btn_reloginho = st.form_submit_button("💾 Salvar Esquema Semanal")

                    if btn_reloginho:
                        p["reloginho"] = valores_dias
                        salvar_dados()
                        st.toast("Esquema semanal atualizado e salvo!", icon="🗓️")
                        st.rerun()

            with tab_evolucao:
                if p.get("evolution"):
                    st.text_area("Registro da Última Evolução:", p["evolution"], height=250, disabled=True)
                else:
                    st.info("Nenhuma evolução registrada para este paciente.")

            with tab_meds:
                st.write("**Farmacoterapia Habitual:**")
                st.info(p.get("meds") or "Nenhum medicamento adicional registrado.")

            with tab_editar:
                st.write("Altere os dados do paciente e clique em salvar.")
                with st.form(f"form_editar_{p['id']}"):
                    col_e1, col_e2 = st.columns(2)

                    with col_e1:
                        edit_nome = st.text_input("Nome completo", value=p.get("name", ""))
                        edit_contato = st.text_input("Contato", value=p.get("contact", ""))
                        idade_atual = p.get("age", 0)
                        idade_atual = int(idade_atual) if str(idade_atual).isdigit() else 0
                        edit_idade = st.number_input("Idade", min_value=0, max_value=120, value=idade_atual)
                        niveis = ["Baixo", "Médio", "Alto"]
                        edit_nivel = st.selectbox("Complexidade", niveis,
                                                   index=niveis.index(p.get("level")) if p.get("level") in niveis else 1)
                        edit_organizador = st.selectbox("Usa organizador de comprimidos?", ["Não", "Sim"],
                                                         index=0 if p.get("organizer", "Não") == "Não" else 1)

                    with col_e2:
                        opcoes_indicacao = ["Fibrilação Atrial", "Prótese Mecânica Mitral", "Prótese Mecânica Aórtica",
                                             "TVP/TEP", "Valvulopatia Reumática", "Outra"]
                        indicacao_atual = p.get("indication", "Fibrilação Atrial")
                        idx_indicacao = opcoes_indicacao.index(indicacao_atual) if indicacao_atual in opcoes_indicacao else 0
                        edit_indicacao = st.selectbox("Indicação da anticoagulação", opcoes_indicacao, index=idx_indicacao)

                        lo_atual, hi_atual = faixa_alvo(p)
                        col_alvo1, col_alvo2 = st.columns(2)
                        edit_alvo_min = col_alvo1.number_input("RNI alvo mínimo", value=lo_atual, step=0.1)
                        edit_alvo_max = col_alvo2.number_input("RNI alvo máximo", value=hi_atual, step=0.1)
                        edit_meds = st.text_area("Medicamentos em uso", value=p.get("meds", ""))
                        st.caption("💡 A dose semanal agora é ajustada na aba **💉 Dose & Esquema Semanal**, com histórico.")

                    salvar_edicao = st.form_submit_button("💾 Salvar Alterações", type="primary")

                    if salvar_edicao:
                        if not edit_nome.strip():
                            st.error("O nome do paciente não pode ficar vazio.")
                        else:
                            p["name"] = edit_nome.strip()
                            p["contact"] = edit_contato.strip()
                            p["age"] = edit_idade
                            p["level"] = edit_nivel
                            p["organizer"] = edit_organizador
                            p["indication"] = edit_indicacao
                            p["target"] = f"{edit_alvo_min}-{edit_alvo_max}"
                            p["meds"] = edit_meds.strip()
                            salvar_dados()
                            st.success("Dados do paciente atualizados com sucesso!")
                            st.rerun()

            # --- Backup de dados: salvar (exportar) e importar, no rodapé direito ---
            st.markdown("---")
            col_vazia, col_backup = st.columns([3, 1])
            with col_backup:
                st.markdown("###### ⚙️ Backup de Dados")
                dados_json_str = json.dumps(st.session_state.dados, ensure_ascii=False, indent=2)
                st.download_button(
                    "💾 Salvar (baixar .json)",
                    data=dados_json_str,
                    file_name="dados.json",
                    mime="application/json",
                    use_container_width=True,
                )
                arquivo_importado = st.file_uploader(
                    "📂 Importar dados (.json)", type=["json"], key="importar_dados"
                )
                if arquivo_importado is not None:
                    if st.session_state.get("ultimo_arquivo_importado") != arquivo_importado.name:
                        try:
                            novos_dados = json.load(arquivo_importado)
                            st.session_state.dados = novos_dados
                            st.session_state["ultimo_arquivo_importado"] = arquivo_importado.name
                            salvar_dados()
                            st.success("Dados importados com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao importar arquivo: {e}")

# ------------------------------------------------------------------------------
# 5.3 ADICIONAR PACIENTE
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
