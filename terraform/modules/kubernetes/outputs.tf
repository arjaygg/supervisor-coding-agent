# Output values for the Kubernetes module

# Cluster Information
output "cluster_name" {
  description = "Name of the Kubernetes cluster"
  value = var.cloud_provider == "aws" ? (
    length(aws_eks_cluster.main) > 0 ? aws_eks_cluster.main[0].name : ""
  ) : var.cloud_provider == "azure" ? (
    length(azurerm_kubernetes_cluster.main) > 0 ? azurerm_kubernetes_cluster.main[0].name : ""
  ) : var.cloud_provider == "gcp" ? (
    length(google_container_cluster.main) > 0 ? google_container_cluster.main[0].name : ""
  ) : ""
}

output "cluster_endpoint" {
  description = "Kubernetes cluster endpoint"
  value = var.cloud_provider == "aws" ? (
    length(aws_eks_cluster.main) > 0 ? aws_eks_cluster.main[0].endpoint : ""
  ) : var.cloud_provider == "azure" ? (
    length(azurerm_kubernetes_cluster.main) > 0 ? azurerm_kubernetes_cluster.main[0].kube_config.0.host : ""
  ) : var.cloud_provider == "gcp" ? (
    length(google_container_cluster.main) > 0 ? "https://${google_container_cluster.main[0].endpoint}" : ""
  ) : ""
}

output "cluster_ca_certificate" {
  description = "Kubernetes cluster CA certificate"
  value = var.cloud_provider == "aws" ? (
    length(aws_eks_cluster.main) > 0 ? aws_eks_cluster.main[0].certificate_authority[0].data : ""
  ) : var.cloud_provider == "azure" ? (
    length(azurerm_kubernetes_cluster.main) > 0 ? azurerm_kubernetes_cluster.main[0].kube_config.0.cluster_ca_certificate : ""
  ) : var.cloud_provider == "gcp" ? (
    length(google_container_cluster.main) > 0 ? google_container_cluster.main[0].master_auth[0].cluster_ca_certificate : ""
  ) : ""
  sensitive = true
}

# AWS-specific outputs
output "aws_cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = length(aws_eks_cluster.main) > 0 ? aws_eks_cluster.main[0].arn : ""
}

output "aws_cluster_security_group_id" {
  description = "Security group ID of the EKS cluster"
  value       = length(aws_eks_cluster.main) > 0 ? aws_eks_cluster.main[0].vpc_config[0].cluster_security_group_id : ""
}

output "aws_node_group_arn" {
  description = "ARN of the EKS node group"
  value       = length(aws_eks_node_group.main) > 0 ? aws_eks_node_group.main[0].arn : ""
}

# Azure-specific outputs
output "azure_cluster_id" {
  description = "ID of the AKS cluster"
  value       = length(azurerm_kubernetes_cluster.main) > 0 ? azurerm_kubernetes_cluster.main[0].id : ""
}

output "azure_kubelet_identity" {
  description = "Kubelet identity for AKS cluster"
  value = length(azurerm_kubernetes_cluster.main) > 0 ? {
    client_id                 = azurerm_kubernetes_cluster.main[0].kubelet_identity[0].client_id
    object_id                 = azurerm_kubernetes_cluster.main[0].kubelet_identity[0].object_id
    user_assigned_identity_id = azurerm_kubernetes_cluster.main[0].kubelet_identity[0].user_assigned_identity_id
  } : {}
}

# GCP-specific outputs
output "gcp_cluster_location" {
  description = "Location of the GKE cluster"
  value       = length(google_container_cluster.main) > 0 ? google_container_cluster.main[0].location : ""
}

output "gcp_node_pool_instance_group_urls" {
  description = "Instance group URLs of the GKE node pool"
  value       = length(google_container_node_pool.main) > 0 ? google_container_node_pool.main[0].instance_group_urls : []
}

output "gcp_service_account_email" {
  description = "Email of the service account used by GKE nodes"
  value       = length(google_service_account.gke_nodes) > 0 ? google_service_account.gke_nodes[0].email : ""
}

# Kubeconfig
output "kubeconfig" {
  description = "Kubeconfig for accessing the cluster"
  value = var.cloud_provider == "aws" ? (
    length(aws_eks_cluster.main) > 0 ? {
      apiVersion      = "v1"
      kind            = "Config"
      current-context = "terraform"
      contexts = [{
        name = "terraform"
        context = {
          cluster = "terraform"
          user    = "terraform"
        }
      }]
      clusters = [{
        name = "terraform"
        cluster = {
          certificate-authority-data = aws_eks_cluster.main[0].certificate_authority[0].data
          server                     = aws_eks_cluster.main[0].endpoint
        }
      }]
      users = [{
        name = "terraform"
        user = {
          exec = {
            apiVersion = "client.authentication.k8s.io/v1beta1"
            command    = "aws"
            args       = ["eks", "get-token", "--cluster-name", aws_eks_cluster.main[0].name]
          }
        }
      }]
    } : {}
  ) : var.cloud_provider == "azure" ? (
    length(azurerm_kubernetes_cluster.main) > 0 ? azurerm_kubernetes_cluster.main[0].kube_config[0] : {}
  ) : var.cloud_provider == "gcp" ? (
    length(google_container_cluster.main) > 0 ? {
      apiVersion      = "v1"
      kind            = "Config"
      current-context = "terraform"
      contexts = [{
        name = "terraform"
        context = {
          cluster = "terraform"
          user    = "terraform"
        }
      }]
      clusters = [{
        name = "terraform"
        cluster = {
          certificate-authority-data = google_container_cluster.main[0].master_auth[0].cluster_ca_certificate
          server                     = "https://${google_container_cluster.main[0].endpoint}"
        }
      }]
      users = [{
        name = "terraform"
        user = {
          exec = {
            apiVersion = "client.authentication.k8s.io/v1beta1"
            command    = "gke-gcloud-auth-plugin"
          }
        }
      }]
    } : {}
  ) : {}
  sensitive = true
}

# Add-on status
output "ingress_nginx_installed" {
  description = "Whether NGINX Ingress Controller is installed"
  value       = length(helm_release.ingress_nginx) > 0
}

output "cert_manager_installed" {
  description = "Whether cert-manager is installed"
  value       = length(helm_release.cert_manager) > 0
}

output "external_dns_installed" {
  description = "Whether external-dns is installed"
  value       = length(helm_release.external_dns) > 0
}

# Cluster information for monitoring and management
output "cluster_info" {
  description = "Complete cluster information"
  value = {
    name            = local.cluster_name
    provider        = var.cloud_provider
    location        = var.location
    environment     = var.environment
    kubernetes_version = var.kubernetes_version
    node_count = {
      desired = var.node_desired_size
      min     = var.node_min_size
      max     = var.node_max_size
    }
    addons = {
      ingress_nginx = length(helm_release.ingress_nginx) > 0
      cert_manager  = length(helm_release.cert_manager) > 0
      external_dns  = length(helm_release.external_dns) > 0
    }
  }
}