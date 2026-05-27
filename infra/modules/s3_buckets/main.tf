variable "env"    { type = string }
variable "prefix" { type = string }

locals {
  layers = {
    bronze    = { lifecycle_days = 90  }   # raw data — keep 90 days then IA
    silver    = { lifecycle_days = 365 }   # cleaned — keep 1 year
    gold      = { lifecycle_days = 730 }   # features — keep 2 years
    artifacts = { lifecycle_days = 365 }   # model artefacts
  }
}

resource "aws_s3_bucket" "medallion" {
  for_each = local.layers
  bucket   = "${var.prefix}-${each.key}-${var.env}"
}

resource "aws_s3_bucket_versioning" "medallion" {
  for_each = aws_s3_bucket.medallion
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "medallion" {
  for_each = aws_s3_bucket.medallion
  bucket   = each.value.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

# ── Cost optimisation: intelligent tiering → auto moves cold data to IA/Glacier
resource "aws_s3_bucket_intelligent_tiering_configuration" "medallion" {
  for_each = aws_s3_bucket.medallion
  bucket   = each.value.id
  name     = "AutoTier"
  status   = "Enabled"
  tiering {
    access_tier = "DEEP_ARCHIVE_ACCESS"
    days        = local.layers[each.key].lifecycle_days
  }
}

# Block all public access — no exceptions
resource "aws_s3_bucket_public_access_block" "medallion" {
  for_each                = aws_s3_bucket.medallion
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "bronze_bucket_arn"  { value = aws_s3_bucket.medallion["bronze"].arn }
output "bronze_bucket_name" { value = aws_s3_bucket.medallion["bronze"].bucket }
output "silver_bucket_arn"  { value = aws_s3_bucket.medallion["silver"].arn }
output "silver_bucket_name" { value = aws_s3_bucket.medallion["silver"].bucket }
output "gold_bucket_arn"    { value = aws_s3_bucket.medallion["gold"].arn }
output "gold_bucket_name"   { value = aws_s3_bucket.medallion["gold"].bucket }
