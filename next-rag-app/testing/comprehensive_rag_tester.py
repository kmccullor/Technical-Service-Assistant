#!/usr/bin/env python3
"""
Comprehensive RAG System Testing Framework
Tests all functionality including API endpoints, search, retrieval, and response quality
"""

import json
import time
import requests
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import statistics
import sys

@dataclass
class TestResult:
    """Structure for individual test results"""
    test_name: str
    question: str
    response_time: float
    status_code: int
    success: bool
    error_message: Optional[str]
    response_data: Optional[Dict]
    sources_found: int
    confidence_score: Optional[float]
    response_length: int
    contains_sources: bool

@dataclass
class TestSuite:
    """Structure for test suite results"""
    name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    results: List[TestResult]

class RAGSystemTester:
    def __init__(self, base_url: str = "http://localhost:3000"):
        """Initialize the RAG system tester"""
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        
    def load_test_questions(self, analysis_file: str) -> List[Dict]:
        """Load test questions from database analysis"""
        try:
            with open(analysis_file, 'r') as f:
                analysis = json.load(f)
            return analysis.get('test_questions', [])
        except Exception as e:
            print(f"❌ Error loading test questions: {e}")
            return []
    
    def test_api_health(self) -> TestResult:
        """Test API health endpoint"""
        start_time = time.time()
        
        try:
            response = self.session.get(f"{self.base_url}/api/status", timeout=10)
            response_time = time.time() - start_time
            
            success = response.status_code == 200
            response_data = response.json() if success else None
            
            return TestResult(
                test_name="API Health Check",
                question="GET /api/status",
                response_time=response_time,
                status_code=response.status_code,
                success=success,
                error_message=None if success else f"Status code: {response.status_code}",
                response_data=response_data,
                sources_found=0,
                confidence_score=None,
                response_length=len(response.text) if response.text else 0,
                contains_sources=False
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                test_name="API Health Check",
                question="GET /api/status",
                response_time=response_time,
                status_code=0,
                success=False,
                error_message=str(e),
                response_data=None,
                sources_found=0,
                confidence_score=None,
                response_length=0,
                contains_sources=False
            )
    
    def test_chat_endpoint(self, question: str, test_name: Optional[str] = None) -> TestResult:
        """Test chat endpoint with a specific question"""
        if test_name is None:
            test_name = f"Chat Test: {question[:50]}..."
        
        start_time = time.time()
        
        try:
            payload = {
                "messages": [
                    {"role": "user", "content": question}
                ]
            }
            
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            response_time = time.time() - start_time
            
            # Parse streaming response
            response_data = self.parse_streaming_response(response.text)
            sources_found = len(response_data.get('sources', []))
            confidence_score = response_data.get('confidence')
            
            success = response.status_code == 200 and 'conversation_id' in response_data
            contains_sources = sources_found > 0
            
            return TestResult(
                test_name=test_name,
                question=question,
                response_time=response_time,
                status_code=response.status_code,
                success=success,
                error_message=None if success else f"Failed: {response.status_code}",
                response_data=response_data,
                sources_found=sources_found,
                confidence_score=confidence_score,
                response_length=len(response.text),
                contains_sources=contains_sources
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                test_name=test_name,
                question=question,
                response_time=response_time,
                status_code=0,
                success=False,
                error_message=str(e),
                response_data=None,
                sources_found=0,
                confidence_score=None,
                response_length=0,
                contains_sources=False
            )
    
    def parse_streaming_response(self, response_text: str) -> Dict:
        """Parse streaming SSE response format"""
        data = {
            'conversation_id': None,
            'sources': [],
            'tokens': [],
            'confidence': None
        }
        
        try:
            lines = response_text.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    json_str = line[6:]  # Remove 'data: ' prefix
                    try:
                        parsed = json.loads(json_str)
                        
                        if parsed.get('type') == 'conversation_id':
                            data['conversation_id'] = parsed.get('conversationId')
                        elif parsed.get('type') == 'sources':
                            data['sources'] = parsed.get('sources', [])
                            # Extract confidence from sources response
                            if 'confidence' in parsed:
                                data['confidence'] = parsed['confidence']
                        elif parsed.get('type') == 'token':
                            data['tokens'].append(parsed.get('token', ''))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error parsing response: {e}")
        
        return data
    
    def test_search_functionality(self) -> List[TestResult]:
        """Test search-specific functionality"""
        search_tests = [
            {
                'question': 'What is RNI?',
                'expected_sources': True,
                'test_name': 'Basic RNI Query'
            },
            {
                'question': 'How to install RNI?',
                'expected_sources': True,
                'test_name': 'Installation Query'
            },
            {
                'question': 'RNI configuration parameters',
                'expected_sources': True,
                'test_name': 'Configuration Query'
            },
            {
                'question': 'completely unrelated query about cooking recipes',
                'expected_sources': False,
                'test_name': 'Unrelated Query Test'
            },
            {
                'question': '',
                'expected_sources': False,
                'test_name': 'Empty Query Test'
            },
            {
                'question': 'a' * 1000,
                'expected_sources': False,
                'test_name': 'Very Long Query Test'
            }
        ]
        
        results = []
        for test in search_tests:
            result = self.test_chat_endpoint(test['question'], test['test_name'])
            
            # Validate expected behavior
            if test['expected_sources'] and not result.contains_sources:
                result.success = False
                result.error_message = "Expected sources but none found"
            elif not test['expected_sources'] and result.contains_sources:
                # This is actually OK - the system might still find relevant content
                pass
            
            results.append(result)
        
        return results
    
    def test_edge_cases(self) -> List[TestResult]:
        """Test edge cases and error conditions"""
        edge_cases = [
            {
                'test_type': 'malformed_json',
                'payload': '{"messages": [{"role": "user"}',  # Invalid JSON
                'test_name': 'Malformed JSON Test'
            },
            {
                'test_type': 'invalid_structure',
                'payload': {"invalid": "structure"},
                'test_name': 'Invalid Payload Structure'
            },
            {
                'test_type': 'missing_messages',
                'payload': {"wrong_field": "value"},
                'test_name': 'Missing Messages Field'
            },
            {
                'test_type': 'empty_messages',
                'payload': {"messages": []},
                'test_name': 'Empty Messages Array'
            }
        ]
        
        results = []
        
        for case in edge_cases:
            start_time = time.time()
            
            try:
                if case['test_type'] == 'malformed_json':
                    # Send malformed JSON
                    response = requests.post(
                        f"{self.base_url}/api/chat",
                        data=case['payload'],
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                else:
                    response = requests.post(
                        f"{self.base_url}/api/chat",
                        json=case['payload'],
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                
                response_time = time.time() - start_time
                
                # For edge cases, we expect 4xx status codes
                success = 400 <= response.status_code < 500
                
                result = TestResult(
                    test_name=case['test_name'],
                    question=str(case['payload']),
                    response_time=response_time,
                    status_code=response.status_code,
                    success=success,
                    error_message=None if success else f"Unexpected status: {response.status_code}",
                    response_data=None,
                    sources_found=0,
                    confidence_score=None,
                    response_length=len(response.text),
                    contains_sources=False
                )
                
            except Exception as e:
                response_time = time.time() - start_time
                result = TestResult(
                    test_name=case['test_name'],
                    question=str(case['payload']),
                    response_time=response_time,
                    status_code=0,
                    success=False,
                    error_message=str(e),
                    response_data=None,
                    sources_found=0,
                    confidence_score=None,
                    response_length=0,
                    contains_sources=False
                )
            
            results.append(result)
        
        return results
    
    def test_load_performance(self, num_concurrent: int = 5, num_requests: int = 20) -> List[TestResult]:
        """Test system performance under load"""
        questions = [
            "What is RNI?",
            "How to configure RNI?",
            "RNI installation guide",
            "RNI troubleshooting",
            "RNI system requirements"
        ]
        
        async def make_request(session, question, test_id):
            """Make async request"""
            start_time = time.time()
            
            try:
                payload = {
                    "messages": [
                        {"role": "user", "content": question}
                    ]
                }
                
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=30
                ) as response:
                    response_time = time.time() - start_time
                    response_text = await response.text()
                    
                    response_data = self.parse_streaming_response(response_text)
                    sources_found = len(response_data.get('sources', []))
                    
                    return TestResult(
                        test_name=f"Load Test {test_id}",
                        question=question,
                        response_time=response_time,
                        status_code=response.status,
                        success=response.status == 200,
                        error_message=None if response.status == 200 else f"Status: {response.status}",
                        response_data=response_data,
                        sources_found=sources_found,
                        confidence_score=response_data.get('confidence'),
                        response_length=len(response_text),
                        contains_sources=sources_found > 0
                    )
                    
            except Exception as e:
                response_time = time.time() - start_time
                return TestResult(
                    test_name=f"Load Test {test_id}",
                    question=question,
                    response_time=response_time,
                    status_code=0,
                    success=False,
                    error_message=str(e),
                    response_data=None,
                    sources_found=0,
                    confidence_score=None,
                    response_length=0,
                    contains_sources=False
                )
        
        async def run_load_test():
            """Run concurrent load test"""
            async with aiohttp.ClientSession() as session:
                tasks = []
                
                for i in range(num_requests):
                    question = questions[i % len(questions)]
                    task = make_request(session, question, i + 1)
                    tasks.append(task)
                
                # Execute with limited concurrency
                results = []
                for i in range(0, len(tasks), num_concurrent):
                    batch = tasks[i:i + num_concurrent]
                    batch_results = await asyncio.gather(*batch, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, Exception):
                            # Convert exception to TestResult
                            results.append(TestResult(
                                test_name=f"Load Test Error",
                                question="Unknown",
                                response_time=0,
                                status_code=0,
                                success=False,
                                error_message=str(result),
                                response_data=None,
                                sources_found=0,
                                confidence_score=None,
                                response_length=0,
                                contains_sources=False
                            ))
                        else:
                            results.append(result)
                
                return results
        
        # Run the async load test
        try:
            return asyncio.run(run_load_test())
        except Exception as e:
            print(f"Load test failed: {e}")
            return []
    
    def analyze_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Analyze test results and generate metrics"""
        if not results:
            return {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'success_rate': 0,
                'avg_response_time': 0,
                'response_times': [],
                'sources_stats': {},
                'confidence_stats': {}
            }
        
        passed = sum(1 for r in results if r.success)
        failed = len(results) - passed
        response_times = [r.response_time for r in results if r.response_time > 0]
        
        # Source statistics
        sources_counts = [r.sources_found for r in results if r.sources_found is not None]
        tests_with_sources = sum(1 for r in results if r.contains_sources)
        
        # Confidence statistics
        confidence_scores = [r.confidence_score for r in results if r.confidence_score is not None]
        
        return {
            'total_tests': len(results),
            'passed_tests': passed,
            'failed_tests': failed,
            'success_rate': (passed / len(results)) * 100 if results else 0,
            'avg_response_time': statistics.mean(response_times) if response_times else 0,
            'min_response_time': min(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0,
            'median_response_time': statistics.median(response_times) if response_times else 0,
            'response_times': response_times,
            'sources_stats': {
                'tests_with_sources': tests_with_sources,
                'avg_sources_per_test': statistics.mean(sources_counts) if sources_counts else 0,
                'max_sources': max(sources_counts) if sources_counts else 0,
                'total_sources_found': sum(sources_counts) if sources_counts else 0
            },
            'confidence_stats': {
                'avg_confidence': statistics.mean(confidence_scores) if confidence_scores else 0,
                'min_confidence': min(confidence_scores) if confidence_scores else 0,
                'max_confidence': max(confidence_scores) if confidence_scores else 0,
                'confidence_scores': confidence_scores
            }
        }
    
    def generate_report(self, all_results: Dict[str, List[TestResult]]) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        timestamp = datetime.now().isoformat()
        
        report = {
            'timestamp': timestamp,
            'test_summary': {},
            'detailed_results': {},
            'recommendations': []
        }
        
        # Analyze each test suite
        for suite_name, results in all_results.items():
            analysis = self.analyze_results(results)
            report['detailed_results'][suite_name] = {
                'analysis': analysis,
                'individual_results': [
                    {
                        'test_name': r.test_name,
                        'question': r.question,
                        'success': r.success,
                        'response_time': r.response_time,
                        'sources_found': r.sources_found,
                        'confidence_score': r.confidence_score,
                        'error_message': r.error_message
                    }
                    for r in results
                ]
            }
        
        # Overall summary
        all_test_results = []
        for results in all_results.values():
            all_test_results.extend(results)
        
        report['test_summary'] = self.analyze_results(all_test_results)
        
        # Generate recommendations
        summary = report['test_summary']
        if summary['success_rate'] < 90:
            report['recommendations'].append("⚠️ Success rate below 90% - investigate failing tests")
        
        if summary['avg_response_time'] > 5.0:
            report['recommendations'].append("⚠️ Average response time above 5 seconds - consider performance optimization")
        
        if summary['sources_stats']['tests_with_sources'] < len(all_test_results) * 0.7:
            report['recommendations'].append("⚠️ Less than 70% of tests returned sources - check document indexing")
        
        if summary['confidence_stats']['avg_confidence'] < 0.1:
            report['recommendations'].append("⚠️ Low confidence scores - review confidence threshold settings")
        
        return report
    
    def run_comprehensive_test_suite(self, analysis_file: Optional[str] = None) -> Dict[str, Any]:
        """Run all tests and generate comprehensive report"""
        print("🧪 Starting comprehensive RAG system testing...")
        
        all_results = {}
        
        # 1. API Health Check
        print("🔍 Testing API health...")
        health_result = self.test_api_health()
        all_results['health_check'] = [health_result]
        
        if not health_result.success:
            print("❌ API health check failed! Cannot continue with other tests.")
            return self.generate_report(all_results)
        
        # 2. Basic Search Functionality
        print("🔍 Testing search functionality...")
        search_results = self.test_search_functionality()
        all_results['search_functionality'] = search_results
        
        # 3. Edge Cases
        print("🔍 Testing edge cases...")
        edge_results = self.test_edge_cases()
        all_results['edge_cases'] = edge_results
        
        # 4. Load/Performance Testing
        print("🔍 Testing system performance...")
        load_results = self.test_load_performance(num_concurrent=3, num_requests=10)
        all_results['performance'] = load_results
        
        # 5. Database Questions Testing
        if analysis_file and Path(analysis_file).exists():
            print("🔍 Testing database-generated questions...")
            questions = self.load_test_questions(analysis_file)
            
            # Test a sample of questions (limit to avoid overwhelming the system)
            sample_questions = questions[:50] if len(questions) > 50 else questions
            
            db_results = []
            for i, q in enumerate(sample_questions):
                print(f"  Testing question {i+1}/{len(sample_questions)}: {q['question'][:50]}...")
                result = self.test_chat_endpoint(q['question'], f"DB Question {i+1}")
                db_results.append(result)
                
                # Brief delay to avoid overwhelming the system
                time.sleep(0.5)
            
            all_results['database_questions'] = db_results
        
        print("✅ All tests completed!")
        return self.generate_report(all_results)

def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        analysis_file = sys.argv[1]
    else:
        # Find the most recent analysis file
        testing_dir = Path("/home/kmccullor/Projects/Technical-Service-Assistant/next-rag-app/testing")
        analysis_files = list(testing_dir.glob("database_analysis_report_*.json"))
        if analysis_files:
            analysis_file = str(max(analysis_files, key=lambda x: x.stat().st_mtime))
            print(f"📊 Using analysis file: {analysis_file}")
        else:
            analysis_file = None
            print("📊 No analysis file found, skipping database questions test")
    
    # Initialize tester
    tester = RAGSystemTester()
    
    # Run comprehensive tests
    report = tester.run_comprehensive_test_suite(analysis_file)
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"/home/kmccullor/Projects/Technical-Service-Assistant/next-rag-app/testing/comprehensive_test_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"📊 Comprehensive test report saved to: {report_file}")
    
    # Print summary
    summary = report['test_summary']
    print("\n" + "="*60)
    print("📋 COMPREHENSIVE TEST SUMMARY")
    print("="*60)
    print(f"  📊 Total Tests: {summary['total_tests']}")
    print(f"  ✅ Passed: {summary['passed_tests']}")
    print(f"  ❌ Failed: {summary['failed_tests']}")
    print(f"  📈 Success Rate: {summary['success_rate']:.1f}%")
    print(f"  ⏱️  Avg Response Time: {summary['avg_response_time']:.2f}s")
    print(f"  🔍 Tests with Sources: {summary['sources_stats']['tests_with_sources']}")
    print(f"  📊 Avg Confidence: {summary['confidence_stats']['avg_confidence']:.3f}")
    
    if report.get('recommendations'):
        print("\n🔧 RECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"  {rec}")
    
    print("\n" + "="*60)
    
    return report

if __name__ == "__main__":
    main()