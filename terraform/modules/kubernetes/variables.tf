# Input variables for the Kubernetes module

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "supervisor-agent"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "cloud_provider" {
  description = "Cloud provider (aws, azure, gcp)"
  type        = string
  validation {
    condition     = contains(["aws", "azure", "gcp"], var.cloud_provider)
    error_message = "Cloud provider must be one of: aws, azure, gcp."
  }
}

variable "location" {
  description = "Location/region for the cluster"
  type        = string
}

# Kubernetes Configuration
variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

# Network Configuration
variable "subnet_ids" {
  description = "List of subnet IDs (AWS)"
  type        = list(string)
  default     = []
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs (AWS)"
  type        = list(string)
  default     = []
}

variable "subnet_id" {
  description = "Subnet ID (Azure)"
  type        = string
  default     = ""
}

variable "network" {
  description = "VPC network name (GCP)"
  type        = string
  default     = ""
}

variable "subnetwork" {
  description = "VPC subnetwork name (GCP)"
  type        = string
  default     = ""
}

# Node Configuration
variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 3
}

variable "node_min_size" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 10
}

variable "node_instance_types" {
  description = "Instance types for worker nodes (AWS)"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "Capacity type for nodes (ON_DEMAND or SPOT)"
  type        = string
  default     = "ON_DEMAND"
}

variable "azure_vm_size" {
  description = "VM size for worker nodes (Azure)"
  type        = string
  default     = "Standard_D2s_v3"
}

variable "gcp_machine_type" {
  description = "Machine type for worker nodes (GCP)"
  type        = string
  default     = "e2-medium"
}

variable "use_preemptible_nodes" {
  description = "Use preemptible nodes (GCP)"
  type        = bool
  default     = false
}

# Security Configuration
variable "public_endpoint_access" {
  description = "Enable public API server endpoint"
  type        = bool
  default     = true
}

variable "public_access_cidrs" {
  description = "CIDR blocks for public API access"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption (AWS)"
  type        = string
  default     = ""
}

# Azure-specific variables
variable "resource_group_name" {
  description = "Resource group name (Azure)"
  type        = string
  default     = ""
}

variable "availability_zones" {
  description = "Availability zones (Azure)"
  type        = list(string)
  default     = ["1", "2", "3"]
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID (Azure)"
  type        = string
  default     = ""
}

# GCP-specific variables
variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "node_locations" {
  description = "Node locations for regional cluster (GCP)"
  type        = list(string)
  default     = []
}

variable "pods_range_name" {
  description = "IP range name for pods (GCP)"
  type        = string
  default     = "pods"
}

variable "services_range_name" {
  description = "IP range name for services (GCP)"
  type        = string
  default     = "services"
}

variable "master_ipv4_cidr_block" {
  description = "CIDR block for master nodes (GCP)"
  type        = string
  default     = "172.16.0.0/28"
}

variable "authorized_networks" {
  description = "Authorized networks for master access (GCP)"
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  default = []
}

# Add-ons Configuration
variable "install_ingress" {
  description = "Install NGINX Ingress Controller"
  type        = bool
  default     = true
}

variable "install_cert_manager" {
  description = "Install cert-manager for TLS certificates"
  type        = bool
  default     = true
}

variable "install_external_dns" {
  description = "Install external-dns for DNS management"
  type        = bool
  default     = false
}

variable "domain_filters" {
  description = "Domain filters for external-dns"
  type        = list(string)
  default     = []
}