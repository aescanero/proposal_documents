// ASSUMPTION A1: `from_stack_id` resolves a global INHERITED from a parent
// directory. `global.producer_id` is defined in /globals.tm.hcl and is never
// redefined here. Nothing in this directory declares it.
//
// Mocks are all prefixed `mock-` (or decode to a `mock-` string) per the
// CLAUDE.md convention, and each is TYPE-CORRECT:
//   - cluster_ca_data must be valid base64 or base64decode() blows up
//   - pod_ranges must be a list or [0] and length() blow up
// A wrong-typed mock type-checks in Terramate and fails at apply.

input "cluster_endpoint" {
  backend       = "tofu"
  from_stack_id = global.producer_id
  value         = outputs.cluster_endpoint.value
  mock          = "https://mock-endpoint.example.invalid"
}

input "cluster_ca_data" {
  backend       = "tofu"
  from_stack_id = global.producer_id
  value         = outputs.cluster_ca_data.value
  // base64 of "mock-ca-bundle". A naive mock of "mock" is not valid base64
  // and breaks base64decode() only at apply time.
  mock = "bW9jay1jYS1idW5kbGU="
}

input "pod_ranges" {
  backend       = "tofu"
  from_stack_id = global.producer_id
  value         = outputs.pod_ranges.value
  mock          = ["10.255.0.0/24"]
}
