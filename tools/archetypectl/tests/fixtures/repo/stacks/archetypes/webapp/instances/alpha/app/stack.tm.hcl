stack {
  id    = "gcp-demos-alpha-app"
  name  = "webapp alpha — app"
  tags  = ["gcp", "demos", "app", "archetype:webapp", "instance:alpha", "consumer"]
  after = ["tag:gcp:cluster"]
}

globals {
  capability = "app"
}

import { source = "/imports/contracts/contract_app_gke.tm.hcl" }
