resource "aws_dynamodb_table" "books" {
  name         = "${var.project_name}-books-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "author"
    type = "S"
  }

  global_secondary_index {
    name            = "author-index"
    hash_key        = "author"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "${var.project_name}-books-${var.environment}"
    ManagedBy   = "terraform"
  }
}
