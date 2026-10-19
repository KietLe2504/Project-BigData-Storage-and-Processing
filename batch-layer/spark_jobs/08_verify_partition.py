
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = (
    SparkSession.builder
    .appName("Verify_BTS_All_Months")
    .getOrCreate()
)

BASE_PATH = "hdfs://namenode:9000/aero/processed"
EXPECTED_MONTHS = [
    (year, month)
    for year in range(2022, 2027)
    for month in range(
        1,
        4 if year == 2026 else 13
    )
]

try:
    print("\n========== BTS BATCH VERIFICATION ==========")

    # Input: Xác định các partition dự kiến
    jvm = spark._jvm
    conf = spark._jsc.hadoopConfiguration()
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(
        jvm.java.net.URI(BASE_PATH),
        conf
    )

    existing_paths = []
    missing_months = []
    empty_months = []

    for year, month in EXPECTED_MONTHS:
        month_str = f"{month:02d}"
        path = (
            f"{BASE_PATH}/year={year}/month={month_str}"
        )
        hdfs_path = jvm.org.apache.hadoop.fs.Path(path)

        if not fs.exists(hdfs_path):
            missing_months.append(f"{year}-{month_str}")
            continue

        statuses = fs.listStatus(hdfs_path)
        has_parquet = any(
            status.isFile()
            and status.getPath().getName().endswith(".parquet")
            for status in statuses
        )

        if not has_parquet:
            empty_months.append(f"{year}-{month_str}")
            continue

        existing_paths.append(path)

    print("Expected months:", len(EXPECTED_MONTHS))
    print("Readable-path candidates:", len(existing_paths))
    print("Missing partitions:", missing_months)
    print("Empty/no-Parquet partitions:", empty_months)

    if not existing_paths:
        raise RuntimeError("No readable Parquet partitions found.")

    # Process: Đọc các partition và tổng hợp trong một lượt
    df = (
        spark.read
        .option("basePath", BASE_PATH)
        .parquet(*existing_paths)
    )

    print("Columns:", len(df.columns))
    print("Schema:")
    df.printSchema()

    required = {"FL_DATE", "year", "month"}
    missing_columns = required - set(df.columns)

    if missing_columns:
        raise RuntimeError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    parsed_date = F.to_date(F.col("FL_DATE"))

    summary = (
        df.groupBy("year", "month")
        .agg(
            F.count("*").alias("rows"),
            F.sum(
                F.when(parsed_date.isNull(), 1).otherwise(0)
            ).alias("invalid_dates"),
            F.sum(
                F.when(
                    (F.year(parsed_date) != F.col("year"))
                    | (F.month(parsed_date) != F.col("month")),
                    1
                ).otherwise(0)
            ).alias("date_partition_mismatch"),
            F.min(parsed_date).alias("min_date"),
            F.max(parsed_date).alias("max_date")
        )
        .orderBy("year", "month")
    )

    # Output: Một action để tính toàn bộ thống kê
    results = summary.collect()

    print("\n========== MONTHLY RESULTS ==========")
    print(
        f"{'MONTH':<10} {'ROWS':>12} "
        f"{'BAD_DATE':>10} {'MISMATCH':>10} "
        f"{'MIN_DATE':>12} {'MAX_DATE':>12}"
    )

    total_rows = 0
    bad_dates = 0
    mismatches = 0
    checked_months = set()

    for row in results:
        year = int(row["year"])
        month = int(row["month"])
        key = (year, month)

        checked_months.add(key)

        rows = row["rows"] or 0
        invalid = row["invalid_dates"] or 0
        mismatch = row["date_partition_mismatch"] or 0

        total_rows += rows
        bad_dates += invalid
        mismatches += mismatch

        print(
            f"{year}-{month:02d} "
            f"{rows:>12,} "
            f"{invalid:>10,} "
            f"{mismatch:>10,} "
            f"{str(row['min_date']):>12} "
            f"{str(row['max_date']):>12}"
        )

    missing_results = sorted(
        set(EXPECTED_MONTHS) - checked_months
    )

    # PASS chỉ khi đủ partition và các kiểm tra cơ bản đạt
    passed = (
        len(checked_months) == len(EXPECTED_MONTHS)
        and not missing_months
        and not empty_months
        and not missing_results
        and total_rows > 0
        and bad_dates == 0
        and mismatches == 0
    )

    print("\n========== FINAL SUMMARY ==========")
    print("Expected months:", len(EXPECTED_MONTHS))
    print("Months with rows:", len(checked_months))
    print("Total rows:", f"{total_rows:,}")
    print("Invalid/null dates:", f"{bad_dates:,}")
    print("Date/partition mismatches:", f"{mismatches:,}")
    print("Missing result months:", missing_results)
    print("RESULT:", "PASS" if passed else "FAIL")

    if not passed:
        raise RuntimeError(
            "Batch verification failed. Review the summary above."
        )

except Exception as e:
    print("\nRESULT: FAIL")
    print(str(e))
    raise

finally:
    spark.stop()
