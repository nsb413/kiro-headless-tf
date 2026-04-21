resource "aws_dynamodb_table" "books" {
  name         = "${var.project_name}-books-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-books-${var.environment}"
  }
}
