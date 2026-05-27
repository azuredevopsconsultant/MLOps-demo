terraform {
  required_version = ">= 1.7"
  required_providers {
    aws        = { source = "hashicorp/aws",         version = "~> 5.0" }
    databricks = { source = "databricks/databricks", version = "~> 1.40" }
  }

  # Remote state — never lose state, enables team collaboration
  backend "s3" {
    bucket         = "mlops-demo-tf-state"
    key            = "mlops/${var.env}/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "mlops-tf-locks"   # prevent concurrent apply races
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project    = "mlops-demo"
      ManagedBy  = "terraform"
      Environment = var.env
    }
  }
}

variable "env"           { default = "dev" }
variable "aws_region"    { default = "us-east-1" }
variable "bucket_prefix" { default = "mlops-demo" }

module "s3_buckets" {
  source = "./modules/s3_buckets"
  env    = var.env
  prefix = var.bucket_prefix
}

module "iam_roles" {
  source        = "./modules/iam_roles"
  env           = var.env
  bronze_bucket = module.s3_buckets.bronze_bucket_arn
  silver_bucket = module.s3_buckets.silver_bucket_arn
  gold_bucket   = module.s3_buckets.gold_bucket_arn
}

module "cost_controls" {
  source     = "./modules/cost_controls"
  env        = var.env
  aws_region = var.aws_region
}

output "bronze_bucket" { value = module.s3_buckets.bronze_bucket_name }
output "silver_bucket" { value = module.s3_buckets.silver_bucket_name }
output "gold_bucket"   { value = module.s3_buckets.gold_bucket_name }
