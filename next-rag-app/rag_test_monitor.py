#!/usr/bin/env python3
"""
Real-time RAG Test Monitor
Monitors the comprehensive RAG validation progress and displays real-time statistics.
"""

import time
import json
import os
import glob
from datetime import datetime
# import matplotlib.pyplot as plt
# import numpy as np

def monitor_rag_tests():
    """Monitor RAG test progress and display statistics"""
    print("🔍 RAG Test Monitor Started")
    print("=" * 60)
    
    start_time = time.time()
    last_results_count = 0
    
    while True:
        try:
            # Look for the most recent results file
            result_files = glob.glob("comprehensive_rag_results_*.json")
            
            if result_files:
                latest_file = max(result_files, key=os.path.getctime)
                
                try:
                    with open(latest_file, 'r') as f:
                        data = json.load(f)
                    
                    summary = data.get('summary', {})
                    detailed_results = data.get('detailed_results', [])
                    
                    current_count = len(detailed_results)
                    
                    if current_count > last_results_count:
                        last_results_count = current_count
                        
                        # Calculate current statistics
                        successful_tests = sum(1 for r in detailed_results if r.get('success', False))
                        confidences = [r.get('confidence', 0) for r in detailed_results if r.get('confidence')]
                        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                        high_conf_count = sum(1 for c in confidences if c >= 0.95)
                        
                        # Display progress
                        elapsed_time = time.time() - start_time
                        progress = current_count / 1188 * 100 if current_count > 0 else 0
                        
                        print(f"\n📊 Progress Update - {datetime.now().strftime('%H:%M:%S')}")
                        print(f"   Tests Completed: {current_count}/1188 ({progress:.1f}%)")
                        print(f"   Success Rate: {successful_tests}/{current_count} ({successful_tests/current_count*100:.1f}%)")
                        print(f"   Average Confidence: {avg_confidence*100:.1f}%")
                        print(f"   High Confidence (≥95%): {high_conf_count} ({high_conf_count/len(confidences)*100:.1f}%)")
                        print(f"   Elapsed Time: {elapsed_time/60:.1f} minutes")
                        
                        if current_count > 0:
                            estimated_total = (elapsed_time / current_count) * 1188
                            remaining_time = estimated_total - elapsed_time
                            print(f"   Est. Remaining: {remaining_time/60:.1f} minutes")
                        
                        # Document-level progress
                        doc_stats = {}
                        for result in detailed_results:
                            doc = result.get('document', 'Unknown')
                            if doc not in doc_stats:
                                doc_stats[doc] = {'total': 0, 'success': 0}
                            doc_stats[doc]['total'] += 1
                            if result.get('success', False):
                                doc_stats[doc]['success'] += 1
                        
                        completed_docs = sum(1 for stats in doc_stats.values() if stats['total'] >= 22)
                        print(f"   Documents Completed: {completed_docs}/54")
                        
                        # Show top performing documents
                        if doc_stats:
                            sorted_docs = sorted(doc_stats.items(), 
                                               key=lambda x: x[1]['success']/x[1]['total'] if x[1]['total'] > 0 else 0, 
                                               reverse=True)
                            print(f"   Top Performer: {sorted_docs[0][0]} ({sorted_docs[0][1]['success']}/{sorted_docs[0][1]['total']})")
                
                except Exception as e:
                    print(f"❌ Error reading results: {e}")
            
            else:
                print(f"⏳ Waiting for test results... ({int(time.time() - start_time)}s)")
            
            # Check if test is complete
            if last_results_count >= 1188:
                print("\n🎉 Comprehensive RAG Validation Complete!")
                break
            
            time.sleep(30)  # Update every 30 seconds
            
        except KeyboardInterrupt:
            print("\n⏹️ Monitoring stopped by user")
            break
        except Exception as e:
            print(f"❌ Monitor error: {e}")
            time.sleep(10)

def generate_progress_summary(results_data):
    """Generate a text-based progress summary"""
    try:
        detailed_results = results_data.get('detailed_results', [])
        
        if len(detailed_results) < 10:
            return
        
        # Calculate statistics by confidence ranges
        confidence_ranges = {
            '95-100%': 0, '90-95%': 0, '85-90%': 0, 
            '80-85%': 0, '70-80%': 0, '<70%': 0
        }
        
        for result in detailed_results:
            conf = result.get('confidence', 0) * 100 if result.get('confidence') else 0
            if conf >= 95:
                confidence_ranges['95-100%'] += 1
            elif conf >= 90:
                confidence_ranges['90-95%'] += 1
            elif conf >= 85:
                confidence_ranges['85-90%'] += 1
            elif conf >= 80:
                confidence_ranges['80-85%'] += 1
            elif conf >= 70:
                confidence_ranges['70-80%'] += 1
            else:
                confidence_ranges['<70%'] += 1
        
        print(f"\n📊 Confidence Distribution:")
        for range_name, count in confidence_ranges.items():
            pct = count / len(detailed_results) * 100 if detailed_results else 0
            print(f"   {range_name}: {count} tests ({pct:.1f}%)")
    
    except Exception as e:
        print(f"❌ Summary generation error: {e}")

if __name__ == "__main__":
    monitor_rag_tests()