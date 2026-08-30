terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0.0, < 5.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0, < 4.0.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

variable "location" {
  type    = string
  default = "centralindia"
}

variable "image_tag" {
  type    = string
  default = "bootstrap-placeholder"
}

variable "container_apps_enabled" {
  type    = bool
  default = true
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "cicd_principal_id" {
  type    = string
  default = ""
}

variable "cors_allowed_origins" {
  type    = string
  default = ""
}

variable "clerk_publishable_key" {
  type    = string
  default = ""
}

variable "clerk_jwks_url" {
  type    = string
  default = ""
}

variable "clerk_issuer" {
  type    = string
  default = ""
}

variable "clerk_audience" {
  type    = string
  default = ""
}

variable "kv_allowed_ip_rules" {
  type    = list(string)
  default = []
}

locals {
  environment = "prod"
  tags = {
    project     = "priceradar-india"
    environment = local.environment
    managed_by  = "terraform"
    phase       = "15"
  }
}

module "platform" {
  source = "../../modules/platform"

  environment                           = local.environment
  location                              = var.location
  vnet_cidr                             = "10.30.0.0/16"
  container_apps_subnet_cidr            = "10.30.0.0/23"
  postgres_subnet_cidr                  = "10.30.2.0/24"
  redis_subnet_cidr                     = "10.30.3.0/24"
  private_endpoint_subnet_cidr          = "10.30.4.0/24"
  acr_sku                               = "Premium"
  acr_public_network_access_enabled     = true
  acr_zone_redundancy_enabled           = true
  kv_purge_protection_enabled           = true
  kv_allowed_ip_rules                   = var.kv_allowed_ip_rules
  postgres_sku_name                     = "GP_Standard_D2s_v3"
  postgres_storage_mb                   = 131072
  postgres_storage_tier                 = "P10"
  postgres_backup_retention_days        = 35
  postgres_geo_redundant_backup_enabled = true
  postgres_high_availability_mode       = "ZoneRedundant"
  redis_sku_name                        = "Premium"
  redis_family                          = "P"
  redis_capacity                        = 1
  redis_public_network_access_enabled   = false
  storage_replication_type              = "GRS"
  log_retention_days                    = 90
  alert_email                           = var.alert_email
  image_tag                             = var.image_tag
  container_apps_enabled                = var.container_apps_enabled
  min_replicas                          = 1
  max_replicas                          = 10
  web_min_replicas                      = 2
  zone_redundancy_enabled               = false
  cors_allowed_origins                  = var.cors_allowed_origins
  clerk_publishable_key                 = var.clerk_publishable_key
  clerk_jwks_url                        = var.clerk_jwks_url
  clerk_issuer                          = var.clerk_issuer
  clerk_audience                        = var.clerk_audience
  cicd_principal_id                     = var.cicd_principal_id
  tags                                  = local.tags
}

output "resource_group_name" { value = module.platform.resource_group_name }
output "acr_login_server" { value = module.platform.acr_login_server }
output "acr_name" { value = module.platform.acr_name }
output "key_vault_name" { value = module.platform.key_vault_name }
output "key_vault_uri" { value = module.platform.key_vault_uri }
output "backend_fqdn" { value = module.platform.backend_fqdn }
output "frontend_fqdn" { value = module.platform.frontend_fqdn }
output "ml_fqdn" { value = module.platform.ml_fqdn }
output "backend_app_name" { value = module.platform.backend_app_name }
output "frontend_app_name" { value = module.platform.frontend_app_name }
output "worker_app_name" { value = module.platform.worker_app_name }
output "ml_app_name" { value = module.platform.ml_app_name }
output "migrate_job_name" { value = module.platform.migrate_job_name }
output "ml_train_job_name" { value = module.platform.ml_train_job_name }
output "app_identity_client_id" { value = module.platform.app_identity_client_id }
output "location" { value = module.platform.location }
