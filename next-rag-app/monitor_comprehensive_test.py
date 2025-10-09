#!/usr/bin/env python3
"""
Real-time monitoring of comprehensive RAG validation progress
"""

import os
import time
import json
import glob
from datetime import datetime

def monitor_test_progress():
    """Monitor the comprehensive test progress"""
    print("🔍 Monitoring Comprehensive RAG Validation Progress")
    print("=" * 70)
    
    start_time = time.time()
    last_file_count = 0
    
    while True:
        try:
            # Check for result files
            json_files = glob.glob("comprehensive_rag_report_*.json")
            txt_files = glob.glob("rag_validation_summary_*.txt")
            
            current_time = time.time()
            elapsed_minutes = (current_time - start_time) / 60
            
            print(f"\r⏱️ Elapsed: {elapsed_minutes:.1f} min | JSON reports: {len(json_files)} | Text reports: {len(txt_files)}", end="", flush=True)
            
            # If test completed (new files appeared)
            if len(json_files) > last_file_count:
                print(f"\n✅ Test completed! Found {len(json_files)} result files.")
                
                # Display latest results
                if json_files:
                    latest_file = max(json_files, key=os.path.getctime)
                    print(f"📊 Loading results from: {latest_file}")
                    
                    try:
                        with open(latest_file, 'r') as f:
                            results = json.load(f)
                        
                        stats = results.get('overall_statistics', {})
                        print(f"\n🎯 QUICK SUMMARY:")
                        print(f"   Documents Tested: {stats.get('total_documents', 'N/A')}")
                        print(f"   Questions Asked: {stats.get('total_questions', 'N/A')}")  
                        print(f"   Success Rate: {stats.get('success_rate', 0)*100:.1f}%")
                        print(f"   Average Confidence: {stats.get('average_confidence', 0)*100:.1f}%")
                        print(f"   High Confidence (≥95%): {stats.get('high_confidence_count', 0)}")
                        
                    except Exception as e:
                        print(f"❌ Error reading results: {e}")
                
                break
            
            last_file_count = len(json_files)
            time.sleep(30)  # Check every 30 seconds
            
        except KeyboardInterrupt:
            print(f"\n⏹️ Monitoring stopped by user after {elapsed_minutes:.1f} minutes")
            break
        except Exception as e:
            print(f"\n❌ Monitor error: {e}")
            time.sleep(10)

def check_current_status():
    """Check current test status by looking for partial results"""
    print("\n🔍 Current Test Status Check")
    print("-" * 50)
    
    # Check if test is still running
    json_files = glob.glob("comprehensive_rag_report_*.json")
    txt_files = glob.glob("rag_validation_summary_*.txt")
    
    print(f"Result files found: {len(json_files)} JSON, {len(txt_files)} TXT")
    
    if json_files:
        latest_file = max(json_files, key=os.path.getctime)
        file_time = datetime.fromtimestamp(os.path.getctime(latest_file))
        print(f"Latest results: {latest_file} (created: {file_time})")
    
    # Check for any temporary or log files
    log_files = glob.glob("*.log")
    if log_files:
        print(f"Log files: {len(log_files)}")
    
    return len(json_files) > 0

if __name__ == "__main__":
    os.chdir("/home/kmccullor/Projects/Technical-Service-Assistant/next-rag-app")
    
    # First check current status
    if check_current_status():
        print("✅ Test appears to have completed or partial results available")
    else:
        print("⏳ No results yet - starting monitoring...")
        monitor_test_progress()