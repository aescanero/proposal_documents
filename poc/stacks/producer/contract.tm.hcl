// The producer half of the contract.
//
// `value` is evaluated in the GENERATED OpenTofu code, not by Terramate, so it
// may reference `local.*` / `module.*` / `resource.*` freely. If Terramate
// tried to resolve `local.endpoint` at generate time this file would fail —
// that it does not is itself worth confirming.
//
// Three outputs, chosen to exercise the mock type-correctness trap in CLAUDE.md:
// a plain string, a base64 string, and a list.

output "cluster_endpoint" {
  backend     = "tofu"
  value       = local.endpoint
  description = "Cluster API endpoint, scheme included (EKS-style)"
}

output "cluster_ca_data" {
  backend     = "tofu"
  value       = local.ca_data
  description = "base64-encoded CA bundle — consumer calls base64decode() on it"
}

output "pod_ranges" {
  backend     = "tofu"
  value       = local.pod_ranges
  description = "list(string) — consumer indexes it and takes length()"
}
