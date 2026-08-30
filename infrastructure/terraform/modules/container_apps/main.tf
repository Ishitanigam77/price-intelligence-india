terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0.0, < 5.0.0"
    }
  }
}

variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "infrastructure_subnet_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "user_assigned_identity_id" {
  type = string
}

variable "acr_login_server" {
  type = string
}

variable "image_tag" {
  type        = string
  description = "Immutable image tag produced by CI (never only 'latest' in production)."
}

variable "placeholder_image" {
  type        = string
  default     = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
  description = "Public image used only when image_tag is the bootstrap placeholder."
}

variable "environment" {
  type = string
}

variable "min_replicas" {
  type = number
}

variable "max_replicas" {
  type = number
}

variable "web_min_replicas" {
  type        = number
  default     = 0
  description = "When > 0, overrides min_replicas for frontend and backend (e.g. prod HA)."
}

variable "database_url_secret_id" {
  type = string
}

variable "redis_url_secret_id" {
  type = string
}

variable "celery_broker_url_secret_id" {
  type = string
}

variable "celery_result_backend_secret_id" {
  type = string
}

variable "clerk_secret_key_secret_id" {
  type = string
}

variable "appinsights_connection_string_secret_id" {
  type = string
}

variable "amazon_credential_id_secret_id" {
  type = string
}

variable "amazon_credential_secret_secret_id" {
  type = string
}

variable "amazon_partner_tag_secret_id" {
  type = string
}

variable "flipkart_affiliate_id_secret_id" {
  type = string
}

variable "flipkart_affiliate_token_secret_id" {
  type = string
}

variable "cors_allowed_origins" {
  type = string
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

variable "ml_model_artifact_path" {
  type    = string
  default = "/mnt/ml-artifacts"
}

variable "container_apps_enabled" {
  type    = bool
  default = true
}

variable "zone_redundancy_enabled" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  use_placeholder = var.image_tag == "bootstrap-placeholder"
  backend_image   = local.use_placeholder ? var.placeholder_image : "${var.acr_login_server}/priceradar/backend:${var.image_tag}"
  frontend_image  = local.use_placeholder ? var.placeholder_image : "${var.acr_login_server}/priceradar/frontend:${var.image_tag}"
  worker_image    = local.use_placeholder ? var.placeholder_image : "${var.acr_login_server}/priceradar/workers:${var.image_tag}"
  ml_image        = local.use_placeholder ? var.placeholder_image : "${var.acr_login_server}/priceradar/ml:${var.image_tag}"
  web_min         = var.web_min_replicas > 0 ? var.web_min_replicas : var.min_replicas

  kv_secrets = {
    database-url                  = var.database_url_secret_id
    redis-url                     = var.redis_url_secret_id
    celery-broker-url             = var.celery_broker_url_secret_id
    celery-result-backend         = var.celery_result_backend_secret_id
    clerk-secret-key              = var.clerk_secret_key_secret_id
    appinsights-connection-string = var.appinsights_connection_string_secret_id
    amazon-credential-id          = var.amazon_credential_id_secret_id
    amazon-credential-secret      = var.amazon_credential_secret_secret_id
    amazon-partner-tag            = var.amazon_partner_tag_secret_id
    flipkart-affiliate-id         = var.flipkart_affiliate_id_secret_id
    flipkart-affiliate-token      = var.flipkart_affiliate_token_secret_id
  }
}

resource "azurerm_container_app_environment" "this" {
  name                           = "cae-priceradar-${var.name}"
  location                       = var.location
  resource_group_name            = var.resource_group_name
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  infrastructure_subnet_id       = var.infrastructure_subnet_id
  internal_load_balancer_enabled = false
  zone_redundancy_enabled        = var.zone_redundancy_enabled
  tags                           = var.tags
}

resource "azurerm_container_app" "backend" {
  count                        = var.container_apps_enabled ? 1 : 0
  name                         = "ca-backend-priceradar-${var.name}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.user_assigned_identity_id
  }

  dynamic "secret" {
    for_each = local.kv_secrets
    content {
      name                = secret.key
      key_vault_secret_id = secret.value
      identity            = var.user_assigned_identity_id
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = local.web_min
    max_replicas = var.max_replicas

    container {
      name   = "backend"
      image  = local.backend_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "SERVICE_NAME"
        value = "backend"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "LOG_FORMAT"
        value = "json"
      }
      env {
        name  = "RUN_DB_MIGRATIONS"
        value = "false"
      }
      env {
        name  = "CORS_ALLOWED_ORIGINS"
        value = var.cors_allowed_origins
      }
      env {
        name  = "CLERK_PUBLISHABLE_KEY"
        value = var.clerk_publishable_key
      }
      env {
        name  = "CLERK_JWKS_URL"
        value = var.clerk_jwks_url
      }
      env {
        name  = "CLERK_ISSUER"
        value = var.clerk_issuer
      }
      env {
        name  = "CLERK_AUDIENCE"
        value = var.clerk_audience
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "celery-broker-url"
      }
      env {
        name        = "CELERY_RESULT_BACKEND"
        secret_name = "celery-result-backend"
      }
      env {
        name        = "CLERK_SECRET_KEY"
        secret_name = "clerk-secret-key"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }
      env {
        name        = "RETAILER_AMAZON_IN_CREDENTIAL_ID"
        secret_name = "amazon-credential-id"
      }
      env {
        name        = "RETAILER_AMAZON_IN_CREDENTIAL_SECRET"
        secret_name = "amazon-credential-secret"
      }
      env {
        name        = "RETAILER_AMAZON_IN_PARTNER_TAG"
        secret_name = "amazon-partner-tag"
      }
      env {
        name        = "RETAILER_FLIPKART_AFFILIATE_ID"
        secret_name = "flipkart-affiliate-id"
      }
      env {
        name        = "RETAILER_FLIPKART_AFFILIATE_TOKEN"
        secret_name = "flipkart-affiliate-token"
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/health"
        port             = 8000
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/api/v1/health/ready"
        port             = 8000
        interval_seconds = 15
      }
    }
  }
}

resource "azurerm_container_app" "frontend" {
  count                        = var.container_apps_enabled ? 1 : 0
  name                         = "ca-frontend-priceradar-${var.name}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.user_assigned_identity_id
  }

  secret {
    name                = "clerk-secret-key"
    key_vault_secret_id = var.clerk_secret_key_secret_id
    identity            = var.user_assigned_identity_id
  }

  secret {
    name                = "appinsights-connection-string"
    key_vault_secret_id = var.appinsights_connection_string_secret_id
    identity            = var.user_assigned_identity_id
  }

  ingress {
    external_enabled = true
    target_port      = 3000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = local.web_min
    max_replicas = var.max_replicas

    container {
      name   = "frontend"
      image  = local.frontend_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "CLERK_SECRET_KEY"
        secret_name = "clerk-secret-key"
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "SERVICE_NAME"
        value = "frontend"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/health"
        port             = 3000
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/health"
        port             = 3000
        interval_seconds = 15
      }
    }
  }
}

resource "azurerm_container_app" "worker" {
  count                        = var.container_apps_enabled ? 1 : 0
  name                         = "ca-worker-priceradar-${var.name}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.user_assigned_identity_id
  }

  dynamic "secret" {
    for_each = local.kv_secrets
    content {
      name                = secret.key
      key_vault_secret_id = secret.value
      identity            = var.user_assigned_identity_id
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "worker"
      image  = local.worker_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "SERVICE_NAME"
        value = "worker"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "LOG_FORMAT"
        value = "json"
      }
      env {
        name  = "RUN_DB_MIGRATIONS"
        value = "false"
      }
      env {
        name  = "WORKER_HEALTH_HTTP"
        value = "true"
      }
      env {
        name  = "WORKER_HEALTH_PORT"
        value = "8081"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "celery-broker-url"
      }
      env {
        name        = "CELERY_RESULT_BACKEND"
        secret_name = "celery-result-backend"
      }
      env {
        name        = "RETAILER_AMAZON_IN_CREDENTIAL_ID"
        secret_name = "amazon-credential-id"
      }
      env {
        name        = "RETAILER_AMAZON_IN_CREDENTIAL_SECRET"
        secret_name = "amazon-credential-secret"
      }
      env {
        name        = "RETAILER_AMAZON_IN_PARTNER_TAG"
        secret_name = "amazon-partner-tag"
      }
      env {
        name        = "RETAILER_FLIPKART_AFFILIATE_ID"
        secret_name = "flipkart-affiliate-id"
      }
      env {
        name        = "RETAILER_FLIPKART_AFFILIATE_TOKEN"
        secret_name = "flipkart-affiliate-token"
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/health"
        port             = 8081
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/health/ready"
        port             = 8081
        interval_seconds = 15
      }
    }
  }
}

resource "azurerm_container_app" "ml" {
  count                        = var.container_apps_enabled ? 1 : 0
  name                         = "ca-ml-priceradar-${var.name}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.user_assigned_identity_id
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = var.database_url_secret_id
    identity            = var.user_assigned_identity_id
  }

  secret {
    name                = "appinsights-connection-string"
    key_vault_secret_id = var.appinsights_connection_string_secret_id
    identity            = var.user_assigned_identity_id
  }

  ingress {
    external_enabled = false
    target_port      = 8080
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = 1

    container {
      name   = "ml"
      image  = local.ml_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "SERVICE_NAME"
        value = "ml"
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }
      env {
        name  = "ML_HEALTH_PORT"
        value = "8080"
      }
      env {
        name  = "ML_MODEL_ARTIFACT_PATH"
        value = var.ml_model_artifact_path
      }
      env {
        name  = "RUN_DB_MIGRATIONS"
        value = "false"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/health"
        port             = 8080
        interval_seconds = 30
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/health/ready"
        port             = 8080
        interval_seconds = 15
      }
    }
  }
}

resource "azurerm_container_app_job" "migrate" {
  count                        = var.container_apps_enabled ? 1 : 0
  name                         = "job-migrate-priceradar-${var.name}"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  replica_timeout_in_seconds   = 600
  replica_retry_limit          = 1
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.user_assigned_identity_id
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = var.database_url_secret_id
    identity            = var.user_assigned_identity_id
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "migrate"
      image   = local.backend_image
      cpu     = 0.25
      memory  = "0.5Gi"
      command = ["alembic", "upgrade", "head"]

      env {
        name  = "RUN_DB_MIGRATIONS"
        value = "false"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
    }
  }
}

resource "azurerm_container_app_job" "ml_train" {
  count                        = var.container_apps_enabled ? 1 : 0
  name                         = "job-ml-train-priceradar-${var.name}"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  replica_timeout_in_seconds   = 3600
  replica_retry_limit          = 1
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.user_assigned_identity_id]
  }

  registry {
    server   = var.acr_login_server
    identity = var.user_assigned_identity_id
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = var.database_url_secret_id
    identity            = var.user_assigned_identity_id
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "ml-train"
      image   = local.ml_image
      cpu     = 1.0
      memory  = "2Gi"
      command = ["python", "-m", "scripts.train_sale_price_model"]

      env {
        name  = "RUN_DB_MIGRATIONS"
        value = "false"
      }
      env {
        name  = "ML_MODEL_ARTIFACT_PATH"
        value = var.ml_model_artifact_path
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
    }
  }
}

output "environment_id" {
  value = azurerm_container_app_environment.this.id
}

output "backend_fqdn" {
  value = try(azurerm_container_app.backend[0].ingress[0].fqdn, "")
}

output "frontend_fqdn" {
  value = try(azurerm_container_app.frontend[0].ingress[0].fqdn, "")
}

output "ml_fqdn" {
  value = try(azurerm_container_app.ml[0].ingress[0].fqdn, "")
}

output "backend_id" {
  value = try(azurerm_container_app.backend[0].id, "")
}

output "frontend_id" {
  value = try(azurerm_container_app.frontend[0].id, "")
}

output "worker_id" {
  value = try(azurerm_container_app.worker[0].id, "")
}

output "ml_id" {
  value = try(azurerm_container_app.ml[0].id, "")
}

output "migrate_job_name" {
  value = try(azurerm_container_app_job.migrate[0].name, "")
}

output "ml_train_job_name" {
  value = try(azurerm_container_app_job.ml_train[0].name, "")
}

output "backend_name" {
  value = try(azurerm_container_app.backend[0].name, "")
}

output "frontend_name" {
  value = try(azurerm_container_app.frontend[0].name, "")
}

output "worker_name" {
  value = try(azurerm_container_app.worker[0].name, "")
}

output "ml_name" {
  value = try(azurerm_container_app.ml[0].name, "")
}
