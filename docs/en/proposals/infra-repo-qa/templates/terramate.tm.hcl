# Destination: terramate.tm.hcl — the project's single root configuration (poc/: one root per repository)
terramate {
  required_version = "= 0.17.3"

  config {
    experiments = ["outputs-sharing"]            # scripts are no longer experimental

    git {
      default_branch = "main"
    }

    run {
      env {
        TF_PLUGIN_CACHE_DIR = "${env.HOME}/.terraform.d/plugin-cache"
      }
    }
  }
}

sharing_backend "tofu" {
  type     = terraform
  command  = ["tofu", "output", "-json"]
  filename = "_sharing_generated.tf"
}
