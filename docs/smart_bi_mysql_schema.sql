-- Smart Business Intelligence Module (MySQL) - reference schema
-- Source of truth: Django migrations in `smart_bi/migrations/` and `commerce/migrations/`.
-- This SQL is provided as a convenience for DBAs; names/constraints may vary by deployment.

-- -----------------------------
-- 1) business_metrics
-- -----------------------------
CREATE TABLE IF NOT EXISTS `business_metrics` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `owner_id` BIGINT NOT NULL,
  `date` DATE NOT NULL,
  `total_sales` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `total_profit` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `total_expense` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `outstanding_due` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `stock_value` DECIMAL(14,2) NOT NULL DEFAULT 0.00,
  `health_score` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `computed_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_business_metrics_owner_date` (`owner_id`, `date`),
  KEY `bizm_owner_date_idx` (`owner_id`, `date`),
  CONSTRAINT `fk_business_metrics_owner` FOREIGN KEY (`owner_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
);

-- -----------------------------
-- 2) festival_campaign + festival_products
-- -----------------------------
CREATE TABLE IF NOT EXISTS `festival_campaign` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `owner_id` BIGINT NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  `discount_type` VARCHAR(20) NOT NULL,
  `discount_value` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `theme` VARCHAR(50) NOT NULL DEFAULT 'default',
  `status` VARCHAR(10) NOT NULL DEFAULT 'draft',
  `banner_image` VARCHAR(100) NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `fest_owner_active_idx` (`owner_id`, `status`, `start_date`, `end_date`),
  CONSTRAINT `fk_festival_campaign_owner` FOREIGN KEY (`owner_id`) REFERENCES `accounts_user` (`id`) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS `festival_products` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `campaign_id` BIGINT NOT NULL,
  `product_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_festival_campaign_product` (`campaign_id`, `product_id`),
  CONSTRAINT `fk_festival_products_campaign` FOREIGN KEY (`campaign_id`) REFERENCES `festival_campaign` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_festival_products_product` FOREIGN KEY (`product_id`) REFERENCES `commerce_product` (`id`) ON DELETE CASCADE
);

-- -----------------------------
-- 3) Duplicate invoice tables
-- -----------------------------
-- Table name is the Django default: `smart_bi_duplicateinvoicesettings`.
-- Fields:
-- - owner_id, enabled, window_minutes, strict_mode, similarity_threshold, updated_at

-- Table name is the Django default: `smart_bi_duplicateinvoicelog`.
-- Fields:
-- - owner_id, created_by_id, invoice_id, possible_duplicate_id, similarity_score, created_at

-- -----------------------------
-- 4) commerce_order changes (festival discount fields)
-- -----------------------------
-- Django migration: `commerce/migrations/0025_order_festival_campaign_and_more.py`
ALTER TABLE `commerce_order`
  ADD COLUMN `festival_campaign_id` BIGINT NULL,
  ADD COLUMN `festival_discount_amount` DECIMAL(12,2) NOT NULL DEFAULT 0.00;

ALTER TABLE `commerce_order`
  ADD CONSTRAINT `fk_commerce_order_festival_campaign`
  FOREIGN KEY (`festival_campaign_id`) REFERENCES `festival_campaign` (`id`)
  ON DELETE SET NULL;

