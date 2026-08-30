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

data "azurerm_client_config" "current" {}

variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "vnet_cidr" {
  type = string
}

variable "container_apps_subnet_cidr" {
  type = string
}

variable "postgres_subnet_cidr" {
  type = string
}

variable "redis_subnet_cidr" {
  type = string
}

variable "private_endpoint_subnet_cidr" {
  type = string
}

variable "acr_sku" {
  type    = string
  default = "Standard"
}

variable "acr_public_network_access_enabled" {
  type    = bool
  default = true
}

variable "acr_zone_redundancy_enabled" {
  type    = bool
  default = false
}

variable "kv_purge_protection_enabled" {
  type    = bool
  default = true
}

variable "kv_public_network_access_enabled" {
  type    = bool
  default = true
}

variable "kv_network_default_action" {
  type    = string
  default = "Allow"
}

variable "kv_allowed_ip_rules" {
  type    = list(string)
  default = []
}

variable "postgres_sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "postgres_storage_mb" {
  type    = number
  default = 32768
}

variable "postgres_storage_tier" {
  type    = string
  default = "P4"
}

variable "postgres_backup_retention_days" {
  type    = number
  default = 7
}

variable "postgres_geo_redundant_backup_enabled" {
  type    = bool
  default = false
}

variable "postgres_high_availability_mode" {
  type    = string
  default = ""
}

variable "redis_sku_name" {
  type    = string
  default = "Basic"
}

variable "redis_family" {
  type    = string
  default = "C"
}

variable "redis_capacity" {
  type    = number
  default = 0
}

variable "redis_public_network_access_enabled" {
  type    = bool
  default = true
}

variable "storage_replication_type" {
  type    = string
  default = "LRS"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "image_tag" {
  type    = string
  default = "bootstrap-placeholder"
}

variable "container_apps_enabled" {
  type    = bool
  default = true
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
  type    = number
  default = 3
}

variable "web_min_replicas" {
  type    = number
  default = 0
}

variable "zone_redundancy_enabled" {
  type    = bool
  default = false
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

variable "cicd_principal_id" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "random_string" "suffix" {
  length  = 6
  lower   = true
  upper   = false
  numeric = true
  special = false
}

locals {
  suffix               = random_string.suffix.result
  acr_name             = "acrpr${var.environment}${local.suffix}"
  kv_name              = "kv-pr-${var.environment}-${local.suffix}"
  storage_name         = "stpr${var.environment}${local.suffix}"
  postgres_name        = "psql-priceradar-${var.environment}-${local.suffix}"
  redis_name           = "redis-priceradar-${var.environment}-${local.suffix}"
  operator_placeholder = "PLACEHOLDER_SET_IN_AZURE"
  secret_expiration    = "2099-12-31T23:59:59Z"
}

resource "azurerm_resource_group" "this" {
  name     = "rg-priceradar-${var.environment}"
  location = var.location
  tags     = var.tags

  lifecycle {
    prevent_destroy = true
  }
}

module "networking" {
  source                       = "../networking"
  name                         = var.environment
  location                     = var.location
  resource_group_name          = azurerm_resource_group.this.name
  vnet_cidr                    = var.vnet_cidr
  container_apps_subnet_cidr   = var.container_apps_subnet_cidr
  postgres_subnet_cidr         = var.postgres_subnet_cidr
  redis_subnet_cidr            = var.redis_subnet_cidr
  private_endpoint_subnet_cidr = var.private_endpoint_subnet_cidr
  tags                         = var.tags
}

module "acr" {
  source                        = "../acr"
  name                          = local.acr_name
  location                      = var.location
  resource_group_name           = azurerm_resource_group.this.name
  sku                           = var.acr_sku
  public_network_access_enabled = var.acr_public_network_access_enabled
  zone_redundancy_enabled       = var.acr_zone_redundancy_enabled
  tags                          = var.tags
}

module "key_vault" {
  source                        = "../key_vault"
  name                          = local.kv_name
  location                      = var.location
  resource_group_name           = azurerm_resource_group.this.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  purge_protection_enabled      = var.kv_purge_protection_enabled
  public_network_access_enabled = var.kv_public_network_access_enabled
  network_default_action        = var.kv_network_default_action
  allowed_ip_rules              = var.kv_allowed_ip_rules
  tags                          = var.tags
}

module "storage" {
  source              = "../storage"
  name                = local.storage_name
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  replication_type    = var.storage_replication_type
  tags                = var.tags
}

module "identity" {
  source              = "../identity"
  name                = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  acr_id              = module.acr.id
  key_vault_id        = module.key_vault.id
  storage_account_id  = module.storage.id
  cicd_principal_id   = var.cicd_principal_id
  tags                = var.tags
}

resource "azurerm_role_assignment" "terraform_kv_admin" {
  scope                = module.key_vault.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_private_dns_zone" "postgres" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.this.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = "pdnslink-postgres-${var.environment}"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = module.networking.vnet_id
  registration_enabled  = false
  tags                  = var.tags
}

module "postgresql" {
  source                       = "../postgresql"
  name                         = local.postgres_name
  location                     = var.location
  resource_group_name          = azurerm_resource_group.this.name
  delegated_subnet_id          = module.networking.postgres_subnet_id
  private_dns_zone_id          = azurerm_private_dns_zone.postgres.id
  sku_name                     = var.postgres_sku_name
  storage_mb                   = var.postgres_storage_mb
  storage_tier                 = var.postgres_storage_tier
  backup_retention_days        = var.postgres_backup_retention_days
  geo_redundant_backup_enabled = var.postgres_geo_redundant_backup_enabled
  high_availability_mode       = var.postgres_high_availability_mode
  tags                         = var.tags

  depends_on = [azurerm_private_dns_zone_virtual_network_link.postgres]
}

module "redis" {
  source                        = "../redis"
  name                          = local.redis_name
  location                      = var.location
  resource_group_name           = azurerm_resource_group.this.name
  sku_name                      = var.redis_sku_name
  family                        = var.redis_family
  capacity                      = var.redis_capacity
  subnet_id                     = var.redis_sku_name == "Premium" ? module.networking.redis_subnet_id : null
  public_network_access_enabled = var.redis_public_network_access_enabled
  tags                          = var.tags
}

module "monitoring" {
  source              = "../monitoring"
  name                = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  retention_days      = var.log_retention_days
  alert_email         = var.alert_email
  tags                = var.tags
}

locals {
  postgres_url = format(
    "postgresql+psycopg://%s:%s@%s:5432/%s?sslmode=require",
    module.postgresql.administrator_login,
    urlencode(module.postgresql.administrator_password),
    module.postgresql.fqdn,
    module.postgresql.database_name,
  )
  redis_base = format(
    "rediss://:%s@%s:%s",
    urlencode(module.redis.primary_access_key),
    module.redis.hostname,
    module.redis.ssl_port,
  )
}

resource "azurerm_key_vault_secret" "database_url" {
  name            = "database-url"
  value           = local.postgres_url
  key_vault_id    = module.key_vault.id
  content_type    = "text/plain"
  expiration_date = local.secret_expiration
  tags            = var.tags
  depends_on      = [azurerm_role_assignment.terraform_kv_admin]
}

resource "azurerm_key_vault_secret" "redis_url" {
  name            = "redis-url"
  value           = "${local.redis_base}/0"
  key_vault_id    = module.key_vault.id
  content_type    = "text/plain"
  expiration_date = local.secret_expiration
  tags            = var.tags
  depends_on      = [azurerm_role_assignment.terraform_kv_admin]
}

resource "azurerm_key_vault_secret" "celery_broker_url" {
  name            = "celery-broker-url"
  value           = "${local.redis_base}/1"
  key_vault_id    = module.key_vault.id
  content_type    = "text/plain"
  expiration_date = local.secret_expiration
  tags            = var.tags
  depends_on      = [azurerm_role_assignment.terraform_kv_admin]
}

resource "azurerm_key_vault_secret" "celery_result_backend" {
  name            = "celery-result-backend"
  value           = "${local.redis_base}/2"
  key_vault_id    = module.key_vault.id
  content_type    = "text/plain"
  expiration_date = local.secret_expiration
  tags            = var.tags
  depends_on      = [azurerm_role_assignment.terraform_kv_admin]
}

resource "azurerm_key_vault_secret" "appinsights" {
  name            = "applicationinsights-connection-string"
  value           = module.monitoring.application_insights_connection_string
  key_vault_id    = module.key_vault.id
  content_type    = "text/plain"
  expiration_date = local.secret_expiration
  tags            = var.tags
  depends_on      = [azurerm_role_assignment.terraform_kv_admin]
}

resource "azurerm_key_vault_secret" "operator" {
  for_each = toset([
    "clerk-secret-key",
    "amazon-credential-id",
    "amazon-credential-secret",
    "amazon-partner-tag",
    "flipkart-affiliate-id",
    "flipkart-affiliate-token",
  ])

  name            = each.value
  value           = local.operator_placeholder
  key_vault_id    = module.key_vault.id
  content_type    = "text/plain"
  expiration_date = local.secret_expiration
  tags            = var.tags
  depends_on      = [azurerm_role_assignment.terraform_kv_admin]

  lifecycle {
    ignore_changes = [value]
  }
}

module "container_apps" {
  source                                  = "../container_apps"
  name                                    = var.environment
  location                                = var.location
  resource_group_name                     = azurerm_resource_group.this.name
  infrastructure_subnet_id                = module.networking.container_apps_subnet_id
  log_analytics_workspace_id              = module.monitoring.log_analytics_workspace_id
  user_assigned_identity_id               = module.identity.app_identity_id
  acr_login_server                        = module.acr.login_server
  image_tag                               = var.image_tag
  environment                             = var.environment
  min_replicas                            = var.min_replicas
  max_replicas                            = var.max_replicas
  web_min_replicas                        = var.web_min_replicas
  database_url_secret_id                  = azurerm_key_vault_secret.database_url.versionless_id
  redis_url_secret_id                     = azurerm_key_vault_secret.redis_url.versionless_id
  celery_broker_url_secret_id             = azurerm_key_vault_secret.celery_broker_url.versionless_id
  celery_result_backend_secret_id         = azurerm_key_vault_secret.celery_result_backend.versionless_id
  clerk_secret_key_secret_id              = azurerm_key_vault_secret.operator["clerk-secret-key"].versionless_id
  appinsights_connection_string_secret_id = azurerm_key_vault_secret.appinsights.versionless_id
  amazon_credential_id_secret_id          = azurerm_key_vault_secret.operator["amazon-credential-id"].versionless_id
  amazon_credential_secret_secret_id      = azurerm_key_vault_secret.operator["amazon-credential-secret"].versionless_id
  amazon_partner_tag_secret_id            = azurerm_key_vault_secret.operator["amazon-partner-tag"].versionless_id
  flipkart_affiliate_id_secret_id         = azurerm_key_vault_secret.operator["flipkart-affiliate-id"].versionless_id
  flipkart_affiliate_token_secret_id      = azurerm_key_vault_secret.operator["flipkart-affiliate-token"].versionless_id
  cors_allowed_origins                    = var.cors_allowed_origins
  clerk_publishable_key                   = var.clerk_publishable_key
  clerk_jwks_url                          = var.clerk_jwks_url
  clerk_issuer                            = var.clerk_issuer
  clerk_audience                          = var.clerk_audience
  container_apps_enabled                  = var.container_apps_enabled
  zone_redundancy_enabled                 = var.zone_redundancy_enabled
  tags                                    = var.tags
}

module "alerts" {
  source                    = "../alerts"
  name                      = var.environment
  resource_group_name       = azurerm_resource_group.this.name
  location                  = var.location
  action_group_id           = module.monitoring.action_group_id
  application_insights_id   = module.monitoring.application_insights_id
  backend_container_app_id  = module.container_apps.backend_id
  frontend_container_app_id = module.container_apps.frontend_id
  worker_container_app_id   = module.container_apps.worker_id
  ml_container_app_id       = module.container_apps.ml_id
  postgres_id               = module.postgresql.id
  redis_id                  = module.redis.id
  tags                      = var.tags
}

module "diagnostics" {
  source                     = "../diagnostics"
  name                       = var.environment
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  postgres_id                = module.postgresql.id
  redis_id                   = module.redis.id
  key_vault_id               = module.key_vault.id
  backend_container_app_id   = module.container_apps.backend_id
  frontend_container_app_id  = module.container_apps.frontend_id
  worker_container_app_id    = module.container_apps.worker_id
  ml_container_app_id        = module.container_apps.ml_id
}

module "workbooks" {
  source                  = "../workbooks"
  name                    = var.environment
  location                = var.location
  resource_group_name     = azurerm_resource_group.this.name
  application_insights_id = module.monitoring.application_insights_id
  tags                    = var.tags
}

output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "acr_login_server" {
  value = module.acr.login_server
}

output "acr_name" {
  value = module.acr.name
}

output "key_vault_name" {
  value = module.key_vault.name
}

output "key_vault_uri" {
  value = module.key_vault.vault_uri
}

output "backend_fqdn" {
  value = module.container_apps.backend_fqdn
}

output "frontend_fqdn" {
  value = module.container_apps.frontend_fqdn
}

output "ml_fqdn" {
  value = module.container_apps.ml_fqdn
}

output "backend_app_name" {
  value = module.container_apps.backend_name
}

output "frontend_app_name" {
  value = module.container_apps.frontend_name
}

output "worker_app_name" {
  value = module.container_apps.worker_name
}

output "ml_app_name" {
  value = module.container_apps.ml_name
}

output "migrate_job_name" {
  value = module.container_apps.migrate_job_name
}

output "ml_train_job_name" {
  value = module.container_apps.ml_train_job_name
}

output "app_identity_client_id" {
  value = module.identity.app_identity_client_id
}

output "app_identity_name" {
  value = module.identity.app_identity_name
}

output "location" {
  value = var.location
}
