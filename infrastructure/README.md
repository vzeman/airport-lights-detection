# AWS Infrastructure Setup

This directory contains scripts to set up AWS infrastructure for the Airport Management System.

## Prerequisites

1. **AWS CLI installed**
   ```bash
   # macOS
   brew install awscli

   # Linux
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   ```

2. **jq installed** (for JSON parsing)
   ```bash
   # macOS
   brew install jq

   # Linux
   sudo apt-get install jq
   ```

3. **AWS Admin Credentials**
   - You need an AWS user with admin permissions to run the setup script
   - This is a ONE-TIME setup

## Setup Instructions

### Step 1: Configure AWS CLI with Admin Credentials

```bash
aws configure
```

Enter your admin credentials:
- AWS Access Key ID: `AKIAWO5JVUDXECMQPIJ4`
- AWS Secret Access Key: `[your secret key]`
- Default region: `us-east-1`
- Default output format: `json`

### Step 2: Run the Setup Script

```bash
cd infrastructure
chmod +x aws-setup.sh
./aws-setup.sh
```

The script will:
1. Create S3 bucket `airport-mgmt-storage`
2. Configure encryption, versioning, and lifecycle policies
3. Create IAM user `airport-mgmt-app` with minimal S3 permissions
4. Generate new access keys for the app

### Step 3: Save the Generated Credentials

The script will output something like:

```
🔐 CREDENTIALS (SAVE THESE SECURELY!)

Add these to your .env file:

AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=airport-mgmt-storage
USE_S3_STORAGE=true
```

Copy these values to `backend/.env` (create from `backend/.env.example`)

### Step 4: Remove Admin Credentials

After setup is complete, remove the admin credentials from your AWS CLI:

```bash
# Remove credentials
rm ~/.aws/credentials

# Or configure a different profile
aws configure --profile default
```

**IMPORTANT**: The admin key (`AKIAWO5JVUDXECMQPIJ4`) should only be used for this one-time setup. The application will use the new `airport-mgmt-app` user credentials.

## What Gets Created

### S3 Bucket Structure
```
s3://airport-mgmt-storage/
├── videos/
│   ├── original/{session_id}/original.mp4
│   └── processed/{session_id}/enhanced.mp4
├── frames/{session_id}/measurements.json.gz
├── reports/{session_id}/report.pdf
└── temp/{session_id}/processing_*.tmp
```

### IAM Policy Permissions

The `airport-mgmt-app` user can only:
- List objects in the bucket
- Get/Put/Delete objects in the bucket
- Cannot modify bucket settings
- Cannot access other AWS services

### Lifecycle Policies

- **Temp files**: Deleted after 7 days
- **Processed videos**: Moved to Glacier after 90 days
- **Frame measurements**: Moved to Standard-IA after 30 days, then Glacier after 180 days

## Testing the Setup

```bash
# Test with the new app credentials
export AWS_ACCESS_KEY_ID="[from script output]"
export AWS_SECRET_ACCESS_KEY="[from script output]"

# List bucket contents
aws s3 ls s3://airport-mgmt-storage/

# Upload a test file
echo "test" > /tmp/test.txt
aws s3 cp /tmp/test.txt s3://airport-mgmt-storage/temp/test.txt

# Download it back
aws s3 cp s3://airport-mgmt-storage/temp/test.txt /tmp/test-download.txt

# Delete it
aws s3 rm s3://airport-mgmt-storage/temp/test.txt
```

## Security Best Practices

1. **Never commit credentials to git**
   - The `.env` file is in `.gitignore`
   - Use `.env.example` as a template only

2. **Rotate keys regularly**
   - Delete old access keys after creating new ones
   - Maximum 2 keys per user

3. **Use IAM roles in production**
   - For EC2/ECS deployments, use IAM roles instead of access keys
   - Roles are more secure and don't require credential management

4. **Monitor CloudTrail**
   - Enable CloudTrail to track all S3 API calls
   - Set up alerts for unusual activity

## Troubleshooting

### Error: "AccessDenied" when creating bucket
- Ensure your admin credentials have `s3:CreateBucket` permission
- Check if the bucket name is already taken (must be globally unique)

### Error: "User already exists"
- The script handles this gracefully
- If you need to start fresh, delete the user manually:
  ```bash
  aws iam delete-user --user-name airport-mgmt-app
  ```

### Error: "Too many access keys"
- Delete old keys first:
  ```bash
  aws iam list-access-keys --user-name airport-mgmt-app
  aws iam delete-access-key --user-name airport-mgmt-app --access-key-id [OLD_KEY_ID]
  ```

## Cost Estimation

For 100 video sessions/month (~20GB total):
- S3 Standard: ~$0.50/month
- S3 Standard-IA (after 30 days): ~$0.25/month
- Glacier (after 90 days): ~$0.08/month
- Data transfer: ~$2-5/month
- **Total**: ~$3-6/month

Much cheaper than storing everything in MySQL/RDS!
