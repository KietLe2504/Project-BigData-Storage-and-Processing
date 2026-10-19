from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim
from datetime import datetime

# =========================
# 1. CONFIGURATION
# =========================
HDFS_RAW = "hdfs://namenode:9000/aero/raw/bts"
HDFS_PROCESSED = "hdfs://namenode:9000/aero/processed"

START_YEAR = 2022
START_MONTH = 1
END_YEAR = 2026
END_MONTH = 3

# =========================
# 2. CREATE SPARK SESSION
# =========================
spark = (
    SparkSession.builder
    .appName("AERO-BTS-Batch-All-Months")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

success_months = []
failed_months = []

# =========================
# 3. GENERATE MONTH LIST
# =========================
months = []

for year in range(START_YEAR, END_YEAR + 1):
    first_month = START_MONTH if year == START_YEAR else 1
    last_month = END_MONTH if year == END_YEAR else 12

    for month in range(first_month, last_month + 1):
        months.append((year, month))

print("=" * 70)
print("AERO BATCH ETL STARTED")
print("Start time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("Total months:", len(months))
print("=" * 70)

# =========================
# 4. PROCESS EACH MONTH
# =========================
for index, (year, month) in enumerate(months, start=1):

    filename = f"On_Time_Reporting_{year}_{month}.csv"

    input_path = f"{HDFS_RAW}/{filename}"
    output_path = (
        f"{HDFS_PROCESSED}/year={year}/month={month:02d}"
    )

    print("\n" + "=" * 70)
    print(f"[{index}/{len(months)}] Processing {year}-{month:02d}")
    print("Input :", input_path)
    print("Output:", output_path)

    df = None
    clean_df = None

    try:
        # Read monthly CSV from HDFS
        df = (
            spark.read
            .option("header", True)
            .option("inferSchema", True)
            .csv(input_path)
        )

        columns = df.columns

        # Check required columns
        required_columns = ["FL_DATE", "ORIGIN", "DEST"]
        missing_columns = [
            name for name in required_columns
            if name not in columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        # Select available columns for the deduplication key
        carrier_col = next(
            (
                name for name in
                ["OP_UNIQUE_CARRIER", "OP_CARRIER", "UNIQUE_CARRIER"]
                if name in columns
            ),
            None
        )

        flight_num_col = next(
            (
                name for name in
                ["OP_CARRIER_FL_NUM", "OP_FL_NUM", "FL_NUM"]
                if name in columns
            ),
            None
        )

        dedup_keys = ["FL_DATE"]

        if carrier_col:
            dedup_keys.append(carrier_col)

        if flight_num_col:
            dedup_keys.append(flight_num_col)

        dedup_keys.extend(["ORIGIN", "DEST"])

        # Clean required fields and remove duplicate flight keys
        clean_df = (
            df
            .filter(col("FL_DATE").isNotNull())
            .filter(
                col("ORIGIN").isNotNull()
                & col("DEST").isNotNull()
            )
            .withColumn("ORIGIN", trim(col("ORIGIN")))
            .withColumn("DEST", trim(col("DEST")))
            .filter(
                (col("ORIGIN") != "")
                & (col("DEST") != "")
            )
            .dropDuplicates(dedup_keys)
            .cache()
        )

        input_count = df.count()
        output_count = clean_df.count()

        # Overwrite only this month's processed output
        clean_df.write.mode("overwrite").parquet(output_path)

        print("Input rows :", f"{input_count:,}")
        print("Output rows:", f"{output_count:,}")
        print("Removed rows:", f"{input_count - output_count:,}")
        print("Dedup keys :", dedup_keys)
        print("Status     : SUCCESS")

        success_months.append(f"{year}-{month:02d}")

    except Exception as e:
        print("Status : FAILED")
        print("Error  :", str(e)[:1500])

        failed_months.append({
            "month": f"{year}-{month:02d}",
            "error": str(e)[:1500]
        })

    finally:
        if clean_df is not None:
            clean_df.unpersist()

# =========================
# 5. FINAL SUMMARY
# =========================
print("\n" + "=" * 70)
print("AERO BATCH ETL SUMMARY")
print("Successful:", len(success_months), "/", len(months))
print("Failed    :", len(failed_months), "/", len(months))

print("\nSuccessful months:")
for item in success_months:
    print("  ", item)

if failed_months:
    print("\nFailed months:")
    for item in failed_months:
        print(f"  {item['month']}: {item['error']}")

print("End time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 70)

spark.stop()

if failed_months:
    raise RuntimeError(
        f"Batch ETL finished with {len(failed_months)} failed month(s). "
        "Review the logs before proceeding."
    )
