# US Air Traffic Big Data Pipeline 

Air Traffic Exploration & Real-time Orchestration is a Big Data project for processing historical US flight data and near-real-time flight events. It combines batch and streaming pipelines following the **Lambda Architecture**.

## 1. Project Objectives

Link Dataset : https://www.kaggle.com/datasets/anhdnghng/us-bts-2026

- Build an end-to-end data pipeline covering ingestion, processing, storage, and visualization.
- Process historical flight data using Apache Spark and HDFS.
- Explore near-real-time flight event processing using Apache Kafka and Spark Structured Streaming.
- Apply data cleaning, transformations, aggregations, joins, and performance optimization.
- Demonstrate event-time processing, windowed aggregations, watermarking, checkpointing, and recovery.
- Store query-ready analytical results in MongoDB and present key metrics through a dashboard.
- Evaluate Kubernetes or cloud deployment according to the final course requirements.

## 2. Architecture

### Batch Layer

**BTS Historical Data → HDFS → Apache Spark → Parquet**

The Batch Layer processes historical flight records from the US Bureau of Transportation Statistics (BTS). Raw CSV files are stored separately from processed data. Spark performs data cleaning, type conversion, validation, and analytical transformations before writing the results in Parquet format to HDFS.

The pipeline is developed incrementally, starting with a small dataset and expanding to a larger historical time range.

### Speed Layer

**AviationStack API or Simulated Events → Apache Kafka → Spark Structured Streaming → HDFS**

The Speed Layer is designed to ingest flight events through Kafka and process them with Spark Structured Streaming. It will support event-time windows, watermarking, checkpointing, and recovery.

AviationStack integration depends on API access, subscription limits, and available fields. Simulated events may be used during development and testing, and must be explicitly identified as simulated rather than live API data.

### Serving Layer

**Processed Batch and Streaming Results → MongoDB → Dashboard**

The Serving Layer will store query-ready results in MongoDB and expose key metrics for dashboard visualization. Integration and end-to-end validation remain part of the upcoming development work.

## 3. Technologies

| Component | Technology |
|---|---|
| Historical data source | US Bureau of Transportation Statistics (BTS) |
| Flight event source | AviationStack API or simulated events |
| Distributed storage | HDFS |
| Batch processing | Apache Spark / PySpark |
| Event streaming | Apache Kafka |
| Stream processing | Spark Structured Streaming |
| Serving database | MongoDB |
| Local development | Docker Compose |
| Visualization | Dashboard technology to be finalized |
| Final deployment | Kubernetes or cloud, subject to course requirements |

## 4. Data Sources and Data Quality

### Historical Data

The project uses BTS On-Time Performance data for US domestic flights.

The current local dataset covers **January 2022 through March 2026**, comprising 51 monthly CSV files. Processing and validation are performed incrementally.

### Streaming Data

Flight events may be obtained from AviationStack, subject to API access and usage limits, or generated through a clearly labeled simulator.

### Data Quality Principles

- Keep raw source files separate from processed outputs.
- Preserve source information and record collection or processing timestamps where available.
- Validate schemas, data types, record counts, and required fields.
- Check for missing values, duplicate records, and invalid values.
- Verify Parquet output readability and expected HDFS partition paths.
- Record processing errors and distinguish failed runs from successful runs.
- Make batch reruns safe and avoid unintentionally duplicating output data.

## 5. Repository Structure

```text
.
├── BTS_ZIP\                     # Các file CSV nguồn theo tháng đã giải nén
├── spark_jobs\
│   ├── 02_inspect_bts.py        # Tiện ích kiểm tra một file ban đầu
│   ├── 03_clean_bts.py          # Bản mẫu làm sạch một tháng ở giai đoạn đầu
│   ├── 04_validate_parquet.py   # Kiểm tra một phân vùng ở giai đoạn đầu
│   ├── 05_quality_check.py      # Các kiểm tra tùy chọn cho một phân vùng
│   ├── 06_batch_process_all.py  # ETL Spark chính cho 51 tháng
│   ├── 07_retry_2022_01.py      # Script khôi phục cho tháng 1/2022
│   └── 08_verify_partition.py   # Xác minh toàn bộ khoảng thời gian
├── check_partitions.ps1         # Script PowerShell kiểm tra phân vùng (tùy chọn)
├── docker-compose.yml
└── docs\
    ├── data_inventory.md
    ├── AERO_Member1_End_to_End_Guide_vi.md
    └── data_dictionary.md
```

The structure above illustrates the main project components. Refer to the actual repository tree for the current locations of scripts, configurations, and data.

## 6. Current Development Status

### Completed and Verified

- HDFS NameNode and DataNode run locally using Docker Compose.
- The BTS historical dataset has been downloaded and extracted locally.
- Spark batch processing has successfully written Parquet output for the January 2022 partition to HDFS.
- The January 2022 output has been checked for Parquet readability and schema information.
- Kafka Producer/Consumer messaging has been tested successfully.

### In Progress

- Scaling and validating Spark batch processing across the full 51-month dataset.
- Checking output partitions, record counts, data quality, and rerun behavior.
- Finalizing the batch processing workflow and documenting its execution procedure.

### Planned

- Integrate the flight event source with Kafka.
- Implement Spark Structured Streaming.
- Configure event-time windows, watermarking, checkpointing, and recovery.
- Persist processed batch and streaming results in MongoDB.
- Build a dashboard for key flight metrics.
- Test the end-to-end pipeline and evaluate final deployment options.

> **Status note:** Successful processing of one monthly partition does not imply that all 51 months have been processed and validated. Completion should be reported only after the relevant partitions and data-quality checks pass.

## 7. Local Development

Docker Compose is currently used to run the local development environment.

Typical commands:

```bash
# Start the configured services
docker compose up -d

# Check service status
docker compose ps

# View service logs
docker compose logs --tail=100

# Stop the services
docker compose down
```

Run Spark jobs using the configured Spark environment and the job-specific commands documented in the repository.

Raw data and processed outputs should remain separate. Persistent Docker volumes and HDFS paths should be checked before resetting or removing containers.

## 8. Development Roadmap

1. Complete and validate the Batch Layer across the selected historical period.
2. Finalize data-quality checks and document the batch execution workflow.
3. Complete Kafka event ingestion and Spark Structured Streaming.
4. Implement MongoDB integration for query-ready results.
5. Build and validate the dashboard.
6. Test batch and streaming integration under the Lambda Architecture.
7. Evaluate Kubernetes or cloud deployment against the final course milestones.

## 9. Project Principles

- Develop and test incrementally.
- Keep implementation status and test results transparent.
- Separate raw data, intermediate data, and processed outputs.
- Do not represent simulated events as live API data.
- Document configuration, dependencies, data schemas, and execution commands.
- Validate each pipeline stage before scaling or integrating it with downstream components.
