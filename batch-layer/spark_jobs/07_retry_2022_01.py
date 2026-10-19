
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim
from datetime import datetime

# 1. Configuration
input_path = (
    "hdfs://namenode:9000/aero/raw/bts/"
    "On_Time_Reporting_2022_1.csv"
)

output_path = (
    "hdfs://namenode:9000/aero/processed/"
    "year=2022/month=01"
)

# 2. Create Spark session
spark = (
    SparkSession.builder
    .appName("AERO-Retry-2022-01")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

print("=" * 60)
print("RETRY BTS ETL: 2022-01")
print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("Input :", input_path)
print("Output:", output_path)
print("=" * 60)

df = None
clean_df = None

try:
    # 3. Read CSV from HDFS
    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(input_path)
    )

    print("Columns:", len(df.columns))

    # 4. Check required columns
    required = ["FL_DATE", "ORIGIN", "DEST"]
    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # 5. Build deduplication key based on available columns
    carrier_col = next(
        (
            c for c in
            ["OP_UNIQUE_CARRIER", "OP_CARRIER", "UNIQUE_CARRIER"]
            if c in df.columns
        ),
        None
    )

    flight_num_col = next(
        (
            c for c in
            ["OP_CARRIER_FL_NUM", "OP_FL_NUM", "FL_NUM"]
            if c in df.columns
        ),
        None
    )

    dedup_keys = ["FL_DATE"]

    if carrier_col:
        dedup_keys.append(carrier_col)

    if flight_num_col:
        dedup_keys.append(flight_num_col)

    dedup_keys.extend(["ORIGIN", "DEST"])

    # 6. Clean records
    clean_df = (
        df
        .filter(col("FL_DATE").isNotNull())
        .filter(col("ORIGIN").isNotNull() & col("DEST").isNotNull())
        .withColumn("ORIGIN", trim(col("ORIGIN")))
        .withColumn("DEST", trim(col("DEST")))
        .filter((col("ORIGIN") != "") & (col("DEST") != ""))
        .dropDuplicates(dedup_keys)
        .cache()
    )

    input_count = df.count()
    output_count = clean_df.count()

    print("Input rows :", f"{input_count:,}")
    print("Output rows:", f"{output_count:,}")
    print("Removed    :", f"{input_count - output_count:,}")
    print("Dedup keys :", dedup_keys)

    # 7. Write only January 2022
    print("Writing Parquet to HDFS...")

    clean_df.write.mode("overwrite").parquet(output_path)

    print("WRITE STATUS: SUCCESS")

    # 8. Verify output by reading it back
    result_df = spark.read.parquet(output_path)
    result_count = result_df.count()

    print("Verified output rows:", f"{result_count:,}")

    if result_count != output_count:
        raise RuntimeError(
            f"Row count mismatch: expected {output_count}, "
            f"read back {result_count}"
        )

    print("VERIFICATION: PASSED")

except Exception as e:
    print("RETRY STATUS: FAILED")
    print("Error:", repr(e))
    raise

finally:
    if clean_df is not None:
        clean_df.unpersist()

    spark.stop()

print("End time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("JANUARY 2022 ETL COMPLETED")
