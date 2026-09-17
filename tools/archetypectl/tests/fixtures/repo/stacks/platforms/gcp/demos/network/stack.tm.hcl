stack {
  id   = "gcp-demos-network"
  name = "GCP demos — network"
  tags = ["gcp", "demos", "network", "platform", "producer"]
}

globals {
  capability = "network"
}

import { source = "/imports/contracts/contract_network_gcp.tm.hcl" }
