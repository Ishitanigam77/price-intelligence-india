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
  description = "ACR name. Must be globally unique, alphanumeric, 5-50 characters."
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "sku" {
  type    = string
  default = "Standard"
}

variable "public_network_access_enabled" {
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

resource "azurerm_container_registry" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku                           = var.sku
  admin_enabled                 = false
  public_network_access_enabled = var.public_network_access_enabled
  zone_redundancy_enabled       = var.sku == "Premium" ? var.zone_redundancy_enabled : false
  anonymous_pull_enabled        = false
  retention_policy_in_days      = var.sku == "Premium" ? 7 : null
  data_endpoint_enabled         = var.sku == "Premium"
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "id" {
  value = azurerm_container_registry.this.id
}

output "login_server" {
  value = azurerm_container_registry.this.login_server
}

output "name" {
  value = azurerm_container_registry.this.name
}
