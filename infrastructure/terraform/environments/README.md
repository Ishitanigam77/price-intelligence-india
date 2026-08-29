# terraform/environments/

Root modules for **dev**, **staging**, and **prod**. They only pass environment-specific SKUs, CIDRs, and replica counts into `modules/platform`.

- Copy `terraform.tfvars.example` → `terraform.tfvars` (gitignored) for local applies. Placeholders only.
- Copy `backend.hcl.example` → `backend.hcl` after the bootstrap stack exists.
- Validate without Azure: `terraform init -backend=false && terraform validate`
- Production apply is performed only from Azure DevOps after the `production` Environment approval.

No `.tfvars` with real secrets are committed.
