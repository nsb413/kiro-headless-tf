"""
CRUD API handler for DynamoDB-backed books resource.

Routes:
  GET    /books       - List all books
  GET    /books/{id}  - Get a single book
  POST   /books       - Create a book
  PUT    /books/{id}  - Update a book
  DELETE /books/{id}  - Delete a book
"""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}
    book_id = path_params.get("id")

    try:
        if method == "GET" and book_id:
            return get_book(book_id)
        elif method == "GET":
            return list_books()
        elif method == "POST":
            body = _parse_body(event)
            return create_book(body)
        elif method == "PUT" and book_id:
            body = _parse_body(event)
            return update_book(book_id, body)
        elif method == "DELETE" and book_id:
            return delete_book(book_id)
        else:
            return _response(404, {"error": "Not found"})
    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return _response(500, {"error": "Internal server error"})
    except (json.JSONDecodeError, ValueError) as e:
        return _response(400, {"error": str(e)})


# ---------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------

def list_books():
    result = table.scan()
    return _response(200, result.get("Items", []))


def get_book(book_id):
    result = table.get_item(Key={"id": book_id})
    item = result.get("Item")
    if not item:
        return _response(404, {"error": f"Book {book_id} not found"})
    return _response(200, item)


def create_book(body):
    if not body:
        raise ValueError("Request body is required")

    book_id = body.get("id", str(uuid.uuid4()))
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "id": book_id,
        "createdAt": now,
        "updatedAt": now,
    }
    # Merge caller-provided fields (title, author, etc.)
    for key, value in body.items():
        if key not in ("id", "createdAt", "updatedAt"):
            item[key] = value

    table.put_item(Item=item)
    return _response(201, item)


def update_book(book_id, body):
    if not body:
        raise ValueError("Request body is required")

    # Check the item exists
    existing = table.get_item(Key={"id": book_id}).get("Item")
    if not existing:
        return _response(404, {"error": f"Book {book_id} not found"})

    now = datetime.now(timezone.utc).isoformat()

    update_parts = []
    attr_names = {}
    attr_values = {":updatedAt": now}
    update_parts.append("#updatedAt = :updatedAt")
    attr_names["#updatedAt"] = "updatedAt"

    for key, value in body.items():
        if key in ("id", "createdAt"):
            continue
        safe_key = f"#f_{key}"
        safe_val = f":v_{key}"
        update_parts.append(f"{safe_key} = {safe_val}")
        attr_names[safe_key] = key
        attr_values[safe_val] = value

    result = table.update_item(
        Key={"id": book_id},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
        ReturnValues="ALL_NEW",
    )
    return _response(200, result.get("Attributes", {}))


def delete_book(book_id):
    # Check the item exists
    existing = table.get_item(Key={"id": book_id}).get("Item")
    if not existing:
        return _response(404, {"error": f"Book {book_id} not found"})

    table.delete_item(Key={"id": book_id})
    return _response(200, {"message": f"Book {book_id} deleted"})


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _parse_body(event):
    body = event.get("body", "")
    if not body:
        return {}
    return json.loads(body)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
