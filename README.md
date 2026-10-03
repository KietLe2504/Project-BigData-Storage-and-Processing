# Live Weather Data Aggregation & Prediction System

## 1. Project Overview

**Live Weather Data Aggregation & Prediction System** is a proposed end-to-end Big Data system for collecting, processing, storing, and analyzing real-time weather data from multiple sources.

The project is developed for the **Big Data Storage and Processing** course, with the initial focus on building a scalable data pipeline for weather data aggregation. The system is also intended to be extended with a **weather prediction component**, using historical and continuously collected weather data to support short-term forecasting.

The main objectives are:

- Continuously ingest weather data from multiple sources, such as APIs and sensors.
- Process and aggregate incoming data using distributed and streaming technologies.
- Store both raw and processed weather data for further analysis.
- Provide SQL-based access to weather data for analytical queries.
- Explore the use of historical and real-time weather data for **short-term weather prediction**.
- Visualize weather observations, trends, and potentially prediction results.

The prediction component is considered an **extension of the core data aggregation pipeline**. Depending on the available data and project progress, the system may be used to predict variables such as temperature, humidity, precipitation, or other weather-related conditions.

---

## 2. Proposed Technology Stack

The following technologies are **planned candidates** for the system architecture. The final implementation may be adjusted depending on technical feasibility, data availability, and project requirements.

| Component | Proposed Technology |
|---|---|
| Data Ingestion | **Apache NiFi** |
| Message Streaming | **Apache Kafka** |
| Stream / Batch Processing | **Apache Spark** |
| Data Lake Storage | **MinIO / S3-compatible Storage** |
| Table Format | **Apache Iceberg** |
| Data Format | **CSV / Parquet** |
| Metadata & SQL Metastore | **Apache Hive** |
| SQL Query Engine | **Trino** |
| NoSQL Storage | **MongoDB** |
| Visualization | **Apache Superset** |
| Weather Prediction | **Machine Learning models** *(planned)* |

The proposed architecture follows the general flow:

```text
Weather Data Sources
        │
        ▼
   Apache NiFi
        │
        ▼
   Apache Kafka
        │
        ▼
    Apache Spark
        │
        ▼
 MinIO / S3 + Iceberg
        │
        ├──────────────► Trino ───► Apache Superset
        │
        ▼
 Weather Prediction
    (Planned)
```

> **Note:** This technology stack represents the **current project plan**, rather than a fixed implementation. Individual components may be changed or removed during development based on system requirements and experimental results.
