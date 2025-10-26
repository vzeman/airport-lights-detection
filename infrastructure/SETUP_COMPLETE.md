# AWS S3 Setup Complete

## Setup Summary

Successfully configured AWS S3 storage for the Airport Management System on **October 25, 2025**.

### Resources Created

1. **S3 Bucket**: `airport-mgmt-storage-1761415525`
   - Region: `eu-central-1` (Frankfurt)
   - Encryption: AES256 (enabled)
   - Versioning: Enabled
   - Public Access: Blocked

2. **IAM User**: `airport-mgmt-app`
   - Access Key ID: `AKIA...` (stored in .env)
   - Permissions: S3 bucket access only (least privilege)

3. **IAM Policy**: `AirportMgmtS3Policy`
   - Scope: Limited to the S3 bucket only
   - Actions: List, Get, Put, Delete objects

### Lifecycle Policies

Automated cost optimization through lifecycle policies:

- **Temp files** (`temp/`): Deleted after 7 days
- **Processed videos** (`videos/processed/`): Moved to Glacier after 90 days
- **Frame measurements** (`frames/`): Moved to Standard-IA after 30 days

### CORS Configuration

Enabled CORS for:
- `http://localhost:3001`
- `http://localhost:3000`

Allowed methods: GET, HEAD

### Configuration Files

#### Environment Variables (`backend/.env`)
```env
USE_S3_STORAGE=true
AWS_ACCESS_KEY_ID=<your_access_key_id>
AWS_SECRET_ACCESS_KEY=<your_secret_access_key>
AWS_REGION=eu-central-1
S3_BUCKET=airport-mgmt-storage-1761415525
S3_PRESIGNED_URL_EXPIRATION=3600
```

### Bucket Structure

```
s3://airport-mgmt-storage-1761415525/
├── videos/
│   ├── original/{session_id}/
│   │   └── original.mp4
│   └── processed/{session_id}/
│       ├── enhanced.mp4
│       └── enhanced_with_audio.mp4
├── frames/
│   └── {session_id}/
│       └── measurements.json.gz  (compressed JSON)
├── reports/
│   └── {session_id}/
│       ├── report.pdf
│       └── report.html
└── temp/
    └── {session_id}/
        └── processing_*.tmp
```

### Testing Results

✓ S3 bucket access verified
✓ File upload capability tested
✓ File deletion capability tested

### Security Notes

1. **Admin credentials** were used only for setup with AWS CLI
2. **App credentials** have minimal permissions (stored in .env)
3. Credentials are stored in `.env` which is git-ignored
4. Never commit credentials to version control

### Cost Optimization

Expected monthly costs for 100 video sessions (~20GB):
- S3 Standard storage: ~$0.50/month
- S3 Standard-IA (after 30 days): ~$0.25/month
- Glacier (after 90 days): ~$0.08/month
- Data transfer out: ~$2-5/month
- **Total: ~$3-6/month** (vs ~$15-20/month for RDS storage)

### Next Steps

1. ✅ S3 bucket created in Frankfurt
2. ✅ IAM user and policy configured
3. ✅ Environment variables set
4. ⏳ Implement S3 storage service in backend
5. ⏳ Update video processing to use S3
6. ⏳ Migrate frame measurements to JSON/S3
7. ⏳ Update database schema
8. ⏳ Test end-to-end workflow

### Useful Commands

```bash
# List bucket contents
export AWS_PROFILE=airport-mgmt
aws s3 ls s3://airport-mgmt-storage-1761415525/

# Check bucket size
aws s3 ls s3://airport-mgmt-storage-1761415525/ --recursive --summarize

# Monitor lifecycle transitions
aws s3api get-bucket-lifecycle-configuration \
  --bucket airport-mgmt-storage-1761415525

# Generate presigned URL (1 hour expiration)
aws s3 presign s3://airport-mgmt-storage-1761415525/videos/processed/SESSION_ID/enhanced.mp4 \
  --expires-in 3600
```

### Troubleshooting

If you encounter access issues:
1. Verify credentials in `.env` match the ones above
2. Check AWS region is set to `eu-central-1`
3. Ensure IAM policy is attached to the user
4. Test with: `aws s3 ls s3://airport-mgmt-storage-1761415525/`

### Support

For issues or questions:
- Check: `infrastructure/README.md`
- AWS Documentation: https://docs.aws.amazon.com/s3/
- Boto3 Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
