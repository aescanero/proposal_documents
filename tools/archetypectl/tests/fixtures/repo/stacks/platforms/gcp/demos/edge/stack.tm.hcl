stack {
  id    = "gcp-demos-edge"
  name  = "GCP demos — edge"
  tags  = ["gcp", "demos", "edge", "platform", "consumer"]
  after = ["tag:gcp:cluster"]
}

globals {
  capability = "edge"
}

import { source = "/imports/contracts/contract_edge_gcp.tm.hcl" }
