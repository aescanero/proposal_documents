// Echo the resolved values back out as OpenTofu outputs so that `tofu output`
// shows whether a REAL producer value or a MOCK was used. That distinction is
// the whole test for A4 — a run that silently mocks in a deploy path is the
// failure mode CLAUDE.md warns about.

generate_hcl "_main.tf" {
  content {
    terraform {
      required_version = ">= 1.6.0"
    }

    locals {
      // Forces the type-correctness of the mocks to be exercised, not assumed.
      decoded_ca  = base64decode(var.cluster_ca_data)
      first_range = var.pod_ranges[0]
      range_count = length(var.pod_ranges)
    }
  }
}

generate_hcl "_observed.tf" {
  content {
    output "observed_endpoint" {
      value = var.cluster_endpoint
    }

    output "observed_ca_decoded" {
      value = local.decoded_ca
    }

    output "observed_first_range" {
      value = local.first_range
    }

    output "observed_range_count" {
      value = local.range_count
    }
  }
}
