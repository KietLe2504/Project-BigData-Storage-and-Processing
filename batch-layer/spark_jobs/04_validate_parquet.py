from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("AERO-Validate-Parquet")
    .getOrCreate()
)

path = "hdfs://namenode:9000/aero/processed/year=2023/month=01"

df = spark.read.parquet(path)

print("=== PARQUET SCHEMA ===")
df.printSchema()

print("=== ROW COUNT ===")
print("Output rows:", df.count())

print("=== SAMPLE DATA ===")
df.select(
    "FL_DATE",
    "OP_CARRIER",
    "ORIGIN",
    "DEST",
    "DEP_DELAY",
    "ARR_DELAY"
).show(10, truncate=False)

print("=== VALIDATION ===")
print("Has FL_DATE:", "FL_DATE" in df.columns)
print("Has ORIGIN:", "ORIGIN" in df.columns)
print("Has DEST:", "DEST" in df.columns)

spark.stop()
