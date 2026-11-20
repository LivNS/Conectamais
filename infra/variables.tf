variable "nome_servico" {
  description = "Nome do Web Service no Render"
  type        = string
  default     = "conecta"
}

variable "regiao" {
  description = "Região do Render (confira a do serviço existente antes do import)"
  type        = string
  default     = "oregon"
}

variable "plano" {
  description = "Plano do Render"
  type        = string
  default     = "free"
}

variable "repo_url" {
  description = "Repositório público do projeto"
  type        = string
  default     = "https://github.com/LivNS/Conecta-"
}

variable "branch" {
  type    = string
  default = "main"
}

variable "admin_usuario" {
  description = "Usuário da tela /revisao"
  type        = string
  sensitive   = true
}

variable "admin_senha" {
  description = "Senha da tela /revisao"
  type        = string
  sensitive   = true
}

variable "rpa_api_token" {
  description = "Token do robô de alertas"
  type        = string
  sensitive   = true
}

variable "metrics_token" {
  description = "Token que o Prometheus usa para ler /metrics"
  type        = string
  sensitive   = true
}
