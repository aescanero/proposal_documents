// Deliberately provider-free: locals and outputs only. `tofu init` then needs
// no network and no credentials, which keeps the Phase 0 answers about
// Terramate uncontaminated by cloud setup.
//
// Functions without the `tm_` prefix are NOT evaluated by Terramate; they are
// emitted verbatim for OpenTofu. That is why `base64encode` below survives
// into _main.tf instead of being folded at generate time.

generate_hcl "_main.tf" {
  content {
    terraform {
      required_version = ">= 1.6.0"
    }

    locals {
      endpoint   = "https://poc-producer.example.invalid"
      ca_data    = base64encode("poc-cluster-ca-bundle")
      pod_ranges = ["10.10.0.0/24", "10.10.1.0/24"]
    }
  }
}
