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

variable "acr_id" {
  type = string
}

variable "key_vault_id" {
  type = string
}

variable "storage_account_id" {
  type    = string
  default = ""
}

variable "cicd_principal_id" {
  type        = string
  default     = ""
  description = "Optional Entra object id of the Azure DevOps service connection. Empty skips CI role assignments."
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-app-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_role_assignment" "app_acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_kv_secrets_user" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_storage_blob" {
  count                = var.storage_account_id == "" ? 0 : 1
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "cicd_acr_push" {
  count                = var.cicd_principal_id == "" ? 0 : 1
  scope                = var.acr_id
  role_definition_name = "AcrPush"
  principal_id         = var.cicd_principal_id
}

resource "azurerm_role_assignment" "cicd_kv_secrets_officer" {
  count                = var.cicd_principal_id == "" ? 0 : 1
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.cicd_principal_id
}

output "app_identity_id" {
  value = azurerm_user_assigned_identity.app.id
}

output "app_identity_client_id" {
  value = azurerm_user_assigned_identity.app.client_id
}

output "app_identity_principal_id" {
  value = azurerm_user_assigned_identity.app.principal_id
}

output "app_identity_name" {
  value = azurerm_user_assigned_identity.app.name
}
