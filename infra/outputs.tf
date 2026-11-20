output "url" {
  description = "Endereço público do MVP"
  value       = render_web_service.conecta.url
}

output "service_id" {
  description = "ID do serviço (usado no pipeline como RENDER_SERVICE_ID)"
  value       = render_web_service.conecta.id
}
