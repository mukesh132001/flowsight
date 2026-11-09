"""Two interchangeable execution engines for the same SQL models.

* ``SQLiteEngine`` - zero-install, used for local runs, tests and CI.
* ``SparkEngine``  - PySpark (local[*] or Databricks). Bronze ingestion uses an explicit
  all-string schema, lineage columns and a quarantine for malformed rows; every model is
  executed with ``spark.sql`` and cached; gold tables are written as Parquet.

Both engines load raw files with every column as text, so the SQL models do all type
casting and parsing themselves - which is what keeps the two engines' results identical.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def snake(name: str) -> str:
    """'RowID' -> 'row_id', 'TradeDt' -> 'trade_dt', 'firm_name' -> 'firm_name'."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    return re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()


class SQLiteEngine:
    name = "sqlite"

    def __init__(self, db_path: str | Path, fresh: bool = False):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if fresh and self.db_path.exists():
            self.db_path.unlink()
        self.con = sqlite3.connect(self.db_path)
        self.con.execute("PRAGMA journal_mode = OFF")
        self.con.execute("PRAGMA synchronous = OFF")
        self.con.execute("PRAGMA temp_store = MEMORY")
        self.con.execute("PRAGMA cache_size = -400000")

    # ---- loading
    def load_csv(self, table: str, path: Path) -> int:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        df.columns = [snake(c) for c in df.columns]
        df = df.astype(object).where(df != "", None)       # empty string -> NULL (same as Spark)
        df["_source_file"] = path.name
        df["_ingested_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        df.to_sql(table, self.con, if_exists="replace", index=False, chunksize=50_000)
        return len(df)

    def load_df(self, table: str, df: pd.DataFrame) -> int:
        df.to_sql(table, self.con, if_exists="replace", index=False, chunksize=50_000)
        return len(df)

    # ---- models
    def materialize(self, table: str, sql: str, indexes: list[list[str]] | None = None) -> int:
        self.con.execute(f"DROP TABLE IF EXISTS {table}")
        self.con.execute(f"CREATE TABLE {table} AS {sql}")
        for cols in indexes or []:
            self.con.execute(f"CREATE INDEX ix_{table}_{'_'.join(cols)} ON {table} ({', '.join(cols)})")
        return self.row_count(table)

    def query(self, sql: str) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.con)

    def table(self, name: str) -> pd.DataFrame:
        return self.query(f"SELECT * FROM {name}")

    def row_count(self, table: str) -> int:
        return int(self.con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def tables(self) -> list[str]:
        return [r[0] for r in self.con.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    def write_outputs(self, tables: list[str], out_dir: Path) -> None:
        self.con.commit()               # the .db file itself is the warehouse

    def close(self) -> None:
        self.con.commit()
        self.con.close()


class SparkEngine:
    """PySpark engine. Needs `pip install pyspark` and Java 17+ (or a Databricks cluster)."""
    name = "spark"

    def __init__(self, warehouse_dir: str | Path, spark=None):
        from pyspark.sql import SparkSession

        self.warehouse_dir = Path(warehouse_dir)
        self.warehouse_dir.mkdir(parents=True, exist_ok=True)
        self.spark = spark or (
            SparkSession.builder.appName("flowsight")
            .master("local[*]")
            .config("spark.sql.ansi.enabled", "false")          # NULL on bad casts, like SQLite
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.execution.arrow.pyspark.enabled", "true")      # fast toPandas()
            .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
            .getOrCreate())
        self.spark.conf.set("spark.sql.ansi.enabled", "false")
        self._cached = {}

    # ---- loading (bronze)
    def load_csv(self, table: str, path: Path) -> int:
        from pyspark.sql import functions as F
        from pyspark.sql.types import StringType, StructField, StructType

        if path.name.startswith(("_", ".")):
            # Spark's file index skips these names ("All paths were ignored") and returns no rows
            raise ValueError(f"{path.name}: Spark ignores files starting with '_' or '.' - rename the feed")
        header = pd.read_csv(path, nrows=0).columns.tolist()
        schema = StructType([StructField(c, StringType(), True) for c in header]
                            + [StructField("_corrupt_record", StringType(), True)])
        df = (self.spark.read.option("header", True).option("mode", "PERMISSIVE")
              .option("columnNameOfCorruptRecord", "_corrupt_record")
              .schema(schema).csv(str(path)))
        df = df.cache()
        bad = df.filter(F.col("_corrupt_record").isNotNull())
        n_bad = bad.count()
        if n_bad:
            bad.write.mode("overwrite").json(str(self.warehouse_dir / "_quarantine" / table))
        df = (df.filter(F.col("_corrupt_record").isNull()).drop("_corrupt_record")
              .toDF(*[snake(c) for c in header])
              .withColumn("_source_file", F.lit(path.name))
              .withColumn("_ingested_at", F.date_format(F.current_timestamp(), "yyyy-MM-dd'T'HH:mm:ss'Z'")))
        return self._register(table, df)

    def load_df(self, table: str, df: pd.DataFrame) -> int:
        return self._register(table, self.spark.createDataFrame(df))

    def _register(self, table: str, sdf) -> int:
        if table in self._cached:
            self._cached[table].unpersist()
        sdf = sdf.cache()
        n = sdf.count()
        sdf.createOrReplaceTempView(table)
        self._cached[table] = sdf
        return n

    # ---- models
    def materialize(self, table: str, sql: str, indexes=None) -> int:
        return self._register(table, self.spark.sql(sql))

    def query(self, sql: str) -> pd.DataFrame:
        return self.spark.sql(sql).toPandas()

    def table(self, name: str) -> pd.DataFrame:
        return self.spark.table(name).toPandas()

    def row_count(self, table: str) -> int:
        return int(self.spark.table(table).count())

    def tables(self) -> list[str]:
        return [t.name for t in self.spark.catalog.listTables()]

    def write_outputs(self, tables: list[str], out_dir: Path) -> None:
        for t in tables:
            (self.spark.table(t).coalesce(1).write.mode("overwrite")
             .parquet(str(Path(out_dir) / "parquet" / t)))

    def close(self) -> None:
        for df in self._cached.values():
            df.unpersist()


def make_engine(kind: str, warehouse_dir: Path, fresh: bool = False):
    if kind == "sqlite":
        return SQLiteEngine(Path(warehouse_dir) / "flowsight.db", fresh=fresh)
    if kind == "spark":
        return SparkEngine(warehouse_dir)
    raise ValueError(f"unknown engine {kind!r} (use sqlite or spark)")
