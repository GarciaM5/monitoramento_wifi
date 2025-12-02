"""
Aplicação Streamlit para monitorar o status dos carros (Wi-Fi).

Para executar localmente:
    streamlit run src/app.py
"""

from __future__ import annotations

import logging

import pandas as pd
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

    url_padrao = "http://45.71.160.173/monitoramento/"
    url = st.text_input("URL da página de monitoramento:", url_padrao)

    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "resumo" not in st.session_state:
        st.session_state["resumo"] = None

    if st.button("Atualizar dados agora"):
        with st.spinner("Buscando dados no servidor..."):
            try:
                df, resumo = carregar_dados(url)
                st.session_state["df"] = df
                st.session_state["resumo"] = resumo
                st.success("Dados atualizados com sucesso.")
            except MonitoramentoError as exc:
                st.error(f"Não foi possível atualizar os dados: {exc}")

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

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de carros", resumo.get("total_carros", 0))
    col2.metric("Carros funcionando", resumo.get("total_funcionando", 0))
    col3.metric("Carros não funcionando", resumo.get("total_nao_funcionando", 0))

    st.markdown("---")

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
