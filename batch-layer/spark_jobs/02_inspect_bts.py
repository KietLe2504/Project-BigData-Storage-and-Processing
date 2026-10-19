from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("AERO-BTS-Inspect")
    .getOrCreate()
)

path = "file:///data/input/On_Time_Reporting_2023_1.csv"

df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(path)
)

print("=== COLUMNS ===")
print(df.columns)

print("=== SCHEMA ===")
df.printSchema()

print("=== SAMPLE ===")
df.show(5, truncate=False)

print("=== TOTAL ROWS ===")
print(df.count())

spark.stop()
