# Importing existing Azure resources

This repository's Terraform was an empty scaffold before Phase 15. **Do not recreate resources that already exist.** Use `terraform import` (or `import` blocks) so Terraform adopts them.

Never `terraform destroy` to "make import easier".

## Procedure

1. `terraform init` for the target environment (`dev`, `staging`, or `prod`) with that environment's `backend.hcl`.
2. `terraform plan` and note resources that would be **created** but already exist in Azure.
3. Import each one, then plan again until the only remaining changes are intentional.

Example addresses (replace names with the real Azure names):

```bash
ENV=dev
cd infrastructure/terraform/environments/${ENV}

terraform import module.platform.azurerm_resource_group.this /subscriptions/SUB/resourceGroups/rg-priceradar-dev
terraform import module.platform.module.acr.azurerm_container_registry.this /subscriptions/SUB/resourceGroups/rg-priceradar-dev/providers/Microsoft.ContainerRegistry/registries/EXISTINGACR
terraform import module.platform.module.key_vault.azurerm_key_vault.this /subscriptions/SUB/resourceGroups/rg-priceradar-dev/providers/Microsoft.KeyVault/vaults/EXISTINGKV
```

PostgreSQL, Redis, networking, and Container Apps follow the same pattern: `terraform state list` after a successful import to confirm.

## Random suffix

The platform module uses `random_string.suffix` for globally unique names. If you import an existing ACR/Key Vault/storage account, either:

- import `module.platform.random_string.suffix` is **not** possible from Azure; instead use `terraform state` / `-target` carefully, or
- set names to match the imported resources by adjusting locals in a follow-up change **without** replacing the live resource (`lifecycle.prevent_destroy` is set on data stores).

If a plan shows `must be replaced` on PostgreSQL, Key Vault, ACR, or storage, **do not apply**. Adjust configuration or import until the plan is in-place or no-op.
