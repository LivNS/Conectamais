variable "location" {
  description = "Região da Azure"
  type        = string
  default     = "brazilsouth"
}

variable "project_name" {
  description = "Prefixo do projeto"
  type        = string
  default     = "conectamais"
}

variable "admin_cidr" {
  description = "IP ou CIDR da equipe para porta administrativa (nunca 0.0.0.0/0)"
  type        = string
}