-- MySQL schema reference for Procurement module (generated from Django models).
-- Source of truth remains Django migrations in `procurement/migrations/`.

CREATE TABLE IF NOT EXISTS `procurement_supplierproduct` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `price` decimal(12,2) NOT NULL DEFAULT 0.00,
  `moq` int unsigned NOT NULL DEFAULT 1,
  `delivery_days` int unsigned NOT NULL DEFAULT 1,
  `last_updated` datetime(6) NOT NULL,
  `is_active` bool NOT NULL DEFAULT 1,
  `created_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  `supplier_id` bigint NOT NULL,
  `product_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `procurement_supplierproduct_owner_supplier_product_uniq` (`owner_id`,`supplier_id`,`product_id`),
  KEY `procurement_sp_owner_product_idx` (`owner_id`,`product_id`),
  KEY `procurement_sp_owner_supplier_idx` (`owner_id`,`supplier_id`),
  KEY `procurement_sp_owner_product_supplier_idx` (`owner_id`,`product_id`,`supplier_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `procurement_supplierpricehistory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `old_price` decimal(12,2) NOT NULL,
  `new_price` decimal(12,2) NOT NULL,
  `change_pct` decimal(8,2) NOT NULL DEFAULT 0.00,
  `updated_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  `supplier_id` bigint NOT NULL,
  `product_id` bigint NOT NULL,
  `updated_by_id` bigint NULL,
  PRIMARY KEY (`id`),
  KEY `procurement_sph_owner_product_supplier_idx` (`owner_id`,`product_id`,`supplier_id`),
  KEY `procurement_sph_owner_supplier_updated_idx` (`owner_id`,`supplier_id`,`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `procurement_supplierrating` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `delivery_speed` smallint unsigned NOT NULL DEFAULT 3,
  `product_quality` smallint unsigned NOT NULL DEFAULT 3,
  `pricing` smallint unsigned NOT NULL DEFAULT 3,
  `comment` longtext NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  `supplier_id` bigint NOT NULL,
  `rated_by_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `procurement_supplierrating_owner_supplier_ratedby_uniq` (`owner_id`,`supplier_id`,`rated_by_id`),
  KEY `procurement_sr_owner_supplier_idx` (`owner_id`,`supplier_id`),
  KEY `procurement_sr_owner_ratedby_idx` (`owner_id`,`rated_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `procurement_supplierpricealert` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `old_price` decimal(12,2) NOT NULL,
  `new_price` decimal(12,2) NOT NULL,
  `change_pct` decimal(8,2) NOT NULL DEFAULT 0.00,
  `direction` varchar(8) NOT NULL DEFAULT 'up',
  `threshold_pct` decimal(8,2) NOT NULL DEFAULT 10.00,
  `is_read` bool NOT NULL DEFAULT 0,
  `created_at` datetime(6) NOT NULL,
  `owner_id` bigint NOT NULL,
  `supplier_id` bigint NOT NULL,
  `product_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `procurement_spa_owner_isread_created_idx` (`owner_id`,`is_read`,`created_at`),
  KEY `procurement_spa_owner_product_created_idx` (`owner_id`,`product_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

