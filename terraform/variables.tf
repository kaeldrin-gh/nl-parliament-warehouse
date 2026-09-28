variable "project_id" {
  description = "BigQuery sandbox project (no billing account)."
  type        = string
  default     = "project-510017"
}

variable "location" {
  description = "BigQuery location for all datasets."
  type        = string
  default     = "EU"
}

variable "github_repository" {
  description = "The only repository whose workflows may use the ingest service account."
  type        = string
  default     = "kaeldrin-gh/nl-parliament-warehouse"
}
