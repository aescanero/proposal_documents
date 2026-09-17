output "network_self_link" { backend = "tofu"  value = module.network.network_self_link }
output "subnet_self_link"  { backend = "tofu"  value = module.network.subnet_self_link }
output "project_id"        { backend = "tofu"  value = var.project_id }
