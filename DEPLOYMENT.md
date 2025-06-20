# Gmail Service Account Deployment Guide

## Overview

The SalesShortcut application now uses Gmail service account authentication for automated email sending. This eliminates the need for manual OAuth authentication and makes the system fully automated.

## Local Development Setup

### 1. Service Account JSON File
- Place your `sales-automation-service.json` file in the `.secrets/` directory
- The file should be already configured with domain-wide delegation
- Make sure the service account has the following Gmail API scopes:
  - `https://www.googleapis.com/auth/gmail.send`
  - `https://www.googleapis.com/auth/gmail.readonly`
  - `https://www.googleapis.com/auth/gmail.modify`

### 2. Environment Variables
```bash
# Optional: Override default service account file path
SERVICE_ACCOUNT_FILE=.secrets/sales-automation-service.json

# Required: Email to send from (must be in your domain)
SALES_EMAIL=sales@zemzen.org
```

## Cloud Deployment Options

### Option 1: Using GOOGLE_APPLICATION_CREDENTIALS Environment Variable

1. **Upload service account JSON to your cloud environment**
2. **Set environment variable:**
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/sales-automation-service.json
   SALES_EMAIL=sales@zemzen.org
   ```

### Option 2: Using Cloud Run with Attached Service Account (Recommended)

1. **Create a service account in Google Cloud Console**
2. **Grant the service account Gmail API permissions**
3. **Attach the service account to your Cloud Run service**
4. **Set environment variables:**
   ```bash
   SALES_EMAIL=sales@zemzen.org
   ```

The application will automatically use default credentials from the attached service account.

### Option 3: Using Kubernetes with Workload Identity

1. **Set up Workload Identity**
2. **Configure service account binding**
3. **Deploy with environment variables:**
   ```bash
   SALES_EMAIL=sales@zemzen.org
   ```

## Security Best Practices

### For Cloud Deployment:
- ✅ Use attached service accounts (Option 2) instead of JSON files
- ✅ Rotate service account keys regularly if using JSON files
- ✅ Limit service account permissions to minimum required scopes
- ✅ Use environment variables for configuration
- ❌ Never commit service account JSON files to version control

### For Local Development:
- ✅ Keep service account JSON files in `.secrets/` directory (gitignored)
- ✅ Use environment variables for sensitive configuration
- ✅ Regularly rotate service account keys

## Troubleshooting

### Common Issues:

1. **"Service account file not found"**
   - Ensure the JSON file is in the correct location
   - Check file permissions
   - Verify the file path in environment variables

2. **"Domain-wide delegation not configured"**
   - Ensure the service account has domain-wide delegation enabled
   - Verify the service account has been authorized in Google Workspace Admin Console

3. **"Insufficient permissions"**
   - Check that the service account has the required Gmail API scopes
   - Verify the service account has been granted necessary permissions

4. **"Authentication failed in cloud"**
   - Verify the service account is properly attached to your cloud service
   - Check that GOOGLE_APPLICATION_CREDENTIALS points to the correct file
   - Ensure the service account has the required IAM roles

## Testing

### Local Testing:
```bash
# Test email sending
python -c "
from sdr.sdr.sub_agents.outreach_email_agent.tools.gmail_service_account_tool import send_email_with_attachment
result = send_email_with_attachment('meinnps@gmail.com', 'Test Subject', 'Test Body')
print(result)
"
```

### Cloud Testing:
Deploy to your cloud environment and test the email sending functionality through your application's normal workflow.

## Migration Notes

### From GmailToolset to Service Account:
- ✅ No more manual OAuth authentication required
- ✅ Fully automated email sending
- ✅ Better security with service account delegation
- ✅ Easier cloud deployment
- ✅ Supports attachments (PDFs, images, etc.)

The migration maintains backward compatibility while providing improved automation and security.