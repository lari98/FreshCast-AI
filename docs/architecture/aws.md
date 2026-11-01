# AWS infrastructure (phase 7)

Region: `eu-central-1` (Frankfurt) by default; only EU regions are accepted by
`DeployConfig`. **Tests never deploy.** `cdk deploy` creates billable resources.

| Stack | Contents |
|---|---|
| Data | KMS key (rotation, retained), data-lake and model-artifact buckets (private, versioned, KMS, TLS-only) |
| Db | VPC with isolated subnets (no NAT, no internet gateway), S3/SQS/Secrets endpoints, RDS PostgreSQL 16 (encrypted, private; Multi-AZ + deletion protection in prod) |
| Messaging | SQS FIFO queue + DLQ (3 receives), worker Lambda in the VPC with partial batch responses, DLQ alarm -> SNS -> email |
| Mlops | SageMaker model package group (registry), least-privilege training role, optional monthly budget alert |

Run: `.\scripts\build-worker.ps1`, then in `infrastructure/cdk`:
`cdk synth -c env_name=dev -c alert_email=you@example.com` and, deliberately,
`cdk deploy --all`. Tear down with `cdk destroy --all` (dev only).

Cost notes: interface endpoints (SQS, Secrets Manager) and RDS are the main
fixed costs. Destroy the dev stacks when not demoing.

Training: `pipelines/training/train.py` is SageMaker script-mode ready; locally
`python -m freshcast.models.training`. Metrics include data/code fingerprints and
a `beats_baseline` gate to be checked before a model is approved in the registry.

Not yet done: Step Functions training workflow, GitHub OIDC deploy role,
CloudWatch dashboards, real stage recomputation inside the worker, and
publishing outbox rows to SQS (adapter). Run a legal/privacy review before any real data.
