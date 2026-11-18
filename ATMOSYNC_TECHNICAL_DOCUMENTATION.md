# ATMOSYNC
## Comprehensive Technical Project Documentation

**Project Title:** AtmoSync – Micro-Climate Arbitrage Analytics  
**Domain:** Data Analytics, Data Engineering and Supply Chain Intelligence  
**Project Type:** Team-Based Internship Project  
**Organization:** Infotact Solutions  
**Project Reference:** ITS/DA/1709

---

# 1. Introduction

AtmoSync is a micro-climate analytics platform designed to improve the monitoring and decision-making process involved in agricultural supply chains.

Agricultural commodities such as fruits and vegetables are sensitive to environmental conditions during transportation and storage. Changes in temperature, humidity and physical handling conditions can influence product quality and increase the possibility of spoilage.

Traditional supply chain monitoring systems often depend on standard transit times and general weather information. However, these sources may not accurately represent the environmental conditions experienced inside an individual shipping container.

AtmoSync addresses this challenge by combining simulated or collected IoT sensor readings, data processing, analytical models and business intelligence techniques.

The platform aims to identify potentially unsafe shipment conditions, estimate spoilage risks and explore alternative market opportunities before product quality deteriorates.

# 2. Problem Statement

Agricultural shipments travel through multiple transportation routes and storage environments before reaching their destinations.

During transportation, environmental conditions can change unexpectedly due to:

- Temperature fluctuations.
- Excessive humidity.
- Inadequate refrigeration.
- Transportation delays.
- Physical vibration and handling.
- Unexpected storage conditions.

These variations may affect the quality and remaining shelf life of perishable commodities.

Conventional monitoring approaches may not provide sufficient shipment-level environmental visibility or connect shipment health information with market opportunities.

Therefore, a system is required that can process environmental readings, monitor shipment conditions, estimate potential risks and support data-driven rerouting decisions.

# 3. Project Objectives

The major objectives of AtmoSync are:

1. Develop a system for monitoring environmental conditions inside agricultural shipments.
2. Simulate or ingest IoT sensor readings such as temperature, humidity and vibration.
3. Clean, validate and transform collected sensor information.
4. Identify abnormal environmental conditions.
5. Estimate potential spoilage risks using configurable analytical assumptions.
6. Analyze agricultural commodity prices across different markets.
7. Estimate possible arbitrage opportunities after considering transportation and handling costs.
8. Provide meaningful visualizations through business intelligence dashboards.
9. Support better decision-making through analytical reports and alerts.
10. Develop an extensible data pipeline that can support future real-time integrations.

# 4. Proposed System Architecture

AtmoSync follows a modular data engineering and analytics architecture.

The major components are:

1. Data generation and ingestion.
2. Data storage.
3. Data cleaning and transformation.
4. Analytical processing.
5. Business intelligence visualization.
6. Alert generation and reporting.

## 4.1 Architecture Workflow

```text
        IoT SENSOR DATA
   Temperature | Humidity
          Vibration
              |
              v
     PYTHON DATA SIMULATOR
              |
              v
       DATA INGESTION
              |
       +------+------+
       |             |
       v             v
   APACHE KAFKA   LOCAL INPUT
       |             |
       +------+------+
              |
              v
       DATA STORAGE
              |
       +------+------+
       |             |
       v             v
    DUCKDB        SNOWFLAKE
   LOCAL MODE    CLOUD MODE
       |             |
       +------+------+
              |
              v
       DBT TRANSFORMATION
              |
              v
       ANALYTICAL MODELS
              |
       +------+------+
       |             |
       v             v
  RISK ANALYSIS  MARKET ANALYSIS
       |             |
       +------+------+
              |
              v
       BUSINESS INTELLIGENCE
              |
        +-----+------+
        |            |
        v            v
      TABLEAU     REPORTS
```

The local implementation supports development and testing without requiring cloud credentials. The complete Kafka and Snowflake integration is intended for the deployment environment and must be validated separately.

# 5. Data Sources and Data Generation

AtmoSync requires two major categories of information.

## 5.1 Environmental Sensor Data

Environmental readings describe the conditions experienced by a shipment.

Important parameters include:

| Parameter | Description | Unit |
|---|---|---|
| Temperature | Internal container temperature | °C |
| Humidity | Relative humidity | % |
| Vibration | Physical movement intensity | Configured sensor unit |
| Timestamp | Time of observation | Date and time |
| Container ID | Unique shipment identifier | Text |
| Location | Shipment location | Geographic reference |

Temperature and humidity are important indicators when monitoring perishable agricultural products.

Vibration information can also help identify unusual transportation or handling conditions.

## 5.2 Commodity Market Data

Market information is used to compare potential selling opportunities across destinations.

Relevant attributes include:

- Commodity name.
- Market name.
- Market location.
- Observation date.
- Wholesale price.
- Retail price, where available.
- Currency.
- Quantity or weight unit.
- Data source.

Real market prices and simulated demonstration prices must remain distinguishable.

## 5.3 Simulated Data

When live sensor data is unavailable, AtmoSync can use a Python-based simulator to generate representative readings.

Simulation scenarios can include:

- Normal storage conditions.
- Gradual temperature increases.
- Sudden temperature spikes.
- High humidity conditions.
- Unusual vibration patterns.
- Combined environmental disturbances.

Simulated readings are useful for development, testing and demonstrations. They should not be presented as actual shipment measurements.

# 6. Data Ingestion Layer

The ingestion layer is responsible for receiving environmental information and making it available for further processing.

Python is used to generate or process sensor readings.

Each reading should contain sufficient information to identify its source and observation time.

A typical sensor event contains:

```json
{
  "container_id": "CONT_001",
  "timestamp": "2026-11-18T10:30:00",
  "temperature": 8.5,
  "humidity": 82.0,
  "vibration": 0.24
}
```

The values above are illustrative sample data.

## 6.1 Apache Kafka

Apache Kafka is intended to support real-time event streaming.

Kafka topics can separate different categories of information, such as:

- Sensor readings.
- Container status updates.
- Environmental alerts.
- Rejected or invalid messages.

A producer publishes sensor events to the appropriate topic. Consumers receive those events and pass them to downstream processing components.

Kafka provides a scalable architecture for handling continuous event streams.

Live broker deployment and throughput must be verified separately.

# 7. Data Storage

The project supports a local development architecture and a planned cloud storage architecture.

## 7.1 DuckDB

DuckDB provides local analytical storage.

It is useful for:

- Loading structured datasets.
- Executing analytical SQL queries.
- Storing processed sensor readings.
- Supporting local dbt transformations.
- Testing analytical models without cloud infrastructure.

## 7.2 Snowflake

Snowflake is the intended cloud data warehouse.

Its role includes:

- Storing raw sensor events.
- Managing historical commodity price information.
- Supporting transformed analytical datasets.
- Providing scalable analytical query execution.

The Snowflake integration requires valid credentials and environment configuration. Its live functionality should only be reported after an actual deployment test.

# 8. Data Cleaning and Transformation

Raw sensor information may contain incomplete, duplicate or invalid records.

Data cleaning is necessary before performing reliable analysis.

Important validation operations include:

1. Checking required columns.
2. Validating container identifiers.
3. Converting timestamps into consistent formats.
4. Checking numeric sensor values.
5. Identifying missing readings.
6. Detecting duplicate events.
7. Identifying unusual values.
8. Maintaining consistent units.

## 8.1 Role of dbt

dbt is used to organize SQL-based data transformations.

The transformation workflow can be divided into:

**Staging Layer**

- Read raw sensor information.
- Standardize column names.
- Convert data types.
- Handle invalid and missing values.

**Intermediate Layer**

- Aggregate sensor readings.
- Calculate environmental statistics.
- Join shipment and commodity information.
- Prepare analytical datasets.

**Mart Layer**

- Shipment health summaries.
- Environmental risk indicators.
- Market comparison results.
- Potential arbitrage opportunities.

The local DuckDB implementation allows these transformations to be developed and tested before cloud deployment.

# 9. Sensor Analytics

Sensor analytics examines environmental readings to identify potentially unsafe shipment conditions.

## 9.1 Temperature Monitoring

Temperature monitoring helps identify changes in storage conditions.

The system can compare observed temperature values against configurable commodity-specific thresholds.

A temperature reading outside the configured range can generate a warning or critical indicator.

## 9.2 Humidity Monitoring

Humidity measurements help monitor moisture-related storage conditions.

Excessively high or low humidity may affect the quality of agricultural products depending on the commodity.

Therefore, humidity limits should be configurable rather than universally fixed.

## 9.3 Vibration Monitoring

Vibration readings provide information about physical movement during transportation.

Unusual vibration patterns can indicate possible handling disturbances or transportation irregularities.

# 10. Spoilage-Risk Estimation

One of the main analytical components of AtmoSync is spoilage-risk estimation.

The objective is to identify shipments that may experience increased quality deterioration under unfavorable environmental conditions.

The model considers parameters such as:

- Commodity type.
- Current temperature.
- Relative humidity.
- Time spent under unfavorable conditions.
- Configured storage thresholds.
- Remaining estimated shelf life.

A simplified conceptual risk score can be represented as:

\[
R = w_T T + w_H H + w_V V
\]

Where:

- \(R\) represents the combined risk indicator.
- \(T\) represents the normalized temperature-risk contribution.
- \(H\) represents the normalized humidity-risk contribution.
- \(V\) represents the normalized vibration-risk contribution.
- \(w_T,w_H,w_V\) represent configurable weights.

The weights must be documented and validated before using the score for operational decisions.

A higher risk score indicates a greater estimated environmental concern.

## 10.1 Risk Classification

A configurable classification system can categorize shipments into:

| Category | Interpretation |
|---|---|
| Healthy | Conditions are within configured limits |
| Warning | Early environmental deviation |
| At Risk | Significant environmental concern |
| Critical | Severe or prolonged deviation |

These categories are operational indicators, not guaranteed measurements of actual product spoilage.

# 11. Market Price Intelligence

AtmoSync connects shipment monitoring with agricultural market analytics.

The objective is to identify whether selling a shipment at an alternative destination could produce a better financial outcome.

For example, a shipment may be heading toward Market A while Market B offers a higher commodity price.

However, a higher market price does not automatically indicate a profitable rerouting opportunity.

Transportation costs, handling charges, market demand and product quality must also be considered.

## 11.1 Gross Price Difference

\[
G = P_B - P_A
\]

Where:

- \(P_B\) is the price at the alternative market.
- \(P_A\) is the price at the original market.

## 11.2 Estimated Net Arbitrage Margin

\[
M = Q(P_B-P_A)-C_T-C_H-C_O
\]

Where:

- \(Q\) is the saleable quantity.
- \(C_T\) is transportation cost.
- \(C_H\) is handling cost.
- \(C_O\) represents other applicable costs.

A positive estimated margin indicates a potentially favorable opportunity under the supplied assumptions.

The calculation should also consider the quantity that may remain saleable after transportation.

These calculations are estimates and require accurate market prices and cost information before real-world use.

# 12. Shipment Rerouting Intelligence

The rerouting component compares the original destination with potential alternative markets.

Important decision parameters include:

- Remaining estimated shelf life.
- Distance to alternative destinations.
- Estimated transportation time.
- Transportation cost.
- Alternative market price.
- Shipment environmental risk.

The system can rank possible alternatives using a configurable decision score.

A rerouting recommendation should explain the reason behind its selection.

For example:

- Alternative market offers a better estimated selling price.
- The destination is reachable within the estimated remaining shelf life.
- Additional transportation expenses are acceptable.
- The estimated net margin is positive.

A recommendation should not be treated as an automatic transportation instruction.

# 13. Alert Management

Alerts help users identify environmental conditions that require attention.

Potential alert categories include:

- High-temperature warning.
- Low-temperature warning.
- High-humidity warning.
- Abnormal vibration.
- Missing sensor readings.
- Critical shipment risk.

An alert record should contain:

- Alert ID.
- Container ID.
- Timestamp.
- Alert category.
- Severity.
- Description.
- Acknowledgement status.
- Resolution status.

Alerts should be generated using configurable conditions.

# 14. Business Intelligence Dashboard

The dashboard is intended to present important shipment and market information in a clear format.

Tableau is the requested primary BI platform.

The dashboard should help users understand shipment conditions without needing to examine raw sensor records.

## 14.1 Recommended Dashboard Sections

**Executive Overview**

- Total shipments monitored.
- Healthy shipments.
- At-risk shipments.
- Critical shipments.
- Active alerts.
- Potential rerouting opportunities.

**Shipment Monitoring**

- Container-wise temperature trends.
- Humidity variations.
- Vibration patterns.
- Latest sensor observations.

**Risk Analysis**

- Shipment health scores.
- Risk classifications.
- Historical risk progression.
- Environmental threshold violations.

**Market Intelligence**

- Commodity price comparison.
- Market-wise price differences.
- Estimated transportation expenses.
- Estimated net arbitrage margins.

**Rerouting Analysis**

- Original destination.
- Alternative destination.
- Estimated travel time.
- Potential financial benefit.
- Risk-related recommendation.

All dashboard outputs must clearly distinguish real observations from simulated or estimated values.

# 15. Streamlit Supporting Application

Streamlit provides a supporting interface for local project interaction and demonstrations.

It can be used to:

- Display shipment information.
- Explore sensor readings.
- View analytical results.
- Inspect environmental anomalies.
- Review risk indicators.
- Explore market comparisons.
- Access reports.

The Streamlit application complements the Tableau dashboard rather than replacing it.

# 16. Testing and Validation

Testing is important for ensuring that the individual components operate correctly.

The project testing strategy includes:

## 16.1 Unit Testing

Individual functions are tested using representative inputs.

Examples include:

- Sensor reading validation.
- Data cleaning functions.
- Risk calculation.
- Shipment classification.
- Market margin calculations.
- Alert generation.

## 16.2 Integration Testing

Integration testing examines communication between related modules.

Examples include:

- Simulator to ingestion.
- Ingestion to DuckDB.
- DuckDB to dbt.
- Analytics to Tableau export.
- Analytics to alert generation.

## 16.3 Pipeline Testing

The local pipeline should be executed from start to finish.

Expected operations include:

1. Generate or load sample readings.
2. Validate and clean records.
3. Load data into local storage.
4. Execute dbt transformations.
5. Generate analytical outputs.
6. Export dashboard-ready datasets.
7. Generate alert summaries.

The actual test report should record the execution date, test count, results and failures.

# 17. Security and Data Management

The project should follow basic data management practices.

Important recommendations include:

- Store credentials in environment variables.
- Never commit passwords or API keys.
- Maintain an `.env.example` file.
- Validate incoming data.
- Separate raw and transformed datasets.
- Avoid uploading sensitive raw records.
- Document external data sources and applicable licences.
- Maintain clear distinctions between real and simulated data.

# 18. Limitations

The current implementation and demonstration architecture have several limitations.

1. Simulated sensor data cannot fully represent actual transportation conditions.
2. Heuristic spoilage-risk calculations are not equivalent to validated scientific shelf-life predictions.
3. Real market prices may vary by region, date, quality and quantity.
4. Route recommendations depend on the accuracy of supplied travel and cost information.
5. Live Kafka functionality requires broker configuration and deployment testing.
6. Snowflake integration requires cloud credentials and validation.
7. Tableau dashboard development and workbook validation must be completed separately.
8. Alert delivery through external communication services requires configuration and testing.

These limitations should be addressed progressively before operational deployment.

# 19. Future Enhancements

Potential future improvements include:

- Integration with real IoT devices.
- Live GPS-based shipment tracking.
- Advanced time-series forecasting.
- Machine-learning-based anomaly detection.
- Commodity-specific shelf-life models.
- Real-time market price ingestion.
- Automated route optimization.
- Predictive maintenance for refrigeration systems.
- Role-based access control.
- Cloud deployment and monitoring.
- Automated executive report generation.

# 20. Conclusion

AtmoSync demonstrates how data engineering, analytics and business intelligence can be combined to address challenges in agricultural supply chains.

By collecting environmental readings, processing shipment information and comparing agricultural market prices, the platform aims to support better shipment monitoring and informed business decisions.

The modular architecture provides a foundation for future integration with real-time streaming technologies, cloud data warehouses and business intelligence platforms.

The project also demonstrates the practical use of Python, SQL, DuckDB, dbt, Kafka, Snowflake and Tableau within an end-to-end analytics workflow.

The ultimate objective is to transform environmental and market data into meaningful insights that help reduce avoidable losses and improve supply-chain decision-making.

---

**Document Status:** Technical Project Documentation  
**Project:** AtmoSync – Micro-Climate Arbitrage Analytics  
**Reference:** ITS/DA/1709

*Note: This document describes the intended architecture and analytical approach. Any feature described as planned or proposed should not be interpreted as a completed live deployment. Actual implementation and testing status must be verified against the project repository.*
