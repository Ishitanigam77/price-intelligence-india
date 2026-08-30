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

variable "postgres_id" {
  type    = string
  default = ""
}

variable "redis_id" {
  type    = string
  default = ""
}

variable "location" {
  type    = string
  default = ""
}

variable "application_insights_id" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  query_alerts_enabled = var.action_group_id != "" && var.application_insights_id != "" && var.location != ""
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

resource "azurerm_monitor_metric_alert" "frontend_unhealthy" {
  count               = var.action_group_id == "" || var.frontend_container_app_id == "" ? 0 : 1
  name                = "alert-frontend-unhealthy-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.frontend_container_app_id]
  description         = "Frontend Container App has unhealthy replicas."
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

resource "azurerm_monitor_metric_alert" "worker_unhealthy" {
  count               = var.action_group_id == "" || var.worker_container_app_id == "" ? 0 : 1
  name                = "alert-worker-unhealthy-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.worker_container_app_id]
  description         = "Worker Container App has unhealthy replicas."
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

resource "azurerm_monitor_metric_alert" "ml_unhealthy" {
  count               = var.action_group_id == "" || var.ml_container_app_id == "" ? 0 : 1
  name                = "alert-ml-unhealthy-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.ml_container_app_id]
  description         = "ML Container App has unhealthy replicas."
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

resource "azurerm_monitor_metric_alert" "backend_latency" {
  count               = var.action_group_id == "" || var.backend_container_app_id == "" ? 0 : 1
  name                = "alert-backend-latency-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.backend_container_app_id]
  description         = "Backend average response time exceeded 2s for 15 minutes."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "ResponseTime"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 2000
  }

  action {
    action_group_id = var.action_group_id
  }
}

resource "azurerm_monitor_metric_alert" "postgres_connections_failed" {
  count               = var.action_group_id == "" || var.postgres_id == "" ? 0 : 1
  name                = "alert-postgres-connections-${var.name}"
  resource_group_name = var.resource_group_name
  scopes              = [var.postgres_id]
  description         = "PostgreSQL flexible server reported more than 5 failed connections in 15 minutes."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true
  tags                = var.tags

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "connections_failed"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5
  }

  action {
    action_group_id = var.action_group_id
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "api_error_rate" {
  count                = local.query_alerts_enabled ? 1 : 0
  name                 = "alert-api-error-rate-${var.name}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [var.application_insights_id]
  description          = "API error rate exceeded 5% for two consecutive 5-minute evaluations in a 15-minute window."
  severity             = 2
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  enabled              = true
  tags                 = var.tags

  criteria {
    query                   = <<-QUERY
      requests
      | where timestamp > ago(15m)
      | summarize total = count(), failed = countif(success == false)
      | extend error_rate = iff(total == 0, 0.0, failed * 100.0 / total)
      | project error_rate
    QUERY
    time_aggregation_method = "Maximum"
    threshold               = 5
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [var.action_group_id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "collection_failures" {
  count                = local.query_alerts_enabled ? 1 : 0
  name                 = "alert-collection-failures-${var.name}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [var.application_insights_id]
  description          = "Retailer collection reported more than 5 failed jobs in 30 minutes."
  severity             = 2
  evaluation_frequency = "PT5M"
  window_duration      = "PT30M"
  enabled              = true
  tags                 = var.tags

  criteria {
    query                   = <<-QUERY
      customMetrics
      | where name == "jobs_failed"
      | summarize failures = sum(value)
      | project failures
    QUERY
    time_aggregation_method = "Total"
    threshold               = 5
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [var.action_group_id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "stale_retailer_data" {
  count                = local.query_alerts_enabled ? 1 : 0
  name                 = "alert-stale-retailer-data-${var.name}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [var.application_insights_id]
  description          = "Price freshness for a retailer exceeded 24 hours (86400 seconds)."
  severity             = 3
  evaluation_frequency = "PT15M"
  window_duration      = "PT30M"
  enabled              = true
  tags                 = var.tags

  criteria {
    query                   = <<-QUERY
      customMetrics
      | where name == "price_freshness"
      | summarize freshness = max(value)
      | project freshness
    QUERY
    time_aggregation_method = "Maximum"
    threshold               = 86400
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [var.action_group_id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "worker_task_failures" {
  count                = local.query_alerts_enabled ? 1 : 0
  name                 = "alert-worker-task-failures-${var.name}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [var.application_insights_id]
  description          = "Worker task failures exceeded 5 in 15 minutes."
  severity             = 2
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  enabled              = true
  tags                 = var.tags

  criteria {
    query                   = <<-QUERY
      customMetrics
      | where name == "worker.task.failures"
      | summarize failures = sum(value)
      | project failures
    QUERY
    time_aggregation_method = "Total"
    threshold               = 5
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [var.action_group_id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "queue_depth" {
  count                = local.query_alerts_enabled ? 1 : 0
  name                 = "alert-worker-queue-depth-${var.name}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [var.application_insights_id]
  description          = "Celery queue depth exceeded 100 for 15 minutes."
  severity             = 3
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  enabled              = true
  tags                 = var.tags

  criteria {
    query                   = <<-QUERY
      customMetrics
      | where name == "worker.queue.depth"
      | summarize depth = max(value)
      | project depth
    QUERY
    time_aggregation_method = "Maximum"
    threshold               = 100
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [var.action_group_id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "ml_prediction_failures" {
  count                = local.query_alerts_enabled ? 1 : 0
  name                 = "alert-ml-prediction-failures-${var.name}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [var.application_insights_id]
  description          = "ML prediction failures exceeded 5 or p95 latency exceeded 5s in 15 minutes."
  severity             = 2
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  enabled              = true
  tags                 = var.tags

  criteria {
    query                   = <<-QUERY
      customMetrics
      | where name in ("ml.prediction.failures", "ml.prediction.duration_ms")
      | summarize failures = sumif(value, name == "ml.prediction.failures"), p95 = percentileif(value, 95, name == "ml.prediction.duration_ms")
      | extend signal = iff(failures > 5 or p95 > 5000, 1.0, 0.0)
      | project signal
    QUERY
    time_aggregation_method = "Maximum"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 2
      number_of_evaluation_periods             = 3
    }
  }

  action {
    action_groups = [var.action_group_id]
  }
}
