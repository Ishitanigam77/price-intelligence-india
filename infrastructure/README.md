# infrastructure/

Infrastructure as code and CI/CD pipeline definitions for deploying PriceRadar India to Azure.

**Status**: empty scaffold. Introduced in **Phase 11 — Infrastructure & Production
Readiness**. No cloud resources are defined or provisioned yet.

## Layout

- `terraform/` — Terraform modules and per-environment configuration for Azure resources
  (hosting, PostgreSQL, Redis, Key Vault, ACR, Monitor/Application Insights)
- `docker/` — Dockerfiles and compose files, introduced per-service as each service is built
- `pipelines/` — Azure DevOps pipeline (YAML) definitions for CI/CD
