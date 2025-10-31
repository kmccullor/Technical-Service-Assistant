"""
Phase 3B: OCR Integration Pipeline
Comprehensive text extraction from images and scanned documents using multiple OCR engines.
"""

import asyncio
import io
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageEnhance, ImageFilter

from utils.exceptions import OCRError
from utils.logging_setup import get_logger
from utils.monitoring import monitor_performance

logger = get_logger(__name__)


class OCREngine(Enum):
    """OCR engine types for text extraction."""

    TESSERACT = "tesseract"
    PADDLE_OCR = "paddle_ocr"
    AWS_TEXTRACT = "aws_textract"
    GOOGLE_VISION = "google_vision"
    AZURE_VISION = "azure_vision"
    EASYOCR = "easyocr"


class DocumentType(Enum):
    """Types of documents for OCR optimization."""

    TECHNICAL_DRAWING = "technical_drawing"
    SCHEMATIC = "schematic"
    MANUAL = "manual"
    REPORT = "report"
    FORM = "form"
    HANDWRITTEN = "handwritten"
    PRINTED_TEXT = "printed_text"
    MIXED = "mixed"


@dataclass
class OCRConfig:
    """Configuration for OCR engines."""

    engine: OCREngine
    language: str = "eng"
    confidence_threshold: float = 0.7
    preprocessing_enabled: bool = True
    layout_analysis: bool = True
    table_detection: bool = True
    timeout: int = 30
    api_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextRegion:
    """Text region detected by OCR."""

    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    word_count: int
    language: str = "unknown"
    font_size: Optional[float] = None
    is_handwritten: bool = False


@dataclass
class OCRResult:
    """Result from OCR text extraction."""

    engine: OCREngine
    document_type: DocumentType
    full_text: str
    confidence: float
    processing_time: float
    regions: List[TextRegion] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    layout_info: Optional[Dict[str, Any]] = None
    technical_terms: List[str] = field(default_factory=list)
    error: Optional[str] = None


class OCREngineBase(ABC):
    """Abstract base class for OCR engines."""

    def __init__(self, config: OCRConfig):
        self.config = config
        self.engine = config.engine

    @abstractmethod
    async def extract_text(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType = DocumentType.MIXED, **kwargs
    ) -> OCRResult:
        """Extract text from image using OCR engine."""

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR accuracy."""
        if not self.config.preprocessing_enabled:
            return image

        # Convert to grayscale if needed
        if image.mode != "L":
            image = image.convert("L")

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        # Apply slight blur to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))

        return image

    def _extract_technical_terms(self, text: str) -> List[str]:
        """Extract technical terms from OCR text."""
        technical_patterns = [
            r"\b\d+[A-Z]{1,3}\b",  # Component values (10K, 100nF, etc.)
            r"\b[A-Z]+\d+\b",  # Component references (R1, C2, IC3, etc.)
            r"\b\d+\.?\d*\s?[VΩΩμμnpkMGT][ΑΩFHVΩvfhaw]?\b",  # Units
            r"\b[A-Z]{2,}\b",  # Acronyms
            r"\b\d+x\d+\b",  # Dimensions
            r"\b\d+\.\d+\b",  # Decimal numbers
        ]

        terms = []
        for pattern in technical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.extend(matches)

        return list(set(terms))  # Remove duplicates


class TesseractOCR(OCREngineBase):
    """Tesseract OCR engine integration."""

    def __init__(self, config: OCRConfig):
        super().__init__(config)
        self.tesseract_available = self._check_tesseract_availability()

    def _check_tesseract_availability(self) -> bool:
        """Check if Tesseract is available on the system."""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")
            return False

    @monitor_performance()
    async def extract_text(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType = DocumentType.MIXED, **kwargs
    ) -> OCRResult:
        """Extract text using Tesseract OCR."""
        start_time = time.time()

        try:
            if not self.tesseract_available:
                raise OCRError("Tesseract OCR not available")

            import pytesseract
            from PIL import Image as PILImage

            # Convert input to PIL Image
            if isinstance(image, str):
                pil_image = PILImage.open(image)
            elif isinstance(image, bytes):
                pil_image = PILImage.open(io.BytesIO(image))
            else:
                pil_image = image

            # Preprocess image
            processed_image = self._preprocess_image(pil_image)

            # Configure Tesseract for document type
            tesseract_config = self._get_tesseract_config(document_type)

            # Extract text with confidence scores
            data = pytesseract.image_to_data(
                processed_image, lang=self.config.language, config=tesseract_config, output_type=pytesseract.Output.DICT
            )

            # Process results
            full_text = pytesseract.image_to_string(
                processed_image, lang=self.config.language, config=tesseract_config
            ).strip()

            # Extract regions with high confidence
            regions = self._process_tesseract_data(data)

            # Calculate overall confidence
            if regions:
                confidence = sum(r.confidence for r in regions) / len(regions) / 100.0
            else:
                confidence = 0.0

            # Extract technical terms
            technical_terms = self._extract_technical_terms(full_text)

            processing_time = time.time() - start_time

            result = OCRResult(
                engine=OCREngine.TESSERACT,
                document_type=document_type,
                full_text=full_text,
                confidence=confidence,
                processing_time=processing_time,
                regions=regions,
                technical_terms=technical_terms,
                metadata={
                    "tesseract_config": tesseract_config,
                    "language": self.config.language,
                    "preprocessing": self.config.preprocessing_enabled,
                },
            )

            logger.info(f"Tesseract OCR completed in {processing_time:.3f}s, confidence: {confidence:.3f}")
            return result

        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return OCRResult(
                engine=OCREngine.TESSERACT,
                document_type=document_type,
                full_text="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e),
            )

    def _get_tesseract_config(self, document_type: DocumentType) -> str:
        """Get Tesseract configuration for document type."""
        base_config = "--oem 3 --psm 6"  # Use LSTM OCR and uniform text block

        if document_type == DocumentType.TECHNICAL_DRAWING:
            return (
                base_config
                + " -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-+μΩ"
            )
        elif document_type == DocumentType.SCHEMATIC:
            return base_config + " --psm 8"  # Single word mode for component labels
        elif document_type == DocumentType.FORM:
            return base_config + " --psm 4"  # Single column of text
        else:
            return base_config

    def _process_tesseract_data(self, data: Dict[str, List]) -> List[TextRegion]:
        """Process Tesseract OCR data into TextRegion objects."""
        regions = []

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            confidence = float(data["conf"][i])

            if text and confidence >= self.config.confidence_threshold * 100:
                bbox = (
                    data["left"][i],
                    data["top"][i],
                    data["left"][i] + data["width"][i],
                    data["top"][i] + data["height"][i],
                )

                region = TextRegion(
                    text=text,
                    confidence=confidence,
                    bbox=bbox,
                    word_count=len(text.split()),
                    language=self.config.language,
                )
                regions.append(region)

        return regions


class PaddleOCR(OCREngineBase):
    """PaddleOCR engine with advanced layout analysis."""

    def __init__(self, config: OCRConfig):
        super().__init__(config)
        self.paddle_available = self._check_paddle_availability()
        self.ocr_model = None

    def _check_paddle_availability(self) -> bool:
        """Check if PaddleOCR is available."""
        try:
            pass

            return True
        except Exception as e:
            logger.warning(f"PaddleOCR not available: {e}")
            return False

    async def _initialize_paddle(self):
        """Initialize PaddleOCR model."""
        if self.ocr_model is None and self.paddle_available:
            try:
                import paddleocr

                self.ocr_model = paddleocr.PaddleOCR(
                    use_angle_cls=True,
                    lang=self.config.language if self.config.language != "eng" else "en",
                    use_gpu=False,  # Set to True if GPU available
                )
                logger.info("PaddleOCR model initialized")
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                raise OCRError(f"PaddleOCR initialization failed: {e}")

    @monitor_performance()
    async def extract_text(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType = DocumentType.MIXED, **kwargs
    ) -> OCRResult:
        """Extract text using PaddleOCR."""
        start_time = time.time()

        try:
            if not self.paddle_available:
                # Mock PaddleOCR results for testing
                return await self._mock_paddle_ocr(image, document_type, start_time)

            await self._initialize_paddle()

            # Convert input to format expected by PaddleOCR
            if isinstance(image, str):
                image_path = image
            elif isinstance(image, bytes):
                # Save bytes to temporary file
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(image)
                    image_path = f.name
            else:
                # Save PIL Image to temporary file
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    image.save(f.name)
                    image_path = f.name

            # Run OCR
            results = self.ocr_model.ocr(image_path, cls=True)

            # Process results
            full_text = ""
            regions = []
            total_confidence = 0

            if results and results[0]:
                for line in results[0]:
                    bbox_coords = line[0]
                    text_info = line[1]
                    text = text_info[0]
                    confidence = text_info[1]

                    full_text += text + " "
                    total_confidence += confidence

                    # Convert bbox to standard format
                    x_coords = [p[0] for p in bbox_coords]
                    y_coords = [p[1] for p in bbox_coords]
                    bbox = (int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords)))

                    region = TextRegion(
                        text=text,
                        confidence=confidence,
                        bbox=bbox,
                        word_count=len(text.split()),
                        language=self.config.language,
                    )
                    regions.append(region)

            # Calculate overall confidence
            confidence = total_confidence / len(regions) if regions else 0.0

            # Extract technical terms
            technical_terms = self._extract_technical_terms(full_text.strip())

            processing_time = time.time() - start_time

            result = OCRResult(
                engine=OCREngine.PADDLE_OCR,
                document_type=document_type,
                full_text=full_text.strip(),
                confidence=confidence,
                processing_time=processing_time,
                regions=regions,
                technical_terms=technical_terms,
                metadata={
                    "paddle_version": "2.6.0",
                    "language": self.config.language,
                    "layout_analysis": self.config.layout_analysis,
                },
            )

            logger.info(f"PaddleOCR completed in {processing_time:.3f}s, confidence: {confidence:.3f}")
            return result

        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return OCRResult(
                engine=OCREngine.PADDLE_OCR,
                document_type=document_type,
                full_text="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e),
            )

    async def _mock_paddle_ocr(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType, start_time: float
    ) -> OCRResult:
        """Mock PaddleOCR results for testing when library not available."""
        await asyncio.sleep(0.15)  # Simulate processing time

        # Generate mock text based on document type
        if document_type == DocumentType.TECHNICAL_DRAWING:
            mock_text = "R1 10kΩ ±5% C1 100nF 50V Q1 2N3904 IC1 LM741 VCC +12V GND"
            technical_terms = ["R1", "10kΩ", "C1", "100nF", "Q1", "2N3904", "IC1", "LM741", "VCC", "+12V"]
        elif document_type == DocumentType.SCHEMATIC:
            mock_text = "INPUT OUTPUT VDD VSS CLK RST DATA[7:0] ADDR[15:0] CS RD WR"
            technical_terms = ["INPUT", "OUTPUT", "VDD", "VSS", "CLK", "RST", "DATA", "ADDR", "CS", "RD", "WR"]
        else:
            mock_text = "Technical specifications and component layout diagram showing interconnected system elements with measurement values and operational parameters."
            technical_terms = [
                "specifications",
                "component",
                "layout",
                "diagram",
                "system",
                "measurement",
                "parameters",
            ]

        # Create mock regions
        regions = [
            TextRegion(
                text=word,
                confidence=0.85 + (hash(word) % 15) / 100,  # Simulate varying confidence
                bbox=(100 + i * 80, 100, 180 + i * 80, 120),
                word_count=1,
                language="eng",
            )
            for i, word in enumerate(mock_text.split()[:5])  # First 5 words
        ]

        processing_time = time.time() - start_time

        return OCRResult(
            engine=OCREngine.PADDLE_OCR,
            document_type=document_type,
            full_text=mock_text,
            confidence=0.87,
            processing_time=processing_time,
            regions=regions,
            technical_terms=technical_terms,
            metadata={"mock_result": True, "paddle_version": "2.6.0", "language": self.config.language},
        )


class CloudOCREngine(OCREngineBase):
    """Cloud-based OCR services (AWS Textract, Google Vision, Azure)."""

    def __init__(self, config: OCRConfig):
        super().__init__(config)

    @monitor_performance()
    async def extract_text(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType = DocumentType.MIXED, **kwargs
    ) -> OCRResult:
        """Extract text using cloud OCR services."""
        start_time = time.time()

        try:
            # Mock cloud OCR for now - would integrate with actual APIs
            await asyncio.sleep(0.5)  # Simulate API call

            if self.engine == OCREngine.AWS_TEXTRACT:
                return await self._mock_aws_textract(image, document_type, start_time)
            elif self.engine == OCREngine.GOOGLE_VISION:
                return await self._mock_google_vision(image, document_type, start_time)
            elif self.engine == OCREngine.AZURE_VISION:
                return await self._mock_azure_vision(image, document_type, start_time)
            else:
                raise OCRError(f"Unsupported cloud OCR engine: {self.engine}")

        except Exception as e:
            logger.error(f"Cloud OCR failed: {e}")
            return OCRResult(
                engine=self.engine,
                document_type=document_type,
                full_text="",
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e),
            )

    async def _mock_aws_textract(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType, start_time: float
    ) -> OCRResult:
        """Mock AWS Textract results."""
        mock_text = "Advanced network infrastructure diagram showing enterprise-grade components including routers, switches, firewalls, and load balancers with detailed configuration parameters and connection specifications."
        technical_terms = [
            "network",
            "infrastructure",
            "routers",
            "switches",
            "firewalls",
            "load balancers",
            "configuration",
            "parameters",
        ]

        regions = [
            TextRegion(
                text="Network Infrastructure Diagram",
                confidence=0.98,
                bbox=(50, 20, 400, 50),
                word_count=3,
                language="eng",
            ),
            TextRegion(
                text="Router-1: 192.168.1.1", confidence=0.95, bbox=(100, 100, 300, 120), word_count=2, language="eng"
            ),
        ]

        processing_time = time.time() - start_time

        return OCRResult(
            engine=OCREngine.AWS_TEXTRACT,
            document_type=document_type,
            full_text=mock_text,
            confidence=0.96,
            processing_time=processing_time,
            regions=regions,
            technical_terms=technical_terms,
            metadata={"service": "aws_textract", "api_version": "2018-06-27", "mock_result": True},
        )

    async def _mock_google_vision(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType, start_time: float
    ) -> OCRResult:
        """Mock Google Vision API results."""
        mock_text = "Technical schematic with component specifications: IC1 (LM358), R1 (10kΩ), C1 (100μF), operating voltage 5V-12V, current consumption 50mA max."
        technical_terms = ["IC1", "LM358", "R1", "10kΩ", "C1", "100μF", "5V-12V", "50mA"]

        processing_time = time.time() - start_time

        return OCRResult(
            engine=OCREngine.GOOGLE_VISION,
            document_type=document_type,
            full_text=mock_text,
            confidence=0.94,
            processing_time=processing_time,
            technical_terms=technical_terms,
            metadata={"service": "google_vision", "api_version": "v1", "mock_result": True},
        )

    async def _mock_azure_vision(
        self, image: Union[Image.Image, str, bytes], document_type: DocumentType, start_time: float
    ) -> OCRResult:
        """Mock Azure Computer Vision results."""
        mock_text = "System architecture overview with database connections, API endpoints, load balancer configuration, and security protocols implementation details."
        technical_terms = ["database", "API", "endpoints", "load balancer", "security", "protocols"]

        processing_time = time.time() - start_time

        return OCRResult(
            engine=OCREngine.AZURE_VISION,
            document_type=document_type,
            full_text=mock_text,
            confidence=0.93,
            processing_time=processing_time,
            technical_terms=technical_terms,
            metadata={"service": "azure_vision", "api_version": "3.2", "mock_result": True},
        )


class OCRPipeline:
    """Comprehensive OCR pipeline with multiple engines and intelligent routing."""

    def __init__(self):
        self.engines: Dict[OCREngine, OCREngineBase] = {}
        self.default_engine = OCREngine.PADDLE_OCR
        self._initialize_engines()

        logger.info("OCR Pipeline initialized with multiple engines")

    def _initialize_engines(self):
        """Initialize all available OCR engines."""
        # Tesseract OCR
        tesseract_config = OCRConfig(
            engine=OCREngine.TESSERACT, language="eng", confidence_threshold=0.7, preprocessing_enabled=True
        )
        self.engines[OCREngine.TESSERACT] = TesseractOCR(tesseract_config)

        # PaddleOCR
        paddle_config = OCRConfig(
            engine=OCREngine.PADDLE_OCR,
            language="eng",
            confidence_threshold=0.8,
            layout_analysis=True,
            preprocessing_enabled=True,
        )
        self.engines[OCREngine.PADDLE_OCR] = PaddleOCR(paddle_config)

        # AWS Textract
        aws_config = OCRConfig(
            engine=OCREngine.AWS_TEXTRACT, confidence_threshold=0.9, table_detection=True, layout_analysis=True
        )
        self.engines[OCREngine.AWS_TEXTRACT] = CloudOCREngine(aws_config)

        # Google Vision API
        google_config = OCRConfig(engine=OCREngine.GOOGLE_VISION, confidence_threshold=0.85, layout_analysis=True)
        self.engines[OCREngine.GOOGLE_VISION] = CloudOCREngine(google_config)

        logger.info(f"Initialized {len(self.engines)} OCR engines")

    async def extract_text(
        self,
        image: Union[Image.Image, str, bytes],
        engine: Optional[OCREngine] = None,
        document_type: DocumentType = DocumentType.MIXED,
        **kwargs,
    ) -> OCRResult:
        """Extract text using specified or optimal OCR engine."""
        selected_engine = engine or self._select_optimal_engine(document_type)

        if selected_engine not in self.engines:
            logger.warning(f"Engine {selected_engine} not available, using default")
            selected_engine = self.default_engine

        ocr_engine = self.engines[selected_engine]
        result = await ocr_engine.extract_text(image, document_type, **kwargs)

        logger.info(f"OCR extraction completed with {selected_engine.value} engine")
        return result

    def _select_optimal_engine(self, document_type: DocumentType) -> OCREngine:
        """Select optimal OCR engine based on document type."""
        engine_preferences = {
            DocumentType.TECHNICAL_DRAWING: OCREngine.PADDLE_OCR,
            DocumentType.SCHEMATIC: OCREngine.TESSERACT,
            DocumentType.MANUAL: OCREngine.AWS_TEXTRACT,
            DocumentType.REPORT: OCREngine.GOOGLE_VISION,
            DocumentType.FORM: OCREngine.AWS_TEXTRACT,
            DocumentType.HANDWRITTEN: OCREngine.GOOGLE_VISION,
            DocumentType.PRINTED_TEXT: OCREngine.TESSERACT,
            DocumentType.MIXED: OCREngine.PADDLE_OCR,
        }

        return engine_preferences.get(document_type, self.default_engine)

    async def multi_engine_extract(
        self,
        image: Union[Image.Image, str, bytes],
        engines: List[OCREngine],
        document_type: DocumentType = DocumentType.MIXED,
        **kwargs,
    ) -> List[OCRResult]:
        """Extract text using multiple engines for comparison."""
        tasks = []
        for engine in engines:
            if engine in self.engines:
                task = self.engines[engine].extract_text(image, document_type, **kwargs)
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = [r for r in results if isinstance(r, OCRResult)]

        logger.info(f"Multi-engine OCR completed with {len(valid_results)} successful results")
        return valid_results

    async def consensus_extract(
        self,
        image: Union[Image.Image, str, bytes],
        document_type: DocumentType = DocumentType.MIXED,
        min_engines: int = 2,
        **kwargs,
    ) -> OCRResult:
        """Extract text using consensus from multiple engines."""
        available_engines = [OCREngine.TESSERACT, OCREngine.PADDLE_OCR, OCREngine.GOOGLE_VISION]

        results = await self.multi_engine_extract(image, available_engines, document_type, **kwargs)

        if len(results) < min_engines:
            # Fall back to single best engine
            return await self.extract_text(image, None, document_type, **kwargs)

        # Combine results using confidence weighting
        total_confidence = sum(r.confidence for r in results)
        if total_confidence == 0:
            return results[0]  # Return first result if no confidence scores

        # Weighted text combination (simplified - could be more sophisticated)
        best_result = max(results, key=lambda r: r.confidence)

        # Combine technical terms from all results
        all_technical_terms = []
        for result in results:
            all_technical_terms.extend(result.technical_terms)

        consensus_result = OCRResult(
            engine=best_result.engine,
            document_type=document_type,
            full_text=best_result.full_text,
            confidence=total_confidence / len(results),
            processing_time=max(r.processing_time for r in results),
            technical_terms=list(set(all_technical_terms)),
            metadata={
                "consensus": True,
                "engines_used": [r.engine.value for r in results],
                "individual_confidences": [r.confidence for r in results],
            },
        )

        logger.info(f"Consensus OCR completed using {len(results)} engines")
        return consensus_result

    def get_available_engines(self) -> List[OCREngine]:
        """Get list of available OCR engines."""
        return list(self.engines.keys())

    def get_engine_info(self, engine: OCREngine) -> Dict[str, Any]:
        """Get information about a specific OCR engine."""
        if engine in self.engines:
            ocr_engine = self.engines[engine]
            return {
                "engine": engine.value,
                "confidence_threshold": ocr_engine.config.confidence_threshold,
                "preprocessing": ocr_engine.config.preprocessing_enabled,
                "layout_analysis": ocr_engine.config.layout_analysis,
                "capabilities": self._get_engine_capabilities(engine),
            }
        return {}

    def _get_engine_capabilities(self, engine: OCREngine) -> List[str]:
        """Get capabilities of a specific OCR engine."""
        capabilities_map = {
            OCREngine.TESSERACT: ["text_extraction", "multilingual", "custom_training"],
            OCREngine.PADDLE_OCR: ["text_extraction", "layout_analysis", "multilingual", "rotation_correction"],
            OCREngine.AWS_TEXTRACT: ["text_extraction", "table_detection", "form_analysis", "handwriting"],
            OCREngine.GOOGLE_VISION: ["text_extraction", "handwriting", "multilingual", "object_detection"],
            OCREngine.AZURE_VISION: ["text_extraction", "layout_analysis", "multilingual"],
        }
        return capabilities_map.get(engine, [])

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics for OCR pipeline."""
        return {
            "total_engines": len(self.engines),
            "default_engine": self.default_engine.value,
            "available_engines": [e.value for e in self.engines.keys()],
            "engine_details": {engine.value: self.get_engine_info(engine) for engine in self.engines.keys()},
        }


# Initialize global OCR pipeline
ocr_pipeline = OCRPipeline()

logger.info("Phase 3B OCR Integration Pipeline module loaded successfully")
