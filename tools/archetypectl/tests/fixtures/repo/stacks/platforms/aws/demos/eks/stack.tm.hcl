stack {
  id    = "aws-demos-eks"
  name  = "AWS demos — EKS"
  tags  = ["aws", "demos", "cluster", "platform", "producer", "consumer"]
  after = ["../network"]
}

globals "platform" {
  network_stack_id = "aws-demos-network"
}

import { source = "/imports/contracts/contract_cluster_gke.tm.hcl" }
