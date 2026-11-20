"""Small DuckDB persistence helper for the Phase 2 app tables (schema `ops`) in the existing local database
(data/processed/atmosync.duckdb). Connections are short-lived so dbt / other tools can use the same file.
In full-integration mode the same tables could live in Snowflake; only the local equivalent is implemented here."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import duckdb
import pandas as pd
from common.config import load_settings, abs_path


def _sql_type(dtype) -> str:
    if pd.api.types.is_bool_dtype(dtype): return "BOOLEAN"
    if pd.api.types.is_integer_dtype(dtype): return "BIGINT"
    if pd.api.types.is_float_dtype(dtype): return "DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(dtype): return "TIMESTAMP"
    return "VARCHAR"


def _evolve(con, table: str, df: pd.DataFrame) -> None:
    """Add columns that exist in `df` but not yet in the table (lightweight schema evolution)."""
    have = {r[0] for r in con.execute("select column_name from information_schema.columns where table_schema='ops' and table_name=?", [table]).fetchall()}
    for c in df.columns:
        if c not in have:
            con.execute(f'alter table ops.{table} add column "{c}" {_sql_type(df[c].dtype)}')


class Store:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else abs_path(load_settings()["paths"]["duckdb_file"])

    @contextmanager
    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(self.db_path))
        try:
            con.execute("create schema if not exists ops")
            yield con
        finally:
            con.close()

    def table_exists(self, table: str) -> bool:
        with self.connect() as con:
            return con.execute("select count(*) from information_schema.tables where table_schema='ops' and table_name=?", [table]).fetchone()[0] > 0

    def upsert_df(self, table: str, df: pd.DataFrame, keys: list[str]) -> int:
        """Insert rows; rows whose key already exists are replaced. Creates the table on first use."""
        if df.empty:
            return 0
        with self.connect() as con:
            con.register("_incoming", df)
            exists = con.execute("select count(*) from information_schema.tables where table_schema='ops' and table_name=?", [table]).fetchone()[0]
            if not exists:
                con.execute(f"create table ops.{table} as select * from _incoming")
            else:
                _evolve(con, table, df)
                key_list = ", ".join(keys)
                con.execute(f"delete from ops.{table} where ({key_list}) in (select {key_list} from _incoming)")
                cols = ", ".join(f'"{c}"' for c in df.columns)
                con.execute(f"insert into ops.{table} ({cols}) select {cols} from _incoming")
        return len(df)

    def append_df(self, table: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        with self.connect() as con:
            con.register("_incoming", df)
            if not con.execute("select count(*) from information_schema.tables where table_schema='ops' and table_name=?", [table]).fetchone()[0]:
                con.execute(f"create table ops.{table} as select * from _incoming")
            else:
                _evolve(con, table, df)
                cols = ", ".join(f'"{c}"' for c in df.columns)
                con.execute(f"insert into ops.{table} ({cols}) select {cols} from _incoming")
        return len(df)

    def read(self, sql: str, params: list | None = None) -> pd.DataFrame:
        with self.connect() as con:
            return con.execute(sql, params or []).df()

    def read_table(self, table: str) -> pd.DataFrame:
        return self.read(f"select * from ops.{table}") if self.table_exists(table) else pd.DataFrame()

    def execute(self, sql: str, params: list | None = None) -> None:
        with self.connect() as con:
            con.execute(sql, params or [])
