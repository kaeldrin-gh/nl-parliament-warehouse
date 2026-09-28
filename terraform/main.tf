locals {
  # The sandbox expires every table 60 days after creation and refuses to
  # change that; stating it here keeps the plan honest about it.
  sixty_days_ms = 60 * 24 * 60 * 60 * 1000
}

resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

resource "google_bigquery_dataset" "raw" {
  dataset_id                  = "raw"
  location                    = var.location
  description                 = "Append-only change log from the Tweede Kamer SyncFeed and OData snapshots."
  default_table_expiration_ms = local.sixty_days_ms

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "ingest" {
  account_id   = "nl-parliament-ingest"
  display_name = "nl-parliament-warehouse ingest (GitHub Actions)"
}

# Keyless access for GitHub Actions: the workflow's OIDC token is exchanged
# for short-lived credentials, restricted to one repository.
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "repository" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "nl-parliament-warehouse"
  display_name                       = "nl-parliament-warehouse"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_impersonation" {
  service_account_id = google_service_account.ingest.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# Least privilege: run jobs in the project, write only to this dataset.
resource "google_project_iam_member" "ingest_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_bigquery_dataset_iam_member" "ingest_raw" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingest.email}"
}
