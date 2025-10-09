#!/bin/bash
# DEPRECATED: Use automated_daily_email.sh instead
# This script is maintained for compatibility but automated_daily_email.sh 
# provides enhanced functionality with:
# - Gmail auto-detection
# - Test mode support  
# - Improved error handling
# - Better cron integration
#
# To migrate: Use automated_daily_email.sh which calls scripts/end_of_day.sh internally
#
# Automated Daily Email Report - Secure Version
# This script can be safely added to crontab

cd /home/kmccullor/Projects/Technical-Service-Assistant

# Generate the daily report first
./scripts/end_of_day.sh --automated

# Send via secure email (will prompt for master password if run interactively)
python3 -c "
from secure_file_email import FileBasedSecureManager
import getpass, os
manager = FileBasedSecureManager()

# For automated use, you could store master password in a secure location
# For now, this requires interactive input
try:
    password = manager.get_password('kmccullor@gmail.com', getpass.getpass('Master password: '))
    if password:
        os.environ.update({
            'EOD_SENDER_EMAIL': 'kmccullor@gmail.com',
            'EOD_SMTP_SERVER': 'smtp.gmail.com',
            'EOD_SMTP_PORT': '587',
            'EOD_SMTP_USE_TLS': 'true',
            'EOD_SENDER_PASSWORD': password
        })
        # Find the latest report file
        import glob
        latest_report = max(glob.glob('/home/kmccullor/Projects/Technical-Service-Assistant/logs/daily_report_*.md'), key=os.path.getctime, default='')
        if latest_report:
            os.system(f'python email_eod_report.py kmccullor@gmail.com {latest_report}')
        else:
            os.system('python email_eod_report.py --generate-report kmccullor@gmail.com')
        print('✅ Daily report sent successfully!')
    else:
        print('❌ Failed to retrieve Gmail password')
except Exception as e:
    print(f'❌ Error: {e}')
"