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
  description = "Key Vault name. Globally unique, 3-24 characters."
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "purge_protection_enabled" {
  type    = bool
  default = true
}

variable "soft_delete_retention_days" {
  type    = number
  default = 90
}

variable "public_network_access_enabled" {
  type    = bool
  default = true
}

variable "network_default_action" {
  type    = string
  default = "Allow"
}

variable "allowed_ip_rules" {
  type        = list(string)
  default     = []
  description = "Optional CIDRs allowed to reach Key Vault data plane. Empty with Allow is a documented bootstrap exception."
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_key_vault" "this" {
  name                            = var.name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  tenant_id                       = var.tenant_id
  sku_name                        = "standard"
  rbac_authorization_enabled      = true
  purge_protection_enabled        = var.purge_protection_enabled
  soft_delete_retention_days      = var.soft_delete_retention_days
  public_network_access_enabled   = var.public_network_access_enabled
  enabled_for_deployment          = false
  enabled_for_disk_encryption     = false
  enabled_for_template_deployment = false
  tags                            = var.tags

  network_acls {
    default_action = var.network_default_action
    bypass         = "AzureServices"
    ip_rules       = var.allowed_ip_rules
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "id" {
  value = azurerm_key_vault.this.id
}

output "vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}

output "name" {
  value = azurerm_key_vault.this.name
}
