# Gmail Setup Guide for Enhanced EOD Reporting

## Overview
The enhanced EOD email system automatically detects Gmail addresses and configures the appropriate SMTP settings. You just need to set up authentication.

## Gmail Authentication Setup

### Step 1: Enable 2-Factor Authentication
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Factor Authentication if not already enabled

### Step 2: Generate App-Specific Password
1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Select "Mail" and "Other (custom name)"
3. Enter "Technical Service Assistant" as the app name
4. Copy the generated 16-character password (e.g., `abcd efgh ijkl mnop`)

### Step 3: Configure Environment Variable
```bash
# Option 1: Set environment variable (temporary)
export EOD_SENDER_PASSWORD="your-app-specific-password"

# Option 2: Add to your .bashrc for persistence
echo 'export EOD_SENDER_PASSWORD="your-app-specific-password"' >> ~/.bashrc
source ~/.bashrc

# Option 3: Use secure storage (recommended)
python secure_file_email.py store kmccullor@gmail.com
```

## Testing Your Configuration

### Test Mode (No Email Sent)
```bash
python email_eod_report.py --test kmccullor@gmail.com
```

### Send Actual Email
```bash
python email_eod_report.py kmccullor@gmail.com
```

## Expected Output

### Successful Configuration
```
📧 Auto-configured Gmail sender: kmccullor@gmail.com
📧 Connecting to smtp.gmail.com:587...
✅ Email sent successfully!
   From: kmccullor@gmail.com
   To: kmccullor@gmail.com
   Subject: Technical Service Assistant - End of Day Report (2025-10-08)
```

### What You'll Receive
The email will contain:
- **System Health Overview**: Container status, document counts, resource usage
- **Live Monitoring Metrics**: Prometheus data, alert status, performance metrics
- **Documentation Statistics**: File counts, recent changes, markdown analytics
- **Development Activity**: Git status, commits, file changes
- **Daily Accomplishments**: Processing metrics, backup status
- **Issues & Recommendations**: System warnings and actionable items

## Automated Daily Reports

### Set up Cron Job (Already Configured!)
Your cron job is already set up:
```bash
# Current cron job (runs daily at 8 PM)
0 20 * * * source /home/kmccullor/.technical-service-env && cd /home/kmccullor/Projects/Technical-Service-Assistant && ./automated_daily_email.sh >> logs/automated_email.log 2>&1
```

To test or modify:
```bash
# View current cron jobs
crontab -l

# Edit cron jobs
crontab -e

# Test your setup
./test_gmail_setup.sh
```

## Security Best Practices

1. **Never store passwords in scripts or config files**
2. **Use environment variables or secure storage**
3. **Regularly rotate app-specific passwords**
4. **Monitor Gmail security alerts**

## Troubleshooting

### "Authentication failed" Error
- Verify your app-specific password is correct
- Ensure 2FA is enabled on your Google account
- Try generating a new app-specific password

### "Connection refused" Error
- Check your internet connection
- Verify Gmail SMTP isn't blocked by firewall
- Try using port 465 with SSL instead of 587 with TLS

### "Password not set" Error
- Ensure `EOD_SENDER_PASSWORD` environment variable is set
- Or use secure storage with `secure_file_email.py`

## Advanced Configuration

### Custom SMTP Settings (Override Auto-detection)
```bash
export EOD_SMTP_SERVER="smtp.gmail.com"
export EOD_SMTP_PORT="587"
export EOD_SMTP_USE_TLS="true"
export EOD_SENDER_EMAIL="kmccullor@gmail.com"
```

### Integration with Company Email
The system also supports corporate email systems. See `EOD_REPORTING.md` for full configuration options.

## Support
- Check `EOD_REPORTING.md` for comprehensive documentation
- Review `ALERTING_SETUP.md` for monitoring configuration
- Test with `--test` flag before setting up automation
