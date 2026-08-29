# Identity and RBAC (Phase 15)

No long-lived Azure client secrets are stored in this repository. Prefer OpenID Connect / federated credentials on Azure DevOps service connections.

## Who authenticates as what

| Actor | Identity | How it is configured | Roles (least privilege intent) |
|---|---|---|---|
| **CI (GitHub Actions)** | GitHub-hosted runner, `contents: read` | No Azure login | None. GitHub CI does not deploy. |
| **CI/CD (Azure DevOps)** | Service connection `azure-sc-<env>` (OIDC to an Entra app registration) | Azure DevOps project settings → Service connections. Production connection is a separate Entra app. | Resource Group Contributor; User Access Administrator only if Terraform must create role assignments; **AcrPush** on that environment's ACR; **Key Vault Secrets Officer** if pipelines write secrets (prefer Terraform + operators in the portal). |
| **Terraform** | Same service connection as the environment being applied | `AzureCLI@2` / AzureRM provider with OIDC (`ARM_USE_OIDC=true`) | Same as CD, plus ability to manage the environment resource group. Object ID may be passed as `cicd_principal_id` so Terraform grants AcrPush / KV Secrets Officer. |
| **ACR** | System-assigned identity on the registry (optional); **no admin user** | Terraform `admin_enabled = false` | Runtime does not push. CD pushes with the service connection after `az acr login`. |
| **Application runtime** (frontend, backend, worker, ML, jobs) | User-assigned managed identity `id-app-<env>` | Attached on each Container App / Job; registry block uses this identity | **AcrPull** on ACR; **Key Vault Secrets User** on the environment vault; **Storage Blob Data Contributor** on the ML artifacts account |
| **Key Vault** | Azure RBAC (`rbac_authorization_enabled`) | Terraform. Human operators: Key Vault Secrets Officer (or Administrator) via Entra PIM if available | Data-plane: apps get Secrets User only. Terraform principal: Key Vault Administrator during apply to create generated secrets. |

## What operators must create

1. Entra app registrations (or one per environment) with federated credentials for Azure DevOps.
2. Service connections named `azure-sc-dev`, `azure-sc-staging`, `azure-sc-prod`.
3. Approval check on the `production` Environment bound to `azure-sc-prod`.
4. Optional: `cicd_principal_id` in Terraform so AcrPush / KV assignments are in code.

## What must never be committed

- Client secrets, certificates, storage account keys, PostgreSQL passwords, Redis keys, Clerk secret keys, retailer API tokens, `APPLICATIONINSIGHTS_CONNECTION_STRING`.

Generated database and Redis URLs live in Key Vault and in Terraform state (encrypted Azure Storage, Azure AD auth, no shared keys). Restrict who can read the `tfstate` container.
