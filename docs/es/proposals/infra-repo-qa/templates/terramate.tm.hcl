# Destino: terramate.tm.hcl — la única configuración raíz del proyecto (poc/: una raíz por repositorio)
terramate {
  required_version = "= 0.17.3"

  config {
    experiments = ["outputs-sharing"]            # los scripts ya no son experimentales

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
