#!/usr/bin/env python3
"""
Model Specialization Script for Technical Service Assistant
Redistributes models across 4 Ollama instances for specialized performance

Target Architecture:
- Instance 1 (11434): General Chat & Document QA
- Instance 2 (11435): Code & Technical Analysis
- Instance 3 (11436): Advanced Reasoning & Math
- Instance 4 (11437): Embeddings & Search Optimization
"""

import json
import sys
import time
from dataclasses import dataclass
from typing import Dict, List

import requests


@dataclass
class ModelSpec:
    name: str
    purpose: str
    instance: int
    priority: int  # 1=critical, 2=important, 3=optional


# Target model distribution based on current inventory and specialization plan
TARGET_DISTRIBUTION = {
    1: [  # General Chat & Document QA (11434)
        ModelSpec("mistral:7b", "Primary chat model", 1, 1),
        ModelSpec("mistral:latest", "Chat fallback", 1, 2),
        ModelSpec("llama3.1:8b", "Advanced chat", 1, 2),
        ModelSpec("nomic-embed-text:v1.5", "Primary embeddings", 1, 1),
    ],
    2: [  # Code & Technical Analysis (11435)
        ModelSpec("mistral:7b", "Technical documentation", 2, 1),
        ModelSpec("gemma2:2b", "Fast code analysis", 2, 2),
        ModelSpec("phi3:mini", "Lightweight technical tasks", 2, 2),
        ModelSpec("nomic-embed-text:v1.5", "Code embeddings", 2, 3),
    ],
    3: [  # Advanced Reasoning & Math (11436)
        ModelSpec("llama3.1:8b", "Complex reasoning", 3, 1),
        ModelSpec("llama3.2:3b", "Mathematical analysis", 3, 2),
        ModelSpec("mistral:latest", "Reasoning fallback", 3, 2),
        ModelSpec("nomic-embed-text:latest", "Reasoning embeddings", 3, 3),
    ],
    4: [  # Embeddings & Search Optimization (11437)
        ModelSpec("nomic-embed-text:v1.5", "Primary embeddings", 4, 1),
        ModelSpec("nomic-embed-text:latest", "Backup embeddings", 4, 1),
        ModelSpec("gemma2:2b", "Fast semantic processing", 4, 2),
        ModelSpec("llama3.2:1b", "Lightweight processing", 4, 3),
    ],
}


class OllamaModelManager:
    def __init__(self):
        self.base_ports = [11434, 11435, 11436, 11437]
        self.base_url = "http://localhost"

    def get_instance_url(self, instance: int) -> str:
        """Get URL for instance number (1-4)"""
        return f"{self.base_url}:{self.base_ports[instance-1]}"

    def list_models(self, instance: int) -> List[str]:
        """List models available on an instance"""
        try:
            url = f"{self.get_instance_url(instance)}/api/tags"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            print(f"❌ Error listing models on instance {instance}: {e}")
            return []

    def model_exists(self, instance: int, model_name: str) -> bool:
        """Check if model exists on instance"""
        models = self.list_models(instance)
        return model_name in models

    def pull_model(self, instance: int, model_name: str) -> bool:
        """Pull model to instance"""
        url = f"{self.get_instance_url(instance)}/api/pull"
        payload = {"name": model_name}

        try:
            print(f"📥 Pulling {model_name} to instance {instance}...")
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()

            # Stream response to show progress
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "status" in data:
                        print(f"   Status: {data['status']}")
                    if data.get("status") == "success":
                        print(f"✅ Successfully pulled {model_name} to instance {instance}")
                        return True

        except Exception as e:
            print(f"❌ Error pulling {model_name} to instance {instance}: {e}")

        return False

    def delete_model(self, instance: int, model_name: str) -> bool:
        """Delete model from instance"""
        url = f"{self.get_instance_url(instance)}/api/delete"
        payload = {"name": model_name}

        try:
            print(f"🗑️  Deleting {model_name} from instance {instance}...")
            response = requests.delete(url, json=payload, timeout=60)
            response.raise_for_status()
            print(f"✅ Successfully deleted {model_name} from instance {instance}")
            return True

        except Exception as e:
            print(f"❌ Error deleting {model_name} from instance {instance}: {e}")
            return False


def analyze_current_distribution(manager: OllamaModelManager) -> Dict[int, List[str]]:
    """Analyze current model distribution across instances"""
    print("🔍 Analyzing current model distribution...")

    current_dist = {}
    for instance in range(1, 5):
        models = manager.list_models(instance)
        current_dist[instance] = models
        print(f"   Instance {instance}: {len(models)} models - {', '.join(models)}")

    return current_dist


def calculate_redistribution_plan(
    current_dist: Dict[int, List[str]], target_dist: Dict[int, List[ModelSpec]]
) -> Dict[str, List]:
    """Calculate what models need to be moved/added/removed"""
    plan = {
        "pull": [],  # (instance, model_name, priority)
        "delete": [],  # (instance, model_name)
        "keep": [],  # (instance, model_name)
    }

    # Build target sets per instance
    target_models = {}
    for instance, specs in target_dist.items():
        target_models[instance] = {spec.name: spec.priority for spec in specs}

    # Analyze each instance
    for instance in range(1, 5):
        current_models = set(current_dist.get(instance, []))
        target_set = set(target_models.get(instance, {}).keys())

        # Models to keep (intersection)
        keep_models = current_models & target_set
        for model in keep_models:
            plan["keep"].append((instance, model))

        # Models to pull (target - current)
        pull_models = target_set - current_models
        for model in pull_models:
            priority = target_models[instance][model]
            plan["pull"].append((instance, model, priority))

        # Models to delete (current - target)
        delete_models = current_models - target_set
        for model in delete_models:
            plan["delete"].append((instance, model))

    return plan


def execute_redistribution_plan(manager: OllamaModelManager, plan: Dict[str, List], dry_run: bool = False) -> bool:
    """Execute the model redistribution plan"""

    if dry_run:
        print("🧪 DRY RUN MODE - No actual changes will be made")

    print(f"\n📋 Redistribution Plan Summary:")
    print(f"   Models to pull: {len(plan['pull'])}")
    print(f"   Models to delete: {len(plan['delete'])}")
    print(f"   Models to keep: {len(plan['keep'])}")

    # Show detailed plan
    print(f"\n📥 Models to Pull:")
    for instance, model, priority in sorted(plan["pull"], key=lambda x: x[2]):
        print(f"   Instance {instance}: {model} (priority {priority})")

    print(f"\n🗑️  Models to Delete:")
    for instance, model in plan["delete"]:
        print(f"   Instance {instance}: {model}")

    print(f"\n✅ Models to Keep:")
    for instance, model in plan["keep"]:
        print(f"   Instance {instance}: {model}")

    if dry_run:
        return True

    # Confirm execution
    confirm = input(f"\n⚠️  Proceed with redistribution? (y/N): ").strip().lower()
    if confirm != "y":
        print("❌ Redistribution cancelled")
        return False

    success_count = 0
    total_operations = len(plan["pull"]) + len(plan["delete"])

    # Phase 1: Pull new models (sorted by priority)
    print(f"\n📥 Phase 1: Pulling new models...")
    for instance, model, priority in sorted(plan["pull"], key=lambda x: x[2]):
        if manager.pull_model(instance, model):
            success_count += 1
        time.sleep(2)  # Brief pause between operations

    # Phase 2: Delete unused models
    print(f"\n🗑️  Phase 2: Removing unused models...")
    for instance, model in plan["delete"]:
        if manager.delete_model(instance, model):
            success_count += 1
        time.sleep(1)  # Brief pause between operations

    success_rate = success_count / total_operations if total_operations > 0 else 1.0
    print(
        f"\n📊 Redistribution completed: "
        f"{success_count}/{total_operations} operations successful "
        f"({success_rate:.1%})"
    )

    return success_rate > 0.8


def validate_specialization(manager: OllamaModelManager) -> bool:
    """Validate that specialization was successful"""
    print(f"\n✅ Validating specialization...")

    validation_passed = True

    for instance, specs in TARGET_DISTRIBUTION.items():
        print(f"\n🔸 Instance {instance} validation:")
        current_models = set(manager.list_models(instance))

        for spec in specs:
            if spec.priority == 1:  # Critical models must exist
                if spec.name in current_models:
                    print(f"   ✅ {spec.name} ({spec.purpose})")
                else:
                    print(f"   ❌ MISSING: {spec.name} ({spec.purpose})")
                    validation_passed = False
            else:
                if spec.name in current_models:
                    print(f"   ✅ {spec.name} ({spec.purpose})")
                else:
                    print(f"   ⚠️  Optional missing: {spec.name} ({spec.purpose})")

    return validation_passed


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Redistribute Ollama models for specialization")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--validate-only", action="store_true", help="Only validate current state")
    args = parser.parse_args()

    print("🚀 Technical Service Assistant - Model Specialization")
    print("=" * 60)

    manager = OllamaModelManager()

    # Validate only mode
    if args.validate_only:
        return validate_specialization(manager)

    # Analyze current state
    current_dist = analyze_current_distribution(manager)

    # Calculate redistribution plan
    plan = calculate_redistribution_plan(current_dist, TARGET_DISTRIBUTION)

    # Execute plan
    success = execute_redistribution_plan(manager, plan, dry_run=args.dry_run)

    if success and not args.dry_run:
        # Validate results
        time.sleep(5)  # Allow models to settle
        validation_success = validate_specialization(manager)

        if validation_success:
            print(f"\n🎉 Model specialization completed successfully!")
            print(f"📋 Next steps:")
            print(f"   1. Update intelligent routing logic")
            print(f"   2. Test specialized model performance")
            print(f"   3. Monitor resource utilization")
            return True
        else:
            print(f"\n⚠️  Specialization completed with validation issues")
            return False

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
