packer {
  required_plugins {
    googlecompute = {
      version = ">= 1.0.9"
      source  = "github.com/hashicorp/googlecompute"
    }
  }
}

variable "project_id" {
  type    = string
  default = env("GCP_PROJECT")
}

variable "docker_image" {
  type = string
}

source "googlecompute" "powercord-image" {
  project_id          = var.project_id
  source_image_family = "debian-12"
  zone                = "us-central1-a"
  image_name          = "powercord-app-${formatdate("YYYYMMDD-HHMMSS", timestamp())}"
  image_family        = "powercord-app"
  ssh_username        = "packer"
  startup_script_file = "startup-script.sh"
  metadata = {
    # This tells the startup script which docker image to pull and run
    docker_image = var.docker_image
  }
}
build {
  sources = ["source.googlecompute.powercord-image"]

  provisioner "shell" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common",
      "curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
      "echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
      "sudo apt-get update",
      "sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
      "sudo systemctl enable docker"
    ]
  }
}
