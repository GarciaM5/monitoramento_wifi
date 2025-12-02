"""
Aplicação Streamlit para monitorar o status dos carros (Wi-Fi).

Fluxo ao clicar em "Atualizar dados agora":
1. Chama o endpoint /atualiza_status.php para atualizar a tabela no servidor.
2. Em seguida, lê novamente a página /monitoramento/ e atualiza os dados no app.

Para executar localmente:
    streamlit run src/app.py
"""

from __future__ import annotations

import logging
import datetime

import pandas as pd
import requests
import streamlit as st

from scraper import get_monitoramento, MonitoramentoError

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Funções auxiliares
# -------------------------------------------------------------------------

def carregar_dados(url: str) -> tuple[pd.DataFrame, dict]:
    """Wrapper simples para chamar o scraper e tratar erros."""
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


# -------------------------------------------------------------------------
# Aplicação principal
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
    url_atualiza_status_padrao = "http://45.71.160.173/monitoramento/atualiza_status.php"

    # Campos de entrada para as URLs
    url_monitoramento = st.text_input(
        "URL da página de monitoramento:",
        url_monitoramento_padrao
    )

    url_atualiza_status = st.text_input(
        "URL de atualização de status:",
        url_atualiza_status_padrao
    )

    # Inicialização de sessão
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
        st.subheader("Processando atualização...")
        
        # 1) Atualização do status no servidor
        with st.spinner("Etapa 1/2: Atualizando status no servidor..."):
            ok, msg = chamar_atualiza_status(url_atualiza_status)
            st.session_state["ultima_msg_atualiza"] = msg

        if ok:
            st.success("Etapa 1/2 concluída: Status atualizado.")
        else:
            st.error("Falha na etapa 1/2: Não foi possível atualizar o status.")
            st.write(msg)

        st.info(f"Mensagem do servidor: {msg}")

        # 2) Carregar dados do monitoramento
        with st.spinner("Etapa 2/2: Carregando dados atualizados..."):
            try:
                df, resumo = carregar_dados(url_monitoramento)
                st.session_state["df"] = df
                st.session_state["resumo"] = resumo
                st.session_state["ultima_execucao"] = datetime.datetime.now()
                st.success("Etapa 2/2 concluída: Dados carregados.")
            except MonitoramentoError as exc:
                st.error(f"Erro ao carregar dados do monitoramento: {exc}")

    # Carregamento inicial automático
    if st.session_state["df"] is None:
        try:
            df, resumo = carregar_dados(url_monitoramento)
            st.session_state["df"] = df
            st.session_state["resumo"] = resumo
        except MonitoramentoError:
            st.warning("Clique em 'Atualizar dados agora' para iniciar.")

    df = st.session_state["df"]
    resumo = st.session_state["resumo"]

    if df is None or resumo is None:
        st.stop()

    # Mostrar última atualização
    if st.session_state["ultima_execucao"]:
        dt = st.session_state["ultima_execucao"].strftime("%d/%m/%Y %H:%M:%S")
        st.caption(f"Última atualização completa em: {dt}")

    # Métricas principais
    st.subheader("Resumo do Monitoramento")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de carros", resumo.get("total_carros", 0))
    col2.metric("Carros funcionando", resumo.get("total_funcionando", 0))
    col3.metric("Carros não funcionando", resumo.get("total_nao_funcionando", 0))

    st.markdown("---")

    # Mensagem retornada pelo servidor PHP
    if st.session_state["ultima_msg_atualiza"]:
        st.info(f"Mensagem da última atualização: {st.session_state['ultima_msg_atualiza']}")

    # Filtro de carro
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

    st.dataframe(
        df_exibicao,
        use_container_width=True,
        height=500,
    )


if __name__ == "__main__":
    main()
