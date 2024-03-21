provider "google" {
  credentials = file("<YOUR-CREDENTIALS-FILE>.json")
  project     = "sun-peach-solar"
  region      = "us-central1"
}

resource "google_storage_bucket" "bucket" {
  location = "US"
  name     = "sun-peach-bucket"
}

resource "google_storage_bucket_object" "object" {
  name   = "function-source.zip"
  bucket = google_storage_bucket.bucket.name
  source = "function-source.zip"
}

resource "google_cloudfunctions_function" "email_processor" {
  name                  = "process-email-event"
  runtime               = "python39"
  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.bucket.name
  source_archive_object = google_storage_bucket_object.object.name
  trigger_http          = false
  entry_point           = "process_email_event"
  event_trigger {
    event_type = "providers/cloud.pubsub/eventTypes/topic.publish"
    resource   = google_pubsub_topic.email_topic.id
  }
}
resource "google_pubsub_topic" "email_topic" {
  name = "process_email_event"
}

# Add any necessary IAM roles or permissions
