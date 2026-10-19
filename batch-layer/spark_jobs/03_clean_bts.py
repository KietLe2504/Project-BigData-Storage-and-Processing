from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim

spark = (
    SparkSession.builder
    .appName("AERO-BTS-Clean")
    .getOrCreate()
)

input_path = "file:///data/input/On_Time_Reporting_2023_1.csv"
output_path = "hdfs://namenode:9000/aero/processed/year=2023/month=01"

df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(input_path)
)

# Loại bỏ dòng thiếu ngày hoặc mã sân bay
clean_df = (
    df
    .filter(col("FL_DATE").isNotNull())
    .filter(col("ORIGIN").isNotNull() & col("DEST").isNotNull())
    .withColumn("ORIGIN", trim(col("ORIGIN")))
    .withColumn("DEST", trim(col("DEST")))
    .dropDuplicates(["FL_DATE", "OP_CARRIER", "OP_CARRIER_FL_NUM", "ORIGIN", "DEST"])
)

# Ghi Parquet lên HDFS
clean_df.write.mode("overwrite").parquet(output_path)

print("Input rows:", df.count())
print("Output rows:", clean_df.count())
print("Parquet saved to:", output_path)

spark.stop()
