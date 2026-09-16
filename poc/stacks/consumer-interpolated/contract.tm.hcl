// ASSUMPTION A2: `from_stack_id` accepts INTERPOLATION, not only a bare
// global reference. `global.env` is "poc" (inherited from /globals.tm.hcl), so
// "${global.env}-producer" must render to "poc-producer" — the same producer
// consumer-inherited binds to by bare reference.
//
// If only bare references worked, the resolver would have to emit a contract
// file per instance rather than one per capability. See CLAUDE.md, "Settled
// decisions — from_stack_id accepts an expression".

input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = "${global.env}-producer"
  value         = outputs.cluster_endpoint.value
  mock          = "https://mock-endpoint.example.invalid"
}

input "pod_ranges" {
  backend       = "tofu"
  from_stack_id = "${global.env}-producer"
  value         = outputs.pod_ranges.value
  mock          = ["10.255.0.0/24"]
}
