#!/usr/bin/env python3
"""
Specialization Performance Monitor for Technical Service Assistant
Tracks and analyzes performance improvements from model specialization

Monitors:
- Instance utilization distribution
- Response time improvements by question type
- Model selection accuracy and effectiveness
- Resource utilization optimization
"""

import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter

@dataclass
class RoutingEvent:
    timestamp: float
    question_type: str
    selected_model: str
    selected_instance: str
    instance_url: str
    reasoning: str
    response_time_ms: float = 0.0
    
class SpecializationMonitor:
    def __init__(self):
        self.base_url = "http://localhost:8008"
        self.routing_log = []
        self.performance_baseline = {}
        self.monitoring_start = time.time()
        
    def test_routing_performance(self, test_queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Test routing performance with various query types"""
        print("🔍 Testing Specialized Routing Performance...")
        
        results = {
            'total_tests': len(test_queries),
            'routing_distribution': Counter(),
            'response_times': defaultdict(list),
            'model_selection': Counter(),
            'instance_utilization': Counter(),
            'question_type_routing': defaultdict(list)
        }
        
        for i, test_query in enumerate(test_queries):
            print(f"   Test {i+1}/{len(test_queries)}: {test_query['query'][:50]}...")
            
            start_time = time.time()
            
            try:
                # Test routing decision
                routing_response = requests.post(
                    f"{self.base_url}/api/intelligent-route",
                    json=test_query,
                    timeout=10
                )
                routing_response.raise_for_status()
                routing_data = routing_response.json()
                
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                # Record routing event
                event = RoutingEvent(
                    timestamp=time.time(),
                    question_type=routing_data['question_type'],
                    selected_model=routing_data['selected_model'],
                    selected_instance=routing_data['selected_instance'],
                    instance_url=routing_data['instance_url'],
                    reasoning=routing_data['reasoning'],
                    response_time_ms=response_time
                )
                
                self.routing_log.append(event)
                
                # Update results
                results['routing_distribution'][routing_data['selected_instance']] += 1
                results['response_times'][routing_data['question_type']].append(response_time)
                results['model_selection'][routing_data['selected_model']] += 1
                results['instance_utilization'][routing_data['selected_instance']] += 1
                results['question_type_routing'][routing_data['question_type']].append(routing_data['selected_instance'])
                
            except Exception as e:
                print(f"   ❌ Error testing query: {e}")
                continue
        
        return results
    
    def analyze_specialization_effectiveness(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze how well specialization is working"""
        print("\n📊 Analyzing Specialization Effectiveness...")
        
        analysis = {
            'routing_accuracy': {},
            'instance_specialization_score': {},
            'performance_metrics': {},
            'recommendations': []
        }
        
        # Expected routing patterns based on our specialization
        expected_routing = {
            'code': ['ollama-server-2-code-technical'],
            'technical': ['ollama-server-1-chat-qa', 'ollama-server-2-code-technical'],
            'math': ['ollama-server-3-reasoning-math'],
            'factual': ['ollama-server-1-chat-qa'],
            'chat': ['ollama-server-1-chat-qa']
        }
        
        # Analyze routing accuracy
        for question_type, actual_instances in results['question_type_routing'].items():
            expected_instances = expected_routing.get(question_type, [])
            if expected_instances:
                correct_routes = sum(1 for instance in actual_instances if any(exp in instance for exp in expected_instances))
                accuracy = correct_routes / len(actual_instances) if actual_instances else 0
                analysis['routing_accuracy'][question_type] = {
                    'accuracy': accuracy,
                    'total_queries': len(actual_instances),
                    'correct_routes': correct_routes
                }
        
        # Calculate instance specialization scores
        total_queries = sum(results['instance_utilization'].values())
        for instance, query_count in results['instance_utilization'].items():
            utilization_percentage = (query_count / total_queries) * 100
            analysis['instance_specialization_score'][instance] = {
                'query_count': query_count,
                'utilization_percentage': utilization_percentage
            }
        
        # Performance metrics
        for question_type, response_times in results['response_times'].items():
            if response_times:
                analysis['performance_metrics'][question_type] = {
                    'avg_response_time': sum(response_times) / len(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'query_count': len(response_times)
                }
        
        # Generate recommendations
        overall_accuracy = sum(acc['accuracy'] for acc in analysis['routing_accuracy'].values()) / len(analysis['routing_accuracy'])
        if overall_accuracy < 0.8:
            analysis['recommendations'].append("Consider refining question classification patterns")
        
        if len(set(results['instance_utilization'].keys())) < 3:
            analysis['recommendations'].append("Instance distribution could be more balanced")
        
        # Check if specialization is effective
        code_accuracy = analysis['routing_accuracy'].get('code', {}).get('accuracy', 0)
        if code_accuracy > 0.9:
            analysis['recommendations'].append("Code specialization is working well")
        
        return analysis
    
    def generate_performance_report(self, results: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """Generate comprehensive performance report"""
        report = [
            "# Model Specialization Performance Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Test Duration: {len(self.routing_log)} routing decisions analyzed",
            "",
            "## 🎯 Specialization Effectiveness",
            ""
        ]
        
        # Routing accuracy summary
        if analysis['routing_accuracy']:
            report.extend([
                "### Routing Accuracy by Question Type",
                "| Question Type | Accuracy | Correct/Total | Performance |",
                "|---------------|----------|---------------|-------------|"
            ])
            
            for q_type, accuracy_data in analysis['routing_accuracy'].items():
                accuracy_pct = accuracy_data['accuracy'] * 100
                status = "✅ Excellent" if accuracy_pct >= 90 else "⚠️ Needs Improvement" if accuracy_pct >= 70 else "❌ Poor"
                report.append(f"| {q_type.title()} | {accuracy_pct:.1f}% | {accuracy_data['correct_routes']}/{accuracy_data['total_queries']} | {status} |")
        
        # Instance utilization
        report.extend([
            "",
            "### Instance Utilization Distribution",
            "| Instance | Queries | Utilization | Specialization |",
            "|----------|---------|-------------|----------------|"
        ])
        
        for instance, utilization_data in analysis['instance_specialization_score'].items():
            util_pct = utilization_data['utilization_percentage']
            specialization = "Specialized" if "code-technical" in instance or "reasoning-math" in instance or "chat-qa" in instance else "General"
            report.append(f"| {instance} | {utilization_data['query_count']} | {util_pct:.1f}% | {specialization} |")
        
        # Performance metrics
        if analysis['performance_metrics']:
            report.extend([
                "",
                "### Response Time Performance",
                "| Question Type | Avg Response (ms) | Min (ms) | Max (ms) | Queries |",
                "|---------------|-------------------|----------|----------|---------|"
            ])
            
            for q_type, perf_data in analysis['performance_metrics'].items():
                report.append(f"| {q_type.title()} | {perf_data['avg_response_time']:.1f} | {perf_data['min_response_time']:.1f} | {perf_data['max_response_time']:.1f} | {perf_data['query_count']} |")
        
        # Model selection distribution
        report.extend([
            "",
            "### Model Selection Distribution",
            "| Model | Usage Count | Percentage |",
            "|-------|-------------|------------|"
        ])
        
        total_model_usage = sum(results['model_selection'].values())
        for model, count in results['model_selection'].most_common():
            percentage = (count / total_model_usage) * 100
            report.append(f"| {model} | {count} | {percentage:.1f}% |")
        
        # Recommendations
        if analysis['recommendations']:
            report.extend([
                "",
                "## 📋 Recommendations",
                ""
            ])
            for i, rec in enumerate(analysis['recommendations'], 1):
                report.append(f"{i}. {rec}")
        
        # Summary
        overall_accuracy = sum(acc['accuracy'] for acc in analysis['routing_accuracy'].values()) / len(analysis['routing_accuracy'])
        avg_response_time = sum(sum(times) for times in results['response_times'].values()) / sum(len(times) for times in results['response_times'].values())
        
        report.extend([
            "",
            "## 📊 Summary",
            f"- **Overall Routing Accuracy**: {overall_accuracy:.1%}",
            f"- **Average Response Time**: {avg_response_time:.1f}ms",
            f"- **Instances Utilized**: {len(results['instance_utilization'])}/4",
            f"- **Models Used**: {len(results['model_selection'])}",
            f"- **Specialization Status**: {'✅ Effective' if overall_accuracy > 0.8 else '⚠️ Needs Tuning'}"
        ])
        
        return "\\n".join(report)
    
    def run_comprehensive_test(self) -> str:
        """Run comprehensive specialization test"""
        # Test queries covering different question types
        test_queries = [
            # Code questions (should route to instance 2)
            {"query": "How do I write a Python function to parse JSON?", "prefer_speed": False, "require_context": False},
            {"query": "What's the syntax for SQL JOIN statements?", "prefer_speed": False, "require_context": False},
            {"query": "Debug this JavaScript code for me", "prefer_speed": False, "require_context": False},
            
            # Technical questions (should route to instance 1 or 2)
            {"query": "How do I configure RNI database connections?", "prefer_speed": False, "require_context": False},
            {"query": "Troubleshoot network connectivity issues", "prefer_speed": False, "require_context": False},
            {"query": "Install and setup Active Directory integration", "prefer_speed": False, "require_context": False},
            
            # Math questions (should route to instance 3)
            {"query": "Calculate the derivative of x^3 + 2x", "prefer_speed": False, "require_context": False},
            {"query": "What is the integral of sin(x)?", "prefer_speed": False, "require_context": False},
            {"query": "Solve this quadratic equation: x^2 + 5x + 6 = 0", "prefer_speed": False, "require_context": False},
            
            # Factual questions (should route to instance 1)
            {"query": "What is the capital of France?", "prefer_speed": False, "require_context": False},
            {"query": "Explain how photosynthesis works", "prefer_speed": False, "require_context": False},
            {"query": "What are the benefits of renewable energy?", "prefer_speed": False, "require_context": False},
            
            # Chat questions (should route to instance 1)
            {"query": "Hello, how are you today?", "prefer_speed": False, "require_context": False},
            {"query": "Can you help me plan a vacation?", "prefer_speed": False, "require_context": False},
            {"query": "Tell me a joke", "prefer_speed": False, "require_context": False}
        ]
        
        # Run tests
        results = self.test_routing_performance(test_queries)
        
        # Analyze results
        analysis = self.analyze_specialization_effectiveness(results)
        
        # Generate report
        report = self.generate_performance_report(results, analysis)
        
        return report

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor model specialization performance")
    parser.add_argument("--output", "-o", help="Output file for report")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data")
    args = parser.parse_args()
    
    print("🚀 Model Specialization Performance Monitor")
    print("=" * 60)
    
    monitor = SpecializationMonitor()
    
    if args.json:
        # Run test and output raw JSON
        test_queries = [
            {"query": "How do I write Python code?", "prefer_speed": False, "require_context": False},
            {"query": "Configure RNI server settings", "prefer_speed": False, "require_context": False},
            {"query": "Calculate 2 + 2", "prefer_speed": False, "require_context": False}
        ]
        results = monitor.test_routing_performance(test_queries)
        analysis = monitor.analyze_specialization_effectiveness(results)
        
        output_data = {
            'results': results,
            'analysis': analysis,
            'routing_log': [asdict(event) for event in monitor.routing_log]
        }
        
        print(json.dumps(output_data, indent=2, default=str))
    else:
        # Run comprehensive test and generate report
        report = monitor.run_comprehensive_test()
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"\\n📄 Report saved to: {args.output}")
        else:
            print("\\n" + report)
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)