# Accidental Data Loss Prevention
STOP AND VERIFY: Before running any command or tool that results in irreversible data loss, obtain explicit user consent.
Checks:
- SQL: DROP TABLE/VIEW/SCHEMA/DATABASE, TRUNCATE, or broad DELETE.
- Cloud Storage: gsutil rm / gcloud storage rm.
- Infrastructure: gcloud projects delete, deleting Spanner/BigQuery/Dataproc resources, deleting secrets.
