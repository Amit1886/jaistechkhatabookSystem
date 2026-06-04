-- MySQL schema reference for Smart Khata module (generated from Django models).
-- Source of truth remains Django migrations in:
--   - smart_khata/migrations/
--   - khataapp/migrations/0010_party_credit_score_fields_and_reminderlog_invoice_tone.py

-- 1) New table: smart_khata_paymentbehavior
CREATE TABLE IF NOT EXISTS `smart_khata_paymentbehavior` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `due_date` date NOT NULL,
  `paid_date` date NULL,
  `delay_days` int NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  `customer_id` bigint NOT NULL,
  `invoice_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `smart_khata_paymentbehavior_invoice_id_uniq` (`invoice_id`),
  KEY `skb_owner_cust_ca_idx` (`owner_id`,`customer_id`,`created_at`),
  KEY `skb_owner_due_idx` (`owner_id`,`due_date`),
  KEY `skb_owner_delay_idx` (`owner_id`,`delay_days`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) Existing tables updated by migrations:
-- khataapp_party: adds credit_score, last_payment_date, average_payment_delay, total_due
-- khataapp_reminderlog: adds invoice_id, tone
-- (Use Django migrations to apply these ALTERs safely.)

