// PoC root configuration.
//
// This file must sit at the *project root*. Terramate derives the project root
// from the git root, so this PoC cannot be run in place inside the
// proposal_documents repository — `required_version` and `config.experiments`
// are rejected with "can only be declared at the project root directory".
// `run-poc.sh` copies this tree to a scratch directory outside git, where the
// directory holding this file becomes the project root.

terramate {
  // Pin the CLI. Phase 0 answers are only valid for the version they were
  // measured against; see RESULTS.md for the version actually used.
  required_version = "~> 0.16"

  config {
    // Without this, `sharing_backend`, `input` and `output` are parse errors.
    experiments = ["outputs-sharing"]
  }
}

// The transport. Defined once at the root so every stack sees the same
// namespace. `command` runs inside the *producer* stack directory and its
// stdout must be a JSON object, so the producer must be initialised and
// applied before a consumer can read it for real.
sharing_backend "tofu" {
  type     = terraform
  filename = "_sharing_generated.tf"
  command  = ["tofu", "output", "-json"]
}
