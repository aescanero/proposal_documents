stack {
  id    = "gcp-demos-gke"
  name  = "GCP demos — GKE"
  tags  = ["gcp", "demos", "cluster", "platform", "producer", "consumer"]
  after = ["/stacks/platforms/gcp/demos/network"]
}

globals {
  capability = "cluster"
}

globals "platform" {
  network_stack_id = "gcp-demos-network"
}

import { source = "/imports/contracts/contract_cluster_gke.tm.hcl" }
