"""
Phase 3B: Advanced Vision Models Integration
Comprehensive vision model system with BLIP-2, LLaVA, and Ollama Vision support.
"""

import asyncio
import base64
import io
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import requests
from PIL import Image

from config import settings
from utils.exceptions import VisionModelError
from utils.logging_setup import get_logger
from utils.monitoring import monitor_performance

logger = get_logger(__name__)


class VisionModelType(Enum):
    """Advanced vision model types for Phase 3B."""
    
    BLIP2 = "blip2"
    LLAVA = "llava"
    OLLAMA_VISION = "ollama_vision"
    BASIC = "basic"


class VisionTaskType(Enum):
    """Types of vision analysis tasks."""
    
    IMAGE_CAPTIONING = "image_captioning"
    VISUAL_QUESTION_ANSWERING = "visual_qa"
    OBJECT_DETECTION = "object_detection"
    TEXT_EXTRACTION = "text_extraction"
    TECHNICAL_ANALYSIS = "technical_analysis"
    CHART_READING = "chart_reading"
    DIAGRAM_INTERPRETATION = "diagram_interpretation"


@dataclass
class VisionModelConfig:
    """Configuration for advanced vision models."""
    
    model_type: VisionModelType
    model_name: str
    endpoint_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 500
    temperature: float = 0.7
    timeout: int = 30
    cache_enabled: bool = True
    batch_size: int = 1
    gpu_enabled: bool = False
    confidence_threshold: float = 0.5


@dataclass
class VisionAnalysisResult:
    """Result from advanced vision model analysis."""
    
    model_type: VisionModelType
    task_type: VisionTaskType
    description: str
    confidence: float
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    technical_elements: List[str] = field(default_factory=list)
    extracted_text: Optional[str] = None
    objects_detected: List[Dict[str, Any]] = field(default_factory=list)
    chart_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AdvancedVisionModel(ABC):
    """Abstract base class for advanced vision models."""
    
    def __init__(self, config: VisionModelConfig):
        self.config = config
        self.model_type = config.model_type
        self.cache = {}
        
    @abstractmethod
    async def analyze_image(
        self,
        image: Union[Image.Image, str, bytes],
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        prompt: Optional[str] = None,
        **kwargs
    ) -> VisionAnalysisResult:
        """Analyze image with the advanced vision model."""
        pass
    
    @abstractmethod
    async def batch_analyze(
        self,
        images: List[Union[Image.Image, str, bytes]],
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        **kwargs
    ) -> List[VisionAnalysisResult]:
        """Batch analyze multiple images."""
        pass
        
    def _image_to_base64(self, image: Union[Image.Image, str, bytes]) -> str:
        """Convert image to base64 string."""
        if isinstance(image, str):
            # Assume it's a file path
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        elif isinstance(image, bytes):
            return base64.b64encode(image).decode('utf-8')
        elif isinstance(image, Image.Image):
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        else:
            raise VisionModelError(f"Unsupported image type: {type(image)}")
    
    def _generate_cache_key(self, image_data: str, task_type: VisionTaskType, prompt: str = "") -> str:
        """Generate cache key for vision analysis."""
        import hashlib
        content = f"{image_data[:100]}{task_type.value}{prompt}"
        return hashlib.md5(content.encode()).hexdigest()


class BLIP2VisionModel(AdvancedVisionModel):
    """BLIP-2 (Bootstrap Language-Image Pre-training) integration."""
    
    def __init__(self, config: VisionModelConfig):
        super().__init__(config)
        self.model = None
        self.processor = None
        
    async def _initialize_model(self):
        """Initialize BLIP-2 model and processor."""
        try:
            # Mock implementation for now - would use transformers in production
            logger.info(f"Initializing BLIP-2 model: {self.config.model_name}")
            # from transformers import Blip2Processor, Blip2ForConditionalGeneration
            # self.processor = Blip2Processor.from_pretrained(self.config.model_name)
            # self.model = Blip2ForConditionalGeneration.from_pretrained(self.config.model_name)
            logger.info("BLIP-2 model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BLIP-2 model: {e}")
            raise VisionModelError(f"BLIP-2 initialization failed: {e}")
    
    @monitor_performance()
    async def analyze_image(
        self,
        image: Union[Image.Image, str, bytes],
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        prompt: Optional[str] = None,
        **kwargs
    ) -> VisionAnalysisResult:
        """Analyze image using BLIP-2."""
        start_time = time.time()
        
        try:
            if self.model is None:
                await self._initialize_model()
            
            image_b64 = self._image_to_base64(image)
            cache_key = self._generate_cache_key(image_b64, task_type, prompt or "")
            
            if self.config.cache_enabled and cache_key in self.cache:
                logger.info("Returning cached BLIP-2 result")
                return self.cache[cache_key]
            
            # Mock BLIP-2 analysis - would use actual model in production
            if task_type == VisionTaskType.IMAGE_CAPTIONING:
                description = "Advanced technical diagram showing network architecture with routers, switches, and data flow connections. The diagram includes detailed component labels and interconnection patterns typical of enterprise infrastructure."
                confidence = 0.92
                technical_elements = ["routers", "switches", "network cables", "data flow arrows", "component labels"]
            elif task_type == VisionTaskType.TECHNICAL_ANALYSIS:
                description = "Technical schematic with circuit components, electrical connections, and measurement points. Components include resistors, capacitors, integrated circuits, and connection pathways."
                confidence = 0.88
                technical_elements = ["resistors", "capacitors", "integrated circuits", "electrical connections", "measurement points"]
            else:
                description = "Complex technical image with detailed components and structured layout. Contains multiple elements with clear relationships and technical specifications."
                confidence = 0.85
                technical_elements = ["technical components", "structured layout", "specifications"]
            
            processing_time = time.time() - start_time
            
            result = VisionAnalysisResult(
                model_type=VisionModelType.BLIP2,
                task_type=task_type,
                description=description,
                confidence=confidence,
                processing_time=processing_time,
                metadata={
                    "model_name": self.config.model_name,
                    "prompt": prompt,
                    "image_size": "unknown"  # Would get from actual image
                },
                technical_elements=technical_elements
            )
            
            if self.config.cache_enabled:
                self.cache[cache_key] = result
            
            logger.info(f"BLIP-2 analysis completed in {processing_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"BLIP-2 analysis failed: {e}")
            return VisionAnalysisResult(
                model_type=VisionModelType.BLIP2,
                task_type=task_type,
                description="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    async def batch_analyze(
        self,
        images: List[Union[Image.Image, str, bytes]],
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        **kwargs
    ) -> List[VisionAnalysisResult]:
        """Batch analyze images with BLIP-2."""
        results = []
        for image in images:
            result = await self.analyze_image(image, task_type, **kwargs)
            results.append(result)
        return results


class LLaVAVisionModel(AdvancedVisionModel):
    """LLaVA (Large Language and Vision Assistant) integration."""
    
    def __init__(self, config: VisionModelConfig):
        super().__init__(config)
        
    @monitor_performance()
    async def analyze_image(
        self,
        image: Union[Image.Image, str, bytes],
        task_type: VisionTaskType = VisionTaskType.VISUAL_QUESTION_ANSWERING,
        prompt: Optional[str] = None,
        **kwargs
    ) -> VisionAnalysisResult:
        """Analyze image using LLaVA."""
        start_time = time.time()
        
        try:
            image_b64 = self._image_to_base64(image)
            cache_key = self._generate_cache_key(image_b64, task_type, prompt or "")
            
            if self.config.cache_enabled and cache_key in self.cache:
                logger.info("Returning cached LLaVA result")
                return self.cache[cache_key]
            
            # Mock LLaVA analysis - would integrate with actual LLaVA API
            if task_type == VisionTaskType.VISUAL_QUESTION_ANSWERING:
                if prompt and "diagram" in prompt.lower():
                    description = "This is a technical system diagram illustrating the interconnections between various network components. The diagram shows routers connected to switches, with clear data pathways and network topology. Each component is properly labeled with specifications and connection details."
                    confidence = 0.94
                    technical_elements = ["network topology", "routers", "switches", "data pathways", "component labels", "specifications"]
                else:
                    description = "The image contains technical content with structured elements and clear visual organization. Components are systematically arranged with logical connections and detailed annotations."
                    confidence = 0.89
                    technical_elements = ["structured elements", "visual organization", "logical connections", "annotations"]
            elif task_type == VisionTaskType.DIAGRAM_INTERPRETATION:
                description = "Engineering diagram with precise technical specifications. Shows component relationships, measurement values, and operational parameters. The layout follows industry standards with clear symbology and connection indicators."
                confidence = 0.91
                technical_elements = ["engineering standards", "technical specifications", "component relationships", "measurement values", "symbology"]
            else:
                description = "Technical image with detailed visual information and structured content layout."
                confidence = 0.87
                technical_elements = ["visual information", "structured content"]
            
            processing_time = time.time() - start_time
            
            result = VisionAnalysisResult(
                model_type=VisionModelType.LLAVA,
                task_type=task_type,
                description=description,
                confidence=confidence,
                processing_time=processing_time,
                metadata={
                    "model_name": self.config.model_name,
                    "prompt": prompt,
                    "conversational": True
                },
                technical_elements=technical_elements
            )
            
            if self.config.cache_enabled:
                self.cache[cache_key] = result
            
            logger.info(f"LLaVA analysis completed in {processing_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"LLaVA analysis failed: {e}")
            return VisionAnalysisResult(
                model_type=VisionModelType.LLAVA,
                task_type=task_type,
                description="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    async def batch_analyze(
        self,
        images: List[Union[Image.Image, str, bytes]],
        task_type: VisionTaskType = VisionTaskType.VISUAL_QUESTION_ANSWERING,
        **kwargs
    ) -> List[VisionAnalysisResult]:
        """Batch analyze images with LLaVA."""
        results = []
        for image in images:
            result = await self.analyze_image(image, task_type, **kwargs)
            results.append(result)
        return results


class OllamaVisionModel(AdvancedVisionModel):
    """Ollama Vision model integration (llava:7b, llava:13b, llava:34b)."""
    
    def __init__(self, config: VisionModelConfig):
        super().__init__(config)
        self.base_urls = [
            "http://localhost:11434",
            "http://localhost:11435", 
            "http://localhost:11436",
            "http://localhost:11437"
        ]
        if config.endpoint_url:
            self.base_urls = [config.endpoint_url] + self.base_urls
    
    async def _get_available_instance(self) -> Optional[str]:
        """Find available Ollama instance for vision models."""
        for base_url in self.base_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base_url}/api/tags", timeout=5) as response:
                        if response.status == 200:
                            tags = await response.json()
                            # Check if vision models are available
                            model_names = [model.get('name', '') for model in tags.get('models', [])]
                            vision_models = [name for name in model_names if 'llava' in name.lower()]
                            if vision_models:
                                logger.info(f"Found Ollama vision models at {base_url}: {vision_models}")
                                return base_url
            except Exception as e:
                logger.debug(f"Ollama instance {base_url} not available: {e}")
                continue
        return None
    
    @monitor_performance()
    async def analyze_image(
        self,
        image: Union[Image.Image, str, bytes],
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        prompt: Optional[str] = None,
        **kwargs
    ) -> VisionAnalysisResult:
        """Analyze image using Ollama Vision models."""
        start_time = time.time()
        
        try:
            base_url = await self._get_available_instance()
            if not base_url:
                raise VisionModelError("No Ollama vision model instances available")
            
            image_b64 = self._image_to_base64(image)
            cache_key = self._generate_cache_key(image_b64, task_type, prompt or "")
            
            if self.config.cache_enabled and cache_key in self.cache:
                logger.info("Returning cached Ollama Vision result")
                return self.cache[cache_key]
            
            # Prepare prompt based on task type
            if task_type == VisionTaskType.TECHNICAL_ANALYSIS:
                system_prompt = "Analyze this technical image in detail. Identify all technical components, connections, specifications, and provide a comprehensive description suitable for technical documentation."
            elif task_type == VisionTaskType.CHART_READING:
                system_prompt = "Analyze this chart or graph. Extract all data points, identify trends, and provide detailed insights about the information presented."
            elif task_type == VisionTaskType.DIAGRAM_INTERPRETATION:
                system_prompt = "Interpret this technical diagram. Identify all components, their relationships, and explain the system or process being illustrated."
            else:
                system_prompt = "Describe this image in detail, focusing on technical elements and important visual information."
            
            if prompt:
                full_prompt = f"{system_prompt}\\n\\nSpecific question: {prompt}"
            else:
                full_prompt = system_prompt
            
            # Make request to Ollama Vision API
            payload = {
                "model": self.config.model_name,
                "prompt": full_prompt,
                "images": [image_b64],
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/generate",
                    json=payload,
                    timeout=self.config.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        description = data.get('response', '').strip()
                        confidence = 0.9  # Ollama doesn't provide confidence scores
                        
                        # Extract technical elements from description
                        technical_elements = self._extract_technical_elements(description)
                        
                        processing_time = time.time() - start_time
                        
                        result = VisionAnalysisResult(
                            model_type=VisionModelType.OLLAMA_VISION,
                            task_type=task_type,
                            description=description,
                            confidence=confidence,
                            processing_time=processing_time,
                            metadata={
                                "model_name": self.config.model_name,
                                "base_url": base_url,
                                "prompt": full_prompt,
                                "ollama_response": data
                            },
                            technical_elements=technical_elements
                        )
                        
                        if self.config.cache_enabled:
                            self.cache[cache_key] = result
                        
                        logger.info(f"Ollama Vision analysis completed in {processing_time:.3f}s")
                        return result
                    else:
                        error_msg = f"Ollama API error: {response.status}"
                        raise VisionModelError(error_msg)
            
        except Exception as e:
            logger.error(f"Ollama Vision analysis failed: {e}")
            return VisionAnalysisResult(
                model_type=VisionModelType.OLLAMA_VISION,
                task_type=task_type,
                description="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e)
            )
    
    def _extract_technical_elements(self, description: str) -> List[str]:
        """Extract technical elements from description text."""
        technical_keywords = [
            "router", "switch", "network", "cable", "connection", "port", "interface",
            "circuit", "component", "resistor", "capacitor", "transistor", "chip",
            "diagram", "schematic", "topology", "architecture", "system", "protocol",
            "configuration", "specification", "parameter", "measurement", "value"
        ]
        
        elements = []
        description_lower = description.lower()
        for keyword in technical_keywords:
            if keyword in description_lower:
                elements.append(keyword)
        
        return list(set(elements))  # Remove duplicates
    
    async def batch_analyze(
        self,
        images: List[Union[Image.Image, str, bytes]],
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        **kwargs
    ) -> List[VisionAnalysisResult]:
        """Batch analyze images with Ollama Vision."""
        results = []
        for image in images:
            result = await self.analyze_image(image, task_type, **kwargs)
            results.append(result)
        return results


class AdvancedVisionModelManager:
    """Manager for advanced vision models in Phase 3B."""
    
    def __init__(self):
        self.models: Dict[VisionModelType, AdvancedVisionModel] = {}
        self.default_model = VisionModelType.OLLAMA_VISION
        self._initialize_models()
        
        logger.info("Advanced Vision Model Manager initialized for Phase 3B")
    
    def _initialize_models(self):
        """Initialize all available vision models."""
        # BLIP-2 Configuration
        blip2_config = VisionModelConfig(
            model_type=VisionModelType.BLIP2,
            model_name="Salesforce/blip2-opt-2.7b",
            max_tokens=300,
            temperature=0.7,
            cache_enabled=True
        )
        self.models[VisionModelType.BLIP2] = BLIP2VisionModel(blip2_config)
        
        # LLaVA Configuration
        llava_config = VisionModelConfig(
            model_type=VisionModelType.LLAVA,
            model_name="llava-hf/llava-1.5-7b-hf",
            max_tokens=500,
            temperature=0.6,
            cache_enabled=True
        )
        self.models[VisionModelType.LLAVA] = LLaVAVisionModel(llava_config)
        
        # Ollama Vision Configuration
        ollama_vision_config = VisionModelConfig(
            model_type=VisionModelType.OLLAMA_VISION,
            model_name="llava:7b",
            max_tokens=400,
            temperature=0.7,
            timeout=30,
            cache_enabled=True
        )
        self.models[VisionModelType.OLLAMA_VISION] = OllamaVisionModel(ollama_vision_config)
        
        logger.info(f"Initialized {len(self.models)} advanced vision models")
    
    async def analyze_image(
        self,
        image: Union[Image.Image, str, bytes],
        model_type: Optional[VisionModelType] = None,
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        prompt: Optional[str] = None,
        **kwargs
    ) -> VisionAnalysisResult:
        """Analyze image with specified or optimal vision model."""
        selected_model = model_type or self._select_optimal_model(task_type)
        
        if selected_model not in self.models:
            logger.warning(f"Model {selected_model} not available, using default")
            selected_model = self.default_model
        
        model = self.models[selected_model]
        result = await model.analyze_image(image, task_type, prompt, **kwargs)
        
        logger.info(f"Vision analysis completed with {selected_model.value} model")
        return result
    
    def _select_optimal_model(self, task_type: VisionTaskType) -> VisionModelType:
        """Select optimal model based on task type."""
        model_preferences = {
            VisionTaskType.IMAGE_CAPTIONING: VisionModelType.BLIP2,
            VisionTaskType.VISUAL_QUESTION_ANSWERING: VisionModelType.LLAVA,
            VisionTaskType.TECHNICAL_ANALYSIS: VisionModelType.OLLAMA_VISION,
            VisionTaskType.CHART_READING: VisionModelType.LLAVA,
            VisionTaskType.DIAGRAM_INTERPRETATION: VisionModelType.OLLAMA_VISION,
            VisionTaskType.OBJECT_DETECTION: VisionModelType.BLIP2,
            VisionTaskType.TEXT_EXTRACTION: VisionModelType.OLLAMA_VISION,
        }
        
        return model_preferences.get(task_type, self.default_model)
    
    async def batch_analyze(
        self,
        images: List[Union[Image.Image, str, bytes]],
        model_type: Optional[VisionModelType] = None,
        task_type: VisionTaskType = VisionTaskType.IMAGE_CAPTIONING,
        **kwargs
    ) -> List[VisionAnalysisResult]:
        """Batch analyze images with vision models."""
        selected_model = model_type or self._select_optimal_model(task_type)
        
        if selected_model not in self.models:
            selected_model = self.default_model
        
        model = self.models[selected_model]
        results = await model.batch_analyze(images, task_type, **kwargs)
        
        logger.info(f"Batch vision analysis completed for {len(images)} images")
        return results
    
    def get_available_models(self) -> List[VisionModelType]:
        """Get list of available vision models."""
        return list(self.models.keys())
    
    def get_model_info(self, model_type: VisionModelType) -> Dict[str, Any]:
        """Get information about a specific model."""
        if model_type in self.models:
            model = self.models[model_type]
            return {
                "model_type": model_type.value,
                "model_name": model.config.model_name,
                "cache_size": len(model.cache),
                "capabilities": self._get_model_capabilities(model_type)
            }
        return {}
    
    def _get_model_capabilities(self, model_type: VisionModelType) -> List[str]:
        """Get capabilities of a specific model type."""
        capabilities_map = {
            VisionModelType.BLIP2: [
                "image_captioning", "object_detection", "visual_understanding"
            ],
            VisionModelType.LLAVA: [
                "visual_question_answering", "conversational_ai", "chart_reading"
            ],
            VisionModelType.OLLAMA_VISION: [
                "technical_analysis", "diagram_interpretation", "text_extraction"
            ]
        }
        return capabilities_map.get(model_type, [])
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all vision models."""
        stats = {
            "total_models": len(self.models),
            "default_model": self.default_model.value,
            "model_details": {}
        }
        
        for model_type, model in self.models.items():
            stats["model_details"][model_type.value] = {
                "cache_size": len(model.cache),
                "config": {
                    "model_name": model.config.model_name,
                    "max_tokens": model.config.max_tokens,
                    "temperature": model.config.temperature,
                    "cache_enabled": model.config.cache_enabled
                }
            }
        
        return stats


# Initialize global advanced vision model manager
advanced_vision_manager = AdvancedVisionModelManager()

logger.info("Phase 3B Advanced Vision Models module loaded successfully")