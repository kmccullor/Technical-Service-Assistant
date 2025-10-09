#!/usr/bin/env python3
"""
Comprehensive End-to-End RAG Validation Suite with Reranking
Tests 20+ questions per document across all archive documents with detailed reporting.
"""

import json
import time
import requests
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
import concurrent.futures
from threading import Lock

@dataclass
class TestResult:
    document: str
    question: str
    question_type: str
    confidence: Optional[float]
    response_time: float
    answer_length: int
    sources_count: int
    success: bool
    answer_preview: str
    reasoning: str
    error_message: Optional[str] = None

@dataclass
class DocumentSummary:
    document: str
    total_questions: int
    successful_questions: int
    success_rate: float
    avg_confidence: float
    high_confidence_count: int
    avg_response_time: float
    total_sources: int
    avg_answer_length: float

class ComprehensiveRAGValidator:
    def __init__(self, api_url: str = "http://localhost:3025/api/chat"):
        self.api_url = api_url
        self.results: List[TestResult] = []
        self.lock = Lock()
        
        # Enhanced question templates for comprehensive testing
        self.question_templates = {
            "Installation Guide": [
                "What are the system requirements for installing {product}?",
                "What are the prerequisites needed before installing {product}?",
                "How do you prepare the system environment for {product}?",
                "What ports and network configurations are required for {product}?",
                "What are the minimum hardware specifications for {product}?",
                "How do you verify that {product} installation was successful?",
                "What services need to be started after {product} installation?",
                "How do you troubleshoot common {product} installation issues?",
                "What are the post-installation configuration steps for {product}?",
                "How do you perform a clean uninstallation of {product}?",
                "What firewall rules and security settings are needed for {product}?",
                "How do you upgrade {product} from a previous version?",
                "What database setup and configuration is required for {product}?",
                "How do you configure SSL/TLS security for {product}?",
                "What are the typical installation error codes and solutions for {product}?",
                "How do you perform a silent or automated installation of {product}?",
                "What environment variables and system paths need to be configured for {product}?",
                "How do you backup existing data before installing {product}?",
                "What are the disk space and storage requirements for {product}?",
                "How do you validate and test the {product} installation?",
                "What licensing requirements and activation steps are needed for {product}?",
                "How do you configure high availability and clustering for {product}?"
            ],
            
            "User Guide": [
                "How do you access and navigate the {product} user interface?",
                "What are the main features and capabilities of {product}?",
                "How do you configure basic settings and preferences in {product}?",
                "What are the primary navigation menus and options in {product}?",
                "How do you create, add, or register new items in {product}?",
                "How do you edit, modify, or update existing configurations in {product}?",
                "What security features and access controls are available in {product}?",
                "How do you manage user accounts, roles, and permissions in {product}?",
                "What reports, analytics, and monitoring features does {product} provide?",
                "How do you export data, configurations, or reports from {product}?",
                "How do you import data, configurations, or settings into {product}?",
                "What keyboard shortcuts and efficiency features are available in {product}?",
                "How do you customize dashboards, views, and layouts in {product}?",
                "What troubleshooting and diagnostic tools are built into {product}?",
                "How do you backup and restore {product} configurations and data?",
                "What are the performance optimization tips and best practices for {product}?",
                "How do you monitor system health, status, and performance in {product}?",
                "What alerts, notifications, and alarm features does {product} support?",
                "How do you schedule automated tasks, jobs, or processes in {product}?",
                "What integration capabilities and third-party connections does {product} support?",
                "How do you manage workflows, processes, and business rules in {product}?",
                "What mobile, remote, or web-based access options are available for {product}?"
            ],
            
            "Reference Manual": [
                "What are the complete technical specifications and capabilities of {product}?",
                "What APIs, web services, and programming interfaces are available in {product}?",
                "What are all the configuration parameters, settings, and options for {product}?",
                "What data formats, file types, and protocols does {product} support?",
                "What are the detailed protocol specifications and communication standards for {product}?",
                "What error codes, status messages, and diagnostic information can {product} generate?",
                "What performance metrics, benchmarks, and capacity limits apply to {product}?",
                "What are the memory, CPU, and resource requirements for {product}?",
                "What network protocols, communication methods, and connectivity options does {product} use?",
                "What file formats, data structures, and storage methods does {product} utilize?",
                "What security protocols, encryption methods, and authentication mechanisms does {product} implement?",
                "What logging, auditing, and monitoring capabilities are built into {product}?",
                "What backup, recovery, and disaster preparedness procedures are recommended for {product}?",
                "What are the scalability limits, capacity constraints, and expansion options for {product}?",
                "What third-party integrations, plugins, and extensions are compatible with {product}?",
                "What compliance standards, regulations, and certifications does {product} meet?",
                "What monitoring tools, diagnostic utilities, and health check methods work with {product}?",
                "What are the disaster recovery, failover, and business continuity procedures for {product}?",
                "What performance tuning, optimization strategies, and efficiency improvements are available for {product}?",
                "What are the detailed upgrade, migration, and version management procedures for {product}?",
                "What debugging tools, diagnostic methods, and troubleshooting resources are available for {product}?",
                "What are the comprehensive best practices, guidelines, and recommended configurations for {product}?"
            ],
            
            "Release Notes": [
                "What new features and enhancements were introduced in {version}?",
                "What bugs, issues, and defects were fixed in {version}?",
                "What are the known issues, limitations, and workarounds in {version}?",
                "What security updates, patches, and vulnerability fixes are included in {version}?",
                "What breaking changes, incompatibilities, and migration requirements exist in {version}?",
                "What performance improvements and optimizations were made in {version}?",
                "What deprecated features, functions, and capabilities were removed in {version}?",
                "What are the detailed upgrade instructions and migration steps for {version}?",
                "What compatibility changes and system requirement updates exist in {version}?",
                "What new APIs, interfaces, and integration capabilities were added in {version}?",
                "What configuration changes, setting updates, and parameter modifications are required for {version}?",
                "What are the rollback procedures and downgrade instructions for {version}?",
                "What testing, validation, and quality assurance was performed for {version}?",
                "What documentation updates and user guide changes accompany {version}?",
                "What third-party component updates, library changes, and dependency modifications are included in {version}?",
                "What are the system requirement changes and hardware specification updates for {version}?",
                "What new integrations, partnerships, and ecosystem enhancements are available in {version}?",
                "What licensing changes, terms updates, and usage modifications occurred in {version}?",
                "What migration tools, conversion utilities, and upgrade assistance is available for {version}?",
                "What validation steps, verification procedures, and testing recommendations are provided for {version}?",
                "What monitoring changes, alerting updates, and diagnostic enhancements exist in {version}?",
                "What support changes, maintenance updates, and service modifications accompany {version}?"
            ]
        }

    def get_document_list(self) -> List[str]:
        """Get list of all PDF documents in the archive"""
        archive_path = "/home/kmccullor/Projects/Technical-Service-Assistant/uploads/archive"
        try:
            documents = [f for f in os.listdir(archive_path) if f.endswith('.pdf')]
            return sorted(documents)
        except Exception as e:
            print(f"❌ Error reading archive: {e}")
            return []

    def extract_product_info(self, filename: str) -> Tuple[str, str, str]:
        """Extract product name, version, and document type from filename"""
        # Remove .pdf extension
        name = filename.replace('.pdf', '')
        
        # Extract version if present (e.g., "4.14", "4.15.1")
        version = "latest"
        try:
            if " 4." in name:
                parts = name.split(" 4.")
                if len(parts) > 1:
                    version_part = parts[1].split()[0] if parts[1].split() else "14"
                    version = f"4.{version_part}"
            elif "4." in name:
                # Handle cases like "PPA.4.14.TechNote"
                import re
                version_match = re.search(r'4\.(\d+)', name)
                if version_match:
                    version = f"4.{version_match.group(1)}"
        except (IndexError, AttributeError):
            version = "4.14"  # Safe fallback
        
        # Determine document type
        doc_type = "User Guide"  # Default
        if "Installation Guide" in name or "Install" in name:
            doc_type = "Installation Guide"
        elif "Reference Manual" in name or "Specs" in name or "Reference" in name:
            doc_type = "Reference Manual"
        elif "Release Notes" in name or "Release" in name:
            doc_type = "Release Notes"
        elif "Integration Guide" in name:
            doc_type = "User Guide"  # Treat as user guide for questions
        elif "TechNote" in name or "Technical" in name:
            doc_type = "Reference Manual"  # Technical notes are reference material
        
        # Extract product name - be more robust
        product = name
        try:
            # Remove version information to get cleaner product name
            if version != "latest" and version in name:
                product = name.replace(version, "").strip()
            # Clean up common patterns
            product = product.replace("..", ".").replace("  ", " ").strip(".")
            if not product:
                product = name  # Fallback to full name if cleaning failed
        except:
            product = name  # Safe fallback
        
        return product, version, doc_type

    def generate_questions_for_document(self, filename: str) -> List[Dict[str, str]]:
        """Generate 22 targeted questions for a specific document"""
        product, version, doc_type = self.extract_product_info(filename)
        
        # Get appropriate templates
        templates = self.question_templates.get(doc_type, self.question_templates["User Guide"])
        
        questions = []
        for i, template in enumerate(templates[:22]):  # Limit to 22 questions
            if doc_type == "Release Notes":
                question = template.format(version=version)
            else:
                question = template.format(product=product)
            
            questions.append({
                'question': question,
                'type': doc_type,
                'template_id': i + 1
            })
        
        return questions

    def test_single_question(self, document: str, question_data: Dict[str, str]) -> TestResult:
        """Test a single question and return detailed results"""
        question = question_data['question']
        question_type = question_data['type']
        
        start_time = time.time()
        
        try:
            payload = {
                "messages": [{"role": "user", "content": question}]
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60,  # Increased timeout for complex queries
                headers={"Content-Type": "application/json"}
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                # Parse streaming response
                answer_tokens = []
                confidence = None
                sources_count = 0
                
                lines = response.text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            parsed = json.loads(line[6:])
                            if parsed.get('type') == 'token':
                                answer_tokens.append(parsed.get('token', ''))
                            elif parsed.get('type') == 'sources':
                                confidence = parsed.get('confidence')
                                sources_count = len(parsed.get('sources', []))
                        except json.JSONDecodeError:
                            continue
                
                answer = ''.join(answer_tokens)
                answer_length = len(answer)
                answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
                
                # Determine success (≥95% confidence target)
                success = confidence is not None and confidence >= 0.95 and answer_length > 50
                
                # Generate reasoning
                conf_pct = confidence * 100 if confidence else 0
                reasoning = f"Confidence: {conf_pct:.1f}% | Sources: {sources_count} | Length: {answer_length} chars"
                
                if success:
                    reasoning = "✅ " + reasoning + " | HIGH CONFIDENCE ACHIEVED"
                else:
                    reasoning = "⚠️ " + reasoning + " | Below 95% target"
                
                return TestResult(
                    document=document,
                    question=question,
                    question_type=question_type,
                    confidence=confidence,
                    response_time=response_time,
                    answer_length=answer_length,
                    sources_count=sources_count,
                    success=success,
                    answer_preview=answer_preview,
                    reasoning=reasoning
                )
            
            else:
                return TestResult(
                    document=document,
                    question=question,
                    question_type=question_type,
                    confidence=None,
                    response_time=response_time,
                    answer_length=0,
                    sources_count=0,
                    success=False,
                    answer_preview="",
                    reasoning=f"API Error: {response.status_code}",
                    error_message=f"HTTP {response.status_code}"
                )
        
        except Exception as e:
            return TestResult(
                document=document,
                question=question,
                question_type=question_type,
                confidence=None,
                response_time=time.time() - start_time,
                answer_length=0,
                sources_count=0,
                success=False,
                answer_preview="",
                reasoning=f"Exception: {str(e)[:100]}",
                error_message=str(e)
            )

    def test_document(self, document: str) -> List[TestResult]:
        """Test all questions for a single document"""
        print(f"\n🔍 Testing: {document}")
        print("=" * 80)
        
        questions = self.generate_questions_for_document(document)
        doc_results = []
        
        for i, question_data in enumerate(questions, 1):
            print(f"  📋 Question {i}/22: {question_data['question'][:80]}...")
            
            result = self.test_single_question(document, question_data)
            doc_results.append(result)
            
            # Display immediate result
            status = "✅" if result.success else "❌"
            conf_display = f"{result.confidence*100:.1f}%" if result.confidence else "N/A"
            print(f"      {status} Confidence: {conf_display} | Time: {result.response_time:.1f}s | Sources: {result.sources_count}")
            
            # Brief pause between requests
            time.sleep(1)
        
        # Document summary
        successful = sum(1 for r in doc_results if r.success)
        avg_conf = statistics.mean([r.confidence for r in doc_results if r.confidence]) if doc_results else 0
        
        print(f"\n📊 {document} Summary:")
        print(f"   Success Rate: {successful}/{len(doc_results)} ({successful/len(doc_results)*100:.1f}%)")
        print(f"   Average Confidence: {avg_conf*100:.1f}%")
        
        with self.lock:
            self.results.extend(doc_results)
        
        return doc_results

    def generate_document_summary(self, doc_results: List[TestResult]) -> Optional[DocumentSummary]:
        """Generate summary statistics for a document"""
        if not doc_results:
            return None
        
        document = doc_results[0].document
        total_questions = len(doc_results)
        successful_questions = sum(1 for r in doc_results if r.success)
        success_rate = successful_questions / total_questions
        
        confidences = [r.confidence for r in doc_results if r.confidence]
        avg_confidence = statistics.mean(confidences) if confidences else 0
        high_confidence_count = sum(1 for c in confidences if c >= 0.95)
        
        response_times = [r.response_time for r in doc_results]
        avg_response_time = statistics.mean(response_times) if response_times else 0
        
        total_sources = sum(r.sources_count for r in doc_results)
        
        answer_lengths = [r.answer_length for r in doc_results if r.answer_length > 0]
        avg_answer_length = statistics.mean(answer_lengths) if answer_lengths else 0
        
        return DocumentSummary(
            document=document,
            total_questions=total_questions,
            successful_questions=successful_questions,
            success_rate=success_rate,
            avg_confidence=avg_confidence,
            high_confidence_count=high_confidence_count,
            avg_response_time=avg_response_time,
            total_sources=total_sources,
            avg_answer_length=avg_answer_length
        )

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation across all documents"""
        print("🚀 COMPREHENSIVE END-TO-END RAG VALIDATION WITH RERANKING")
        print("=" * 100)
        
        start_time = time.time()
        documents = self.get_document_list()
        
        print(f"📚 Found {len(documents)} documents in archive")
        print(f"📋 Testing 22 questions per document = {len(documents) * 22} total questions")
        print(f"🎯 Target: ≥95% confidence per answer with reranking enabled")
        
        # Test each document sequentially for better stability
        document_summaries = []
        
        for i, document in enumerate(documents, 1):
            print(f"\n🔍 Document {i}/{len(documents)}: {document}")
            
            try:
                doc_results = self.test_document(document)
                doc_summary = self.generate_document_summary(doc_results)
                if doc_summary:
                    document_summaries.append(doc_summary)
                
                # Progress update
                elapsed = time.time() - start_time
                avg_time_per_doc = elapsed / i
                remaining_docs = len(documents) - i
                estimated_remaining = avg_time_per_doc * remaining_docs
                
                print(f"\n⏱️ Progress: {i}/{len(documents)} docs completed")
                print(f"   Elapsed: {elapsed/60:.1f} min | Est. remaining: {estimated_remaining/60:.1f} min")
                
            except Exception as e:
                print(f"❌ Error testing {document}: {e}")
                continue
        
        total_time = time.time() - start_time
        
        # Generate comprehensive report
        report = self.generate_comprehensive_report(document_summaries, total_time)
        
        # Save results
        self.save_results(report)
        
        return report

    def generate_comprehensive_report(self, document_summaries: List[DocumentSummary], total_time: float) -> Dict[str, Any]:
        """Generate a comprehensive validation report"""
        
        # Overall statistics
        total_documents = len(document_summaries)
        total_questions = sum(ds.total_questions for ds in document_summaries)
        total_successful = sum(ds.successful_questions for ds in document_summaries)
        overall_success_rate = total_successful / total_questions if total_questions > 0 else 0
        
        # Confidence statistics
        all_confidences = []
        for result in self.results:
            if result.confidence is not None:
                all_confidences.append(result.confidence)
        
        avg_confidence = statistics.mean(all_confidences) if all_confidences else 0
        high_confidence_count = sum(1 for c in all_confidences if c >= 0.95)
        high_confidence_rate = high_confidence_count / len(all_confidences) if all_confidences else 0
        
        # Performance statistics  
        all_response_times = [r.response_time for r in self.results if r.response_time > 0]
        avg_response_time = statistics.mean(all_response_times) if all_response_times else 0
        
        # Document type analysis
        doc_type_stats = {}
        for ds in document_summaries:
            doc_type = "Unknown"
            if "Installation Guide" in ds.document:
                doc_type = "Installation Guide"
            elif "User Guide" in ds.document:
                doc_type = "User Guide"
            elif "Reference Manual" in ds.document or "Specs" in ds.document:
                doc_type = "Reference Manual"
            elif "Release Notes" in ds.document:
                doc_type = "Release Notes"
            
            if doc_type not in doc_type_stats:
                doc_type_stats[doc_type] = {
                    'documents': 0, 'questions': 0, 'successful': 0,
                    'avg_confidence': 0, 'high_confidence': 0
                }
            
            doc_type_stats[doc_type]['documents'] += 1
            doc_type_stats[doc_type]['questions'] += ds.total_questions
            doc_type_stats[doc_type]['successful'] += ds.successful_questions
        
        # Top and bottom performers
        document_summaries.sort(key=lambda x: x.success_rate, reverse=True)
        top_performers = document_summaries[:5]
        bottom_performers = document_summaries[-5:] if len(document_summaries) >= 5 else []
        
        report = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'test_duration_minutes': total_time / 60,
                'api_endpoint': self.api_url,
                'reranking_enabled': True,
                'target_confidence': 95.0
            },
            'overall_statistics': {
                'total_documents': total_documents,
                'total_questions': total_questions,
                'successful_questions': total_successful,
                'success_rate': overall_success_rate,
                'average_confidence': avg_confidence,
                'high_confidence_count': high_confidence_count,
                'high_confidence_rate': high_confidence_rate,
                'average_response_time': avg_response_time,
                'total_test_time_minutes': total_time / 60
            },
            'confidence_analysis': {
                'target_achieved': high_confidence_rate >= 0.80,  # 80% of questions ≥95% confidence
                'confidence_95_plus': high_confidence_count,
                'confidence_90_95': sum(1 for c in all_confidences if 0.90 <= c < 0.95),
                'confidence_85_90': sum(1 for c in all_confidences if 0.85 <= c < 0.90),
                'confidence_80_85': sum(1 for c in all_confidences if 0.80 <= c < 0.85),
                'confidence_below_80': sum(1 for c in all_confidences if c < 0.80)
            },
            'document_type_analysis': doc_type_stats,
            'top_performers': [asdict(ds) for ds in top_performers],
            'bottom_performers': [asdict(ds) for ds in bottom_performers],
            'detailed_results': [asdict(result) for result in self.results]
        }
        
        return report

    def save_results(self, report: Dict[str, Any]):
        """Save comprehensive results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed JSON report
        json_file = f"comprehensive_rag_report_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate and save text summary report
        text_file = f"rag_validation_summary_{timestamp}.txt"
        self.generate_text_report(report, text_file)
        
        print(f"\n💾 Results saved:")
        print(f"   📄 Detailed report: {json_file}")
        print(f"   📝 Summary report: {text_file}")
        
        # Display final summary
        self.display_final_summary(report)

    def generate_text_report(self, report: Dict[str, Any], filename: str):
        """Generate a formatted text summary report"""
        
        with open(filename, 'w') as f:
            f.write("=" * 100 + "\n")
            f.write("COMPREHENSIVE RAG VALIDATION REPORT WITH RERANKING\n")
            f.write("=" * 100 + "\n")
            f.write(f"Generated: {report['metadata']['timestamp']}\n")
            f.write(f"Test Duration: {report['metadata']['test_duration_minutes']:.1f} minutes\n")
            f.write(f"API Endpoint: {report['metadata']['api_endpoint']}\n")
            f.write(f"Reranking: {'Enabled' if report['metadata']['reranking_enabled'] else 'Disabled'}\n")
            f.write(f"Target Confidence: {report['metadata']['target_confidence']}%\n\n")
            
            # Overall Statistics
            stats = report['overall_statistics']
            f.write("OVERALL PERFORMANCE\n")
            f.write("-" * 50 + "\n")
            f.write(f"Documents Tested: {stats['total_documents']}\n")
            f.write(f"Questions Asked: {stats['total_questions']}\n")
            f.write(f"Successful Questions: {stats['successful_questions']}\n")
            f.write(f"Success Rate: {stats['success_rate']*100:.1f}%\n")
            f.write(f"Average Confidence: {stats['average_confidence']*100:.1f}%\n")
            f.write(f"High Confidence (≥95%): {stats['high_confidence_count']} ({stats['high_confidence_rate']*100:.1f}%)\n")
            f.write(f"Average Response Time: {stats['average_response_time']:.1f}s\n\n")
            
            # Confidence Analysis
            conf = report['confidence_analysis']
            f.write("CONFIDENCE DISTRIBUTION\n")
            f.write("-" * 50 + "\n")
            f.write(f"95-100%: {conf['confidence_95_plus']} questions\n")
            f.write(f"90-95%:  {conf['confidence_90_95']} questions\n")
            f.write(f"85-90%:  {conf['confidence_85_90']} questions\n")
            f.write(f"80-85%:  {conf['confidence_80_85']} questions\n")
            f.write(f"<80%:    {conf['confidence_below_80']} questions\n")
            f.write(f"Target Achieved: {'✅ YES' if conf['target_achieved'] else '❌ NO'}\n\n")
            
            # Top Performers
            f.write("TOP PERFORMING DOCUMENTS\n")
            f.write("-" * 50 + "\n")
            for i, doc in enumerate(report['top_performers'][:10], 1):
                f.write(f"{i}. {doc['document']}\n")
                f.write(f"   Success Rate: {doc['success_rate']*100:.1f}% ({doc['successful_questions']}/{doc['total_questions']})\n")
                f.write(f"   Avg Confidence: {doc['avg_confidence']*100:.1f}%\n")
                f.write(f"   High Confidence: {doc['high_confidence_count']}\n\n")

    def display_final_summary(self, report: Dict[str, Any]):
        """Display comprehensive final summary"""
        print("\n" + "=" * 100)
        print("🎯 COMPREHENSIVE RAG VALIDATION SUMMARY WITH RERANKING")
        print("=" * 100)
        
        stats = report['overall_statistics']
        conf = report['confidence_analysis']
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Documents Tested: {stats['total_documents']}")
        print(f"   Questions Asked: {stats['total_questions']}")
        print(f"   Success Rate: {stats['successful_questions']}/{stats['total_questions']} ({stats['success_rate']*100:.1f}%)")
        
        print(f"\n🎯 CONFIDENCE ACHIEVEMENT:")
        print(f"   Average Confidence: {stats['average_confidence']*100:.1f}%")
        print(f"   High Confidence (≥95%): {stats['high_confidence_count']}/{len(report['detailed_results'])} ({stats['high_confidence_rate']*100:.1f}%)")
        target_status = "✅ TARGET ACHIEVED" if conf['target_achieved'] else "❌ TARGET NOT MET"
        print(f"   Target Status: {target_status}")
        
        print(f"\n⚡ PERFORMANCE:")
        print(f"   Average Response Time: {stats['average_response_time']:.1f}s")
        print(f"   Total Test Duration: {stats['total_test_time_minutes']:.1f} minutes")
        
        print(f"\n📚 TOP PERFORMERS:")
        for i, doc in enumerate(report['top_performers'][:5], 1):
            print(f"   {i}. {doc['document']}")
            print(f"      Success: {doc['successful_questions']}/{doc['total_questions']} ({doc['success_rate']*100:.1f}%) | Confidence: {doc['avg_confidence']*100:.1f}%")

if __name__ == "__main__":
    validator = ComprehensiveRAGValidator()
    report = validator.run_comprehensive_validation()