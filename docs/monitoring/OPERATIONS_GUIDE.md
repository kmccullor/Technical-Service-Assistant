# Operations Guide

This document consolidates operational procedures, monitoring, and daily management tasks.

## Daily Operations

### Morning Checklist
1. **System Health Check**
   - Verify all containers are running
   - Check system resource usage
   - Review overnight logs for errors
   - Validate database connectivity

2. **Performance Validation**
   - Run quick accuracy test
   - Check response times
   - Verify monitoring systems
   - Review alert status

3. **Content Updates**
   - Check for new documents to process
   - Review processing queue
   - Validate recent ingestions
   - Update content indexes

### Quick Start Daily Checklist
```bash
# System Status
make status

# Health Check
make health-check

# Performance Test
make test-performance

# Review Logs
make logs-today
```

## End-of-Day Reporting

### Automated EOD System
**Schedule**: Daily at 8:00 PM
**Recipients**: Configured via Gmail integration

#### Report Contents
- System health overview
- Performance metrics
- Processing statistics
- Error summaries
- Resource utilization
- Backup status

#### Configuration
- Gmail integration with app-specific passwords
- Automated report generation
- HTML-formatted emails with metrics
- Attachment of detailed logs

### Manual EOD Process
```bash
# Generate comprehensive report
./scripts/end_of_day.sh

# Send email report (if automated system fails)
python email_eod_report.py your-email@domain.com
```

## Monitoring & Alerting

### Prometheus & Grafana Setup
**Access URLs**:
- Grafana: http://rni-llm-01.lab.sensus.net:3001
- Prometheus: http://rni-llm-01.lab.sensus.net:9091
- Alertmanager: http://rni-llm-01.lab.sensus.net:9093

#### Key Metrics Monitored
- System resource usage (CPU, memory, disk)
- Container health and status
- Database performance and connections
- API response times and error rates
- Document processing metrics
- Search accuracy and performance
- Reranker service metrics (Python GC, application health)

### Alert Configuration
**Alert Types**:
- System resource exhaustion
- Service downtime
- Performance degradation
- Error rate increases
- Database connectivity issues

**Notification Channels**:
- Email alerts via Alertmanager
- Slack integration (configurable)
- PagerDuty integration (enterprise)

### Manual Monitoring Commands
```bash
# System status
./monitoring_summary.sh

# Check all services
./check_monitoring.sh

# Performance validation
./verify_monitoring.sh

# View metrics
curl http://rni-llm-01.lab.sensus.net:9091/api/v1/query?query=up
```

## Cron Job Management

### Automated Tasks
1. **Daily EOD Report** (8:00 PM)
   ```
   0 20 * * * source ~/.technical-service-env && cd /path/to/project && ./automated_daily_email.sh
   ```

2. **Weekly Backup** (Sunday 2:00 AM)
   ```
   0 2 * * 0 cd /path/to/project && ./scripts/backup.sh
   ```

3. **Log Rotation** (Daily 1:00 AM)
   ```
   0 1 * * * cd /path/to/project && ./scripts/rotate_logs.sh
   ```

### Cron Setup Guide
1. **Edit crontab**: `crontab -e`
2. **Add environment variables**: Source configuration files
3. **Set proper paths**: Use absolute paths for scripts
4. **Configure logging**: Redirect output to log files
5. **Test manually**: Verify scripts work before automation

## Gmail Integration

### Setup Requirements
1. **Google Account**: Enable 2-factor authentication
2. **App Password**: Generate app-specific password
3. **Environment Config**: Set `GMAIL_APP_PASSWORD`
4. **Test Configuration**: Use `--test` flag for validation

### Configuration Files
- `~/.technical-service-env`: Environment variables
- `automated_daily_email.sh`: Email automation script
- `email_eod_report.py`: Enhanced email system

### Testing Commands
```bash
# Test Gmail configuration
./test_gmail_setup.sh

# Send test email
python email_eod_report.py --test your-email@gmail.com

# Manual email send
python email_eod_report.py your-email@gmail.com
```

## Backup & Recovery

### Automated Backups
- **Database**: Daily PostgreSQL dumps
- **Configuration**: Environment and config files
- **Logs**: Important log file preservation
- **Code**: Git-based version control

### Manual Backup
```bash
# Full system backup
./scripts/backup.sh

# Database only
./scripts/backup_database.sh

# Configuration backup
./scripts/backup_config.sh
```

### Recovery Procedures
1. **Database Recovery**: Restore from PostgreSQL dump
2. **Configuration Recovery**: Restore environment files
3. **Service Recovery**: Restart containers and services
4. **Validation**: Run health checks and tests

## Log Management

### Log Locations
- **System Logs**: `logs/`
- **Container Logs**: `docker logs <container>`
- **Application Logs**: Component-specific locations
- **Audit Logs**: Security and access logs

### Log Analysis
```bash
# View recent errors
grep -i error logs/*.log

# Check performance issues
grep -i "slow\|timeout" logs/*.log

# Monitor real-time logs
tail -f logs/system.log

# Analyze log patterns
./scripts/analyze_logs.sh
```

### Log Rotation
- **Automated**: Daily log rotation via cron
- **Manual**: `./scripts/rotate_logs.sh`
- **Retention**: 30 days for standard logs, 90 days for audit logs

## Performance Optimization

### Resource Monitoring
- **CPU Usage**: Keep below 80% average
- **Memory Usage**: Monitor for memory leaks
- **Disk Usage**: Maintain 20% free space
- **Network**: Monitor bandwidth and latency

### Optimization Techniques
1. **Container Resources**: Adjust memory and CPU limits
2. **Database Tuning**: Optimize queries and indexes
3. **Caching**: Implement appropriate caching strategies
4. **Load Balancing**: Distribute load across services

## Security Operations

### Daily Security Tasks
1. **Update Monitoring**: Check for security alerts
2. **Access Review**: Monitor access logs
3. **Vulnerability Scanning**: Run security scans
4. **Backup Verification**: Ensure backup integrity

### Security Incident Response
1. **Detect**: Monitor for security events
2. **Assess**: Evaluate impact and scope
3. **Contain**: Isolate affected systems
4. **Recover**: Restore normal operations
5. **Learn**: Document and improve procedures

## Troubleshooting

### Common Issues
1. **Container Failures**: Check logs and resource limits
2. **Database Connectivity**: Verify connection parameters
3. **Performance Issues**: Check resource usage and optimization
4. **Email Delivery**: Verify configuration and credentials

### Debugging Tools
```bash
# System health
make health-check

# Component status
docker ps -a

# Resource usage
htop
df -h

# Network connectivity
curl -v http://localhost:8080/health
```

### Support Resources
- **Documentation**: See `TROUBLESHOOTING.md`
- **Community**: Project GitHub issues
- **Internal**: Team knowledge base
- **Vendor**: Component-specific support

## Maintenance Windows

### Scheduled Maintenance
- **Weekly**: Sunday 2:00 AM - 4:00 AM (low usage)
- **Monthly**: First Saturday of month (extended maintenance)
- **Emergency**: As needed with notification

### Maintenance Procedures
1. **Pre-maintenance**: Backup and validation
2. **During**: Systematic updates and changes
3. **Post-maintenance**: Testing and validation
4. **Communication**: Status updates to stakeholders

## Contact Information

### On-Call Procedures
- **Primary Contact**: System administrator
- **Secondary Contact**: Development team lead
- **Escalation**: Management team
- **Emergency**: Follow incident response plan

### Communication Channels
- **Email**: Operations distribution list
- **Slack**: #technical-service-ops
- **PagerDuty**: Automated alerting
- **Documentation**: Confluence/Wiki updates
