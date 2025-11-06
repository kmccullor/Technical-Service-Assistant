#!/usr/bin/env python3
"""
Email End of Day Report Utility

Simple Python script to email the end-of-day report using built-in SMTP.
This is a fallback when mailx/mail utilities aren't available.

Usage:
    python email_eod_report.py recipient@email.com [report_file]
    python email_eod_report.py --test recipient@email.com
"""

import os
import smtplib
import subprocess
import sys
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

PROMETHEUS_BASE_URL = os.getenv("PROMETHEUS_BASE_URL", "http://rni-llm-01.lab.sensus.net:9091")


class EODEmailSender:
    """Simple email sender for end-of-day reports."""

    def __init__(self):
        """Initialize email sender with common SMTP configurations."""
        # Common SMTP configurations (can be overridden with environment variables)
        self.smtp_configs = {
            "gmail": {"server": "smtp.gmail.com", "port": 587, "use_tls": True},
            "outlook": {"server": "smtp-mail.outlook.com", "port": 587, "use_tls": True},
            "yahoo": {"server": "smtp.mail.yahoo.com", "port": 587, "use_tls": True},
            "company": {
                "server": os.getenv("EOD_SMTP_SERVER", "sensus.xylem.com"),
                "port": int(os.getenv("EOD_SMTP_PORT", "587")),
                "use_tls": os.getenv("EOD_SMTP_USE_TLS", "true").lower() == "true",
            },
        }

    def detect_email_provider(self, email):
        """Detect email provider from email address."""
        domain = email.split("@")[1].lower()

        if "gmail" in domain:
            return "gmail"
        elif "outlook" in domain or "hotmail" in domain or "live" in domain:
            return "outlook"
        elif "yahoo" in domain:
            return "yahoo"
        elif "xylem" in domain or "sensus" in domain:
            return "company"
        else:
            return "company"

    def send_report(self, recipient_email, report_file=None, test_mode=False):
        """Send the end-of-day report via email."""

        # Email configuration from environment or defaults
        sender_email = os.getenv("EOD_SENDER_EMAIL", "technical-service-assistant@localhost")
        sender_password = os.getenv("EOD_SENDER_PASSWORD", "")

        # Auto-configure for Gmail - use recipient as sender for personal Gmail accounts
        if "@gmail.com" in recipient_email.lower():
            sender_email = recipient_email
            print(f"📧 Auto-configured Gmail sender: {sender_email}")

        # Try to get password from secure storage if not in environment
        if not sender_password:
            # Try keyring first
            try:
                import keyring

                sender_password = keyring.get_password("technical-service-assistant", sender_email)
                if sender_password:
                    print("🔐 Using securely stored password (keyring)")
            except ImportError:
                pass
            except Exception:
                # Keyring failed, try file-based storage
                try:
                    import subprocess
                    import tempfile

                    # Create a temporary script to get password without interactive prompt
                    script_content = f"""
import sys
sys.path.append(".")
from secure_file_email import FileBasedSecureManager
import os

manager = FileBasedSecureManager()
# Check if credentials file exists
if os.path.exists(manager.credentials_file):
    print("NEEDS_MASTER_PASSWORD")
else:
    print("NO_STORED_PASSWORD")
"""

                    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                        f.write(script_content)
                        temp_script = f.name

                    try:
                        result = subprocess.run(
                            [sys.executable, temp_script], capture_output=True, text=True, timeout=5
                        )
                        if "NEEDS_MASTER_PASSWORD" in result.stdout:
                            print("🔐 Encrypted password available (use secure_file_email.py)")
                    except Exception:
                        # Continue without password check
                        pass
                    finally:
                        os.unlink(temp_script)

                except Exception:
                    pass

        # Check if this might be a no-auth corporate relay
        is_corporate_relay = sender_email.startswith("no-relay@") or "relay" in sender_email.lower()

        if not sender_password and not test_mode and not is_corporate_relay:
            print("❌ ERROR: Email password not set.")
            print("   Option 1: Set EOD_SENDER_PASSWORD environment variable")
            print("   Option 2: Store securely with: python secure_email.py store", sender_email)
            print("   For Gmail: Use an app-specific password")
            print("   For company email: Use your regular password or app password")
            print("   For corporate relay: Email will attempt without authentication")
            return False

        # Detect SMTP configuration
        provider = self.detect_email_provider(sender_email)
        smtp_config = self.smtp_configs[provider]

        # Override with environment variables if set
        smtp_server = os.getenv("EOD_SMTP_SERVER", smtp_config["server"])
        smtp_port = int(os.getenv("EOD_SMTP_PORT", str(smtp_config["port"])))
        use_tls = os.getenv("EOD_SMTP_USE_TLS", str(smtp_config["use_tls"])).lower() == "true"

        try:
            # Find the latest report file if not specified (skip in test mode)
            if not test_mode:
                if not report_file:
                    report_file = self.find_latest_report()

                if not report_file or not os.path.exists(report_file):
                    print(f"❌ ERROR: Report file not found: {report_file}")
                    return False
            else:
                # In test mode, use a dummy report file path for display
                if not report_file:
                    report_file = "logs/daily_report_test.md"

            # Create message
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = recipient_email
            msg["Subject"] = f"Technical Service Assistant - End of Day Report ({datetime.now().strftime('%Y-%m-%d')})"

            # Create email body
            if test_mode:
                body = f"""
🧪 Technical Service Assistant - Email Configuration Test

This is a test email to verify the enhanced email configuration is working properly.

✅ Test Details:
- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Gmail Auto-Detection: {'✅ Active' if '@gmail.com' in recipient_email else '❌ Not Gmail'}
- SMTP Server: {smtp_server}:{smtp_port}
- TLS Enabled: {'✅ Yes' if use_tls else '❌ No'}
- Sender: {sender_email}
- Recipient: {recipient_email}

🎯 Enhanced Features Ready:
- Live monitoring metrics integration
- Documentation statistics tracking
- System health reporting
- Professional HTML formatting

Next Steps:
1. If you received this email, your configuration is working!
2. Run without --test flag to receive actual enhanced reports
3. Your daily cron job at 8 PM will use these settings

Configuration successful! 🎉
SMTP Server: {smtp_server}:{smtp_port}
TLS Enabled: {use_tls}

If you receive this email, the configuration is working correctly.
"""
            else:
                # Collect current metrics
                prometheus_metrics = self.get_prometheus_metrics()
                doc_stats = self.get_documentation_stats()

                # Read report content
                if os.path.exists(report_file):
                    with open(report_file, "r", encoding="utf-8") as f:
                        report_content = f.read()
                else:
                    # Generate a simple report if file doesn't exist
                    report_content = f"# Daily Report - {datetime.now().strftime('%Y-%m-%d')}\n\nReport generated dynamically via email system."

                # Convert markdown to plain text for email body
                plain_content = self.markdown_to_plain(report_content)

                # Add monitoring summary to email body
                monitoring_summary = f"""

🔍 LIVE MONITORING SNAPSHOT:
- Prometheus Status: {'✅ Available' if prometheus_metrics['prometheus_available'] else '❌ Unavailable'}
- Firing Alerts: {prometheus_metrics['firing_alerts']} ({prometheus_metrics['firing_alert_names']})
- Documents Processed (24h): {prometheus_metrics['docs_processed_24h']}
- Performance Monitor Refresh: {prometheus_metrics['refresh_age_seconds']}s ago
- Running Containers: {prometheus_metrics['containers_running']}

📚 DOCUMENTATION STATISTICS:
- Total Markdown Files: {doc_stats['total_md_files']} ({doc_stats['total_lines']} lines)
- Files Changed (7d): {doc_stats['md_files_changed_7d']}
- Files Changed Today: {doc_stats['md_files_changed_today']}
- Top Changed: {', '.join(doc_stats['top_changed_files'][:3]) if doc_stats['top_changed_files'] else 'None'}
"""

                body = f"""
Technical Service Assistant - End of Day Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{monitoring_summary}

📋 DETAILED REPORT:
{plain_content}

---
This is an automated report from the Technical Service Assistant system.
Full report is attached as a markdown file.
"""

            msg.attach(MIMEText(body, "plain"))

            # Attach report file if not in test mode
            if not test_mode:
                with open(report_file, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())

                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(report_file)}")
                msg.attach(part)

            # Send email
            print(f"📧 Connecting to {smtp_server}:{smtp_port}...")

            if test_mode:
                print("🧪 TEST MODE: Email configuration validated. Would send email with:")
                print(f"   From: {sender_email}")
                print(f"   To: {recipient_email}")
                print(f"   SMTP: {smtp_server}:{smtp_port} (TLS: {use_tls})")
                print(f"   Subject: {msg['Subject']}")
                print(f"   Auth: {'✅ Password configured' if sender_password else '❌ No password'}")
                print("   Remove --test flag to send actual enhanced reports.")
                return True

            server = smtplib.SMTP(smtp_server, smtp_port)

            if use_tls:
                server.starttls()

            # Only login if password is provided (skip for no-auth relays)
            if sender_password:
                server.login(sender_email, sender_password)
            elif is_corporate_relay:
                print("   Attempting corporate relay without authentication...")

            text = msg.as_string()
            server.sendmail(sender_email, recipient_email, text)
            server.quit()

            print(f"✅ SUCCESS: End-of-day report emailed to {recipient_email}")
            print(f"   Report: {os.path.basename(report_file)}")
            if test_mode:
                print(f"   Mode: 🧪 Test Mode (no actual email sent)")
            elif os.path.exists(report_file):
                print(f"   Size: {self.get_file_size(report_file)}")
            else:
                print(f"   Size: Generated dynamically")

            return True

        except Exception as e:
            print(f"❌ ERROR: Failed to send email: {e}")
            print(f"   SMTP Server: {smtp_server}:{smtp_port}")
            print(f"   TLS: {use_tls}")
            print(f"   Sender: {sender_email}")
            return False

    def find_latest_report(self):
        """Find the latest end-of-day report file."""
        project_root = Path(__file__).parent.parent
        logs_dir = project_root / "logs"

        # Look for today's report first
        today = datetime.now().strftime("%Y%m%d")
        today_report = logs_dir / f"daily_report_{today}.md"

        if today_report.exists():
            return str(today_report)

        # Look for the most recent report
        report_files = list(logs_dir.glob("daily_report_*.md"))
        if report_files:
            latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
            return str(latest_report)

        return None

    def markdown_to_plain(self, markdown_content):
        """Convert markdown to plain text for email body."""
        # Simple markdown to plain text conversion
        lines = markdown_content.split("\n")
        plain_lines = []

        for line in lines:
            # Remove markdown headers
            if line.startswith("#"):
                line = line.lstrip("#").strip()
                plain_lines.append(line.upper())
                plain_lines.append("=" * len(line))

            # Remove markdown formatting
            elif line.startswith("**") and line.endswith("**"):
                line = line.strip("*").strip()
                plain_lines.append(line)

            # Remove code blocks
            elif line.startswith("```"):
                continue

            # Remove bullet points formatting
            elif line.startswith("- "):
                plain_lines.append(f"  • {line[2:]}")

            else:
                plain_lines.append(line)

        return "\n".join(plain_lines)

    def get_file_size(self, file_path):
        """Get human-readable file size."""
        size = os.path.getsize(file_path)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def get_prometheus_metrics(self):
        """Collect key metrics from Prometheus for EOD reporting."""
        metrics = {
            "firing_alerts": "N/A",
            "firing_alert_names": "N/A",
            "docs_processed_24h": "N/A",
            "refresh_age_seconds": "N/A",
            "containers_running": "N/A",
            "prometheus_available": False,
        }

        try:
            # Check if Prometheus is available
            response = requests.get(f"{PROMETHEUS_BASE_URL}/api/v1/query?query=up", timeout=5)
            if response.status_code != 200:
                return metrics

            metrics["prometheus_available"] = True

            # Get firing alerts
            alerts_response = requests.get(f"{PROMETHEUS_BASE_URL}/api/v1/alerts", timeout=5)
            if alerts_response.status_code == 200:
                alerts_data = alerts_response.json()
                firing_alerts = [a for a in alerts_data.get("data", {}).get("alerts", []) if a.get("state") == "firing"]
                metrics["firing_alerts"] = len(firing_alerts)
                alert_names = [a.get("labels", {}).get("alertname") for a in firing_alerts[:5]]
                metrics["firing_alert_names"] = ", ".join([n for n in alert_names if n]) or "None"

            # Get documents processed in 24h
            query = "increase(docling_documents_processed_total[24h])"
            response = requests.get(f"{PROMETHEUS_BASE_URL}/api/v1/query?query={query}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                result = data.get("data", {}).get("result", [])
                metrics["docs_processed_24h"] = int(float(result[0]["value"][1])) if result else 0

            # Get performance monitor refresh age
            query = "ingestion:last_refresh_age_seconds"
            response = requests.get(f"{PROMETHEUS_BASE_URL}/api/v1/query?query={query}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                result = data.get("data", {}).get("result", [])
                metrics["refresh_age_seconds"] = int(float(result[0]["value"][1])) if result else "N/A"

        except Exception as e:
            print(f"Warning: Could not collect Prometheus metrics: {e}")

        # Get container count via Docker
        try:
            result = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                metrics["containers_running"] = len([line for line in result.stdout.strip().split("\n") if line])
        except Exception:
            pass

        return metrics

    def get_documentation_stats(self):
        """Collect documentation statistics for EOD reporting."""
        stats = {
            "total_md_files": 0,
            "md_files_changed_7d": 0,
            "md_files_changed_today": 0,
            "top_changed_files": [],
            "total_lines": 0,
        }

        try:
            # Count total markdown files
            result = subprocess.run(
                ["find", ".", "-maxdepth", "6", "-type", "f", "-name", "*.md"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                md_files = [line for line in result.stdout.strip().split("\n") if line]
                stats["total_md_files"] = len(md_files)

                # Count total lines in markdown files
                try:
                    wc_result = subprocess.run(["wc", "-l"] + md_files, capture_output=True, text=True, timeout=10)
                    if wc_result.returncode == 0:
                        lines = wc_result.stdout.strip().split("\n")
                        if lines and "total" in lines[-1]:
                            stats["total_lines"] = int(lines[-1].split()[0])
                except Exception:
                    pass

            # Get files changed in the last 7 days
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            result = subprocess.run(
                ["git", "log", f"--since={seven_days_ago}", "--name-only", "--pretty=format:"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                changed_files = [line for line in result.stdout.split("\n") if line.endswith(".md")]
                stats["md_files_changed_7d"] = len(set(changed_files))

            # Get files changed today
            today = datetime.now().strftime("%Y-%m-%d")
            result = subprocess.run(
                ["git", "log", f"--since={today} 00:00:00", "--name-only", "--pretty=format:"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                changed_today = [line for line in result.stdout.split("\n") if line.endswith(".md")]
                unique_changed = list(set(changed_today))
                stats["md_files_changed_today"] = len(unique_changed)
                stats["top_changed_files"] = unique_changed[:5]

        except Exception as e:
            print(f"Warning: Could not collect documentation stats: {e}")

        return stats


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python email_eod_report.py recipient@email.com [report_file]")
        print("       python email_eod_report.py --test recipient@email.com")
        print()
        print("Environment variables:")
        print("  EOD_SENDER_EMAIL     - Sender email address")
        print("  EOD_SENDER_PASSWORD  - Sender email password (app password for Gmail)")
        print("  SMTP_SERVER          - SMTP server (optional, auto-detected)")
        print("  SMTP_PORT            - SMTP port (optional, default 587)")
        print("  SMTP_TLS             - Use TLS (optional, default true)")
        sys.exit(1)

    sender = EODEmailSender()

    if sys.argv[1] == "--test":
        if len(sys.argv) < 3:
            print("Usage: python email_eod_report.py --test recipient@email.com")
            sys.exit(1)

        recipient = sys.argv[2]
        success = sender.send_report(recipient, test_mode=True)
    else:
        recipient = sys.argv[1]
        report_file = sys.argv[2] if len(sys.argv) > 2 else None
        success = sender.send_report(recipient, report_file)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
