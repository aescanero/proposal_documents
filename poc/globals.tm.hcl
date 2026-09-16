// PARENT-DIRECTORY GLOBALS.
//
// This is the whole point of assumption A1: these globals are defined here, at
// the PoC root, and are never redefined inside any stack directory. If
// `from_stack_id` only resolved globals defined in the stack itself, the
// consumers would fail to resolve and the late-binding model in
// docs/terramate-outputs-sharing-architecture.md §4.4 would not work.

globals {
  // Stands in for the environment name. Used by the interpolation case:
  // "${global.env}-producer" must render to "poc-producer".
  env = "poc"

  // Bare-reference case: from_stack_id = global.producer_id
  producer_id = "poc-producer"

  // Used to test whether `stack.after` accepts a globals-derived path.
  // This is the one that fails SILENTLY, so it is checked with run-graph,
  // not by the absence of an error.
  producer_path = "/stacks/producer"
}
