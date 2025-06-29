# IAM roles and policies for Kubernetes clusters

# AWS IAM Roles
resource "aws_iam_role" "eks_cluster" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  name = "${local.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
    Version = "2012-10-17"
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster[0].name
}

resource "aws_iam_role_policy_attachment" "eks_vpc_resource_controller" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.eks_cluster[0].name
}

# EKS Node Group IAM Role
resource "aws_iam_role" "eks_node_group" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  name = "${local.cluster_name}-node-group-role"

  assume_role_policy = jsonencode({
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
    Version = "2012-10-17"
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node_group[0].name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node_group[0].name
}

resource "aws_iam_role_policy_attachment" "eks_container_registry_policy" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node_group[0].name
}

# Additional IAM policy for Supervisor Agent specific permissions
resource "aws_iam_role_policy" "supervisor_agent_policy" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  name = "${local.cluster_name}-supervisor-agent-policy"
  role = aws_iam_role.eks_node_group[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
        ]
        Resource = [
          "arn:aws:secretsmanager:*:*:secret:supervisor-agent/*",
          "arn:aws:ssm:*:*:parameter/supervisor-agent/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups"
        ]
        Resource = "arn:aws:logs:*:*:log-group:/aws/eks/${local.cluster_name}/*"
      }
    ]
  })
}

# Security Groups for AWS EKS
resource "aws_security_group" "eks_cluster" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  name_prefix = "${local.cluster_name}-cluster-"
  vpc_id      = data.aws_subnet.first[0].vpc_id

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.public_access_cidrs
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-cluster-sg"
  })
}

# Data source to get VPC info
data "aws_subnet" "first" {
  count = var.cloud_provider == "aws" && length(var.subnet_ids) > 0 ? 1 : 0
  id    = var.subnet_ids[0]
}

# CloudWatch Log Group for EKS
resource "aws_cloudwatch_log_group" "eks_cluster" {
  count = var.cloud_provider == "aws" ? 1 : 0
  
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = 30
  kms_key_id        = var.kms_key_arn

  tags = local.common_tags
}

# GCP Service Accounts
resource "google_service_account" "gke_nodes" {
  count = var.cloud_provider == "gcp" ? 1 : 0
  
  account_id   = "${local.cluster_name}-nodes"
  display_name = "GKE Node Service Account for ${local.cluster_name}"
  project      = var.project_id
}

resource "google_project_iam_member" "gke_nodes" {
  count = var.cloud_provider == "gcp" ? length(local.gke_node_roles) : 0
  
  project = var.project_id
  role    = local.gke_node_roles[count.index]
  member  = "serviceAccount:${google_service_account.gke_nodes[0].email}"
}

locals {
  gke_node_roles = [
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor"
  ]
}

# Workload Identity for GCP
resource "google_service_account" "supervisor_agent" {
  count = var.cloud_provider == "gcp" ? 1 : 0
  
  account_id   = "${local.cluster_name}-supervisor-agent"
  display_name = "Supervisor Agent Service Account"
  project      = var.project_id
}

resource "google_service_account_iam_member" "workload_identity" {
  count = var.cloud_provider == "gcp" ? 1 : 0
  
  service_account_id = google_service_account.supervisor_agent[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[supervisor-agent/supervisor-agent]"
}

resource "google_project_iam_member" "supervisor_agent" {
  count = var.cloud_provider == "gcp" ? length(local.supervisor_agent_roles) : 0
  
  project = var.project_id
  role    = local.supervisor_agent_roles[count.index]
  member  = "serviceAccount:${google_service_account.supervisor_agent[0].email}"
}

locals {
  supervisor_agent_roles = [
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/storage.objectViewer"
  ]
}