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

# Local state on purpose: this stack *creates* the remote-state storage account.
# Operators apply this once per subscription, then copy the storage account name
# into each environment's backend.hcl.

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}

variable "location" {
  type    = string
  default = "centralindia"
}

resource "random_string" "suffix" {
  length  = 6
  lower   = true
  upper   = false
  numeric = true
  special = false
}

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-priceradar-tfstate"
  location = var.location
  tags = {
    project    = "priceradar-india"
    purpose    = "terraform-state"
    managed_by = "terraform"
    phase      = "15"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "stprtfstate${random_string.suffix.result}"
  location                        = var.location
  resource_group_name             = azurerm_resource_group.tfstate.name
  account_tier                    = "Standard"
  account_replication_type        = "GRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  local_user_enabled              = false

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
    container_delete_retention_policy {
      days = 30
    }
  }

  # Default Allow is a bootstrap exception so Microsoft-hosted agents can reach remote state.
  # Operators should switch default_action to Deny and add kv/storage IP rules once agents
  # are known or self-hosted. See infrastructure/CICD.md.
  network_rules {
    default_action = "Allow"
    bypass         = ["AzureServices"]
  }

  tags = azurerm_resource_group.tfstate.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.tfstate.id
  container_access_type = "private"
}

output "resource_group_name" {
  value = azurerm_resource_group.tfstate.name
}

output "storage_account_name" {
  value = azurerm_storage_account.tfstate.name
}

output "container_name" {
  value = azurerm_storage_container.tfstate.name
}
