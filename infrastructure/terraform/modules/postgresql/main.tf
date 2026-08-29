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

variable "name" {
  type        = string
  description = "PostgreSQL flexible server name (globally unique, lowercase)."
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "delegated_subnet_id" {
  type = string
}

variable "private_dns_zone_id" {
  type = string
}

variable "administrator_login" {
  type    = string
  default = "priceradar_admin"
}

variable "database_name" {
  type    = string
  default = "priceradar"
}

variable "sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "storage_mb" {
  type    = number
  default = 32768
}

variable "storage_tier" {
  type    = string
  default = "P4"
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "geo_redundant_backup_enabled" {
  type    = bool
  default = false
}

variable "high_availability_mode" {
  type        = string
  default     = ""
  description = "Empty disables HA. Use ZoneRedundant only with a General Purpose or Memory Optimized SKU."
}

variable "postgres_version" {
  type    = string
  default = "16"
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "random_password" "administrator" {
  length           = 32
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "_%@"
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  version                       = var.postgres_version
  delegated_subnet_id           = var.delegated_subnet_id
  private_dns_zone_id           = var.private_dns_zone_id
  public_network_access_enabled = false
  administrator_login           = var.administrator_login
  administrator_password        = random_password.administrator.result
  sku_name                      = var.sku_name
  storage_mb                    = var.storage_mb
  storage_tier                  = var.storage_tier
  backup_retention_days         = var.backup_retention_days
  geo_redundant_backup_enabled  = var.geo_redundant_backup_enabled
  auto_grow_enabled             = true
  tags                          = var.tags

  dynamic "high_availability" {
    for_each = var.high_availability_mode == "" ? [] : [var.high_availability_mode]
    content {
      mode = high_availability.value
    }
  }

  authentication {
    password_auth_enabled         = true
    active_directory_auth_enabled = false
  }

  maintenance_window {
    day_of_week  = 0
    start_hour   = 3
    start_minute = 0
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [zone]
  }
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "require_tls" {
  name      = "require_secure_transport"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "on"
}

output "id" {
  value = azurerm_postgresql_flexible_server.this.id
}

output "fqdn" {
  value = azurerm_postgresql_flexible_server.this.fqdn
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.app.name
}

output "administrator_login" {
  value = var.administrator_login
}

output "administrator_password" {
  value     = random_password.administrator.result
  sensitive = true
}
