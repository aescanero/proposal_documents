stack {
  id   = "poc-consumer-inherited"
  name = "PoC consumer — inherited global in from_stack_id"

  tags = ["poc", "consumer"]

  // ASSUMPTION A3, control case: a literal project-absolute path.
  //
  // The globals-derived form (`after = [global.producer_path]`) is NOT used
  // here because it does not parse at all — see cases/after-global-expr/ and
  // RESULTS.md A3. Globals are unavailable in the `stack` block; Terramate
  // 0.16.0 aborts rather than silently emptying `after`.
  after = ["/stacks/producer"]
}
