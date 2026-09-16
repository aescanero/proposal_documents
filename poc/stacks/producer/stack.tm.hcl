stack {
  id   = "poc-producer"
  name = "PoC producer"
  // The "producer" tag is the fallback ordering mechanism tested by
  // consumer-interpolated (`after = ["tag:producer"]`).
  tags = ["poc", "producer"]
}
