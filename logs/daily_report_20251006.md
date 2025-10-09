# 🌅 Automated End of Day Report - October 06, 2025

**Report Generated**: October 06, 2025 at 08:00 PM EDT  
**System Status**: 17 containers running  
**Automation**: Generated via crontab scheduled task

---

## 📊 **System Health Summary**

### **Container Status**


### **Resource Utilization**
```
/dev/mapper/vg.01-lv.root  418G  277G  141G  67% /
/dev/mapper/vg.01-lv.var   467G  135G  332G  29% /var
               total        used        free      shared  buff/cache   available
Mem:           754Gi        12Gi       629Gi       122Mi       117Gi       741Gi
Swap:          8.0Gi          0B       8.0Gi
```

### **Database Status**
- /home/kmccullor/Projects/Technical-Service-Assistant/quality_metrics.db: 20K
- /home/kmccullor/Projects/Technical-Service-Assistant/rag_validation.db: 40K
- /home/kmccullor/Projects/Technical-Service-Assistant/test_optimization.db: 28K

---

## 🔍 **Health Check Results**

- === AUTOMATED HEALTH CHECK - 2025-10-06 20:00:01 ===
- ✅ Reranker service: HEALTHY
- ✅ PostgreSQL database: HEALTHY
- ✅ Ollama instance (port 11434): HEALTHY
- ✅ Ollama instance (port 11435): HEALTHY
- ✅ Ollama instance (port 11436): HEALTHY
- ✅ Ollama instance (port 11437): HEALTHY

---

## ⚡ **Performance Summary**

Performance tests executed - see performance_test_20251006.log for details

---

## 📝 **Log Files Generated**
- End of day automation: `end_of_day_automation_20251006.log`
- Health check results: `health_check_20251006.log`
- Performance test results: `performance_test_20251006.log`
- Daily summary: `daily_report_20251006.md`
- System snapshot: `system_snapshot_20251006.json`

---

## 🎯 **Action Items**
- Review any failed health checks
- Monitor performance trends
- Check container logs for any issues
- Verify backup and monitoring systems

---

**Next automated report**: Tomorrow at scheduled time  
**Manual reports**: Run `./scripts/end_of_day.sh` anytime  
**System monitoring**: Available at http://localhost:3001 (Grafana)

