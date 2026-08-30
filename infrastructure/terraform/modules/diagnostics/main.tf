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

variable "log_analytics_workspace_id" {
  type = string
}

variable "postgres_id" {
  type    = string
  default = ""
}

variable "redis_id" {
  type    = string
  default = ""
}

variable "key_vault_id" {
  type    = string
  default = ""
}

variable "backend_container_app_id" {
  type    = string
  default = ""
}

variable "frontend_container_app_id" {
  type    = string
  default = ""
}

variable "worker_container_app_id" {
  type    = string
  default = ""
}

variable "ml_container_app_id" {
  type    = string
  default = ""
}

resource "azurerm_monitor_diagnostic_setting" "postgres" {
  count                      = var.postgres_id == "" ? 0 : 1
  name                       = "diag-postgres-${var.name}"
  target_resource_id         = var.postgres_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "PostgreSQLLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "redis" {
  count                      = var.redis_id == "" ? 0 : 1
  name                       = "diag-redis-${var.name}"
  target_resource_id         = var.redis_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ConnectedClientList"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "key_vault" {
  count                      = var.key_vault_id == "" ? 0 : 1
  name                       = "diag-kv-${var.name}"
  target_resource_id         = var.key_vault_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "AuditEvent"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "backend" {
  count                      = var.backend_container_app_id == "" ? 0 : 1
  name                       = "diag-backend-${var.name}"
  target_resource_id         = var.backend_container_app_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "frontend" {
  count                      = var.frontend_container_app_id == "" ? 0 : 1
  name                       = "diag-frontend-${var.name}"
  target_resource_id         = var.frontend_container_app_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "worker" {
  count                      = var.worker_container_app_id == "" ? 0 : 1
  name                       = "diag-worker-${var.name}"
  target_resource_id         = var.worker_container_app_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "ml" {
  count                      = var.ml_container_app_id == "" ? 0 : 1
  name                       = "diag-ml-${var.name}"
  target_resource_id         = var.ml_container_app_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }

  enabled_log {
    category = "ContainerAppSystemLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
