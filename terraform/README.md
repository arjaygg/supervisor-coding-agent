# Infrastructure as Code for Supervisor Coding Agent

This directory contains Terraform modules for deploying the Supervisor Coding Agent across multiple cloud providers with enterprise-grade infrastructure.

## Architecture Overview

The infrastructure supports:
- **Multi-cloud deployment** (AWS, Azure, GCP)
- **High availability** with auto-scaling
- **Blue-green deployments** with zero downtime
- **Monitoring and observability** with comprehensive metrics
- **Security hardening** with network isolation
- **Cost optimization** with right-sizing recommendations

## Quick Start

```bash
# 1. Choose your cloud provider
cd environments/aws  # or azure, gcp

# 2. Configure variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings

# 3. Initialize and deploy
terraform init
terraform plan
terraform apply
```

## Directory Structure

```
terraform/
├── modules/                    # Reusable infrastructure modules
│   ├── kubernetes/            # EKS/AKS/GKE cluster setup
│   ├── database/              # PostgreSQL with HA
│   ├── redis/                 # Redis cluster
│   ├── monitoring/            # Prometheus/Grafana stack
│   ├── security/              # Security groups, IAM, etc.
│   └── networking/            # VPC, subnets, load balancers
├── environments/              # Environment-specific configurations
│   ├── development/           # Dev environment
│   ├── staging/              # Staging environment
│   └── production/           # Production environment
├── providers/                 # Cloud provider specific modules
│   ├── aws/                  # AWS-specific resources
│   ├── azure/                # Azure-specific resources
│   └── gcp/                  # GCP-specific resources
└── scripts/                  # Deployment and utility scripts
    ├── deploy.sh             # Automated deployment script
    ├── backup.sh             # Database backup automation
    └── rollback.sh           # Emergency rollback script
```

## Supported Cloud Providers

### AWS
- **Compute**: EKS with managed node groups
- **Database**: RDS PostgreSQL with Multi-AZ
- **Cache**: ElastiCache Redis
- **Storage**: EFS for shared storage
- **Networking**: VPC with public/private subnets
- **Security**: IAM roles, Security Groups, WAF

### Azure
- **Compute**: AKS with virtual machine scale sets
- **Database**: Azure Database for PostgreSQL
- **Cache**: Azure Cache for Redis
- **Storage**: Azure Files
- **Networking**: Virtual Network with NSGs
- **Security**: Azure AD, Key Vault, Application Gateway

### Google Cloud Platform
- **Compute**: GKE with auto-scaling node pools
- **Database**: Cloud SQL PostgreSQL with HA
- **Cache**: Memorystore for Redis
- **Storage**: Filestore
- **Networking**: VPC with Cloud Load Balancer
- **Security**: IAM, Cloud Armor, Cloud KMS

## Environment Management

### Development
- Single-zone deployment
- Smaller instance sizes
- Simplified networking
- Development-friendly settings

### Staging
- Multi-zone deployment
- Production-like configuration
- Blue-green deployment testing
- Performance testing environment

### Production
- Multi-region deployment
- High availability setup
- Auto-scaling enabled
- Full monitoring and alerting
- Disaster recovery configured

## Deployment Strategies

### Blue-Green Deployment
```bash
# Deploy to green environment
./scripts/deploy.sh --environment=production --color=green

# Test green environment
./scripts/test.sh --environment=production --color=green

# Switch traffic to green
./scripts/switch-traffic.sh --from=blue --to=green

# Cleanup old blue environment
./scripts/cleanup.sh --environment=production --color=blue
```

### Canary Deployment
```bash
# Deploy canary with 10% traffic
./scripts/deploy.sh --environment=production --strategy=canary --traffic=10

# Monitor metrics and errors
./scripts/monitor-canary.sh --duration=30m

# Promote to full deployment or rollback
./scripts/promote-canary.sh  # or ./scripts/rollback-canary.sh
```

## Security Features

- **Network Isolation**: Private subnets for application and database tiers
- **Encryption**: Data at rest and in transit encryption
- **Access Control**: IAM roles with least privilege principle
- **Secret Management**: Integration with cloud-native secret stores
- **Compliance**: SOC2, GDPR, HIPAA ready configurations
- **Monitoring**: Security event logging and alerting

## Monitoring and Observability

### Metrics Collection
- Application metrics via Prometheus
- Infrastructure metrics via cloud provider APIs
- Custom business metrics via StatsD

### Logging
- Centralized logging with ELK stack
- Structured JSON logging
- Log aggregation and analysis
- Security audit logs

### Alerting
- Slack/Email integration
- PagerDuty for critical alerts
- Custom alerting rules
- Escalation policies

### Dashboards
- Grafana dashboards for infrastructure
- Application performance monitoring
- Business metrics visualization
- Cost tracking and optimization

## Cost Optimization

### Right-Sizing
- Automated instance size recommendations
- CPU and memory utilization analysis
- Spot instance integration for non-critical workloads

### Auto-Scaling
- Horizontal pod autoscaling (HPA)
- Vertical pod autoscaling (VPA)
- Cluster autoscaling
- Schedule-based scaling

### Resource Management
- Resource quotas and limits
- Unused resource identification
- Cost allocation and tagging
- Budget alerts and limits

## Disaster Recovery

### Backup Strategy
- Automated database backups
- Cross-region backup replication
- Application state backup
- Configuration backup

### Recovery Procedures
- Point-in-time recovery
- Cross-region failover
- Data consistency verification
- Recovery time objective (RTO): 4 hours
- Recovery point objective (RPO): 1 hour

## Getting Started

1. **Prerequisites**
   ```bash
   # Install required tools
   brew install terraform kubectl helm
   
   # Configure cloud provider CLI
   aws configure  # or az login, gcloud auth login
   ```

2. **Configure Variables**
   ```bash
   cp environments/production/terraform.tfvars.example environments/production/terraform.tfvars
   # Edit terraform.tfvars with your specific configuration
   ```

3. **Deploy Infrastructure**
   ```bash
   cd environments/production
   terraform init
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

4. **Deploy Application**
   ```bash
   # Get Kubernetes config
   terraform output kubeconfig > kubeconfig
   export KUBECONFIG=./kubeconfig
   
   # Deploy application
   helm install supervisor-agent ../../helm/supervisor-agent
   ```

## Troubleshooting

### Common Issues

**Terraform State Conflicts**
```bash
# Force unlock if state is locked
terraform force-unlock <lock-id>

# Import existing resources
terraform import aws_instance.example i-1234567890abcdef0
```

**Kubernetes Connection Issues**
```bash
# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name supervisor-agent-cluster

# Verify connection
kubectl cluster-info
kubectl get nodes
```

**Database Connection Issues**
```bash
# Check security groups
aws ec2 describe-security-groups --group-ids sg-12345678

# Test database connectivity
psql -h <rds-endpoint> -U <username> -d supervisor_agent
```

## Best Practices

### Security
- Use separate AWS accounts/Azure subscriptions for different environments
- Enable CloudTrail/Activity Logs for audit trails
- Implement least privilege access policies
- Regular security scanning and updates

### Operations
- Use infrastructure versioning with Git tags
- Implement proper change management processes
- Monitor terraform plan output before applying
- Regular backup testing and disaster recovery drills

### Cost Management
- Regular cost reviews and optimization
- Use reserved instances for predictable workloads
- Implement proper resource tagging
- Monitor and alert on budget thresholds

## Support and Contributing

For issues and questions:
1. Check the troubleshooting section
2. Review cloud provider documentation
3. Open an issue in the project repository
4. Contact the infrastructure team

For contributing:
1. Follow the established patterns in existing modules
2. Include proper documentation and examples
3. Test changes in development environment first
4. Submit pull requests with detailed descriptions

---

**Note**: This infrastructure supports the Supervisor Coding Agent's enterprise deployment requirements with a focus on security, scalability, and operational excellence.