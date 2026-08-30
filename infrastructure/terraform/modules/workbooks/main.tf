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

variable "application_insights_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  api_workbook = jsonencode({
    version = "Notebook/1.0"
    items = [
      { type = 1, content = { json = "# Application / API health\nLatency, error rate, request volume, and service health for the PriceRadar backend API." } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Request volume", query = "requests\n| where cloud_RoleName in ('backend','priceradar-backend') or isempty(cloud_RoleName)\n| summarize requests=count() by bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Error rate (%)", query = "requests\n| summarize total=count(), failed=countif(success == false) by bin(timestamp, 5m)\n| extend error_rate = iff(total == 0, 0.0, failed * 100.0 / total)\n| project timestamp, error_rate\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Request latency (ms)", query = "requests\n| summarize p50=percentile(duration, 50), p95=percentile(duration, 95) by bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Custom API metrics", query = "customMetrics\n| where name in ('api.requests','api.errors','api.request.duration_ms','api.dependency.failures')\n| summarize value=sum(value) by name, bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } }
    ]
    isLocked = false
    fallbackResourceIds = [var.application_insights_id]
  })

  collection_workbook = jsonencode({
    version = "Notebook/1.0"
    items = [
      { type = 1, content = { json = "# Retailer collection health\nCollection success/failure, duration, adapter errors, and price freshness. Dimensions are retailer_id and job_type only." } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Collection job volume", query = "customMetrics\n| where name in ('jobs_total','jobs_successful','jobs_failed')\n| summarize value=sum(value) by name, bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Adapter failures", query = "customMetrics\n| where name in ('retailer_adapter.failures','retailer_adapter.timeouts')\n| summarize value=sum(value) by name, tostring(customDimensions.retailer_id), bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Price freshness (seconds)", query = "customMetrics\n| where name == 'price_freshness'\n| summarize freshness=max(value) by tostring(customDimensions.retailer_id), bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Collection job duration (ms)", query = "customMetrics\n| where name == 'job_duration'\n| summarize p95=percentile(value, 95) by bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } }
    ]
    isLocked = false
    fallbackResourceIds = [var.application_insights_id]
  })

  worker_workbook = jsonencode({
    version = "Notebook/1.0"
    items = [
      { type = 1, content = { json = "# Worker health\nTask volume, failures, retries, duration, and queue depth." } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Worker tasks", query = "customMetrics\n| where name in ('worker.tasks','worker.task.failures','worker.task.retries')\n| summarize value=sum(value) by name, bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Queue depth", query = "customMetrics\n| where name == 'worker.queue.depth'\n| summarize depth=max(value) by bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Task duration (ms)", query = "customMetrics\n| where name == 'worker.task.duration_ms'\n| summarize p95=percentile(value, 95) by bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } }
    ]
    isLocked = false
    fallbackResourceIds = [var.application_insights_id]
  })

  database_workbook = jsonencode({
    version = "Notebook/1.0"
    items = [
      { type = 1, content = { json = "# Database health\nQuery latency, connection failures, and dependency failures. SQL text and credentials are never logged." } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Query latency (ms)", query = "customMetrics\n| where name == 'db.query.duration_ms'\n| summarize p95=percentile(value, 95) by bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Connection / dependency failures", query = "customMetrics\n| where name in ('db.connection.failures','db.dependency.failures')\n| summarize value=sum(value) by name, bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Connection health gauge", query = "customMetrics\n| where name == 'db.connection.health'\n| summarize health=min(value) by bin(timestamp, 5m)\n| render timechart", size = 0, timeContext = { durationMs = 14400000 }, queryType = 0, resourceType = "microsoft.insights/components" } }
    ]
    isLocked = false
    fallbackResourceIds = [var.application_insights_id]
  })

  ml_workbook = jsonencode({
    version = "Notebook/1.0"
    items = [
      { type = 1, content = { json = "# ML health\nPrediction volume, latency, failures, and model version. Predictions remain labelled as predictions." } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Prediction volume", query = "customMetrics\n| where name == 'ml.predictions'\n| summarize value=sum(value) by tostring(customDimensions.status), bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Prediction latency (ms)", query = "customMetrics\n| where name == 'ml.prediction.duration_ms'\n| summarize p95=percentile(value, 95) by bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } },
      { type = 3, content = { version = "KqlItem/1.0", title = "Prediction failures", query = "customMetrics\n| where name == 'ml.prediction.failures'\n| summarize value=sum(value) by bin(timestamp, 15m)\n| render timechart", size = 0, timeContext = { durationMs = 86400000 }, queryType = 0, resourceType = "microsoft.insights/components" } }
    ]
    isLocked = false
    fallbackResourceIds = [var.application_insights_id]
  })
}

resource "azurerm_application_insights_workbook" "api" {
  name                = uuidv5("dns", "priceradar-workbook-api-${var.name}.priceradar")
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = "PriceRadar API health (${var.name})"
  source_id           = var.application_insights_id
  category            = "workbook"
  data_json           = local.api_workbook
  tags                = var.tags
}

resource "azurerm_application_insights_workbook" "collection" {
  name                = uuidv5("dns", "priceradar-workbook-collection-${var.name}.priceradar")
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = "PriceRadar retailer collection health (${var.name})"
  source_id           = var.application_insights_id
  category            = "workbook"
  data_json           = local.collection_workbook
  tags                = var.tags
}

resource "azurerm_application_insights_workbook" "worker" {
  name                = uuidv5("dns", "priceradar-workbook-worker-${var.name}.priceradar")
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = "PriceRadar worker health (${var.name})"
  source_id           = var.application_insights_id
  category            = "workbook"
  data_json           = local.worker_workbook
  tags                = var.tags
}

resource "azurerm_application_insights_workbook" "database" {
  name                = uuidv5("dns", "priceradar-workbook-database-${var.name}.priceradar")
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = "PriceRadar database health (${var.name})"
  source_id           = var.application_insights_id
  category            = "workbook"
  data_json           = local.database_workbook
  tags                = var.tags
}

resource "azurerm_application_insights_workbook" "ml" {
  name                = uuidv5("dns", "priceradar-workbook-ml-${var.name}.priceradar")
  resource_group_name = var.resource_group_name
  location            = var.location
  display_name        = "PriceRadar ML health (${var.name})"
  source_id           = var.application_insights_id
  category            = "workbook"
  data_json           = local.ml_workbook
  tags                = var.tags
}

output "workbook_ids" {
  value = {
    api        = azurerm_application_insights_workbook.api.id
    collection = azurerm_application_insights_workbook.collection.id
    worker     = azurerm_application_insights_workbook.worker.id
    database   = azurerm_application_insights_workbook.database.id
    ml         = azurerm_application_insights_workbook.ml.id
  }
}
