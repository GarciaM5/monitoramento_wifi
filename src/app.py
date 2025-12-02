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

import pandas as pd
import requests
import streamlit as st

from scraper import get_monitoramento, MonitoramentoError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def carregar_dados(url: str) -> tuple[pd.DataFrame, dict]:
    """Wrapper simples para chamar o scraper e tratar erros."""
    return get_monitoramento(url)


def chamar_atualiza_status(url_monitoramento: str) -> tuple[bool, str]:
    """
    Chama o endpoint que atualiza a tabela de status no servidor.

    :param url_monitoramento: URL base de monitoramento, ex:
        http://45.71.160.173/monitoramento/
    :return: (sucesso: bool, mensagem: str)
    """
    # Garante que não tenha barra duplicada
    base = url_monitoramento.rstrip("/")
    url_atualiza = f"{base}/atualiza_status.php"

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


def main() -> None:
    st.set_page_config(
        page_title="Monitoramento de Carros - Wi-Fi",
        layout="wide",
    )

    st.title("Monitoramento de Carros - Wi-Fi")

    st.write(
        "Aplicação para consulta rápida do monitoramento de carros Wi-Fi, "
        "extraindo os dados diretamente do sistema interno."
    )

    # URL base do monitoramento
    url_padrao = "http://45.71.160.173/monitoramento/"
    url = st.text_input("URL da página de monitoramento:", url_padrao)

    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "resumo" not in st.session_state:
        st.session_state["resumo"] = None
    if "ultima_msg_atualiza" not in st.session_state:
        st.session_state["ultima_msg_atualiza"] = ""

    # Botão principal
    if st.button("Atualizar dados agora"):
        # 1) Atualiza status no servidor
        with st.spinner("Atualizando status no servidor..."):
            ok, msg = chamar_atualiza_status(url)
            st.session_state["ultima_msg_atualiza"] = msg

        if ok:
            st.success("Etapa 1/2 concluída: status atualizado no servidor.")
        else:
            st.error("Falha na etapa 1/2: não foi possível atualizar o status.")
            st.write(msg)
            # Mesmo com erro, ainda podemos tentar ler a página atual.
            # Se quiser abortar totalmente, basta fazer: st.stop()

        # Mostra mensagem retornada pelo PHP (ex.: "Tabela de status atualizada com sucesso")
        st.info(f"Mensagem do servidor: {msg}")

        # 2) Carrega os dados atualizados
        with st.spinner("Carregando dados atualizados do monitoramento..."):
            try:
                df, resumo = carregar_dados(url)
                st.session_state["df"] = df
                st.session_state["resumo"] = resumo
                st.success("Etapa 2/2 concluída: dados de monitoramento carregados.")
            except MonitoramentoError as exc:
                st.error(f"Não foi possível carregar os dados de monitoramento: {exc}")

    # Carga inicial (caso ainda não tenha nada na sessão)
    if st.session_state["df"] is None:
        try:
            df, resumo = carregar_dados(url)
            st.session_state["df"] = df
            st.session_state["resumo"] = resumo
        except MonitoramentoError as exc:
            st.warning(
                "Falha ao carregar dados automaticamente. "
                f"Clique em 'Atualizar dados agora'. Detalhes: {exc}"
            )

    df = st.session_state["df"]
    resumo = st.session_state["resumo"]

    if df is None or resumo is None:
        st.stop()

    # Métricas principais
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de carros", resumo.get("total_carros", 0))
    col2.metric("Carros funcionando", resumo.get("total_funcionando", 0))
    col3.metric("Carros não funcionando", resumo.get("total_nao_funcionando", 0))

    st.markdown("---")

    # Última mensagem do endpoint de atualização (opcional)
    if st.session_state.get("ultima_msg_atualiza"):
        st.caption(f"Última atualização de status: {st.session_state['ultima_msg_atualiza']}")

    # Filtro de carro
    filtro_carro = st.text_input("Filtrar por carro (contém):", "")

    df_exibicao = df.copy()

    if filtro_carro.strip():
        mask = df_exibicao["Carro"].astype(str).str.contains(
            filtro_carro, case=False, na=False
        )
        df_exibicao = df_exibicao[mask]

    if "Último Acesso" in df_exibicao.columns:
        df_exibicao = df_exibicao.sort_values(by="Último Acesso", ascending=False)

    st.subheader("Tabela de carros")
    st.dataframe(
        df_exibicao,
        use_container_width=True,
        height=500,
    )


if __name__ == "__main__":
    main()
