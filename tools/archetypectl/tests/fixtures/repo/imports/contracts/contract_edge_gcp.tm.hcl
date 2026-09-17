# Deliberately unresolvable: a function call, not a literal or a global.
input "backend_service" {
  backend       = "tofu"
  from_stack_id = tm_try(global.platform.edge_stack_id, "unknown")
  value         = outputs.backend_service_id.value
  mock          = "mock-backend-service"
}
