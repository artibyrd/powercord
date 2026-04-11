output "instance_public_ip" {
  description = "The public IP address of the Powercord instance"
  value       = google_compute_instance.main.network_interface[0].access_config[0].nat_ip
}
