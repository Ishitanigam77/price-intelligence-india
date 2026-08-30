# terraform/

Azure infrastructure for PriceRadar India (Phase 15).

## Workflow

```
terraform fmt → terraform validate → checkov → terraform plan → approval (prod) → terraform apply
```

Never `terraform destroy`. Never apply a plan that replaces PostgreSQL, Key Vault, ACR, or the state storage account.

## Layout

- `bootstrap/` — one-time remote state (resource group + storage account + `tfstate` container)
- `modules/` — networking, ACR, Key Vault, identity, PostgreSQL, Redis, storage, monitoring, Container Apps, alerts, platform
- `environments/dev|staging|prod/` — environment roots
- `checkov.yaml` — IaC scan config and justified skips
- `IMPORT.md` — adopting resources that already exist

## Local commands

```bash
terraform fmt -recursive
cd infrastructure/terraform/environments/dev
terraform init -backend=false
terraform validate
checkov -d .. --config-file ../checkov.yaml
```

Apply (operators, after Azure login and `backend.hcl`):

```bash
terraform init -backend-config=backend.hcl
terraform plan -out=tfplan
terraform apply tfplan
```

Production: use `infrastructure/pipelines/azure-pipelines.terraform.yml` with parameter `environment=prod` so apply runs only after the Azure DevOps `production` Environment check.
