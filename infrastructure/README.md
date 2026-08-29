# infrastructure/

Infrastructure as code and CI/CD for deploying PriceRadar India to Azure.

**Status**: **Phase 15 — Production DevOps** implemented. Terraform modules, Azure DevOps pipelines, GitHub Actions CI, Docker images, and local Compose exist in this repository. **No Azure subscription was applied from this change**; operators must apply Terraform and wire Azure DevOps.

## Layout

- `CICD.md` — pipeline stages, environments, approvals, variable groups, how to deploy safely
- `IDENTITY.md` — CI, Terraform, ACR, runtime, and Key Vault identities
- `terraform/` — modules + `environments/dev|staging|prod` + `bootstrap` (remote state)
- `docker/docker-compose.yml` — local PostgreSQL, Redis, backend, worker, frontend, ML
- `pipelines/` — Azure DevOps YAML (`azure-pipelines.yml`, `azure-pipelines.terraform.yml`)

There is no `terraform destroy` in any pipeline.
