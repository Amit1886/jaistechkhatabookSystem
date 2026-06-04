# SaaS Upgrade — Step 1 (Project Analysis)

Date: 2026-03-19

This repository already contains a large portion of the requested “modular SaaS” surface area (apps, APIs, services). The main gaps for the requested roadmap are **true multi-tenant isolation**, **geo-location hierarchy**, and a **multi-level role + downline hierarchy** model that is consistent across the platform.

## 1) Current Django project layout (high-level)

Settings module: `khatapro.settings` (custom user model: `accounts.User`).

Key installed apps (non-exhaustive):
- Core auth + API stack: `rest_framework`, `simplejwt`, `drf_spectacular`, `django_filters`, `allauth`
- Core business apps: `khataapp`, `billing`, `ledger`, `commerce`, `orders`, `payments`, `products`, `warehouse`
- SaaS/ops apps: `accounts`, `core_settings`, `reports`, `analytics`, `ai_engine`, `event_bus`, `realtime`
- Messaging/integrations: `whatsapp`, `whatsapp_gateway`, `sms_center`, `voice`

## 2) Existing user system (important)

Custom user model:
- `accounts.User` extends `AbstractUser` and uses `email` as `USERNAME_FIELD`.

There are **multiple “profile” models** in the system (used by different UI/API code paths):
- `accounts.UserProfile` (used by templates and permissions; contains `company` FK to `core_settings.CompanySettings` and `plan` FK to `billing.Plan`).
- `khataapp.UserProfile` (used by billing signals/services and app flows; contains `plan` FK to `billing.Plan` and business fields; related name `user.khata_profile`).
- `users.UserProfileExt` (used by “universal SaaS modules” for wallet/commission/preferences; related name `user.saas_profile`).

There are sync signals in `billing/signals.py` to keep `accounts.UserProfile.plan` and `khataapp.UserProfile.plan` aligned.

## 3) Existing billing/subscription foundations

`billing` already includes:
- `Plan`, `PlanPermissions`, `FeatureRegistry`, `PlanFeature`, `UserFeatureOverride`
- Subscription/plan history models and feature gating middleware via `core_settings.middleware.FeatureGateMiddleware`

This is a good base to attach the requested “permission control” and plan-feature enabling/disabling.

## 4) Existing agent/customer assignment foundations

`khataapp` already includes:
- `FieldAgent` with `assigned_parties` (M2M) for collector/staff workflows
- `CollectorVisit` and reminder/logging models

However, the requested **multi-level org hierarchy** (StateAdmin → DistrictAdmin → AreaAdmin → SuperAgent → Agent → Customer) is not yet modeled as a general-purpose downline graph that can power commissions, lead routing, and permissions.

## 5) Existing wallet + commission foundations

Wallet-like ledgers exist:
- `users.WalletLedger` (credit/debit entries)
- `users.CommissionLedger` (commission entries)
- plus `commission.CommissionRule` / `commission.CommissionPayout` tied to `orders.Order` margins

This can be extended into a multi-level commission engine without removing current functionality.

## 6) Key gaps vs requested roadmap

Missing/needs upgrade:
- **Location hierarchy**: Country → State → District → Pincode (no dedicated app/models found).
- **Multi-level role system**: Roles exist as group-mapping helpers (`accounts/roles.py`) but not as a first-class persisted hierarchy on the user.
- **Tenant isolation**: There are company settings models (`core_settings.CompanySettings` and a separate `khataapp.CompanySettings`), but there is not yet a consistent tenant boundary enforced at the ORM/queryset/API layer.

## 7) Recommended next step (Step 2 implementation plan)

Implement in small, backward-compatible increments:
1. Add a `location` app with Country/State/District/Pincode models and read APIs.
2. Extend `accounts.User` with `role` + `parent` fields (nullable) and keep existing group-based role mapping as fallback.
3. Add optional location FKs to `accounts.UserProfile` and `khataapp.UserProfile` (no breaking changes).
4. Add DRF endpoints for location and basic hierarchy introspection (safe read paths first).

