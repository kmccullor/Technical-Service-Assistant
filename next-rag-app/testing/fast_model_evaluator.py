#!/usr/bin/env python3
"""
Fast Model Evaluation System
Tests smaller models for improved response times while maintaining quality
"""

import requests
import time
import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ModelTestResult:
    model_name: str
    avg_response_time: float
    success_rate: float
    quality_score: float
    token_efficiency: float
    overall_score: float

class FastModelEvaluator:
    def __init__(self, ollama_instances: Optional[List[str]] = None):
        self.ollama_instances = ollama_instances or [
            'http://localhost:11434',
            'http://localhost:11435', 
            'http://localhost:11436',
            'http://localhost:11437'
        ]
        
        # Test models to evaluate (small to large)
        self.test_models = [
            'llama3.2:1b',      # Fastest, smallest
            'llama3.2:3b',      # Good balance
            'phi3:mini',        # Microsoft's efficient model
            'gemma2:2b',        # Google's compact model
            'mistral:7b',       # Current model (baseline)
            'llama3.1:8b',      # Larger model for comparison
        ]
        
        # Standard test questions
        self.test_questions = [
            "What is RNI?",
            "How do I install RNI?",
            "What are the system requirements?",
            "How do I configure RNI?",
            "What troubleshooting steps are available?",
            "What are the latest features?",
            "How do I integrate with other systems?",
            "What are the security requirements?",
            "How do I update RNI?",
            "What support options are available?"
        ]

    async def check_model_availability(self, model: str) -> Dict[str, bool]:
        """Check which instances have the model available"""
        available_instances = {}
        
        async with aiohttp.ClientSession() as session:
            for instance_url in self.ollama_instances:
                try:
                    async with session.get(f"{instance_url}/api/tags", timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            models = [m['name'] for m in data.get('models', [])]
                            available_instances[instance_url] = model in models
                        else:
                            available_instances[instance_url] = False
                except Exception as e:
                    print(f"❌ {instance_url} not responding: {e}")
                    available_instances[instance_url] = False
        
        return available_instances

    async def pull_model(self, model: str, instance_url: str) -> bool:
        """Pull a model to an Ollama instance"""
        print(f"📥 Pulling {model} to {instance_url}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                pull_data = {"name": model}
                
                async with session.post(
                    f"{instance_url}/api/pull",
                    json=pull_data,
                    timeout=600  # 10 minutes timeout for model pulling
                ) as response:
                    if response.status == 200:
                        # Stream the pull progress
                        async for line in response.content:
                            if line:
                                try:
                                    progress = json.loads(line.decode())
                                    if 'status' in progress:
                                        print(f"  {progress['status']}")
                                    if progress.get('status') == 'success':
                                        return True
                                except json.JSONDecodeError:
                                    continue
                    
                    return response.status == 200
                    
        except Exception as e:
            print(f"❌ Failed to pull {model}: {e}")
            return False

    async def test_model_performance(
        self, 
        model: str, 
        instance_url: str, 
        questions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Test a model's performance on standard questions"""
        questions = questions or self.test_questions[:5]  # Use first 5 for speed
        results = {
            'response_times': [],
            'success_count': 0,
            'total_questions': len(questions),
            'responses': []
        }
        
        print(f"🧪 Testing {model} on {instance_url}...")
        
        async with aiohttp.ClientSession() as session:
            for i, question in enumerate(questions, 1):
                start_time = time.time()
                
                try:
                    # Create optimized prompt for testing
                    prompt = f"user: {question}\nassistant:"
                    
                    generate_data = {
                        "model": model,
                        "prompt": prompt,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 512,  # Limited for speed testing
                            "top_k": 40,
                            "top_p": 0.9
                        },
                        "stream": False
                    }
                    
                    async with session.post(
                        f"{instance_url}/api/generate",
                        json=generate_data,
                        timeout=30  # 30 second timeout
                    ) as response:
                        response_time = time.time() - start_time
                        
                        if response.status == 200:
                            data = await response.json()
                            response_text = data.get('response', '')
                            
                            results['response_times'].append(response_time)
                            results['success_count'] += 1
                            results['responses'].append({
                                'question': question,
                                'response': response_text,
                                'response_time': response_time
                            })
                            
                            print(f"  ✅ Q{i}: {response_time:.2f}s - {response_text[:50]}...")
                        else:
                            print(f"  ❌ Q{i}: Failed with status {response.status}")
                            
                except Exception as e:
                    response_time = time.time() - start_time
                    print(f"  ❌ Q{i}: Error - {str(e)} ({response_time:.2f}s)")
        
        return results

    def calculate_quality_score(self, responses: List[Dict]) -> float:
        """Calculate quality score based on response characteristics"""
        if not responses:
            return 0.0
        
        quality_metrics = []
        
        for resp in responses:
            response_text = resp['response'].strip()
            question = resp['question'].lower()
            
            # Basic quality indicators
            score = 0.0
            
            # Length appropriateness (not too short, not too long)
            length = len(response_text)
            if 50 <= length <= 500:
                score += 0.3
            elif 30 <= length <= 800:
                score += 0.2
            
            # Relevance indicators (basic keyword matching)
            if 'rni' in response_text.lower():
                score += 0.2
            
            # Question-specific relevance
            if 'install' in question and any(word in response_text.lower() 
                for word in ['install', 'setup', 'configure', 'download']):
                score += 0.2
            elif 'what is' in question and any(word in response_text.lower() 
                for word in ['is', 'system', 'platform', 'software']):
                score += 0.2
            elif 'how' in question and any(word in response_text.lower() 
                for word in ['step', 'process', 'procedure', 'follow']):
                score += 0.2
            
            # Avoid generic responses
            generic_phrases = ['i don\'t know', 'cannot provide', 'not enough information']
            if not any(phrase in response_text.lower() for phrase in generic_phrases):
                score += 0.1
            
            quality_metrics.append(min(score, 1.0))
        
        return sum(quality_metrics) / len(quality_metrics)

    async def evaluate_all_models(self) -> List[ModelTestResult]:
        """Evaluate all available models"""
        results = []
        
        print("🚀 Starting fast model evaluation...")
        print("=" * 60)
        
        for model in self.test_models:
            print(f"\n📊 Evaluating {model}...")
            
            # Check availability
            availability = await self.check_model_availability(model)
            available_instances = [url for url, available in availability.items() if available]
            
            if not available_instances:
                # Try to pull the model to the first instance
                first_instance = self.ollama_instances[0]
                print(f"📥 {model} not found, attempting to pull...")
                
                if await self.pull_model(model, first_instance):
                    available_instances = [first_instance]
                else:
                    print(f"❌ Could not pull {model}, skipping...")
                    continue
            
            # Test on the first available instance
            test_instance = available_instances[0]
            performance = await self.test_model_performance(model, test_instance)
            
            if performance['response_times']:
                avg_response_time = sum(performance['response_times']) / len(performance['response_times'])
                success_rate = performance['success_count'] / performance['total_questions']
                quality_score = self.calculate_quality_score(performance['responses'])
                
                # Token efficiency (inverse of response time * quality)
                token_efficiency = quality_score / max(avg_response_time, 0.1)
                
                # Overall score (balanced metric)
                overall_score = (
                    (1.0 / max(avg_response_time, 0.1)) * 0.4 +  # Speed (40%)
                    success_rate * 0.3 +                          # Reliability (30%)
                    quality_score * 0.2 +                        # Quality (20%)
                    token_efficiency * 0.1                       # Efficiency (10%)
                )
                
                result = ModelTestResult(
                    model_name=model,
                    avg_response_time=avg_response_time,
                    success_rate=success_rate,
                    quality_score=quality_score,
                    token_efficiency=token_efficiency,
                    overall_score=overall_score
                )
                
                results.append(result)
                
                print(f"📈 Results for {model}:")
                print(f"   Avg Response Time: {avg_response_time:.2f}s")
                print(f"   Success Rate: {success_rate:.1%}")
                print(f"   Quality Score: {quality_score:.2f}")
                print(f"   Overall Score: {overall_score:.3f}")
            else:
                print(f"❌ No successful responses from {model}")
        
        return results

    def generate_recommendations(self, results: List[ModelTestResult]) -> Dict[str, Any]:
        """Generate model recommendations based on results"""
        if not results:
            return {"error": "No models successfully tested"}
        
        # Sort by overall score
        sorted_results = sorted(results, key=lambda x: x.overall_score, reverse=True)
        
        # Find best performers in different categories
        fastest = min(results, key=lambda x: x.avg_response_time)
        most_reliable = max(results, key=lambda x: x.success_rate)
        highest_quality = max(results, key=lambda x: x.quality_score)
        best_overall = sorted_results[0]
        
        recommendations = {
            "best_overall": {
                "model": best_overall.model_name,
                "score": best_overall.overall_score,
                "reason": "Highest overall score balancing speed, reliability, and quality"
            },
            "fastest": {
                "model": fastest.model_name,
                "time": fastest.avg_response_time,
                "reason": f"Fastest average response time ({fastest.avg_response_time:.2f}s)"
            },
            "most_reliable": {
                "model": most_reliable.model_name,
                "rate": most_reliable.success_rate,
                "reason": f"Highest success rate ({most_reliable.success_rate:.1%})"
            },
            "highest_quality": {
                "model": highest_quality.model_name,
                "score": highest_quality.quality_score,
                "reason": f"Best response quality ({highest_quality.quality_score:.2f})"
            },
            "production_recommendation": None
        }
        
        # Production recommendation logic
        for result in sorted_results:
            if (result.avg_response_time < 10.0 and 
                result.success_rate > 0.8 and 
                result.quality_score > 0.5):
                recommendations["production_recommendation"] = {
                    "model": result.model_name,
                    "reason": "Best balance of speed (<10s), reliability (>80%), and quality (>0.5)"
                }
                break
        
        return recommendations

async def main():
    """Main execution function"""
    evaluator = FastModelEvaluator()
    
    # Run evaluation
    results = await evaluator.evaluate_all_models()
    
    if not results:
        print("❌ No models could be evaluated")
        return
    
    # Generate recommendations
    recommendations = evaluator.generate_recommendations(results)
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = Path(f"/home/kmccullor/Projects/Technical-Service-Assistant/next-rag-app/testing/model_evaluation_{timestamp}.json")
    
    evaluation_data = {
        "timestamp": timestamp,
        "results": [
            {
                "model_name": r.model_name,
                "avg_response_time": r.avg_response_time,
                "success_rate": r.success_rate,
                "quality_score": r.quality_score,
                "token_efficiency": r.token_efficiency,
                "overall_score": r.overall_score
            }
            for r in results
        ],
        "recommendations": recommendations
    }
    
    with open(results_file, 'w') as f:
        json.dump(evaluation_data, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("🎯 MODEL EVALUATION SUMMARY")
    print("=" * 60)
    
    print("\n📊 RESULTS (sorted by overall score):")
    sorted_results = sorted(results, key=lambda x: x.overall_score, reverse=True)
    for i, result in enumerate(sorted_results, 1):
        print(f"{i}. {result.model_name}")
        print(f"   Overall Score: {result.overall_score:.3f}")
        print(f"   Avg Time: {result.avg_response_time:.2f}s")
        print(f"   Success: {result.success_rate:.1%}")
        print(f"   Quality: {result.quality_score:.2f}")
        print()
    
    print("🎯 RECOMMENDATIONS:")
    for category, rec in recommendations.items():
        if rec and category != "production_recommendation":
            print(f"  {category.replace('_', ' ').title()}: {rec['model']}")
            print(f"    {rec['reason']}")
            print()
    
    if recommendations.get("production_recommendation"):
        print("🚀 PRODUCTION RECOMMENDATION:")
        prod_rec = recommendations["production_recommendation"]
        print(f"   Model: {prod_rec['model']}")
        print(f"   Reason: {prod_rec['reason']}")
    else:
        print("⚠️  No model meets production criteria (speed <10s, reliability >80%, quality >0.5)")
    
    print(f"\n💾 Detailed results saved to: {results_file}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())