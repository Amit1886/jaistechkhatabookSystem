# Workforce Governance, Productivity, And Payroll Economy Platform

This extends EWOS with AI-ready governance, productivity, payroll, discipline, fraud risk, HR intelligence, and profitability analytics.

## Core Data

- `ProductivitySignal`
- `EmployeeScoreSnapshot`
- `PayrollPolicy`
- `EmployeePayrollProfile`
- `PayrollRun`
- `Payslip`
- `PayoutInstruction`
- `DisciplineCase`
- `FraudRiskSignal`
- `HRInsight`
- `WorkforceProfitabilitySnapshot`

## Productivity Signals

Tracked signal types:

- task completion
- active work hours
- app usage
- browser usage
- screenshots
- idle detection
- coding activity
- support response time
- sales activity
- customer ratings

## Scoring

Generated scores:

- productivity
- discipline
- trust
- leadership
- communication
- quality
- fraud risk
- performance

## Payroll Economy

Supported payout components:

- monthly salary
- hourly salary
- task-based payout
- commission payout
- incentive payout
- revenue share
- overtime payout
- attendance bonus
- performance bonus
- penalties
- deductions
- configurable tax rules

## API

Base:

`/api/v1/platform/workforce/`

New endpoints:

- `command-center/`
- `productivity-signals/`
- `score-snapshots/`
- `payroll-policies/`
- `payroll-profiles/`
- `payroll-runs/generate/`
- `payslips/{id}/queue_payout/`
- `payouts/`
- `discipline-cases/`
- `fraud-risks/`
- `hr-insights/`
- `profitability/`

## Command Center

The command center exposes:

- live employees
- live tasks
- payroll estimates
- attendance status
- burnout alerts
- fraud alerts
- productivity trends

## Important Governance Note

AI/risk scores should be treated as decision support, not automatic termination or disciplinary final action. Keep human review, audit logs, and appeal workflows for fairness and compliance.

