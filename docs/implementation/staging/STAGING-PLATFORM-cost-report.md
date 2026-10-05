# Cost report: staging platform (AUT-101 … AUT-112)

- **Date:** 2026-10-05. **Budget:** 25 USD/month (owner decision N3), forecast alerts at 80 % and 100 % (C1, kept).
- **Prices:** AWS Price List API for ap-south-1 (`AmazonEC2` offer 20260925174521, `AmazonVPC`, `awskms`,
  `AmazonCloudWatch`, `AmazonS3`, `AmazonECR`, `AWSCloudTrail`, `AmazonSNS`, `AWSSystemsManager`), read on 2026-10-05;
  730 hours per month. Usage volumes are estimates for a quiet staging host.
- **Not verified from the price list:** the CloudWatch always-free allowance (10 custom metrics, 10 alarms, 5 GB of
  logs, 3 dashboards) and SES outbound (0.10 USD per 1,000). They come from the AWS pricing pages; the account's
  free-tier status should be confirmed in the Billing console before relying on them.

## Recurring costs

| Item | Quantity | Unit price (USD) | Month (USD) |
|---|---|---|---|
| EC2 t4g.small (credits capped, `standard`) | 730 h | 0.0112 / h | 8.18 |
| Public IPv4 (host, egress model A) | 730 h | 0.005 / h | 3.65 |
| EBS gp3: 12 GB root + 20 GB data | 32 GB | 0.0912 / GB-month | 2.92 |
| EBS snapshots (7 daily, incremental) | ~2–6 GB | 0.05 / GB-month | 0.10–0.30 |
| KMS keys: state key (existing) + data + audit | 3 | 1.00 / key-month | 3.00 |
| KMS requests (bucket keys keep them low) | < 20,000 | free tier | 0.00 |
| CloudWatch custom metrics: 7 log filters, tampering, memory, 2 disks, health | 12 | 0.30 / metric-month | 3.60 |
| CloudWatch alarms (standard): 9 application, trail, 6 host, 2 SES | 18 | 0.10 / alarm-month | 1.80 |
| CloudWatch dashboard | 1 | 3.00 beyond 3 free | 0.00 |
| CloudWatch Logs ingestion: app, host, trail, sessions | ~1–1.5 GB | 0.67 / GB | 0.67–1.00 |
| CloudWatch Logs storage | ~1–2 GB | 0.03 / GB-month | 0.03–0.06 |
| VPC flow logs delivered to S3 | ~0.3 GB | 0.25 / GB | 0.08 |
| S3 storage: Litestream, snapshots, logs, evidence, artifacts | ~3–5 GB | 0.025 / GB-month | 0.08–0.13 |
| S3 requests (Litestream WAL uploads while writes happen, snapshots, logs) | ~50,000 PUT | 0.005 / 1,000 | 0.25 |
| ECR storage | ~1–2 GB | 0.10 / GB-month | 0.10–0.20 |
| CloudTrail: first copy of management events; S3 data events on two buckets | few thousand | 0.10 / 100,000 | < 0.01 |
| SNS email, SQS, SSM standard parameters and sessions, budget, VPC, gateway endpoint, IGW | — | free | 0.00 |
| SES (sandbox, a few hundred messages) | < 1,000 | 0.10 / 1,000 | < 0.10 |
| Data transfer out | < 100 GB | free allowance | 0.00 |

## Totals

| Scenario | Month (USD) | Fits 25 USD |
|---|---|---|
| List prices, no free allowance | **≈ 24.5–25.5** | **At the limit** |
| With the CloudWatch always-free allowance (10 metrics, 10 alarms, 5 GB logs) | **≈ 19.5–20.5** | Yes, ~5 USD margin |

**Consequences.**
- The forecast will sit close to 20 USD, so the **80 % forecast alert (20 USD) is expected to fire** (C1: kept as is).
- Without the free allowance the platform runs at the budget; any growth (a bigger volume, more alarms, detailed
  monitoring, a NAT gateway at 40.88 USD or one interface endpoint at 9.49 USD) exceeds it.

## Cost drivers and the choices that contain them

| Driver | Choice made | Saving |
|---|---|---|
| Embedded Metric Format request metrics (`Route` × `StatusClass`) | 7 fixed log metric filters instead | Avoids tens of custom metrics (a few dozen route/status pairs would cost 10–20 USD) |
| NAT gateway or interface endpoints | Egress model A (N1) | 40.88 USD (NAT) or ~9.49 USD per endpoint |
| Three KMS keys | Two (data, audit) | 1.00 USD |
| t4g.medium | t4g.small (N2) | 8.18 USD |
| Unlimited burst credits | `standard` | No surprise CPU-credit charges |
| Detailed EC2 monitoring | Off | ~2.10 USD (7 metrics) |

## If the total must come down (one bounded owner decision, only if needed)

The lowest-cost safe option is to **trim monitoring, not security**: merge the two disk alarms and drop the root-disk
metric, and fold `scheduled-job-failed` and `outbox-dead` into one alarm (−2 metrics, −3 alarms: about −0.90 USD).
Encryption, the trail, the snapshots and the no-inbound network are not candidates.
