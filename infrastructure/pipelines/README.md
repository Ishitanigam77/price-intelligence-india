# pipelines/

Azure DevOps YAML for PriceRadar India.

| File | Role |
|---|---|
| `azure-pipelines.yml` | App CI/CD: validate, lint, tests, security, builds, Docker, ACR, deploy, smoke, approvals |
| `azure-pipelines.terraform.yml` | Terraform fmt / validate / Checkov / plan / apply (no destroy) |
| `scripts/smoke_test.py` | Post-deploy probes of real `/health` endpoints |
| `scripts/deploy_containerapps.sh` | Updates apps to the CI image tag |
| `scripts/run_migrate_job.sh` | Starts the Alembic Container Apps job |
| `scripts/validate_yaml.py` | Parses pipeline YAML in the Validate stage |

Create the pipelines in Azure DevOps **from GitHub YAML**. Required Environments, service connections, and variable groups are listed in `../CICD.md`.

Production deployment **must** use Environment `production` with an approval check in the Azure DevOps UI.
