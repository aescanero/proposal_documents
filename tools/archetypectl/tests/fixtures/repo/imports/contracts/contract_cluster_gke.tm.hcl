# Consumer half — imported by GKE cluster stacks.
input "network_self_link" {
  backend       = "tofu"
  from_stack_id = global.platform.network_stack_id
  value         = outputs.network_self_link.value
  mock          = "projects/mock-project/global/networks/mock-vpc"
}

input "subnet_self_link" {
  backend       = "tofu"
  from_stack_id = global.platform.network_stack_id
  value         = outputs.subnet_self_link.value
  mock          = "projects/mock-project/regions/europe-west1/subnetworks/mock-subnet"
}

# Producer half — the input label and the producer's output name differ here
# on purpose, so that consumes[].output is exercised against consumes[].name.
output "cluster_endpoint" { backend = "tofu"  value = module.gke.endpoint }
output "cluster_ca"       { backend = "tofu"  value = module.gke.ca_certificate  sensitive = true }
