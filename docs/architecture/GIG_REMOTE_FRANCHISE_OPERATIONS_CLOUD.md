# Gig, Remote Workforce, Franchise, and Partner Operations Cloud

## Goal

This layer extends the Enterprise Workforce Operating System into one multi-tenant operations cloud for employees, remote workers, freelancers, agencies, franchises, resellers, support partners, delivery partners, and field agents.

## Domain Capabilities

- Remote workforce: sessions, activity events, webcam verification flags, project contribution payloads, authenticity scoring, activity scoring.
- Gig economy: micro tasks, support gigs, delivery jobs, sales campaigns, field operations, freelance assignments, payout amounts, AI assignment score.
- Marketplace: companies publish listings, freelancers and agencies apply, support vendors and resellers can enter the partner pipeline.
- Partner ecosystem: franchise/reseller/support/BPO/delivery partner profiles, territories, white-label configuration, commissions, revenue sharing, settlements.
- Training cloud: SOP courses, AI assistant prompt, certifications, learning analytics.
- Wallet and rewards: earnings balance, bonus balance, reward points, source-linked transactions.
- Business network: company, franchise, BPO, reseller, outsourcing, and white-label deployment hierarchy.

## Backend Structure

- Models live in `apps.platform.workforce.models` and remain tenant-scoped.
- Business logic lives in `apps.platform.workforce.application.services.ecosystem_service`.
- APIs live under `/api/v1/platform/workforce/`.
- Frontend consumes the same workforce API service to keep AdminLTE and shared ERP UI behavior consistent.

## API Surface

- `remote-sessions/` with `start` and `record_event` actions.
- `remote-activity/`
- `gig-tasks/` with `ai_assign` and `reward_assignee` actions.
- `marketplace-listings/`
- `marketplace-applications/` with `apply` action.
- `partners/` with `settle` action.
- `partner-settlements/`
- `training-courses/` with `enroll` action.
- `certifications/` with `complete` action.
- `wallets/`
- `wallet-transactions/`
- `business-network/`
- `ecosystem-command-center/`

## Architecture Flow

1. A company publishes a marketplace listing or creates a gig.
2. Freelancers, employees, agencies, or partners apply or become candidates.
3. The AI distribution service scores candidates by skills, workload, and worker type.
4. Work execution emits remote activity events and updates session scores.
5. Completion can credit wallet earnings, reward points, partner commission, or settlement liability.
6. Operations dashboards aggregate open gigs, live remote sessions, partners, marketplace activity, certifications, and wallet exposure.

## Governance Note

AI assignment and authenticity scores are decision-support signals. Final HR, payout, discipline, and partner decisions should stay auditable and reviewable by authorized managers.
