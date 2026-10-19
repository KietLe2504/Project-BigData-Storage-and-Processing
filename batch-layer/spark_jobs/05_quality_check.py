from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum as spark_sum, when, min as spark_min, max as spark_max

spark = (
    SparkSession.builder
    .appName("AERO-Quality-Check")
    .getOrCreate()
)

path = "hdfs://namenode:9000/aero/processed/year=2023/month=01"
df = spark.read.parquet(path)

print("\n=== 1. BASIC STATISTICS ===")
print("Total rows:", df.count())
print("Total columns:", len(df.columns))
df.select(
    spark_min("FL_DATE").alias("min_date"),
    spark_max("FL_DATE").alias("max_date")
).show()

print("=== 2. MISSING VALUES ===")
df.select([
    spark_sum(when(col(c).isNull(), 1).otherwise(0)).alias(c)
    for c in ["FL_DATE", "ORIGIN", "DEST"]
]).show()

print("=== 3. DATE RANGE CHECK ===")
outside_month = df.filter(
    (col("FL_DATE") < "2023-01-01") |
    (col("FL_DATE") >= "2023-02-01")
).count()
print("Rows outside January 2023:", outside_month)

print("=== 4. DUPLICATE FLIGHT KEYS ===")
duplicate_groups = (
    df.groupBy(
        "FL_DATE",
        "OP_CARRIER",
        "OP_CARRIER_FL_NUM",
        "ORIGIN",
        "DEST"
    )
    .count()
    .filter(col("count") > 1)
    .count()
)
print("Duplicate key groups:", duplicate_groups)

print("=== 5. DELAY STATISTICS ===")
df.select(
    spark_min("DEP_DELAY").alias("min_dep_delay"),
    spark_max("DEP_DELAY").alias("max_dep_delay"),
    spark_min("ARR_DELAY").alias("min_arr_delay"),
    spark_max("ARR_DELAY").alias("max_arr_delay")
).show()

print("=== QUALITY CHECK COMPLETED ===")
spark.stop()
