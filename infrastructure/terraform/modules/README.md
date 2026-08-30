# terraform/modules/

Reusable Terraform modules composed by `platform/` and selected from `environments/{dev,staging,prod}`.

| Module | Azure resources |
|---|---|
| `networking` | VNet, subnets, NSGs |
| `acr` | Azure Container Registry (no admin user) |
| `key_vault` | Key Vault with RBAC |
| `identity` | User-assigned MI + role assignments |
| `postgresql` | Flexible Server 16 (VNet, generated password) |
| `redis` | Azure Cache for Redis (TLS) |
| `storage` | StorageV2 for ML artifacts |
| `monitoring` | Log Analytics, Application Insights, action group |
| `container_apps` | Environment, apps, migrate + ML train jobs |
| `alerts` | Metric alerts |
| `platform` | Composition of the above |

`prevent_destroy` is set on data-bearing resources. Do not remove it to force a replacement.
