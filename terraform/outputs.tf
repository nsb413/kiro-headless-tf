output "api_endpoint" {
  description = "Base URL of the API"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.books.name
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.api.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.api.arn
}

output "dynamodb_table_arn" {
  description = "DynamoDB table ARN"
  value       = aws_dynamodb_table.books.arn
}
