# Databricks notebook source
# MAGIC %md
# MAGIC # FlowSight on Databricks
# MAGIC Runs the same bronze -> silver -> gold -> feature models on a Databricks cluster with the
# MAGIC `SparkEngine`, then writes every table to Delta in Unity Catalog.
# MAGIC
# MAGIC 1. Repos -> Add repo -> your `flowsight` GitHub URL (or upload the folder to Workspace files).
# MAGIC 2. Create a Unity Catalog volume for the raw files, e.g. `/Volumes/main/flowsight/raw`.
# MAGIC 3. Attach to a cluster (DBR 14+ or serverless) and run all.

# COMMAND ----------

# MAGIC %pip install pyyaml xlsxwriter python-pptx
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import os
import sys

dbutils.widgets.text("repo_path", os.getcwd().rsplit("/databricks", 1)[0])  # noqa: F821
dbutils.widgets.text("raw_volume", "/Volumes/main/flowsight/raw")              # noqa: F821
dbutils.widgets.text("schema", "main.flowsight")                              # noqa: F821
repo = dbutils.widgets.get("repo_path")                                        # noqa: F821
raw_dir = dbutils.widgets.get("raw_volume")                                    # noqa: F821
schema = dbutils.widgets.get("schema")                                         # noqa: F821
sys.path.insert(0, f"{repo}/src")

# COMMAND ----------

# MAGIC %md ## 1. Generate the synthetic raw feeds into the volume (skip if real feeds land there)

# COMMAND ----------

from flowsight.simulate import generate

counts = generate(raw_dir, f"{raw_dir}/../ground_truth", scale="full", seed=42)
display(spark.createDataFrame(list(counts.items()), ["file", "rows"]))  # noqa: F821

# COMMAND ----------

# MAGIC %md ## 2. Build every model with Spark SQL (identical SQL to the SQLite CI build)

# COMMAND ----------

from pathlib import Path

from flowsight.config import load_settings
from flowsight.pipeline.engines import SparkEngine
from flowsight.pipeline.runner import run_pipeline

settings = load_settings()
engine = SparkEngine("/tmp/flowsight_warehouse", spark=spark)  # noqa: F821  (reuse the cluster session)
result = run_pipeline(engine, Path(raw_dir), settings.months)
display(spark.createDataFrame(result.dq_results))  # noqa: F821
assert result.passed, "Data-quality gate failed - not publishing tables"

# COMMAND ----------

# MAGIC %md ## 3. Publish gold + feature tables to Delta

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")  # noqa: F821
for model in result.model_runs.model:
    if model.startswith(("mart_", "feat_", "fct_", "int_")):
        spark.table(model).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{schema}.{model}")  # noqa: F821
print("published", len(result.model_runs), "models to", schema)

# COMMAND ----------

# MAGIC %md ## 4. KPIs, models and reports run on the driver (pandas / scikit-learn)

# COMMAND ----------

from flowsight.config import month_key
from flowsight.kpi import run_kpis
from flowsight.ml import run_ml

out = Path("/tmp/flowsight_outputs")
run_kpis(engine, month_key(settings.months[-1]), out)
metrics = run_ml(engine, settings, out)
display(spark.createDataFrame(engine.table("kpi_scorecard")))  # noqa: F821
