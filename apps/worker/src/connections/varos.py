"""
Varos API client.

Wraps endpoints from base-de-dados-api.varos.com.br. Returns raw
DataFrames (column names from the API). Persistence and column
normalization are handled elsewhere.
"""
import io
import urllib.request

import pandas as pd
import requests

from src.config import settings
from src.logger import get_logger


_logger = get_logger("worker.varos")


class VarosClient:
    """Client for the Varos data API."""

    BASE_URL = "https://base-de-dados-api.varos.com.br"

    def __init__(self) -> None:
        self.headers = {
            "accept": "application/json",
            "x-api-key": settings.varos_api_key,
        }

    def _get(self, path: str, params: dict) -> dict:
        """Send a GET request and return the parsed JSON body."""
        url = f"{self.BASE_URL}{path}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _download_parquet(link: str) -> pd.DataFrame:
        """Download a parquet file from a temporary link and load into memory."""
        with urllib.request.urlopen(link) as response:
            data = response.read()
        return pd.read_parquet(io.BytesIO(data))

    # ---------- Quotes ----------

    def fetch_quotes(self) -> pd.DataFrame:
        """
        Fetch full historical B3 stock quotes.

        Uses the bulk download endpoint that returns a temporary link
        to a parquet file.
        """
        _logger.info("Fetching B3 quotes from Varos...")
        payload = self._get(
            "/bolsa/b3/avista/cotacoes/historico/arquivos",
            params={"preencher": "true"},
        )
        link = payload.get("link")
        if not link:
            raise ValueError("Varos response did not include a download link for quotes.")
        df = self._download_parquet(link)
        _logger.info(f"Quotes fetched: {len(df)} rows.")
        return df

    # ---------- Accounting files / indicators ----------

    def fetch_accounting_file(
        self,
        name: str,
        data_type: str = "indicator",
    ) -> pd.DataFrame:
        """
        Fetch a single accounting item or fundamental indicator.

        Parameters
        ----------
        name : str
            Item name in the Varos catalog. For accounting items use the
            Portuguese names (e.g. 'ReceitaLiquida', 'LucroLiquido').
            For indicators use the Varos codes (e.g. 'ROIC', 'EBIT_EV',
            'ValorDeMercado').
        data_type : str
            One of: 'financial_statement', 'balance_sheet', 'indicator'.
        """
        if data_type == "financial_statement":
            path = "/bolsa/b3/avista/point-in-time/itens-contabeis/arquivo"
            params = {"item": name, "tipoPeriodo": "12M"}
        elif data_type == "balance_sheet":
            path = "/bolsa/b3/avista/point-in-time/itens-contabeis/arquivo"
            params = {"item": name, "tipoPeriodo": "TRIMESTRAL"}
        elif data_type == "indicator":
            path = "/bolsa/b3/avista/point-in-time/indicadores/arquivo"
            params = {"indicador": name}
        else:
            raise ValueError(
                f"Unknown data_type '{data_type}'. "
                f"Use 'financial_statement', 'balance_sheet' or 'indicator'."
            )

        _logger.info(f"Fetching {data_type} '{name}' from Varos...")
        payload = self._get(path, params=params)
        link = payload.get("link")
        if not link:
            raise ValueError(f"Varos response did not include a download link for '{name}'.")
        df = self._download_parquet(link)
        _logger.info(f"{data_type.capitalize()} '{name}' fetched: {len(df)} rows.")
        return df

    # ---------- Macro / market references ----------

    def fetch_cdi(self) -> pd.DataFrame:
        """Fetch the historical CDI rate."""
        _logger.info("Fetching CDI from Varos...")
        data = self._get(
            "/taxas/historico",
            params={"codigo_bc": "12", "dataInicio": "1994-06-30", "ordem": "ASC"},
        )
        df = pd.DataFrame(data)
        _logger.info(f"CDI fetched: {len(df)} rows.")
        return df

    def fetch_ibov(self) -> pd.DataFrame:
        """Fetch the historical IBOV index."""
        _logger.info("Fetching IBOV from Varos...")
        data = self._get(
            "/indices/historico",
            params={"indice": "IBOV", "dataInicio": "1994-06-30"},
        )
        df = pd.DataFrame(data)
        _logger.info(f"IBOV fetched: {len(df)} rows.")
        return df

    def fetch_bova(self) -> pd.DataFrame:
        """Fetch the historical BOVA11 ETF series."""
        _logger.info("Fetching BOVA11 from Varos...")
        data = self._get(
            "/bolsa/b3/avista/cotacoes/historico",
            params={"ticker": "BOVA11", "dataInicio": "2010-01-01"},
        )
        df = pd.DataFrame(data)
        _logger.info(f"BOVA11 fetched: {len(df)} rows.")
        return df


if __name__ == "__main__":
    client = VarosClient()

    print("Testing Varos client (will hit the live API)...\n")

    df_cdi = client.fetch_cdi()
    print(f"CDI tail:\n{df_cdi.tail(2)}\n")

    df_ibov = client.fetch_ibov()
    print(f"IBOV tail:\n{df_ibov.tail(2)}\n")

    df_roic = client.fetch_accounting_file("ROIC", data_type="indicator")
    print(f"ROIC tail:\n{df_roic.tail(2)}\n")