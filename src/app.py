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
# CONFIGURAÇÕES
# -------------------------------------------------------------------------

# Frota total (meta do gauge de frota)
META_TOTAL_CARROS = 199

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------------------------------

def carregar_dados(url: str) -> tuple[pd.DataFrame, dict]:
    """Chama o scraper e retorna DataFrame + resumo."""
    return get_monitoramento(url)


def chamar_atualiza_status(url_atualiza: str) -> tuple[bool, str]:
    """
    Chama o endpoint que atualiza a tabela no servidor.

    :param url_atualiza: URL completa de atualiza_status.php
    :return: (sucesso, mensagem)
    """
    url_atualiza = url_atualiza.strip()
    logger.info("Chamando endpoint: %s", url_atualiza)

    try:
        resp = requests.get(url_atualiza, timeout=20)
        resp.raise_for_status()
        texto = resp.text.strip() or "Atualização concluída."
        return True, texto
    except requests.RequestException as exc:
        logger.exception("Erro ao chamar atualiza_status")
        return False, f"Erro ao atualizar status: {exc}"


def make_gauge_percent(title: str, value_percent: float) -> go.Figure:
    """
    Gauge com DUAS CORES APENAS:
    - Fundo inteiro vermelho
    - Barra preenchida VERDE ocupando 100% da faixa
    - Ticks a cada 10
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value_percent,
            number={"suffix": "%"},
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100], "dtick": 10},
                # Barra de progresso (verde) ocupa toda a largura
                "bar": {
                    "color": "#198754",
                    "thickness": 1.0,  # 1.0 = ocupa toda a área útil do arco
                },
                # Fundo 100% vermelho
                "steps": [
                    {"range": [0, 100], "color": "#8B0000"},
                ],
                "borderwidth": 0,
            },
        )
    )

    fig.update_layout(
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


def color_status(val: str) -> str:
    """Aplica cor na coluna Status da tabela."""
    if isinstance(val, str) and val.lower().startswith("funcionando"):
        return "background-color:#198754;color:white;"
    return "background-color:#842029;color:white;"


# -------------------------------------------------------------------------
# APLICAÇÃO PRINCIPAL
# -------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Monitoramento Wi-Fi", layout="wide")

    st.title("Monitoramento de Carros - Wi-Fi")
    st.write("Dashboard para consulta e atualização do monitoramento de carros via Wi-Fi.")

    # URLs
    url_monitoramento = st.text_input(
        "URL da página de monitoramento:",
        "http://45.71.160.173/monitoramento/",
    )
    url_atualiza_status = st.text_input(
        "URL de atualização de status:",
        "http://45.71.160.173/monitoramento/atualiza_status.php",
    )

    # Estado interno
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "resumo" not in st.session_state:
        st.session_state["resumo"] = None
    if "ultima_msg_atualiza" not in st.session_state:
        st.session_state["ultima_msg_atualiza"] = ""
    if "ultima_execucao" not in st.session_state:
        st.session_state["ultima_execucao"] = None

    # Botão principal
    if st.button("Atualizar dados agora"):
        # Placeholder para o texto de status
        status_placeholder = st.empty()
        status_placeholder.subheader("Processando...")

        # Etapa 1 – Atualizar status no servidor
        with st.spinner("Etapa 1/2: Atualizando status..."):
            ok, msg = chamar_atualiza_status(url_atualiza_status)
            st.session_state["ultima_msg_atualiza"] = msg

        if ok:
            st.success("Status atualizado com sucesso!")
        else:
            st.error("Falha ao atualizar status.")
        st.info(f"Mensagem do servidor: {msg}")

        # Etapa 2 – Carregar dados
        with st.spinner("Etapa 2/2: Carregando dados..."):
            try:
                df, resumo = carregar_dados(url_monitoramento)
                st.session_state["df"] = df
                st.session_state["resumo"] = resumo

                tz = pytz.timezone("America/Sao_Paulo")
                st.session_state["ultima_execucao"] = datetime.datetime.now(tz)

                st.success("Dados carregados com sucesso.")
            except MonitoramentoError as exc:
                st.error(f"Erro ao buscar dados: {exc}")

        # Ao final de todas as etapas, muda de "Processando..." para "Processado"
        status_placeholder.subheader("Processado")

    df = st.session_state["df"]
    resumo = st.session_state["resumo"]

    if df is None or resumo is None:
        st.stop()

    # Última atualização
    if st.session_state["ultima_execucao"]:
        dt = st.session_state["ultima_execucao"].strftime("%d/%m/%Y %H:%M:%S")
        st.caption(f"Última atualização completa em: {dt}")

    # ---------------------------------------------------------------------
    # INDICADORES GAUGE
    # ---------------------------------------------------------------------

    st.subheader("Indicadores Gauge")

    total = resumo["total_carros"]
    funcionando = resumo["total_funcionando"]
    nao_funcionando = resumo["total_nao_funcionando"]

    pct_funcionando = (funcionando / total * 100) if total else 0
    pct_nok = 100 - pct_funcionando
    pct_total_meta = min(total / META_TOTAL_CARROS * 100, 100)

    col1, col2, col3 = st.columns(3)

    # 1) Carros Funcionando
    col1.plotly_chart(
        make_gauge_percent("Carros Funcionando", pct_funcionando),
        use_container_width=True,
    )
    col1.write(f"{funcionando} de {total} veículos")

    # 2) Carros Inoperantes
    col2.plotly_chart(
        make_gauge_percent("Carros Inoperantes", pct_nok),
        use_container_width=True,
    )
    col2.write(f"{nao_funcionando} de {total} veículos")

    # 3) Total Monitorado em Relação à Frota
    col3.plotly_chart(
        make_gauge_percent("Total Monitorado em Relação à Frota", pct_total_meta),
        use_container_width=True,
    )
    col3.write(f"{total} de {META_TOTAL_CARROS} veículos (frota)")

    # ---------------------------------------------------------------------
    # MENSAGEM DO SERVIDOR
    # ---------------------------------------------------------------------

    if st.session_state["ultima_msg_atualiza"]:
        st.info(
            f"Mensagem da última atualização: "
            f"{st.session_state['ultima_msg_atualiza']}"
        )

    # ---------------------------------------------------------------------
    # TABELA COLORIDA
    # ---------------------------------------------------------------------

    st.subheader("Tabela de Carros")

    filtro = st.text_input("Filtrar por carro:")

    df_exibe = df.copy()

    if filtro.strip():
        df_exibe = df_exibe[
            df_exibe["Carro"].str.contains(filtro, case=False, na=False)
        ]

    if "Último Acesso" in df_exibe.columns:
        df_exibe = df_exibe.sort_values("Último Acesso", ascending=False)

    styled = df_exibe.style.applymap(color_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, height=500)


if __name__ == "__main__":
    main()
