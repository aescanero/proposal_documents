generate_hcl "_main.tf" {
  content {
    terraform {
      required_version = ">= 1.6.0"
    }

    locals {
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

    output "observed_first_range" {
      value = local.first_range
    }

    output "observed_range_count" {
      value = local.range_count
    }
  }
}
