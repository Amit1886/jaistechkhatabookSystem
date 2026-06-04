# Backup And Disaster Recovery

- PostgreSQL PITR with WAL archiving.
- Daily full database backup.
- Hourly incremental backup for critical tenants.
- Object storage versioning for media, invoices, exports, OCR files.
- Redis treated as ephemeral; durable jobs use database/outbox.
- Test restore weekly in isolated environment.
- RPO target: 15 minutes for enterprise cloud.
- RTO target: 60 minutes for standard SaaS, 15 minutes for premium tenants.

