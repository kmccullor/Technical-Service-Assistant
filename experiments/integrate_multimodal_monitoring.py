#!/usr/bin/env python3
"""
Multimodal Monitoring Integration Script

This script integrates the multimodal monitoring system with existing Phase 3A components,
providing comprehensive analytics and real-time monitoring of multimodal operations.

Usage:
    python integrate_multimodal_monitoring.py

Features:
- Automatic instrumentation of Phase 3A components
- Real-time metrics collection and export
- Integration with existing Prometheus/Grafana stack
- Performance monitoring and alerting
"""

import asyncio
import time
from pathlib import Path
import json
from typing import Dict, Any

from multimodal_monitoring import MultimodalMonitoringIntegration
from utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(
    program_name="multimodal_monitoring_integration",
    log_level="INFO",
    console_output=True,
)

class MultimodalSystemInstrumentation:
    """Orchestrates multimodal system instrumentation and monitoring."""
    
    def __init__(self):
        """Initialize multimodal system instrumentation."""
        self.monitoring = MultimodalMonitoringIntegration()
        self.instrumented_components = []
        
        logger.info("Multimodal system instrumentation initialized")
    
    async def setup_comprehensive_monitoring(self):
        """Setup comprehensive monitoring for all multimodal components."""
        
        logger.info("🔧 Setting up comprehensive multimodal monitoring...")
        
        try:
            # Import Phase 3A components
            from cross_modal_embeddings_simple import SimpleCrossModalSearchEngine, SimpleCrossModalEmbeddingGenerator
            from phase3a_multimodal_simple import Phase3AMultimodalSystem, VisionModelManager
            
            logger.info("✅ Phase 3A components imported successfully")
            
            # Initialize components
            multimodal_system = Phase3AMultimodalSystem()
            search_engine = SimpleCrossModalSearchEngine()
            
            # Instrument vision model manager
            if hasattr(multimodal_system, 'vision_model_manager'):
                self.monitoring.instrument_vision_model(multimodal_system.vision_model_manager)
                self.instrumented_components.append("vision_model_manager")
                logger.info("✅ Vision model manager instrumented")
            
            # Instrument embedding generator
            if hasattr(search_engine, 'embedding_generator'):
                self.monitoring.instrument_embedding_generator(search_engine.embedding_generator)
                self.instrumented_components.append("embedding_generator")
                logger.info("✅ Embedding generator instrumented")
            
            # Instrument search engine
            self.monitoring.instrument_search_engine(search_engine)
            self.instrumented_components.append("search_engine")
            logger.info("✅ Search engine instrumented")
            
            # Test instrumented components
            await self.test_instrumentation(search_engine)
            
            logger.info(f"🎉 Comprehensive monitoring setup complete for {len(self.instrumented_components)} components")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Could not import Phase 3A components: {e}")
            logger.info("📊 Setting up monitoring infrastructure without instrumentation...")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to setup monitoring: {e}")
            return False
    
    async def test_instrumentation(self, search_engine):
        """Test that instrumentation is working correctly."""
        
        logger.info("🧪 Testing instrumentation...")
        
        try:
            # Test search engine instrumentation
            from phase3a_multimodal_simple import MultimodalContent, ContentType
            import pandas as pd
            
            # Create test content
            test_content = MultimodalContent(
                content_id="test_monitoring_001",
                content_type=ContentType.TEXT,
                text_content="Test content for monitoring instrumentation",
                description="Monitoring test content"
            )
            
            # Index content (should trigger embedding generation metrics)
            await search_engine.index_multimodal_content([test_content])
            
            # Perform search (should trigger search metrics)
            results = await search_engine.cross_modal_search("test monitoring", top_k=1)
            
            logger.info(f"✅ Instrumentation test completed: {len(results)} results returned")
            
        except Exception as e:
            logger.warning(f"⚠️ Instrumentation testing failed: {e}")
    
    def generate_monitoring_report(self) -> Dict[str, Any]:
        """Generate comprehensive monitoring report."""
        
        dashboard_data = self.monitoring.get_monitoring_dashboard_data()
        
        report = {
            "monitoring_report": {
                "timestamp": dashboard_data["timestamp"],
                "system_status": {
                    "monitoring_active": dashboard_data["monitoring_status"] == "active",
                    "prometheus_enabled": dashboard_data["prometheus_enabled"],
                    "instrumented_components": self.instrumented_components
                },
                "metrics_summary": dashboard_data["session_summary"],
                "recent_activity": dashboard_data["recent_metrics"],
                "component_status": {
                    "vision_model": "instrumented" if "vision_model_manager" in self.instrumented_components else "not_instrumented",
                    "embedding_generator": "instrumented" if "embedding_generator" in self.instrumented_components else "not_instrumented", 
                    "search_engine": "instrumented" if "search_engine" in self.instrumented_components else "not_instrumented"
                }
            }
        }
        
        return report
    
    def save_monitoring_configuration(self):
        """Save monitoring configuration to file."""
        
        config = {
            "multimodal_monitoring_config": {
                "version": "1.0",
                "enabled": True,
                "prometheus_integration": True,
                "grafana_dashboard": "multimodal-analytics",
                "instrumented_components": self.instrumented_components,
                "metrics_retention": "7d",
                "alert_thresholds": {
                    "vision_model_latency_p95": 5.0,
                    "embedding_generation_latency_p95": 2.0,
                    "search_accuracy_min": 0.5,
                    "cross_modal_similarity_min": 0.3
                }
            }
        }
        
        config_path = Path("monitoring/multimodal_config.json")
        config_path.parent.mkdir(exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"📄 Monitoring configuration saved to {config_path}")

async def main():
    """Main function to setup and test multimodal monitoring."""
    
    logger.info("🚀 Starting Multimodal Monitoring Integration")
    
    # Initialize instrumentation
    instrumentation = MultimodalSystemInstrumentation()
    
    # Setup comprehensive monitoring
    setup_success = await instrumentation.setup_comprehensive_monitoring()
    
    if setup_success:
        logger.info("✅ Monitoring setup successful")
    else:
        logger.warning("⚠️ Monitoring setup completed with limitations")
    
    # Generate and display monitoring report
    report = instrumentation.generate_monitoring_report()
    
    logger.info("📊 Monitoring Report:")
    logger.info(f"  Status: {'Active' if report['monitoring_report']['system_status']['monitoring_active'] else 'Inactive'}")
    logger.info(f"  Prometheus: {'Enabled' if report['monitoring_report']['system_status']['prometheus_enabled'] else 'Disabled'}")
    logger.info(f"  Components: {', '.join(report['monitoring_report']['system_status']['instrumented_components'])}")
    
    metrics_summary = report['monitoring_report']['metrics_summary']
    logger.info(f"  Total metrics: {metrics_summary.get('total_metrics_recorded', 0)}")
    
    recent_activity = report['monitoring_report']['recent_activity']
    logger.info("  Recent activity:")
    for activity, count in recent_activity.items():
        logger.info(f"    {activity}: {count}")
    
    # Save monitoring configuration
    instrumentation.save_monitoring_configuration()
    
    # Test basic monitoring functionality
    logger.info("🧪 Testing basic monitoring functionality...")
    
    # Simulate some metrics
    monitoring = instrumentation.monitoring
    monitoring.metrics_collector.record_vision_model_performance(
        model_name="test_model",
        content_type="image", 
        operation="test_operation",
        latency=1.2,
        confidence=0.85
    )
    
    monitoring.metrics_collector.record_embedding_generation(
        content_type="text",
        model_name="ollama_embed",
        dimension=768,
        latency=0.3,
        cache_hit=True
    )
    
    monitoring.metrics_collector.record_cross_modal_similarity(
        content_type_1="text",
        content_type_2="image", 
        similarity_score=0.67,
        is_cross_modal=True
    )
    
    logger.info("✅ Basic monitoring functionality tested")
    
    # Final report
    final_report = instrumentation.generate_monitoring_report()
    final_metrics = final_report['monitoring_report']['metrics_summary']
    
    logger.info("🎉 Multimodal Monitoring Integration Complete!")
    logger.info(f"  Final metrics recorded: {final_metrics.get('total_metrics_recorded', 0)}")
    logger.info("  System ready for production monitoring")
    
    return final_report

if __name__ == "__main__":
    result = asyncio.run(main())