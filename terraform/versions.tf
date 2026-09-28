terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# Local state: the sandbox has no billing account, and Cloud Storage (the
# usual remote backend) needs one. Apply from a workstation with
# `gcloud auth application-default login`.
provider "google" {
  project = var.project_id
  region  = var.location
}
