# 📅 Crontab Setup Guide for End of Day Automation

This guide explains how to set up automated end-of-day reporting using crontab with the enhanced `end_of_day.sh` script.

## 🚀 **Quick Setup**

### **1. Test the Script**
First, test the automated mode manually:
```bash
# Test automated mode
./scripts/end_of_day.sh --automated

# Test cron mode (simulates cron environment)
./scripts/end_of_day.sh --cron
```

### **2. Set Up Crontab**
```bash
# Edit your crontab
crontab -e

# Add one of these lines for automated end-of-day reporting:

# Daily at 5:00 PM (Monday-Friday)
0 17 * * 1-5 /home/kmccullor/Projects/Technical-Service-Assistant/scripts/end_of_day.sh

# Daily at 6:00 PM (every day)
0 18 * * * /home/kmccullor/Projects/Technical-Service-Assistant/scripts/end_of_day.sh

# Daily at 5:30 PM with email notifications (Monday-Friday)
30 17 * * 1-5 EOD_EMAIL=your.email@company.com /home/kmccullor/Projects/Technical-Service-Assistant/scripts/end_of_day.sh
```

### **3. View Cron Jobs**
```bash
# List current cron jobs
crontab -l

# View cron logs (varies by system)
sudo tail -f /var/log/cron
# or
journalctl -f -u cron
```

---

## ⚙️ **Configuration Options**

### **Environment Variables**
Set these in your crontab or shell profile for notifications:

```bash
# Email notifications (Python-based email system)
export EOD_EMAIL="admin@company.com"                    # Recipient email
export EOD_SENDER_EMAIL="sender@company.com"            # Your email address
export EOD_SENDER_PASSWORD="your_app_password"          # App password (Gmail) or regular password

# Optional SMTP settings (auto-detected if not set)
export SMTP_SERVER="smtp.gmail.com"                     # SMTP server
export SMTP_PORT="587"                                   # SMTP port
export SMTP_TLS="true"                                   # Use TLS

# Slack/Teams webhook
export EOD_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### **Crontab with Environment Variables**
```bash
# In crontab -e, add variables at the top:
EOD_EMAIL=admin@company.com
EOD_SENDER_EMAIL=sender@company.com
EOD_SENDER_PASSWORD=your_app_password
EOD_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
PATH=/usr/local/bin:/usr/bin:/bin

# Then add the scheduled job:
0 17 * * 1-5 /home/kmccullor/Projects/Technical-Service-Assistant/scripts/end_of_day.sh
```

---

## 📊 **What the Automated Script Does**

### **Health Checks**
- ✅ Tests reranker service (port 8008)
- ✅ Validates PostgreSQL database connection
- ✅ Checks all 4 Ollama instances (ports 11434-11437)
- ✅ Verifies RAG application (port 3000)

### **Performance Tests**
- ⚡ Runs RAG validation framework benchmarks
- ⚡ Measures API response times
- ⚡ Collects system resource metrics

### **Report Generation**
- 📊 Creates comprehensive daily report
- 📸 Generates system snapshot (JSON format)
- 🧹 Cleans up old log files (30+ days)
- 📧 Sends notifications (if configured)

### **Files Generated**
```
logs/
├── daily_report_YYYYMMDD.md          # Main daily report
├── end_of_day_automation_YYYYMMDD.log # Automation log
├── health_check_YYYYMMDD.log          # Health check results
├── performance_test_YYYYMMDD.log      # Performance metrics
└── system_snapshot_YYYYMMDD.json     # System state snapshot
```

---

## 🔧 **Advanced Crontab Examples**

### **Business Hours Only (9 AM - 6 PM)**
```bash
# Monday-Friday at 6 PM
0 18 * * 1-5 /path/to/Technical-Service-Assistant/scripts/end_of_day.sh

# Multiple times per day
0 12 * * 1-5 /path/to/script/end_of_day.sh  # Lunch time check
0 18 * * 1-5 /path/to/script/end_of_day.sh  # End of day
```

### **Weekend Monitoring**
```bash
# Weekend checks (reduced frequency)
0 20 * * 6,0 /path/to/Technical-Service-Assistant/scripts/end_of_day.sh
```

### **High-Frequency Monitoring**
```bash
# Every 4 hours during business days
0 */4 * * 1-5 /path/to/Technical-Service-Assistant/scripts/end_of_day.sh
```

---

## � **Email Setup (Quick Start)**

### **1. Automated Email Configuration**
Run the interactive setup script:
```bash
./setup_email.sh
```

This will:
- Configure your sender email and password
- Set recipient email address
- Test the email configuration
- Generate environment variables for crontab

### **2. Manual Email Configuration**
```bash
# Test email functionality
python email_eod_report.py --test your.email@company.com

# Send actual report
python email_eod_report.py your.email@company.com

# Send specific report file
python email_eod_report.py your.email@company.com logs/daily_report_20251001.md
```

### **3. Gmail App Password Setup**
For Gmail users:
1. Enable 2-Factor Authentication
2. Go to Google Account settings → Security → App passwords
3. Generate app password for "Mail"
4. Use this app password (not your regular password)

---

## �🚨 **Notification Setup**

### **Slack Integration**
1. Create a Slack webhook URL
2. Set environment variable:
   ```bash
   export EOD_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   ```
3. Add to crontab:
   ```bash
   EOD_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   0 17 * * 1-5 /path/to/script/end_of_day.sh
   ```

### **Email Notifications**
Requires `mail` command installed:
```bash
# Install mail utility (Ubuntu/Debian)
sudo apt-get install mailutils

# Install mail utility (RHEL/CentOS)
sudo yum install mailx

# Set email in crontab
EOD_EMAIL=admin@company.com
0 17 * * 1-5 /path/to/script/end_of_day.sh
```

---

## 🐛 **Troubleshooting**

### **Common Issues**

**1. Script not executing from cron:**
```bash
# Check cron is running
sudo systemctl status cron

# Verify script permissions
ls -la /path/to/Technical-Service-Assistant/scripts/end_of_day.sh

# Should show: -rwxr-xr-x (executable)
```

**2. Path issues in cron:**
```bash
# Add PATH to crontab
PATH=/usr/local/bin:/usr/bin:/bin
```

**3. Docker not available in cron:**
```bash
# Add docker group to PATH or use full path
/usr/bin/docker ps
```

**4. Check cron logs:**
```bash
# View cron execution logs
grep CRON /var/log/syslog
# or
journalctl -u cron
```

### **Testing Cron Environment**
```bash
# Test with cron environment simulation
env -i bash -c 'cd /path/to/project && ./scripts/end_of_day.sh --cron'

# Test with minimal environment
env -i PATH=/usr/bin:/bin ./scripts/end_of_day.sh --automated
```

---

## 📈 **Monitoring and Maintenance**

### **Log Rotation**
The script automatically cleans logs older than 30 days. For additional log management:
```bash
# Manual cleanup
find logs/ -name "*.log" -mtime +30 -delete

# Check log disk usage
du -sh logs/
```

### **Performance Monitoring**
```bash
# View recent performance trends
grep "Performance" logs/end_of_day_automation_*.log | tail -20

# Check system health trends
grep "HEALTHY\|DEGRADED\|CRITICAL" logs/end_of_day_automation_*.log | tail -10
```

### **Report Analysis**
```bash
# View latest report
cat logs/daily_report_$(date +%Y%m%d).md

# Check system snapshots
ls -la logs/system_snapshot_*.json | tail -5
```

---

## 🎯 **Best Practices**

1. **Test First**: Always test the automated mode manually before setting up cron
2. **Set Notifications**: Configure email or webhook notifications for critical issues
3. **Monitor Logs**: Regularly check automation logs for issues
4. **Backup Configuration**: Keep crontab backed up (`crontab -l > crontab_backup.txt`)
5. **Resource Limits**: Monitor script resource usage during peak times
6. **Security**: Use minimal permissions and secure webhook URLs

---

## 📋 **Example Complete Setup**

```bash
# 1. Test the script
cd /home/kmccullor/Projects/Technical-Service-Assistant
./scripts/end_of_day.sh --automated

# 2. Set up crontab with notifications
crontab -e

# Add these lines:
MAILTO=""
EOD_EMAIL=admin@company.com
EOD_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
PATH=/usr/local/bin:/usr/bin:/bin

# End of day report Monday-Friday at 5 PM
0 17 * * 1-5 /home/kmccullor/Projects/Technical-Service-Assistant/scripts/end_of_day.sh

# 3. Verify setup
crontab -l

# 4. Monitor first run
tail -f logs/end_of_day_automation_$(date +%Y%m%d).log
```

---

**Status**: ✅ Ready for automated end-of-day reporting
**Next Steps**: Set up crontab and configure notifications as needed
