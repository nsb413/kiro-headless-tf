# Kiro Headless Terraform

Automated Terraform plan/apply workflows with AI-powered plan summaries using [Kiro CLI headless mode](https://kiro.dev/docs/cli/headless/).

On every pull request that touches `.tf` or `.tfvars` files, GitHub Actions runs `terraform plan`, feeds the output to a Kiro AI agent, and posts a human-friendly summary as a PR comment. On merge to `main`, it runs `terraform apply`.

## Repository Structure

```
.
├── cloudformation/
│   └── github-oidc-terraform.yml       # CFN stack: OIDC provider, IAM role, S3 state bucket
├── .github/workflows/
│   ├── terraform-plan.yml              # PR workflow: plan + Kiro summary comment
│   └── terraform-apply.yml             # Merge workflow: apply with environment gate
├── .kiro/agents/
│   ├── terraform-reviewer.json         # Custom Kiro agent config
│   └── prompts/
│       └── terraform-reviewer.md       # Agent prompt for plan summarization
└── terraform/
    ├── provider.tf                     # AWS provider + S3 backend config
    ├── variables.tf                    # Input variables
    ├── dynamodb.tf                     # DynamoDB table for books
    ├── lambda.tf                       # Lambda function + IAM role
    ├── apigateway.tf                   # HTTP API Gateway with CRUD routes
    ├── outputs.tf                      # API endpoint, table name, function name
    └── lambda/
        └── index.py                    # Python CRUD handler
```

## Prerequisites

- An AWS account with permissions to create IAM roles, OIDC providers, and S3 buckets
- A [Kiro](https://kiro.dev) Pro, Pro+, or Power subscription (required for API keys)
- Terraform >= 1.10 (for `use_lockfile` support)

## Deployment Guide

### Step 1 — Deploy the CloudFormation Stack

The stack creates:
- A GitHub OIDC identity provider (so GitHub Actions can authenticate without static AWS keys)
- An IAM role scoped to the `nsb413/kiro-headless-tf` repo
- An S3 bucket for Terraform state (versioned, encrypted, public access blocked)
- IAM policies for state backend access and infrastructure provisioning

```bash
aws cloudformation deploy \
  --template-file cloudformation/github-oidc-terraform.yml \
  --stack-name github-oidc-terraform \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

If you already have a GitHub OIDC provider in this AWS account, edit the template and change the `CreateOIDCProvider` condition to `!Equals ["true", "false"]` before deploying.

To customize parameters:

```bash
aws cloudformation deploy \
  --template-file cloudformation/github-oidc-terraform.yml \
  --stack-name github-oidc-terraform \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2 \
  --parameter-overrides \
    GitHubOrg=nsb413 \
    GitHubRepo=kiro-headless-tf \
    TerraformStateBucketName=my-custom-bucket-name \
    TerraformStateKey=terraform.tfstate
```

### Step 2 — Get the Stack Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name github-oidc-terraform \
  --query "Stacks[0].Outputs" \
  --output table
```

Note the following values:
- **RoleArn** — the IAM role ARN for GitHub Actions
- **StateBucketName** — the S3 bucket for Terraform state
- **TerraformBackendConfig** — ready-to-paste backend block

### Step 3 — Configure GitHub Secrets

Go to your repository **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `KIRO_API_KEY` | Your Kiro API key ([generate one here](https://app.kiro.dev/)) |

> `GITHUB_TOKEN` is provided automatically by GitHub Actions — no setup needed.
>
> AWS credentials are handled via OIDC — no AWS secrets required.

### Step 4 — Set the IAM Role ARN in Workflows

Open both workflow files and set the `IAM_ROLE_ARN` env variable to the `RoleArn` value from Step 2:

**.github/workflows/terraform-plan.yml**
```yaml
env:
  TF_WORKING_DIR: "terraform"
  AWS_REGION: "us-west-2"
  IAM_ROLE_ARN: "arn:aws:iam::123456789012:role/github-actions-kiro-headless-tf"
```

**.github/workflows/terraform-apply.yml**
```yaml
env:
  TF_WORKING_DIR: "terraform"
  AWS_REGION: "us-west-2"
  IAM_ROLE_ARN: "arn:aws:iam::123456789012:role/github-actions-kiro-headless-tf"
```

### Step 5 — Verify the Terraform Backend

The backend is already configured in `terraform/provider.tf`. If you changed the bucket name or state key during the CloudFormation deployment, update the backend block to match:

```hcl
terraform {
  backend "s3" {
    bucket       = "nsb413-kiro-headless-tf-state"
    key          = "terraform.tfstate"
    region       = "us-west-2"
    use_lockfile = true
    encrypt      = true
  }
}
```

State locking uses S3-native lockfiles (`use_lockfile = true`) — no DynamoDB table needed. Terraform writes a `.tflock` object alongside the state file in the same bucket.

### Step 6 — (Optional) Configure Environment Protection

The apply workflow uses a `production` environment gate. To require manual approval before applies:

1. Go to **Settings → Environments → New environment**
2. Name it `production`
3. Check **Required reviewers** and add approvers
4. Save

### Step 7 — Deploy the Infrastructure

Push to a branch and open a PR to trigger the plan workflow:

```bash
git checkout -b add-infrastructure
git add .
git commit -m "Add CRUD API with API Gateway, Lambda, and DynamoDB"
git push -u origin add-infrastructure
```

Open a PR against `main`. The **Terraform Plan** workflow will run and Kiro will post a summary comment showing the resources to be created:
- 1 DynamoDB table
- 1 Lambda function + IAM role
- 1 HTTP API Gateway with 5 routes
- CloudWatch log groups

After reviewing the plan summary, merge the PR. The **Terraform Apply** workflow will deploy everything (after environment approval if configured).

### Step 8 — Get the API Endpoint

After the apply completes, you can find the API endpoint in the Terraform outputs. Run locally (or check the workflow logs):

```bash
cd terraform
terraform output api_endpoint
```

The output will look like: `https://abc123def4.execute-api.us-west-2.amazonaws.com`

## Testing the API

Set the API endpoint as a variable for convenience:

```bash
export API_URL="https://abc123def4.execute-api.us-west-2.amazonaws.com"
```

### Create a book

```bash
curl -s -X POST "$API_URL/books" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Dune",
    "author": "Frank Herbert",
    "year": 1965,
    "genre": "Science Fiction"
  }' | jq .
```

Response:
```json
{
  "id": "a1b2c3d4-...",
  "title": "Dune",
  "author": "Frank Herbert",
  "year": 1965,
  "genre": "Science Fiction",
  "createdAt": "2026-04-21T12:00:00+00:00",
  "updatedAt": "2026-04-21T12:00:00+00:00"
}
```

### List all books

```bash
curl -s "$API_URL/books" | jq .
```

### Get a single book

```bash
curl -s "$API_URL/books/{id}" | jq .
```

### Update a book

```bash
curl -s -X PUT "$API_URL/books/{id}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Dune Messiah",
    "year": 1969
  }' | jq .
```

### Delete a book

```bash
curl -s -X DELETE "$API_URL/books/{id}" | jq .
```

### Notes

- Replace `{id}` with the actual `id` value returned from the create call.
- The data model is flexible — you can pass any fields you want (title, author, price, isbn, etc.). The only managed fields are `id`, `createdAt`, and `updatedAt`.
- If you don't provide an `id` on create, one is auto-generated as a UUID.

## How It Works

### PR Workflow (`terraform-plan.yml`)

1. Checks out the code and authenticates to AWS via OIDC
2. Runs `terraform init` and `terraform plan`
3. Installs Kiro CLI and runs the `terraform-reviewer` agent in headless mode
4. The agent reads the plan output and produces a markdown summary
5. Posts (or updates) the summary as a PR comment
6. Fails the check if the plan itself failed

### Merge Workflow (`terraform-apply.yml`)

1. Triggered on push to `main` when `.tf`/`.tfvars` files change
2. Requires approval via the `production` environment gate
3. Authenticates via OIDC and runs `terraform apply -auto-approve`

### Kiro Agent

The `terraform-reviewer` agent is configured in `.kiro/agents/terraform-reviewer.json` with a detailed prompt in `.kiro/agents/prompts/terraform-reviewer.md`. It produces summaries that include:

- Change overview table (creates, updates, destroys, replacements)
- Per-resource change details
- Warnings for destructive or security-relevant changes
- Actionable recommendations

## Customization

- **Terraform directory**: Update `TF_WORKING_DIR` in both workflow files (currently set to `terraform`)
- **AWS region**: Update `AWS_REGION` in both workflow files and `aws_region` in `terraform/variables.tf`
- **Terraform version**: Uncomment and set `terraform_version` in the `setup-terraform` step
- **IAM permissions**: Tighten the `TerraformProvisioning` policy in the CFN template to only the services you use
- **Agent prompt**: Edit `.kiro/agents/prompts/terraform-reviewer.md` to match your team's review standards
- **Data model**: The Lambda handler accepts any JSON fields — adapt it for orders, users, products, etc.
- **API auth**: The API Gateway has no auth by default. Add a JWT authorizer or API key for production use

## License

MIT
