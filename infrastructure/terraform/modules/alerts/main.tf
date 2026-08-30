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

variable "resource_group_name" {
  type = string
}

variable "action_group_id" {
  type    = string
  default = ""
}

variable "backend_container_app_id" {
  type    = string
  default = ""
}

variable "postgres_id" {
  type    = string
  default = ""
}

variable "redis_id" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_monitor_metric_alert" "backend_unhealthy" {
  count               = var.action_group_id == "" || var.backend_container_app_id == "" ? 0 : 1
  name                = "alert-backend-unhealthy-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.backend_container_app_id]
  description         = "Backend Container App has unhealthy replicas."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "ReplicasUnhealthy"
    aggregation      = "Maximum"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = var.action_group_id
  }
}

resource "azurerm_monitor_metric_alert" "postgres_storage" {
  count               = var.action_group_id == "" || var.postgres_id == "" ? 0 : 1
  name                = "alert-postgres-storage-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.postgres_id]
  description         = "PostgreSQL flexible server storage percent is high."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "storage_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = var.action_group_id
  }
}

resource "azurerm_monitor_metric_alert" "redis_load" {
  count               = var.action_group_id == "" || var.redis_id == "" ? 0 : 1
  name                = "alert-redis-load-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.redis_id]
  description         = "Redis server load is high."
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.Cache/redis"
    metric_name      = "serverLoad"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = var.action_group_id
  }
}
