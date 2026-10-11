US Air Traffic Big Data Pipeline
A Big Data Storage and Processing project for analyzing historical US flight data and processing near-real-time flight events.
Architecture
- Batch: BTS historical data → HDFS → Apache Spark → Parquet
- Streaming: AviationStack API (or clearly labeled simulated events) → Apache Kafka → Spark Structured Streaming → HDFS
- Serving: Processed batch and streaming results → MongoDB → Dashboard
The project follows a Lambda Architecture, combining batch and streaming pipelines.
Technologies
- Apache Spark / PySpark
- HDFS
- Apache Kafka
- MongoDB (NoSQL)
- Docker Compose for local development
- Kubernetes or Cloud deployment to be evaluated for the final milestone, according to course requirements
Data Sources
- Historical: US Bureau of Transportation Statistics (BTS) On-Time Performance data
- Real-time: AviationStack API, subject to API access and usage limits; simulated events may be used for development and testing
Current Development Scope
Development starts with a small BTS subset (January 2020) before scaling to a larger time range. The pipeline is developed and tested incrementally.
Project Goals
- Build an end-to-end data pipeline: ingestion, processing, storage, and visualization
- Apply intermediate and advanced Spark transformations, aggregations, joins, and optimization
- Demonstrate streaming concepts such as event-time windows, watermarking, checkpointing, and recovery
- Store query-ready results in a NoSQL database and present key metrics in a dashboard
Repository Structure
.
├── hadoop/
│   ├── conf/
│   ├── data/
│   └── scripts/
├── data/
├── spark/
│   └── jobs/
├── kafka/
├── docker-compose.yml
└── README.md
Status
- HDFS is running locally in Docker.
- Spark batch processing has successfully processed the January 2020 BTS subset and written Parquet output to HDFS.
- Kafka Producer/Consumer messaging has been tested successfully.
- Spark Structured Streaming, MongoDB integration, dashboard, and final deployment remain to be completed.
Notes
- Keep raw data separate from processed outputs.
- Record data source, collection time, and data-quality checks.
- Do not label simulated events as live API data.
- Docker Compose is currently used for development; final deployment should follow the course milestone requirements.