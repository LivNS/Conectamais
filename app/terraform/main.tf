provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.project_name}-deploy-blindado"
  location = var.location

  tags = {
    projeto = "Conecta+"
    tema    = "CitizenTech"
  }
}

resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-${var.project_name}"
  address_space       = ["10.20.0.0/16"]
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  tags = {
    projeto = "Conecta+"
  }
}

resource "azurerm_subnet" "app_subnet" {
  name                 = "snet-${var.project_name}-app"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.20.1.0/24"]
}

resource "azurerm_network_security_group" "nsg" {
  name                = "nsg-${var.project_name}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  security_rule {
    name                       = "Allow-HTTPS"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  # Porta administrativa (ex.: SSH 22 / RDP 3389) restrita ao CIDR da equipe, nunca 0.0.0.0/0 ou *
  security_rule {
    name                       = "Allow-Admin-Restricted"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.admin_cidr
    destination_address_prefix = "*"
  }

  tags = {
    projeto = "Conecta+"
  }
}

resource "azurerm_subnet_network_security_group_association" "snet_nsg" {
  subnet_id                 = azurerm_subnet.app_subnet.id
  network_security_group_id = azurerm_network_security_group.nsg.id
}