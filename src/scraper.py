"""
Módulo de extração de dados do Monitoramento de Carros - Wi-Fi.

Responsabilidades principais:
- Baixar o HTML da página de monitoramento.
- Extrair os totais (total de carros, funcionando, não funcionando).
- Ler a tabela com carros, último acesso e status em um DataFrame do pandas.

O objetivo é manter este módulo independente de interface (CLI, Streamlit, etc.),
de modo que possa ser reutilizado em outros projetos com mínima alteração.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MonitoramentoError(Exception):
    """Erro genérico do módulo de monitoramento."""


def fetch_html(url: str, timeout: int = 10) -> str:
    """
    Faz o download do HTML da página de monitoramento.

    :param url: URL completa da página.
    :param timeout: Tempo limite em segundos para a requisição HTTP.
    :return: Conteúdo HTML como string.
    :raises MonitoramentoError: Se houver qualquer problema na requisição.
    """
    try:
        logger.info("Buscando página de monitoramento em %s", url)
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        # Garante que acentuação (UTF-8) seja tratada corretamente.
        response.encoding = response.apparent_encoding
        return response.text
    except requests.RequestException as exc:
        logger.exception("Falha ao acessar a URL de monitoramento.")
        raise MonitoramentoError(f"Erro ao acessar a URL {url}: {exc}") from exc


def parse_resumo(html: str) -> Dict[str, int]:
    """
    Lê os totais que aparecem acima da tabela.

    Exemplo esperado no texto da página:
        Total de Carros: 117
        Total de Carros Funcionando: 34
        Total de Carros Não Funcionando: 83

    Aqui usamos BeautifulSoup para extrair somente o texto visível
    e então aplicamos expressões regulares nesse texto limpo.
    """
    # Extrai somente o texto, ignorando tags HTML
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text(separator="\n")

    padrao_total = re.search(r"Total de Carros:\s*(\d+)", texto)
    padrao_funcionando = re.search(
        r"Total de Carros Funcionando:\s*(\d+)", texto
    )
    padrao_nao_funcionando = re.search(
        r"Total de Carros N[aã]o Funcionando:\s*(\d+)", texto
    )

    if not (padrao_total and padrao_funcionando and padrao_nao_funcionando):
        logger.warning(
            "Não foi possível encontrar todos os totais no texto da página. "
            "Verifique se o layout da página mudou."
        )

    def _to_int(match) -> int:
        return int(match.group(1)) if match else 0

    resumo = {
        "total_carros": _to_int(padrao_total),
        "total_funcionando": _to_int(padrao_funcionando),
        "total_nao_funcionando": _to_int(padrao_nao_funcionando),
    }

    logger.info("Resumo extraído: %s", resumo)
    return resumo


def parse_tabela(html: str) -> pd.DataFrame:
    """
    Lê a tabela principal de carros usando pandas.read_html.

    :param html: HTML da página.
    :return: DataFrame com colunas ['Carro', 'Último Acesso', 'Status'] (ou nomes equivalentes).
    :raises MonitoramentoError: Se a tabela não for encontrada.
    """
    try:
        # read_html devolve uma lista de DataFrames encontrados na página.
        tabelas = pd.read_html(html)
    except ValueError as exc:
        logger.exception("Nenhuma tabela encontrada no HTML.")
        raise MonitoramentoError("Nenhuma tabela HTML encontrada na página.") from exc

    if not tabelas:
        raise MonitoramentoError("Nenhuma tabela HTML encontrada na página.")

    # Assumimos que a primeira tabela é a de interesse.
    df = tabelas[0]

    # Normaliza o nome das colunas, se necessário.
    colunas_normalizadas = {}
    for col in df.columns:
        nome = str(col).strip().lower()
        if "carro" in nome:
            colunas_normalizadas[col] = "Carro"
        elif "último" in nome or "ultimo" in nome:
            colunas_normalizadas[col] = "Último Acesso"
        elif "status" in nome:
            colunas_normalizadas[col] = "Status"

    if colunas_normalizadas:
        df = df.rename(columns=colunas_normalizadas)

    # Garante que as colunas principais existam.
    colunas_esperadas = {"Carro", "Último Acesso", "Status"}
    if not colunas_esperadas.issubset(set(df.columns)):
        logger.warning(
            "As colunas esperadas %s não foram todas encontradas. "
            "Verifique o layout da tabela.",
            colunas_esperadas,
        )

    return df


def get_monitoramento(
    url: str = "http://45.71.160.173/monitoramento/",
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Função de alto nível que faz todo o processo:
    1) baixa o HTML;
    2) extrai os totais;
    3) extrai a tabela.

    :param url: URL da página de monitoramento.
    :return: Tupla (DataFrame, resumo_dict).
    """
    html = fetch_html(url)
    resumo = parse_resumo(html)
    df = parse_tabela(html)
    return df, resumo


if __name__ == "__main__":
    # Pequeno teste de linha de comando:
    logging.basicConfig(level=logging.INFO)
    df_monitor, resumo_monitor = get_monitoramento()
    print("Resumo:", resumo_monitor)
    print(df_monitor.head())
