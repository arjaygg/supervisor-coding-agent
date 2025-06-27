# Kubernetes Cluster Module
# Supports AWS EKS, Azure AKS, and GCP GKE

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

# Local variables for common configuration
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Application = "supervisor-coding-agent"
  }
  
  cluster_name = "${var.project_name}-${var.environment}-cluster"
}

# AWS EKS Cluster
resource "aws_eks_cluster" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  name     = local.cluster_name
  role_arn = aws_iam_role.eks_cluster[0].arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = var.public_endpoint_access
    public_access_cidrs     = var.public_access_cidrs
    
    security_group_ids = [aws_security_group.eks_cluster[0].id]
  }

  encryption_config {
    provider {
      key_arn = var.kms_key_arn
    }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = [
    "api", "audit", "authenticator", "controllerManager", "scheduler"
  ]

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy[0],
    aws_iam_role_policy_attachment.eks_vpc_resource_controller[0],
    aws_cloudwatch_log_group.eks_cluster[0],
  ]

  tags = local.common_tags
}

# AWS EKS Node Group
resource "aws_eks_node_group" "main" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  cluster_name    = aws_eks_cluster.main[0].name
  node_group_name = "${local.cluster_name}-workers"
  node_role_arn   = aws_iam_role.eks_node_group[0].arn
  subnet_ids      = var.private_subnet_ids

  capacity_type  = var.node_capacity_type
  instance_types = var.node_instance_types

  scaling_config {
    desired_size = var.node_desired_size
    max_size     = var.node_max_size
    min_size     = var.node_min_size
  }

  update_config {
    max_unavailable_percentage = 25
  }

  # Ensure that IAM Role permissions are created before and deleted after EKS Node Group handling.
  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy[0],
    aws_iam_role_policy_attachment.eks_cni_policy[0],
    aws_iam_role_policy_attachment.eks_container_registry_policy[0],
  ]

  tags = local.common_tags
}

# Azure AKS Cluster
resource "azurerm_kubernetes_cluster" "main" {
  count = var.cloud_provider == "azure" ? 1 : 0
  
  name                = local.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = "${var.project_name}-${var.environment}"
  kubernetes_version  = var.kubernetes_version

  default_node_pool {
    name                = "default"
    node_count          = var.node_desired_size
    vm_size             = var.azure_vm_size
    availability_zones  = var.availability_zones
    enable_auto_scaling = true
    min_count          = var.node_min_size
    max_count          = var.node_max_size
    max_pods           = 110
    os_disk_size_gb    = 128
    vnet_subnet_id     = var.subnet_id
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "Standard"
    outbound_type     = "loadBalancer"
  }

  addon_profile {
    oms_agent {
      enabled                    = true
      log_analytics_workspace_id = var.log_analytics_workspace_id
    }
    
    azure_policy {
      enabled = true
    }
    
    http_application_routing {
      enabled = false
    }
  }

  role_based_access_control {
    enabled = true
    
    azure_active_directory {
      managed           = true
      azure_rbac_enabled = true
    }
  }

  tags = local.common_tags
}

# GCP GKE Cluster
resource "google_container_cluster" "main" {
  count = var.cloud_provider == "gcp" ? 1 : 0
  
  name     = local.cluster_name
  location = var.location
  
  # Regional cluster for high availability
  node_locations = var.node_locations

  # Kubernetes version
  min_master_version = var.kubernetes_version
  
  # Remove default node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  # Network configuration
  network    = var.network
  subnetwork = var.subnetwork

  # IP allocation for pods and services
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  # Network policy
  network_policy {
    enabled  = true
    provider = "CALICO"
  }

  # Master auth networks
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.authorized_networks
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  # Private cluster configuration
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
  }

  # Workload Identity
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Cluster monitoring and logging
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }
  
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS", "API_SERVER"]
  }

  # Maintenance policy
  maintenance_policy {
    recurring_window {
      start_time = "2023-01-01T02:00:00Z"
      end_time   = "2023-01-01T06:00:00Z"
      recurrence = "FREQ=WEEKLY;BYDAY=SA"
    }
  }

  # Enable shielded nodes
  enable_shielded_nodes = true
  
  # Resource labels
  resource_labels = local.common_tags
}

# GCP GKE Node Pool
resource "google_container_node_pool" "main" {
  count = var.cloud_provider == "gcp" ? 1 : 0
  
  name       = "${local.cluster_name}-workers"
  location   = var.location
  cluster    = google_container_cluster.main[0].name
  
  node_count = var.node_desired_size

  # Auto-scaling configuration
  autoscaling {
    min_node_count = var.node_min_size
    max_node_count = var.node_max_size
  }

  # Management configuration
  management {
    auto_repair  = true
    auto_upgrade = true
  }

  # Node configuration
  node_config {
    preemptible  = var.use_preemptible_nodes
    machine_type = var.gcp_machine_type
    disk_size_gb = 100
    disk_type    = "pd-ssd"
    
    # Service account
    service_account = google_service_account.gke_nodes[0].email
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Shielded instance configuration
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    # Workload metadata configuration
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Labels and tags
    labels = local.common_tags
    
    tags = [
      "${var.project_name}-${var.environment}",
      "kubernetes-worker"
    ]
  }
}

# Install essential cluster add-ons
resource "helm_release" "ingress_nginx" {
  count = var.install_ingress ? 1 : 0
  
  name       = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = "ingress-nginx"
  
  create_namespace = true
  
  values = [
    templatefile("${path.module}/helm-values/ingress-nginx.yaml", {
      cloud_provider = var.cloud_provider
      environment    = var.environment
    })
  ]

  depends_on = [
    aws_eks_cluster.main,
    azurerm_kubernetes_cluster.main,
    google_container_cluster.main
  ]
}

resource "helm_release" "cert_manager" {
  count = var.install_cert_manager ? 1 : 0
  
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  namespace  = "cert-manager"
  version    = "v1.13.2"
  
  create_namespace = true
  
  set {
    name  = "installCRDs"
    value = "true"
  }

  depends_on = [
    aws_eks_cluster.main,
    azurerm_kubernetes_cluster.main,
    google_container_cluster.main
  ]
}

resource "helm_release" "external_dns" {
  count = var.install_external_dns ? 1 : 0
  
  name       = "external-dns"
  repository = "https://kubernetes-sigs.github.io/external-dns/"
  chart      = "external-dns"
  namespace  = "external-dns"
  
  create_namespace = true
  
  values = [
    templatefile("${path.module}/helm-values/external-dns.yaml", {
      cloud_provider = var.cloud_provider
      domain_filters = var.domain_filters
    })
  ]

  depends_on = [
    aws_eks_cluster.main,
    azurerm_kubernetes_cluster.main,
    google_container_cluster.main
  ]
}