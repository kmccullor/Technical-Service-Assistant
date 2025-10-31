"""
Phase 3B: Advanced Image Understanding
Sophisticated image analysis including technical diagram interpretation, chart reading, and visual element classification.
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from phase3b_advanced_vision import AdvancedVisionModelManager, VisionTaskType
from phase3b_ocr_pipeline import DocumentType, OCRPipeline
from PIL import Image

from utils.exceptions import ImageAnalysisError
from utils.logging_setup import get_logger
from utils.monitoring import monitor_performance

logger = get_logger(__name__)


class ImageElementType(Enum):
    """Types of visual elements in technical images."""

    TECHNICAL_COMPONENT = "technical_component"
    ELECTRICAL_SYMBOL = "electrical_symbol"
    MECHANICAL_PART = "mechanical_part"
    CONNECTION_LINE = "connection_line"
    TEXT_LABEL = "text_label"
    MEASUREMENT = "measurement"
    ANNOTATION = "annotation"
    CHART_BAR = "chart_bar"
    CHART_LINE = "chart_line"
    CHART_PIE_SLICE = "chart_pie_slice"
    TABLE_CELL = "table_cell"
    FLOW_ARROW = "flow_arrow"
    BOUNDARY_BOX = "boundary_box"
    GRID_LINE = "grid_line"


class TechnicalDomain(Enum):
    """Technical domains for specialized analysis."""

    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    NETWORK = "network"
    SOFTWARE = "software"
    CHEMICAL = "chemical"
    CIVIL = "civil"
    GENERAL = "general"


@dataclass
class VisualElement:
    """Visual element detected in image."""

    element_type: ImageElementType
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float
    text_content: Optional[str] = None
    technical_value: Optional[str] = None
    connections: List[int] = field(default_factory=list)  # Connected element IDs
    properties: Dict[str, Any] = field(default_factory=dict)
    domain: TechnicalDomain = TechnicalDomain.GENERAL


@dataclass
class ChartData:
    """Extracted data from charts and graphs."""

    chart_type: str  # bar, line, pie, scatter, etc.
    title: Optional[str] = None
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    legend: List[str] = field(default_factory=list)
    data_points: List[Tuple[str, float]] = field(default_factory=list)
    trends: List[str] = field(default_factory=list)
    statistics: Dict[str, float] = field(default_factory=dict)


@dataclass
class DiagramStructure:
    """Structure analysis of technical diagrams."""

    diagram_type: str
    components: List[VisualElement] = field(default_factory=list)
    connections: List[Tuple[int, int]] = field(default_factory=list)  # (from_id, to_id)
    hierarchy_levels: List[List[int]] = field(default_factory=list)
    flow_direction: Optional[str] = None
    technical_specifications: Dict[str, str] = field(default_factory=dict)


@dataclass
class ImageUnderstandingResult:
    """Comprehensive image understanding result."""

    image_type: str
    technical_domain: TechnicalDomain
    confidence: float
    processing_time: float
    visual_elements: List[VisualElement] = field(default_factory=list)
    extracted_text: Optional[str] = None
    chart_data: Optional[ChartData] = None
    diagram_structure: Optional[DiagramStructure] = None
    technical_insights: List[str] = field(default_factory=list)
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class TechnicalDiagramInterpreter:
    """Interprets technical diagrams and schematics."""

    def __init__(self):
        self.component_patterns = self._load_component_patterns()
        self.symbol_classifier = TechnicalSymbolClassifier()

    def _load_component_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for identifying technical components."""
        return {
            "electrical": [
                r"R\d+",  # Resistors
                r"C\d+",  # Capacitors
                r"L\d+",  # Inductors
                r"Q\d+",  # Transistors
                r"IC\d+",  # Integrated circuits
                r"U\d+",  # Generic ICs
                r"D\d+",  # Diodes
                r"LED\d+",  # LEDs
                r"SW\d+",  # Switches
                r"J\d+",  # Connectors
            ],
            "mechanical": [
                r"BEARING\s*\d+",
                r"SHAFT\s*\d+",
                r"GEAR\s*\d+",
                r"BOLT\s*M\d+",
                r"SCREW\s*\d+",
                r"SPRING\s*\d+",
            ],
            "network": [
                r"ROUTER\s*\d+",
                r"SWITCH\s*\d+",
                r"HUB\s*\d+",
                r"SERVER\s*\d+",
                r"PC\s*\d+",
                r"FIREWALL\s*\d+",
            ],
        }

    @monitor_performance()
    async def interpret_diagram(
        self, image: Image.Image, domain_hint: Optional[TechnicalDomain] = None
    ) -> DiagramStructure:
        """Interpret technical diagram structure."""
        start_time = time.time()

        try:
            # Detect visual elements
            elements = await self._detect_visual_elements(image, domain_hint)

            # Analyze connections
            connections = self._analyze_connections(elements)

            # Determine hierarchy
            hierarchy = self._analyze_hierarchy(elements, connections)

            # Classify diagram type
            diagram_type = self._classify_diagram_type(elements, domain_hint)

            # Extract technical specifications
            specs = self._extract_specifications(elements)

            # Determine flow direction
            flow_direction = self._analyze_flow_direction(elements, connections)

            processing_time = time.time() - start_time

            structure = DiagramStructure(
                diagram_type=diagram_type,
                components=elements,
                connections=connections,
                hierarchy_levels=hierarchy,
                flow_direction=flow_direction,
                technical_specifications=specs,
            )

            logger.info(f"Diagram interpretation completed in {processing_time:.3f}s")
            return structure

        except Exception as e:
            logger.error(f"Diagram interpretation failed: {e}")
            raise ImageAnalysisError(f"Diagram interpretation error: {e}")

    async def _detect_visual_elements(
        self, image: Image.Image, domain_hint: Optional[TechnicalDomain]
    ) -> List[VisualElement]:
        """Detect visual elements in the diagram."""
        elements = []

        # Mock element detection - would use computer vision in production
        if domain_hint == TechnicalDomain.ELECTRICAL:
            mock_elements = [
                VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(100, 100, 150, 120),
                    confidence=0.95,
                    text_content="R1",
                    technical_value="10kΩ",
                    domain=TechnicalDomain.ELECTRICAL,
                    properties={"component_type": "resistor", "tolerance": "±5%"},
                ),
                VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(200, 100, 250, 120),
                    confidence=0.92,
                    text_content="C1",
                    technical_value="100nF",
                    domain=TechnicalDomain.ELECTRICAL,
                    properties={"component_type": "capacitor", "voltage": "50V"},
                ),
                VisualElement(
                    element_type=ImageElementType.CONNECTION_LINE,
                    bbox=(150, 110, 200, 110),
                    confidence=0.88,
                    domain=TechnicalDomain.ELECTRICAL,
                    properties={"line_type": "wire", "signal": "analog"},
                ),
            ]
        elif domain_hint == TechnicalDomain.NETWORK:
            mock_elements = [
                VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(50, 50, 150, 100),
                    confidence=0.94,
                    text_content="Router-1",
                    technical_value="192.168.1.1",
                    domain=TechnicalDomain.NETWORK,
                    properties={"device_type": "router", "model": "Cisco 2900"},
                ),
                VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(250, 50, 350, 100),
                    confidence=0.91,
                    text_content="Switch-1",
                    technical_value="192.168.1.10",
                    domain=TechnicalDomain.NETWORK,
                    properties={"device_type": "switch", "ports": "24"},
                ),
            ]
        else:
            # General technical diagram
            mock_elements = [
                VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(100, 100, 200, 150),
                    confidence=0.87,
                    text_content="Component A",
                    domain=TechnicalDomain.GENERAL,
                    properties={"category": "primary"},
                ),
                VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(300, 100, 400, 150),
                    confidence=0.85,
                    text_content="Component B",
                    domain=TechnicalDomain.GENERAL,
                    properties={"category": "secondary"},
                ),
            ]

        elements.extend(mock_elements)
        logger.info(f"Detected {len(elements)} visual elements")
        return elements

    def _analyze_connections(self, elements: List[VisualElement]) -> List[Tuple[int, int]]:
        """Analyze connections between elements."""
        connections = []

        # Mock connection analysis - would use spatial analysis in production
        for i, elem1 in enumerate(elements):
            for j, elem2 in enumerate(elements[i + 1 :], i + 1):
                if elem1.element_type == ImageElementType.CONNECTION_LINE:
                    # Connection line connects two components
                    connections.append((i - 1, j))
                elif self._elements_are_connected(elem1, elem2):
                    connections.append((i, j))

        logger.info(f"Identified {len(connections)} connections")
        return connections

    def _elements_are_connected(self, elem1: VisualElement, elem2: VisualElement) -> bool:
        """Check if two elements are visually connected."""
        # Simple distance-based connection detection
        x1, y1 = (elem1.bbox[0] + elem1.bbox[2]) / 2, (elem1.bbox[1] + elem1.bbox[3]) / 2
        x2, y2 = (elem2.bbox[0] + elem2.bbox[2]) / 2, (elem2.bbox[1] + elem2.bbox[3]) / 2
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return distance < 100  # Threshold for connection

    def _analyze_hierarchy(self, elements: List[VisualElement], connections: List[Tuple[int, int]]) -> List[List[int]]:
        """Analyze hierarchical structure of diagram."""
        # Mock hierarchy analysis - would use graph analysis in production
        hierarchy = []

        # Group elements by y-coordinate (horizontal levels)
        y_positions = {}
        for i, element in enumerate(elements):
            y_center = (element.bbox[1] + element.bbox[3]) / 2
            y_level = int(y_center // 50) * 50  # Group by 50-pixel levels
            if y_level not in y_positions:
                y_positions[y_level] = []
            y_positions[y_level].append(i)

        # Sort levels and create hierarchy
        for level in sorted(y_positions.keys()):
            hierarchy.append(y_positions[level])

        logger.info(f"Identified {len(hierarchy)} hierarchy levels")
        return hierarchy

    def _classify_diagram_type(self, elements: List[VisualElement], domain_hint: Optional[TechnicalDomain]) -> str:
        """Classify the type of technical diagram."""
        if domain_hint == TechnicalDomain.ELECTRICAL:
            if any("IC" in elem.text_content or "" for elem in elements if elem.text_content):
                return "circuit_schematic"
            else:
                return "electrical_diagram"
        elif domain_hint == TechnicalDomain.NETWORK:
            return "network_topology"
        elif domain_hint == TechnicalDomain.MECHANICAL:
            return "mechanical_assembly"
        else:
            return "technical_diagram"

    def _extract_specifications(self, elements: List[VisualElement]) -> Dict[str, str]:
        """Extract technical specifications from elements."""
        specs = {}

        for element in elements:
            if element.technical_value:
                specs[element.text_content or f"element_{id(element)}"] = element.technical_value

            # Extract from properties
            for key, value in element.properties.items():
                if isinstance(value, str) and any(char.isdigit() for char in value):
                    specs[f"{element.text_content or 'element'}_{key}"] = value

        return specs

    def _analyze_flow_direction(
        self, elements: List[VisualElement], connections: List[Tuple[int, int]]
    ) -> Optional[str]:
        """Analyze the flow direction in the diagram."""
        # Look for arrow elements or directional indicators
        arrows = [e for e in elements if e.element_type == ImageElementType.FLOW_ARROW]

        if arrows:
            # Analyze arrow directions
            directions = []
            for arrow in arrows:
                # Mock direction analysis
                width = arrow.bbox[2] - arrow.bbox[0]
                height = arrow.bbox[3] - arrow.bbox[1]

                if width > height:
                    directions.append("horizontal")
                else:
                    directions.append("vertical")

            if directions.count("horizontal") > directions.count("vertical"):
                return "left_to_right"
            else:
                return "top_to_bottom"

        return None


class TechnicalSymbolClassifier:
    """Classifies technical symbols and components."""

    def __init__(self):
        self.symbol_database = self._load_symbol_database()

    def _load_symbol_database(self) -> Dict[str, Dict[str, Any]]:
        """Load database of technical symbols."""
        return {
            "electrical": {
                "resistor": {"symbol": "zigzag", "units": ["Ω", "kΩ", "MΩ"]},
                "capacitor": {"symbol": "parallel_lines", "units": ["pF", "nF", "μF", "mF"]},
                "inductor": {"symbol": "coil", "units": ["μH", "mH", "H"]},
                "diode": {"symbol": "triangle_bar", "units": ["V", "A"]},
                "transistor": {"symbol": "three_terminal", "types": ["NPN", "PNP", "FET"]},
            },
            "mechanical": {
                "bearing": {"symbol": "circle_cross", "types": ["ball", "roller", "thrust"]},
                "gear": {"symbol": "toothed_circle", "specs": ["teeth", "module", "pitch"]},
                "spring": {"symbol": "coiled_line", "types": ["compression", "tension", "torsion"]},
            },
            "network": {
                "router": {"symbol": "rounded_rectangle", "specs": ["ports", "speed", "protocol"]},
                "switch": {"symbol": "rectangle_grid", "specs": ["ports", "vlan", "speed"]},
                "firewall": {"symbol": "brick_wall", "specs": ["throughput", "rules", "zones"]},
            },
        }

    def classify_symbol(self, element: VisualElement, domain: TechnicalDomain) -> Dict[str, Any]:
        """Classify a technical symbol."""
        domain_symbols = self.symbol_database.get(domain.value, {})

        # Mock classification based on text content
        if element.text_content:
            text = element.text_content.lower()

            for symbol_type, properties in domain_symbols.items():
                if symbol_type in text or any(unit in text for unit in properties.get("units", [])):
                    return {"symbol_type": symbol_type, "confidence": 0.9, "properties": properties}

        return {"symbol_type": "unknown", "confidence": 0.0, "properties": {}}


class ChartDataExtractor:
    """Extracts data from charts and graphs."""

    @monitor_performance()
    async def extract_chart_data(self, image: Image.Image) -> ChartData:
        """Extract data from chart image."""
        time.time()

        try:
            # Mock chart analysis - would use computer vision in production
            chart_type = await self._detect_chart_type(image)

            if chart_type == "bar":
                return await self._extract_bar_chart_data(image)
            elif chart_type == "line":
                return await self._extract_line_chart_data(image)
            elif chart_type == "pie":
                return await self._extract_pie_chart_data(image)
            else:
                return await self._extract_generic_chart_data(image, chart_type)

        except Exception as e:
            logger.error(f"Chart data extraction failed: {e}")
            raise ImageAnalysisError(f"Chart extraction error: {e}")

    async def _detect_chart_type(self, image: Image.Image) -> str:
        """Detect the type of chart."""
        # Mock chart type detection
        width, height = image.size
        aspect_ratio = width / height

        if aspect_ratio > 1.5:
            return "bar"
        elif aspect_ratio < 0.8:
            return "line"
        else:
            return "pie"

    async def _extract_bar_chart_data(self, image: Image.Image) -> ChartData:
        """Extract data from bar chart."""
        return ChartData(
            chart_type="bar",
            title="Performance Metrics",
            x_axis_label="Components",
            y_axis_label="Performance (%)",
            legend=["Series A", "Series B"],
            data_points=[("Component 1", 85.0), ("Component 2", 92.0), ("Component 3", 78.0), ("Component 4", 96.0)],
            trends=["increasing", "slight_variation"],
            statistics={"mean": 87.75, "max": 96.0, "min": 78.0, "std": 7.41},
        )

    async def _extract_line_chart_data(self, image: Image.Image) -> ChartData:
        """Extract data from line chart."""
        return ChartData(
            chart_type="line",
            title="System Performance Over Time",
            x_axis_label="Time (hours)",
            y_axis_label="Response Time (ms)",
            data_points=[
                ("0", 120.0),
                ("1", 115.0),
                ("2", 135.0),
                ("3", 110.0),
                ("4", 125.0),
                ("5", 100.0),
                ("6", 95.0),
            ],
            trends=["decreasing", "optimizing"],
            statistics={"mean": 114.3, "trend_slope": -3.57},
        )

    async def _extract_pie_chart_data(self, image: Image.Image) -> ChartData:
        """Extract data from pie chart."""
        return ChartData(
            chart_type="pie",
            title="Resource Allocation",
            legend=["CPU", "Memory", "Storage", "Network"],
            data_points=[("CPU", 35.0), ("Memory", 25.0), ("Storage", 30.0), ("Network", 10.0)],
            statistics={"total": 100.0, "largest_segment": "CPU"},
        )

    async def _extract_generic_chart_data(self, image: Image.Image, chart_type: str) -> ChartData:
        """Extract data from generic chart type."""
        return ChartData(
            chart_type=chart_type,
            title="Technical Data Visualization",
            data_points=[("Data", 100.0)],
            statistics={"confidence": 0.75},
        )


class AdvancedImageUnderstanding:
    """Comprehensive image understanding system."""

    def __init__(self):
        self.vision_manager = AdvancedVisionModelManager()
        self.ocr_pipeline = OCRPipeline()
        self.diagram_interpreter = TechnicalDiagramInterpreter()
        self.chart_extractor = ChartDataExtractor()

        logger.info("Advanced Image Understanding system initialized")

    @monitor_performance()
    async def analyze_image(
        self,
        image: Union[Image.Image, str, bytes],
        analysis_type: Optional[str] = None,
        domain_hint: Optional[TechnicalDomain] = None,
    ) -> ImageUnderstandingResult:
        """Comprehensive image analysis."""
        start_time = time.time()

        try:
            # Convert input to PIL Image
            if isinstance(image, str):
                pil_image = Image.open(image)
            elif isinstance(image, bytes):
                import io

                pil_image = Image.open(io.BytesIO(image))
            else:
                pil_image = image

            # Determine image type and optimal analysis approach
            image_type = await self._classify_image_type(pil_image)
            domain = domain_hint or await self._infer_technical_domain(pil_image)

            # Initialize result
            result = ImageUnderstandingResult(
                image_type=image_type, technical_domain=domain, confidence=0.0, processing_time=0.0
            )

            # Perform appropriate analysis based on image type
            if image_type == "technical_diagram":
                await self._analyze_technical_diagram(pil_image, result, domain)
            elif image_type == "chart":
                await self._analyze_chart(pil_image, result)
            elif image_type == "schematic":
                await self._analyze_schematic(pil_image, result, domain)
            elif image_type == "mixed":
                await self._analyze_mixed_content(pil_image, result, domain)
            else:
                await self._analyze_general_technical(pil_image, result, domain)

            # Extract text using OCR
            await self._extract_text_content(pil_image, result)

            # Generate technical insights
            result.technical_insights = self._generate_insights(result)

            # Calculate quality metrics
            result.quality_metrics = self._calculate_quality_metrics(pil_image, result)

            # Calculate overall confidence
            result.confidence = self._calculate_overall_confidence(result)

            result.processing_time = time.time() - start_time

            logger.info(f"Image understanding completed in {result.processing_time:.3f}s")
            return result

        except Exception as e:
            logger.error(f"Image understanding failed: {e}")
            return ImageUnderstandingResult(
                image_type="unknown",
                technical_domain=TechnicalDomain.GENERAL,
                confidence=0.0,
                processing_time=time.time() - start_time,
                error=str(e),
            )

    async def _classify_image_type(self, image: Image.Image) -> str:
        """Classify the type of technical image."""
        # Use vision model for image classification
        vision_result = await self.vision_manager.analyze_image(image, task_type=VisionTaskType.IMAGE_CAPTIONING)

        description = vision_result.description.lower()

        if any(word in description for word in ["chart", "graph", "plot", "bar", "pie", "line"]):
            return "chart"
        elif any(word in description for word in ["schematic", "circuit", "wiring"]):
            return "schematic"
        elif any(word in description for word in ["diagram", "architecture", "topology", "flow"]):
            return "technical_diagram"
        elif any(word in description for word in ["mixed", "document", "manual"]):
            return "mixed"
        else:
            return "technical_image"

    async def _infer_technical_domain(self, image: Image.Image) -> TechnicalDomain:
        """Infer the technical domain of the image."""
        vision_result = await self.vision_manager.analyze_image(image, task_type=VisionTaskType.TECHNICAL_ANALYSIS)

        description = vision_result.description.lower()
        technical_elements = [elem.lower() for elem in vision_result.technical_elements]

        # Check for electrical domain indicators
        electrical_terms = ["circuit", "resistor", "capacitor", "transistor", "voltage", "current"]
        if any(term in description or term in technical_elements for term in electrical_terms):
            return TechnicalDomain.ELECTRICAL

        # Check for network domain indicators
        network_terms = ["network", "router", "switch", "topology", "protocol", "ip"]
        if any(term in description or term in technical_elements for term in network_terms):
            return TechnicalDomain.NETWORK

        # Check for mechanical domain indicators
        mechanical_terms = ["gear", "bearing", "shaft", "mechanical", "assembly"]
        if any(term in description or term in technical_elements for term in mechanical_terms):
            return TechnicalDomain.MECHANICAL

        return TechnicalDomain.GENERAL

    async def _analyze_technical_diagram(
        self, image: Image.Image, result: ImageUnderstandingResult, domain: TechnicalDomain
    ):
        """Analyze technical diagram."""
        diagram_structure = await self.diagram_interpreter.interpret_diagram(image, domain)
        result.diagram_structure = diagram_structure
        result.visual_elements = diagram_structure.components

        # Add metadata
        result.metadata.update(
            {
                "diagram_type": diagram_structure.diagram_type,
                "components_count": len(diagram_structure.components),
                "connections_count": len(diagram_structure.connections),
                "hierarchy_levels": len(diagram_structure.hierarchy_levels),
            }
        )

    async def _analyze_chart(self, image: Image.Image, result: ImageUnderstandingResult):
        """Analyze chart or graph."""
        chart_data = await self.chart_extractor.extract_chart_data(image)
        result.chart_data = chart_data

        # Add metadata
        result.metadata.update(
            {
                "chart_type": chart_data.chart_type,
                "data_points_count": len(chart_data.data_points),
                "has_trends": len(chart_data.trends) > 0,
                "statistics": chart_data.statistics,
            }
        )

    async def _analyze_schematic(self, image: Image.Image, result: ImageUnderstandingResult, domain: TechnicalDomain):
        """Analyze technical schematic."""
        # Similar to diagram analysis but with schematic-specific processing
        await self._analyze_technical_diagram(image, result, domain)

        # Additional schematic-specific analysis
        if result.diagram_structure:
            result.diagram_structure.diagram_type = "schematic"

    async def _analyze_mixed_content(
        self, image: Image.Image, result: ImageUnderstandingResult, domain: TechnicalDomain
    ):
        """Analyze mixed content (diagrams + charts + text)."""
        # Attempt both diagram and chart analysis
        try:
            await self._analyze_technical_diagram(image, result, domain)
        except Exception:
            # Continue without diagram analysis
            pass

        try:
            chart_data = await self.chart_extractor.extract_chart_data(image)
            result.chart_data = chart_data
        except Exception:
            # Continue without chart data
            pass

        result.metadata["content_type"] = "mixed"

    async def _analyze_general_technical(
        self, image: Image.Image, result: ImageUnderstandingResult, domain: TechnicalDomain
    ):
        """Analyze general technical image."""
        # Use vision model for general analysis
        vision_result = await self.vision_manager.analyze_image(image, task_type=VisionTaskType.TECHNICAL_ANALYSIS)

        # Create visual elements from vision analysis
        if vision_result.technical_elements:
            for i, element in enumerate(vision_result.technical_elements):
                visual_element = VisualElement(
                    element_type=ImageElementType.TECHNICAL_COMPONENT,
                    bbox=(i * 100, 100, (i + 1) * 100, 150),  # Mock positioning
                    confidence=vision_result.confidence,
                    text_content=element,
                    domain=domain,
                )
                result.visual_elements.append(visual_element)

        result.metadata.update(
            {"vision_model_used": vision_result.model_type.value, "vision_confidence": vision_result.confidence}
        )

    async def _extract_text_content(self, image: Image.Image, result: ImageUnderstandingResult):
        """Extract text content using OCR."""
        # Determine appropriate document type for OCR
        doc_type = DocumentType.MIXED
        if result.image_type == "schematic":
            doc_type = DocumentType.SCHEMATIC
        elif result.image_type == "technical_diagram":
            doc_type = DocumentType.TECHNICAL_DRAWING

        ocr_result = await self.ocr_pipeline.extract_text(image, document_type=doc_type)
        result.extracted_text = ocr_result.full_text

        # Add OCR metadata
        result.metadata.update(
            {
                "ocr_engine": ocr_result.engine.value,
                "ocr_confidence": ocr_result.confidence,
                "technical_terms_ocr": ocr_result.technical_terms,
            }
        )

    def _generate_insights(self, result: ImageUnderstandingResult) -> List[str]:
        """Generate technical insights from analysis."""
        insights = []

        # Insights from diagram structure
        if result.diagram_structure:
            structure = result.diagram_structure
            insights.append(f"Diagram contains {len(structure.components)} technical components")

            if structure.connections:
                insights.append(f"System has {len(structure.connections)} interconnections")

            if structure.flow_direction:
                insights.append(f"Data/signal flow direction: {structure.flow_direction}")

            if structure.technical_specifications:
                insights.append(
                    f"Technical specifications identified: {len(structure.technical_specifications)} parameters"
                )

        # Insights from chart data
        if result.chart_data:
            chart = result.chart_data
            insights.append(f"Chart displays {len(chart.data_points)} data points")

            if chart.trends:
                insights.append(f"Data trends identified: {', '.join(chart.trends)}")

            if chart.statistics:
                if "mean" in chart.statistics:
                    insights.append(f"Average value: {chart.statistics['mean']:.2f}")

        # Insights from visual elements
        if result.visual_elements:
            component_types = {}
            for element in result.visual_elements:
                elem_type = element.element_type.value
                component_types[elem_type] = component_types.get(elem_type, 0) + 1

            insights.append(f"Visual element distribution: {component_types}")

        # Domain-specific insights
        if result.technical_domain == TechnicalDomain.ELECTRICAL:
            insights.append("Electrical system analysis: Component values and connections identified")
        elif result.technical_domain == TechnicalDomain.NETWORK:
            insights.append("Network topology analysis: Infrastructure and connectivity mapping")

        return insights

    def _calculate_quality_metrics(self, image: Image.Image, result: ImageUnderstandingResult) -> Dict[str, float]:
        """Calculate image quality metrics."""
        width, height = image.size

        return {
            "resolution_score": min(1.0, (width * height) / (1920 * 1080)),  # Relative to Full HD
            "aspect_ratio": width / height,
            "complexity_score": len(result.visual_elements) / 10.0,  # Normalized by typical count
            "text_clarity": len(result.extracted_text) / 100.0 if result.extracted_text else 0.0,
            "technical_completeness": len(result.technical_insights) / 5.0,  # Normalized by expected insights
        }

    def _calculate_overall_confidence(self, result: ImageUnderstandingResult) -> float:
        """Calculate overall confidence score."""
        confidence_scores = []

        # Vision model confidence
        if result.metadata.get("vision_confidence"):
            confidence_scores.append(result.metadata["vision_confidence"])

        # OCR confidence
        if result.metadata.get("ocr_confidence"):
            confidence_scores.append(result.metadata["ocr_confidence"])

        # Structural analysis confidence
        if result.visual_elements:
            element_confidences = [e.confidence for e in result.visual_elements]
            if element_confidences:
                confidence_scores.append(sum(element_confidences) / len(element_confidences))

        # Quality metrics influence
        if result.quality_metrics:
            quality_avg = sum(result.quality_metrics.values()) / len(result.quality_metrics)
            confidence_scores.append(quality_avg)

        return sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics for image understanding system."""
        return {
            "vision_models": len(self.vision_manager.get_available_models()),
            "ocr_engines": len(self.ocr_pipeline.get_available_engines()),
            "supported_domains": [domain.value for domain in TechnicalDomain],
            "supported_image_types": ["technical_diagram", "schematic", "chart", "mixed", "technical_image"],
            "analysis_capabilities": [
                "component_detection",
                "connection_analysis",
                "hierarchy_detection",
                "chart_data_extraction",
                "text_extraction",
                "technical_insights",
            ],
        }


# Initialize global advanced image understanding system
advanced_image_understanding = AdvancedImageUnderstanding()

logger.info("Phase 3B Advanced Image Understanding module loaded successfully")
