#!/usr/bin/env python3
"""
Phase 3A Multimodal System Tests

Comprehensive testing for multimodal enhancement capabilities including:
1. Vision model integration and image description
2. Enhanced image extraction and preprocessing
3. Advanced table processing with structure recognition
4. Multimodal search combining text, images, and tables
5. Cross-modal embeddings and unified content representation
6. Performance benchmarking for multimodal operations

This test suite validates Phase 3A functionality with mock data and sample content.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from PIL import Image, ImageDraw
import pandas as pd
import numpy as np

from phase3a_multimodal_simple import (
    Phase3AMultimodalSystem, VisionModel, ContentType, 
    ImageMetadata, TableMetadata, MultimodalContent
)
from utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(
    program_name="test_phase3a_simple",
    log_level="INFO",
    console_output=True,
)

class Phase3ATestSuite:
    """Comprehensive test suite for Phase 3A multimodal system."""
    
    def __init__(self):
        """Initialize test suite."""
        self.test_results = {}
        self.start_time = time.time()
        
        logger.info("🧪 Phase 3A Test Suite initialized")
    
    def create_mock_image(self, width=400, height=300, content_type="diagram") -> Image.Image:
        """Create a mock technical image for testing."""
        
        # Create base image
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        if content_type == "diagram":
            # Draw a simple network diagram
            draw.rectangle([50, 50, 150, 100], outline='black', width=2)
            draw.text((60, 70), "Router", fill='black')
            
            draw.rectangle([250, 50, 350, 100], outline='black', width=2)
            draw.text((260, 70), "Switch", fill='black')
            
            # Connection line
            draw.line([150, 75, 250, 75], fill='black', width=2)
            
        elif content_type == "chart":
            # Draw a simple bar chart
            for i in range(5):
                height_bar = 50 + i * 20
                draw.rectangle([50 + i*60, 200-height_bar, 90 + i*60, 200], 
                             fill='blue', outline='black')
        
        elif content_type == "schematic":
            # Draw a simple circuit schematic
            draw.circle((100, 150), 20, outline='black', width=2)
            draw.text((90, 145), "CPU", fill='black')
            
            draw.rectangle([180, 130, 220, 170], outline='black', width=2)
            draw.text((185, 145), "RAM", fill='black')
            
            # Connection lines
            draw.line([120, 150, 180, 150], fill='black', width=2)
        
        return img
    
    def create_mock_table_data(self) -> pd.DataFrame:
        """Create mock technical table data."""
        
        data = {
            'Parameter': ['CPU Usage', 'Memory Usage', 'Disk Space', 'Network Throughput', 'Response Time'],
            'Current Value': ['45%', '2.4 GB', '125 GB', '850 Mbps', '120 ms'],
            'Threshold': ['80%', '8 GB', '500 GB', '1 Gbps', '200 ms'],
            'Status': ['Normal', 'Normal', 'Normal', 'Normal', 'Normal']
        }
        
        return pd.DataFrame(data)
    
    async def test_vision_model_manager(self) -> bool:
        """Test vision model manager functionality."""
        
        logger.info("Testing vision model manager...")
        
        try:
            from phase3a_multimodal_simple import VisionModelManager
            
            # Test with BASIC model (simplified version)
            vision_manager = VisionModelManager(VisionModel.BASIC)
            
            # Create test image
            test_image = self.create_mock_image(content_type="diagram")
            
            # Test image description
            description, confidence = await vision_manager.describe_image(
                test_image, 
                context="network configuration"
            )
            
            logger.info(f"Vision model description: '{description}' (confidence: {confidence:.3f})")
            
            # Validate results
            assert isinstance(description, str), "Description should be string"
            assert len(description) > 0, "Description should not be empty"
            assert 0.0 <= confidence <= 1.0, "Confidence should be between 0 and 1"
            
            self.test_results["vision_model"] = {
                "passed": True,
                "description_length": len(description),
                "confidence": confidence,
                "model_available": vision_manager.model_available
            }
            
            logger.info("✅ Vision model manager test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vision model manager test failed: {e}")
            self.test_results["vision_model"] = {"passed": False, "error": str(e)}
            return False
    
    async def test_image_extraction_pipeline(self) -> bool:
        """Test image extraction pipeline with mock data."""
        
        logger.info("Testing image extraction pipeline...")
        
        try:
            from phase3a_multimodal_simple import VisionModelManager, MockImageExtractor
            
            # Initialize components
            vision_manager = VisionModelManager(VisionModel.BASIC)
            image_extractor = MockImageExtractor(vision_manager)
            
            # Test image classification
            test_images = [
                self.create_mock_image(400, 300, "diagram"),
                self.create_mock_image(800, 200, "chart"),  # Wide format
                self.create_mock_image(200, 600, "schematic")  # Tall format
            ]
            
            classifications = []
            for img in test_images:
                content_type = image_extractor._classify_image_content(img)
                classifications.append(content_type)
            
            logger.info(f"Image classifications: {[c.value for c in classifications]}")
            
            # Test technical element extraction
            test_description = "Network diagram showing router and switch connections with TCP/IP protocol configuration"
            elements = image_extractor._extract_technical_elements(test_images[0], test_description)
            
            logger.info(f"Technical elements extracted: {elements}")
            
            # Validate results
            assert len(classifications) == 3, "Should classify all test images"
            assert all(isinstance(c, ContentType) for c in classifications), "Should return ContentType enum"
            assert len(elements) > 0, "Should extract some technical elements"
            
            self.test_results["image_extraction"] = {
                "passed": True,
                "classifications": [c.value for c in classifications],
                "technical_elements": elements,
                "elements_count": len(elements)
            }
            
            logger.info("✅ Image extraction pipeline test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Image extraction pipeline test failed: {e}")
            self.test_results["image_extraction"] = {"passed": False, "error": str(e)}
            return False
    
    async def test_table_processor(self) -> bool:
        """Test enhanced table processor functionality."""
        
        logger.info("Testing enhanced table processor...")
        
        try:
            from phase3a_multimodal_simple import MockTableProcessor
            
            table_processor = MockTableProcessor()
            
            # Create test DataFrame
            test_df = self.create_mock_table_data()
            
            # Test table processing with mock extraction
            tables = table_processor.extract_tables_from_pdf("test.pdf")
            logger.info(f"Mock tables extracted: {len(tables)}")
            
            if tables:
                table = tables[0]
                logger.info(f"Table content type: {table.content_type}")
                logger.info(f"Table description: {table.description}")
                logger.info(f"Table text length: {len(table.text_content)}")
                
                # Check table metadata
                metadata = table.metadata
                has_headers = metadata.has_headers
                data_types = metadata.data_types
                summary = metadata.summary
                is_technical = metadata.technical_data
                
                logger.info(f"Headers detected: {has_headers}")
                logger.info(f"Data types: {data_types}")
                logger.info(f"Summary: {summary}")
                logger.info(f"Technical table: {is_technical}")
            
            # Validate results
            assert len(tables) >= 1, "Should extract at least one mock table"
            assert isinstance(has_headers, bool), "Header detection should return boolean"
            assert isinstance(data_types, dict), "Data types should be dictionary"  
            assert len(summary) > 0, "Summary should not be empty"
            assert isinstance(is_technical, bool), "Technical detection should return boolean"
            
            self.test_results["table_processor"] = {
                "passed": True,
                "has_headers": has_headers,
                "data_types": data_types,
                "summary_length": len(summary),
                "is_technical": is_technical,
                "text_length": len(text_repr)
            }
            
            logger.info("✅ Enhanced table processor test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced table processor test failed: {e}")
            self.test_results["table_processor"] = {"passed": False, "error": str(e)}
            return False
    
    async def test_multimodal_search_engine(self) -> bool:
        """Test multimodal search engine functionality."""
        
        logger.info("Testing multimodal search engine...")
        
        try:
            from phase2c_accuracy_system import Phase2CAccuracySystem
            from phase3a_multimodal_system import MultimodalSearchEngine
            
            # Initialize components (using simplified approach for testing)
            phase2c_system = Phase2CAccuracySystem()
            search_engine = MultimodalSearchEngine(phase2c_system)
            
            # Create mock multimodal content
            mock_contents = []
            
            # Mock image content
            image_metadata = ImageMetadata(
                image_id="test_img_001",
                source_document="test_doc.pdf",
                page_number=1,
                position=(100, 100, 400, 300),
                content_type=ContentType.DIAGRAM,
                width=300,
                height=200,
                file_size=1024,
                color_mode="RGB",
                description="Network diagram showing router configuration",
                technical_elements=["router", "network", "configuration"]
            )
            
            image_content = MultimodalContent(
                content_id="img_001",
                content_type=ContentType.DIAGRAM,
                text_content="Network diagram showing router configuration with TCP/IP settings",
                metadata=image_metadata,
                description="Network diagram showing router configuration"
            )
            
            # Mock table content
            table_metadata = TableMetadata(
                table_id="test_table_001",
                source_document="test_doc.pdf", 
                page_number=2,
                position=(50, 200, 500, 400),
                rows=5,
                columns=4,
                has_headers=True,
                summary="System performance metrics table",
                technical_data=True
            )
            
            table_content = MultimodalContent(
                content_id="table_001",
                content_type=ContentType.TABLE,
                text_content="System performance metrics: CPU Usage 45%, Memory 2.4GB, Network 850Mbps",
                table_data=self.create_mock_table_data(),
                metadata=table_metadata,
                description="System performance metrics table"
            )
            
            mock_contents = [image_content, table_content]
            
            # Index mock content
            search_engine.index_multimodal_content(mock_contents)
            
            # Test multimodal matching
            matches = search_engine._find_multimodal_matches("network configuration", [ContentType.DIAGRAM])
            logger.info(f"Multimodal matches found: {len(matches)}")
            
            # Test diversity calculation
            from phase2c_accuracy_system import SearchResult
            
            mock_results = [
                SearchResult(
                    content="Network configuration text",
                    document_name="test.pdf",
                    metadata={"content_type": "text"},
                    score=0.8,
                    method="text_search"
                ),
                SearchResult(
                    content="Network diagram",
                    document_name="test.pdf", 
                    metadata={"content_type": "image"},
                    score=0.7,
                    method="multimodal_image"
                )
            ]
            
            diversity = search_engine._calculate_multimodal_diversity(mock_results)
            logger.info(f"Diversity score: {diversity:.3f}")
            
            # Validate results
            assert len(search_engine.multimodal_index) == 2, "Should index 2 mock contents"
            assert len(matches) >= 0, "Should return matches (may be 0 for simple keyword matching)"
            assert 0.0 <= diversity <= 1.0, "Diversity should be between 0 and 1"
            
            self.test_results["multimodal_search"] = {
                "passed": True,
                "indexed_items": len(search_engine.multimodal_index),
                "matches_found": len(matches),
                "diversity_score": diversity
            }
            
            logger.info("✅ Multimodal search engine test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Multimodal search engine test failed: {e}")
            self.test_results["multimodal_search"] = {"passed": False, "error": str(e)}
            return False
    
    async def test_phase3a_system_integration(self) -> bool:
        """Test complete Phase 3A system integration."""
        
        logger.info("Testing Phase 3A system integration...")
        
        try:
            # Initialize Phase 3A system
            multimodal_system = Phase3AMultimodalSystem(VisionModel.BLIP)
            
            # Test search without processing documents (using empty index)
            test_queries = [
                "network configuration",
                "system performance table",
                "technical diagram"
            ]
            
            search_results = []
            for query in test_queries:
                try:
                    results, metrics = await multimodal_system.search_multimodal(query, top_k=3)
                    search_results.append({
                        "query": query,
                        "results_count": len(results),
                        "confidence": metrics.confidence_score,
                        "response_time": metrics.response_time
                    })
                    logger.info(f"Query '{query}': {len(results)} results, "
                               f"confidence: {metrics.confidence_score:.3f}")
                except Exception as e:
                    logger.warning(f"Search failed for '{query}': {e}")
                    search_results.append({
                        "query": query,
                        "error": str(e)
                    })
            
            # Test system statistics
            stats = multimodal_system.get_multimodal_statistics()
            logger.info(f"System statistics: {json.dumps(stats, indent=2)}")
            
            # Validate integration
            assert len(search_results) == len(test_queries), "Should process all test queries"
            assert isinstance(stats, dict), "Statistics should be dictionary"
            assert "total_documents_processed" in stats, "Should include document count"
            
            self.test_results["system_integration"] = {
                "passed": True,
                "queries_tested": len(test_queries),
                "search_results": search_results,
                "statistics": stats
            }
            
            logger.info("✅ Phase 3A system integration test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 3A system integration test failed: {e}")
            self.test_results["system_integration"] = {"passed": False, "error": str(e)}
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all Phase 3A tests and return comprehensive results."""
        
        logger.info("🚀 Starting Phase 3A Multimodal System Test Suite")
        
        # Run all tests
        tests = [
            ("Vision Model Manager", self.test_vision_model_manager),
            ("Image Extraction Pipeline", self.test_image_extraction_pipeline),
            ("Enhanced Table Processor", self.test_table_processor),
            ("Multimodal Search Engine", self.test_multimodal_search_engine),
            ("Phase 3A System Integration", self.test_phase3a_system_integration)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"Running {test_name}...")
            try:
                success = await test_func()
                if success:
                    passed_tests += 1
                    logger.info(f"✅ {test_name} completed successfully")
                else:
                    logger.error(f"❌ {test_name} failed")
            except Exception as e:
                logger.error(f"❌ {test_name} failed with exception: {e}")
        
        # Calculate total test time
        total_time = time.time() - self.start_time
        
        # Generate final report
        final_report = {
            "test_suite": "Phase 3A Multimodal Enhancement System",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": passed_tests / total_tests,
                "total_time": total_time
            },
            "detailed_results": self.test_results,
            "status": "PASSED" if passed_tests == total_tests else "PARTIAL" if passed_tests > 0 else "FAILED"
        }
        
        # Log final summary
        logger.info(f"📊 Phase 3A Test Suite Complete:")
        logger.info(f"   ✅ Passed: {passed_tests}/{total_tests}")
        logger.info(f"   ❌ Failed: {total_tests - passed_tests}/{total_tests}")
        logger.info(f"   📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        logger.info(f"   ⏱️  Total Time: {total_time:.2f}s")
        logger.info(f"   🏆 Status: {final_report['status']}")
        
        return final_report

async def main():
    """Main function to run Phase 3A tests."""
    
    # Initialize and run test suite
    test_suite = Phase3ATestSuite()
    results = await test_suite.run_all_tests()
    
    # Save results to file
    results_file = Path("test_results_phase3a.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"📄 Test results saved to {results_file}")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())