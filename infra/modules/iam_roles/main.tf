variable "env"           { type = string }
variable "bronze_bucket" { type = string }
variable "silver_bucket" { type = string }
variable "gold_bucket"   { type = string }

# Least-privilege IAM role per environment
resource "aws_iam_role" "databricks" {
  name = "databricks-mlops-${var.env}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  name = "mlops-s3-${var.env}"
  role = aws_iam_role.databricks.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "MedallionReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket","s3:GetBucketLocation"]
        Resource = [
          "${var.bronze_bucket}/*", var.bronze_bucket,
          "${var.silver_bucket}/*", var.silver_bucket,
          "${var.gold_bucket}/*",   var.gold_bucket,
        ]
      },
      {
        Sid      = "DenyDeleteOnGold"
        Effect   = "Deny"
        Action   = ["s3:DeleteObject"]
        Resource = ["${var.gold_bucket}/*"]
        Condition = {
          StringNotEquals = { "aws:PrincipalTag/role": "admin" }
        }
      }
    ]
  })
}

output "databricks_role_arn" { value = aws_iam_role.databricks.arn }
