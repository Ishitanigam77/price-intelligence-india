# bootstrap/

One-time Terraform stack that creates the **remote state** storage account. It uses **local** Terraform state on purpose (chicken-and-egg).

```bash
cd infrastructure/terraform/bootstrap
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Copy `storage_account_name` into each environment `backend.hcl`. Never commit `backend.hcl`. Never destroy this stack from a pipeline.
