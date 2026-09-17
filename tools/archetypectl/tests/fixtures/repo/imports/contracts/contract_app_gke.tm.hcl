# from_stack_id built by interpolation rather than a bare reference.
input "kube_endpoint" {
  backend       = "tofu"
  from_stack_id = "${global.cloud}-${global.env}-gke"
  value         = outputs.cluster_endpoint.value
  mock          = "mock-endpoint.example.invalid"
}
