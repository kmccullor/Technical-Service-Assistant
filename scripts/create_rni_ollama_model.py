#!/usr/bin/env python3
"""
Create RNI-Trained Ollama Model

Creates a custom Ollama model that incorporates RNI technical knowledge
through enhanced system prompts and context injection.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def create_rni_modelfile():
    """Create an Ollama Modelfile for RNI-trained model."""

    # Load training data to extract key knowledge
    training_data_path = "training_data/rni_training_tuned.jsonl"
    knowledge_samples = []

    if os.path.exists(training_data_path):
        with open(training_data_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 10:  # Just get first 10 examples for knowledge base
                    break
                try:
                    data = json.loads(line)
                    knowledge_samples.append(data["output"][:500])  # First 500 chars
                except:
                    continue

    # Create comprehensive system prompt
    system_prompt = f"""You are an expert technical support specialist for RNI (Regional Network Interface) systems and Sensus products.

Your knowledge includes:

TECHNICAL EXPERTISE:
- RNI 4.16 platform architecture and configuration
- Sensus gas meters (R175, R200, RT200, RT230, R275, RT275, R315, R250 models)
- AMI (Advanced Metering Infrastructure) systems
- SmartPoint 100GM transceiver installation and configuration
- Utility communications protocols (MultiSpeak, CMEP)
- FlexNet communication systems
- PostgreSQL database administration for utility systems

KEY CAPABILITIES:
- Provide step-by-step installation and configuration guidance
- Troubleshoot technical issues with detailed diagnostic steps
- Explain complex technical concepts in clear, practical terms
- Reference specific documentation sections when relevant
- Suggest best practices for system maintenance and optimization

RESPONSE STYLE:
- Be precise and technically accurate
- Use clear, professional language
- Provide actionable solutions
- Include safety considerations when relevant
- Cite specific components, versions, and procedures

SAMPLE KNOWLEDGE BASE:
{knowledge_samples[0] if knowledge_samples else "SmartPoint 100GM transceiver installation requires calibrated torque screwdrivers and proper meter indexing."}

Always base your responses on technical documentation and established procedures."""

    # Create Modelfile content
    modelfile_content = f"""FROM mistral:7b

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 4096

SYSTEM \"\"\"{system_prompt}\"\"\"

# Enhanced technical knowledge template
TEMPLATE \"\"\"{{ if .System }}{{ .System }}{{ end }}{{ if .Prompt }} {{ .Prompt }}{{ end }}{{ if .Response }} {{ .Response }}{{ end }}{{ if .Tools }} {{ .Tools }}{{ end }}\"\"\"

# Parameter overrides for technical accuracy
PARAMETER mirostat 2
PARAMETER mirostat_tau 3.0
PARAMETER mirostat_eta 0.1
"""

    return modelfile_content


def create_knowledge_injection_script():
    """Create a script to inject RNI knowledge into responses."""

    script_content = """#!/usr/bin/env python3
\"\"\"
RNI Knowledge Injection Script

Enhances Ollama responses with RNI technical knowledge injection.
\"\"\"

import json
import sys
from typing import Dict, List

class RNIKnowledgeInjector:
    \"\"\"Inject RNI technical knowledge into model responses.\"\"\"

    def __init__(self):
        self.knowledge_base = self.load_knowledge_base()

    def load_knowledge_base(self) -> Dict[str, List[str]]:
        \"\"\"Load RNI knowledge from training data.\"\"\"
        knowledge = {
            'installation': [],
            'configuration': [],
            'troubleshooting': [],
            'specifications': []
        }

        try:
            with open('training_data/rni_training_tuned.jsonl', 'r') as f:
                for line in f:
                    data = json.loads(line)
                    content = data.get('output', '').lower()

                    if 'install' in content:
                        knowledge['installation'].append(data['output'][:300])
                    if 'config' in content or 'setup' in content:
                        knowledge['configuration'].append(data['output'][:300])
                    if 'error' in content or 'problem' in content or 'fix' in content:
                        knowledge['troubleshooting'].append(data['output'][:300])
                    if 'spec' in content or 'requirement' in content:
                        knowledge['specifications'].append(data['output'][:300])
        except FileNotFoundError:
            print("Warning: Training data not found, using default knowledge")

        return knowledge

    def inject_knowledge(self, query: str, response: str) -> str:
        \"\"\"Inject relevant RNI knowledge into the response.\"\"\"
        query_lower = query.lower()

        relevant_knowledge = []

        # Match query to knowledge categories
        if any(word in query_lower for word in ['install', 'setup', 'mount']):
            relevant_knowledge.extend(self.knowledge_base.get('installation', [])[:2])

        if any(word in query_lower for word in ['config', 'configure', 'setting']):
            relevant_knowledge.extend(self.knowledge_base.get('configuration', [])[:2])

        if any(word in query_lower for word in ['error', 'problem', 'issue', 'fix', 'trouble']):
            relevant_knowledge.extend(self.knowledge_base.get('troubleshooting', [])[:2])

        if any(word in query_lower for word in ['spec', 'requirement', 'version']):
            relevant_knowledge.extend(self.knowledge_base.get('specifications', [])[:2])

        # Inject knowledge if relevant
        if relevant_knowledge:
            knowledge_text = "\\n\\n**Additional Technical Reference:**\\n" + "\\n".join(relevant_knowledge[:1])
            return response + knowledge_text

        return response


def main():
    \"\"\"Main function for testing knowledge injection.\"\"\"
    injector = RNIKnowledgeInjector()

    # Test queries
    test_queries = [
        "How do I install the SmartPoint transceiver?",
        "What are the configuration requirements for RNI?",
        "How do I troubleshoot communication issues?",
        "What are the specifications for gas meters?"
    ]

    for query in test_queries:
        print(f"Query: {query}")
        # Simulate response enhancement
        enhanced = injector.inject_knowledge(query, "This is a sample response.")
        print(f"Enhanced: {enhanced[:200]}...")
        print("-" * 50)


if __name__ == "__main__":
    main()
"""

    return script_content


def main():
    """Create RNI-trained Ollama model."""
    logging.basicConfig(level=logging.INFO)

    # Create model directory
    model_dir = Path("./models/rni-mistral")
    model_dir.mkdir(parents=True, exist_ok=True)

    # Create Modelfile
    logger.info("Creating RNI Modelfile...")
    modelfile_content = create_rni_modelfile()

    modelfile_path = model_dir / "Modelfile"
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    logger.info(f"Modelfile created at {modelfile_path}")

    # Create knowledge injection script
    logger.info("Creating knowledge injection script...")
    injection_script = create_knowledge_injection_script()

    script_path = model_dir / "knowledge_injector.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(injection_script)

    logger.info(f"Knowledge injection script created at {script_path}")

    # Create usage instructions
    instructions = f"""
# RNI-Trained Mistral Model Setup

## 1. Create the Ollama Model
```bash
cd {model_dir}
ollama create rni-mistral -f Modelfile
```

## 2. Test the Model
```bash
ollama run rni-mistral
```

## 3. Example Queries
- "How do I install a SmartPoint 100GM transceiver?"
- "What are the configuration requirements for RNI 4.16?"
- "How do I troubleshoot gas meter communication issues?"
- "What are the specifications for Sensus RT275 meters?"

## 4. Knowledge Injection (Optional)
For enhanced responses with direct knowledge injection:
```bash
python knowledge_injector.py
```

## Model Features
- Specialized system prompt for RNI technical support
- Optimized parameters for technical accuracy
- Extended context window (4096 tokens)
- Mirostat sampling for consistent responses
"""

    readme_path = model_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(instructions)

    logger.info(f"Setup instructions created at {readme_path}")
    logger.info("\n" + "=" * 50)
    logger.info("RNI-TRAINED MODEL CREATION COMPLETE!")
    logger.info("=" * 50)
    logger.info(f"Model files created in: {model_dir}")
    logger.info("\nNext steps:")
    logger.info("1. cd models/rni-mistral")
    logger.info("2. ollama create rni-mistral -f Modelfile")
    logger.info("3. ollama run rni-mistral")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
