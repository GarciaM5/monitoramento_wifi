"""
Aplicação Streamlit para monitorar o status dos carros (Wi-Fi).

Fluxo ao clicar em "Atualizar dados agora":
1. Chama o endpoint /atualiza_status.php para atualizar a tabela no servidor.
2. Em seguida, lê novamente a página /monitoramento/ e atualiza os dados no app.

Para executar localmente:
    streamlit run src/app.py
"""

from __future__ import annotations

import datetime
import logging

import pandas as pd
import pytz
import requests
import streamlit as st
import plotly.graph_objects as go

from scraper import get_monitoramento, MonitoramentoError

# -------------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# -------------------------------------------------------------------------

# Meta de frota monitorada (para o gauge de total).
# Ajuste se desejar outra meta de referência (ex.: 200 veículos).
META_TOTAL_CARROS = 200

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------------------------------

def carregar_dados(url: str) -> tuple[pd.DataFrame, dict]:
    """
    Chama o scraper para obter a tabela e o resumo de monitoramento.

    :param url: URL da página de monitoramento.
    :return: (DataFrame, dict_resumo)
    """
    return get_monitoramento(url)


def chamar_atualiza_status(url_atualiza: str) -> tuple[bool, str]:
    """
    Chama o endpoint que atualiza a tabela de status no servidor.

    :param url_atualiza: URL completa de atualiza_status.php
    :return: (sucesso: bool, mensagem: str)
    """
    url_atualiza = url_atualiza.strip()

    logger.info("Chamando endpoint de atualização: %s", url_atualiza)

    try:
        resp = requests.get(url_atualiza, timeout=20)
        resp.raise_for_status()
        texto = resp.text.strip()
        if not texto:
            texto = "Atualização concluída (sem mensagem do servidor)."
        return True, texto
    except requests.RequestException as exc:
        logger.exception("Falha ao chamar atualiza_status.php")
        return False, f"Erro ao atualizar status no servidor: {exc}"


def make_gauge_percent(title: str, value_percent: float) -> go.Figure:
    """
    Cria um gauge (relógio) de 0 a 100% com cores por faixa.

    :param title: Título exibido no gauge.
    :param value_percent: Valor em porcentagem.
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value_percent,
            number={"suffix": "%"},
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "white"},
                "steps": [
                    {"range": [0, 60], "color": "#8B0000"},     # vermelho escuro
                    {"range": [60, 85], "color": "#FFC107"},   # amarelo
                    {"range": [85, 100], "color": "#198754"},  # verde
                ],
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def color_status(val: str) -> str:
    """
    Função de estilo para colorir a coluna 'Status' da tabela:
    - Verde para 'Funcionando'
    - Vermelho para o restante
    """
    if isinstance(val, str) and val.strip().lower().startswith("funcionando"):
        return "background-color: #198754; color: white;"
    return "background-color: #842029; color: white;"


# -------------------------------------------------------------------------
# APLICAÇÃO PRINCIPAL
# -------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Monitoramento de Carros - Wi-Fi",
        layout="wide",
    )

    st.title("Monitoramento de Carros - Wi-Fi")

    st.write(
        "Aplicação para consulta rápida e atualização do monitoramento de carros Wi-Fi."
    )

    # URLs padrão
    url_monitoramento_padrao = "http://45.71.160.173/monitoramento/"
    url_atualiza_status_padrao = (
        "http://45.71.160.173/monitoramento/atualiza_status.php"
    )

    col_url1, col_url2 = st.columns(2)

    # Campos de entrada para as URLs (configuráveis na interface)
    url_monitoramento = col_url1.text_input(
        "URL da página de monitoramento:",
        url_monitoramento_padrao,
    )

    url_atualiza_status = col_url2.text_input(
        "URL de atualização de status:",
        url_atualiza_status_padrao,
    )

    # Estado da sessão
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "resumo" not in st.session_state:
        st.session_state["resumo"] = None
    if "ultima_msg_atualiza" not in st.session_state:
        st.session_state["ultima_msg_atualiza"] = ""
    if "ultima_execucao" not in st.session_state:
        st.session_state["ultima_execucao"] = None

    # Botão principal: executa as 2 etapas
    if st.button("Atualizar dados agora"):
        st.subheader("Processando atualização...")

        # 1) Atualização do status no servidor
        with st.spinner("Etapa 1/2: Atualizando status no servidor..."):
            ok, msg = chamar_atualiza_status(url_atualiza_status)
            st.session_state["ultima_msg_atualiza"] = msg

        if ok:
            st.success("Etapa 1/2 concluída: status atualizado no servidor.")
        else:
            st.error("Falha na etapa 1/2: não foi possível atualizar o status.")
            st.write(msg)

        st.info(f"Mensagem do servidor: {msg}")

        # 2) Carregar dados de monitoramento
        with st.spinner("Etapa 2/2: Carregando dados atualizados..."):
            try:
                df, resumo = carregar_dados(url_monitoramento)
                st.session_state["df"] = df
                st.session_state["resumo"] = resumo

                # Horário da última execução em America/Sao_Paulo (UTC-3)
                tz = pytz.timezone("America/Sao_Paulo")
                st.session_state["ultima_execucao"] = datetime.datetime.now(tz)

                st.success("Etapa 2/2 concluída: dados de monitoramento carregados.")
            except MonitoramentoError as exc:
                st.error(f"Erro ao carregar dados do monitoramento: {exc}")

    # Carregamento inicial automático (quando abre o app)
    if st.session_state["df"] is None:
        try:
            df, resumo = carregar_dados(url_monitoramento)
            st.session_state["df"] = df
            st.session_state["resumo"] = resumo
        except MonitoramentoError:
            st.warning(
                "Não foi possível carregar os dados automaticamente. "
                "Clique em 'Atualizar dados agora'."
            )

    df = st.session_state["df"]
    resumo = st.session_state["resumo"]

    if df is None or resumo is None:
        st.stop()

    # ---------------------------------------------------------------------
    # CÁLCULOS DE INDICADORES
    # ---------------------------------------------------------------------

    total = resumo.get("total_carros", 0) or 0
    funcionando = resumo.get("total_funcionando", 0) or 0
    nao_funcionando = resumo.get("total_nao_funcionando", 0) or 0

    if total > 0:
        pct_funcionando = 100 * funcionando / total
        pct_nao_funcionando = 100 * nao_funcionando / total
    else:
        pct_funcionando = 0.0
        pct_nao_funcionando = 0.0

    # Para o gauge de total, comparamos com uma meta
    pct_total_meta = 0.0
    if META_TOTAL_CARROS > 0:
        pct_total_meta = 100 * total / META_TOTAL_CARROS
        pct_total_meta = min(pct_total_meta, 100.0)

    # Health score = % funcionando
    health_score = pct_funcionando

    # ---------------------------------------------------------------------
    # ÚLTIMA ATUALIZAÇÃO
    # ---------------------------------------------------------------------

    if st.session_state["ultima_execucao"]:
        dt = st.session_state["ultima_execucao"].strftime("%d/%m/%Y %H:%M:%S")
        st.caption(f"Última atualização completa em: {dt}")

    # ---------------------------------------------------------------------
    # HEALTH SCORE
    # ---------------------------------------------------------------------

    st.subheader("Health Score do Sistema")

    if health_score >= 85:
        st.success(f"Saúde do sistema: {health_score:.1f}% (Boa)")
    elif health_score >= 60:
        st.warning(f"Saúde do sistema: {health_score:.1f}% (Moderada)")
    else:
        st.error(f"Saúde do sistema: {health_score:.1f}% (Crítica)")

    # ---------------------------------------------------------------------
    # INDICADORES TIPO GAUGE
    # ---------------------------------------------------------------------

    st.subheader("Resumo do Monitoramento - Indicadores Gauge")

    gcol1, gcol2, gcol3 = st.columns(3)

    # Gauge 1: Total / Meta
    fig_total = make_gauge_percent("Total monitorado vs meta", pct_total_meta)
    gcol1.plotly_chart(fig_total, use_container_width=True)
    gcol1.write(f"{total} de {META_TOTAL_CARROS} veículos (meta)")

    # Gauge 2: Funcionando
    fig_func = make_gauge_percent("Carros funcionando", pct_funcionando)
    gcol2.plotly_chart(fig_func, use_container_width=True)
    gcol2.write(f"{funcionando} de {total} veículos ({pct_funcionando:.1f}%)")

    # Gauge 3: Não funcionando
    fig_nok = make_gauge_percent("Carros não funcionando", pct_nao_funcionando)
    gcol3.plotly_chart(fig_nok, use_container_width=True)
    gcol3.write(
        f"{nao_funcionando} de {total} veículos ({pct_nao_funcionando:.1f}%)"
    )

    # ---------------------------------------------------------------------
    # MÉTRICAS COM BARRAS DE PROGRESSO
    # ---------------------------------------------------------------------

    st.subheader("Métricas - Barras de Progresso")

    st.write(
        f"**Carros funcionando:** {funcionando} de {total} veículos "
        f"({pct_funcionando:.1f}%)"
    )
    st.progress(int(round(pct_funcionando)))

    st.write(
        f"**Carros não funcionando:** {nao_funcionando} de {total} veículos "
        f"({pct_nao_funcionando:.1f}%)"
    )
    st.progress(int(round(pct_nao_funcionando)))

    # ---------------------------------------------------------------------
    # MENSAGEM DO SERVIDOR
    # ---------------------------------------------------------------------

    st.markdown("---")

    if st.session_state["ultima_msg_atualiza"]:
        st.info(
            f"Mensagem da última atualização: "
            f"{st.session_state['ultima_msg_atualiza']}"
        )

    # ---------------------------------------------------------------------
    # TABELA COLORIDA
    # ---------------------------------------------------------------------

    st.subheader("Tabela de Carros")

    filtro_carro = st.text_input("Filtrar por carro (contém):")

    df_exibicao = df.copy()

    if filtro_carro.strip():
        mask = df_exibicao["Carro"].astype(str).str.contains(
            filtro_carro, case=False, na=False
        )
        df_exibicao = df_exibicao[mask]

    if "Último Acesso" in df_exibicao.columns:
        df_exibicao = df_exibicao.sort_values(by="Último Acesso", ascending=False)

    # Aplica cor na coluna 'Status' (verde/vermelho)
    if "Status" in df_exibicao.columns:
        styled = df_exibicao.style.applymap(color_status, subset=["Status"])
        st.dataframe(
            styled,
            use_container_width=True,
            height=500,
        )
    else:
        st.dataframe(
            df_exibicao,
            use_container_width=True,
            height=500,
        )


if __name__ == "__main__":
    main()
