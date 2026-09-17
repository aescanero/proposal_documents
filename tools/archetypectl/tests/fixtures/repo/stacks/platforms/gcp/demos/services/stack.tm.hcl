stack {
  id   = "gcp-demos-services"
  name = "GCP demos — platform services"
  tags = ["gcp", "demos", "platform-services", "platform", "consumer"]
}

globals {
  capability = "platform-services"
}

globals "platform" {
  cluster_stack_id = "gcp-demos-gke"
}

import { source = "/imports/contracts/contract_services_gcp.tm.hcl" }
