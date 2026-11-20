# O serviço já existia no Render. Este bloco o traz para o state do Terraform
# na primeira execução de "terraform apply" (Terraform 1.5+).
import {
  to = render_web_service.conecta
  id = "srv-dbv591ajnfac73cldbkg"
}
