input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_stack_id
  value         = outputs.cluster_endpoint.value
  mock          = "mock-endpoint.example.invalid"
}
input "cluster_ca" {
  backend       = "tofu"
  from_stack_id = global.platform.cluster_stack_id
  value         = outputs.cluster_ca.value
  sensitive     = true
  mock          = "bW9jaw=="
}
