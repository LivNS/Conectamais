# Web Service do Conecta+ no Render, criado e mantido por código.
#
# Rede: o Render (PaaS) só expõe a porta HTTPS 443 do serviço. Não existe porta
# de administração (SSH, RDP, banco) aberta para a internet, e este código não
# abre nenhuma. As áreas restritas do app ficam atrás de autenticação:
#   /revisao  -> login (HTTP Basic sobre HTTPS)
#   /metrics  -> token Bearer (METRICS_TOKEN)
#   /api/alertas/rascunhos -> token Bearer do robô (RPA_API_TOKEN)

resource "render_web_service" "conecta" {
  name              = var.nome_servico
  plan              = var.plano
  region            = var.regiao
  health_check_path = "/saude"
  root_directory    = "app"

  runtime_source = {
    docker = {
      repo_url        = var.repo_url
      branch          = var.branch
      context         = "."
      dockerfile_path = "./Dockerfile"

      # Deploy só pelo pipeline (GitHub Actions), depois que os testes e as
      # varreduras de segurança passam. Nada vai ao ar direto do push.
      auto_deploy = false
    }
  }

  env_vars = {
    ADMIN_USUARIO = { value = var.admin_usuario }
    ADMIN_SENHA   = { value = var.admin_senha }
    RPA_API_TOKEN = { value = var.rpa_api_token }
    METRICS_TOKEN = { value = var.metrics_token }
    APP_NOME      = { value = "Conecta+" }
  }
}
