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
  type        = string
  description = "Redis cache name (globally unique)."
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "sku_name" {
  type    = string
  default = "Basic"
}

variable "family" {
  type    = string
  default = "C"
}

variable "capacity" {
  type    = number
  default = 0
}

variable "subnet_id" {
  type        = string
  default     = null
  description = "Required for Premium VNet injection. Leave null for Basic/Standard."
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_redis_cache" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku_name                      = var.sku_name
  family                        = var.family
  capacity                      = var.capacity
  minimum_tls_version           = "1.2"
  non_ssl_port_enabled          = false
  public_network_access_enabled = var.public_network_access_enabled
  redis_version                 = "6"
  subnet_id                     = var.sku_name == "Premium" ? var.subnet_id : null
  tags                          = var.tags

  redis_configuration {
    authentication_enabled                  = true
    active_directory_authentication_enabled = false
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "id" {
  value = azurerm_redis_cache.this.id
}

output "hostname" {
  value = azurerm_redis_cache.this.hostname
}

output "ssl_port" {
  value = azurerm_redis_cache.this.ssl_port
}

output "primary_access_key" {
  value     = azurerm_redis_cache.this.primary_access_key
  sensitive = true
}
