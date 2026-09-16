stack {
  id   = "poc-consumer-interpolated"
  name = "PoC consumer — interpolated from_stack_id + tag ordering"

  tags = ["poc", "consumer"]

  // ASSUMPTION A3, fallback branch: tag-based ordering.
  //
  // If `after = [global.producer_path]` (see consumer-inherited) turns out not
  // to resolve, this is the documented fallback. It is tested here in the same
  // run so the two answers are directly comparable in the same run-graph.
  after = ["tag:producer"]
}
