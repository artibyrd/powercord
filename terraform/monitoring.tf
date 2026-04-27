resource "google_monitoring_alert_policy" "disk_usage_alert" {
  display_name = "Persistent Disk Usage > 80%"
  project      = var.project_id
  combiner     = "OR"
  conditions {
    display_name = "Disk space utilization"
    condition_threshold {
      filter     = "resource.type = \"gce_instance\" AND metric.type = \"compute.googleapis.com/guest/disk/bytes_used\" AND metric.labels.device_name = \"powercord-data-disk\""
      duration   = "300s"
      comparison = "COMPARISON_GT"
      # Assuming a 50GB disk, 80% is 40GB = 42949672960 bytes
      threshold_value = 42949672960
    }
  }
  depends_on = [google_project_service.main]
}
