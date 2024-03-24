
variable "project" {
  description = "The GCP project to deploy resources to"
  type        = string
}

variable "region" {
  description = "The GCP region to deploy resources to"
  type        = string
  default     = "us-central1"
}

variable "google_credentials" {
  description = "The path to the GCP credentials file"
  type        = string
}
