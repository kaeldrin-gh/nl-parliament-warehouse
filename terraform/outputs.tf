output "workload_identity_provider" {
  description = "Value for google-github-actions/auth `workload_identity_provider`."
  value       = google_iam_workload_identity_pool_provider.repository.name
}

output "service_account" {
  description = "Value for google-github-actions/auth `service_account`."
  value       = google_service_account.ingest.email
}
