terraform {
  required_version = ">= 1.5"

  required_providers {
    render = {
      source  = "render-oss/render"
      version = "~> 1.9"
    }
  }

  # State local: o arquivo terraform.tfstate fica só na máquina de quem aplica
  # e está no .gitignore. Em equipe, troque por um backend remoto
  # (ex.: HCP Terraform) — nunca suba o state para o Git.
}

# Credenciais lidas do ambiente, nunca do código:
#   RENDER_API_KEY  e  RENDER_OWNER_ID
provider "render" {}
