#!/usr/bin/env python3
"""
Fine-tune Mistral 7B on RNI Technical Knowledge

Uses the training data extracted from PGVector to fine-tune a Mistral model
for improved technical support capabilities.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class MistralFineTuner:
    """Fine-tune Mistral model on RNI technical data."""

    def __init__(self, model_name: str = "mistralai/Mistral-7B-v0.1"):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Using device: {self.device}")

    def load_model_and_tokenizer(self):
        """Load the base Mistral model and tokenizer."""
        logger.info(f"Loading model: {self.model_name}")

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model with quantization for memory efficiency (GPU) or regular loading (CPU)
        if self.device == "cuda":
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                load_in_8bit=True,  # Use 8-bit quantization
            )
        else:
            # CPU loading without quantization
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,  # Use float32 for CPU
                device_map={"": "cpu"},
            )

        logger.info("Model and tokenizer loaded successfully")

    def setup_lora(self):
        """Configure LoRA for efficient fine-tuning."""
        logger.info("Setting up LoRA configuration")

        lora_config = LoraConfig(
            r=16,  # LoRA rank
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )

        self.model = prepare_model_for_kbit_training(self.model)
        self.model = get_peft_model(self.model, lora_config)

        logger.info("LoRA setup complete")

    def load_training_data(self, data_path: str) -> Dataset:
        """Load training data from JSONL file."""
        logger.info(f"Loading training data from {data_path}")

        data = []
        with open(data_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data.append(json.loads(line))

        # Convert to HuggingFace dataset
        dataset = Dataset.from_list(data)
        logger.info(f"Loaded {len(dataset)} training examples")

        return dataset

    def preprocess_function(self, examples):
        """Preprocess training examples for Mistral."""
        # Format as instruction-response pairs
        formatted_texts = []
        for example in examples:
            instruction = example["instruction"]
            input_text = example.get("input", "")
            output = example["output"]

            # Create chat format
            if input_text:
                text = f"<s>[INST] {instruction}\n\n{input_text} [/INST] {output}</s>"
            else:
                text = f"<s>[INST] {instruction} [/INST] {output}</s>"

            formatted_texts.append(text)

        # Tokenize
        tokenized = self.tokenizer(
            formatted_texts,
            truncation=True,
            padding=False,
            max_length=2048,
            return_tensors="pt"
        )

        return tokenized

    def train(self, train_dataset: Dataset, output_dir: str = "./rni-mistral-finetuned"):
        """Fine-tune the model."""
        logger.info("Starting fine-tuning process")

        # Preprocess dataset
        processed_dataset = train_dataset.map(
            self.preprocess_function,
            batched=True,
            remove_columns=train_dataset.column_names
        )

        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=3,
            per_device_train_batch_size=1,  # Smaller batch size for CPU
            gradient_accumulation_steps=8,  # Compensate with gradient accumulation
            learning_rate=2e-4,
            weight_decay=0.01,
            warmup_steps=100,
            logging_steps=10,
            save_steps=500,
            save_total_limit=2,
            fp16=self.device == "cuda",  # Only use fp16 on GPU
            dataloader_pin_memory=False,
            report_to="none",  # Disable wandb/tensorboard
        )

        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False  # Not masked language modeling
        )

        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=processed_dataset,
            data_collator=data_collator,
        )

        # Train
        logger.info("Beginning training...")
        trainer.train()

        # Save the fine-tuned model
        trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        logger.info(f"Model saved to {output_dir}")
        return output_dir

    def create_ollama_model_file(self, model_dir: str, ollama_model_name: str = "rni-mistral"):
        """Create an Ollama model file for the fine-tuned model."""
        ollama_modelfile = f"""
FROM {model_dir}

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 40

SYSTEM "You are a technical support specialist for RNI (Regional Network Interface) systems. You have extensive knowledge of Sensus products, gas meters, AMI systems, and utility infrastructure. Provide clear, accurate, and helpful responses based on technical documentation."

MESSAGE "You are an expert in RNI systems, gas metering technology, and utility communications. Answer questions with technical accuracy and practical guidance."
"""

        modelfile_path = f"{model_dir}/Modelfile"
        with open(modelfile_path, 'w') as f:
            f.write(ollama_modelfile.strip())

        logger.info(f"Created Ollama Modelfile at {modelfile_path}")
        return modelfile_path


def main():
    """Main fine-tuning pipeline."""
    logging.basicConfig(level=logging.INFO)

    # Configuration
    training_data_path = "training_data/rni_training_tuned.jsonl"
    output_dir = "./models/rni-mistral-finetuned"

    # Initialize fine-tuner
    fine_tuner = MistralFineTuner()

    # Load model and tokenizer
    logger.info("Step 1: Loading base model")
    fine_tuner.load_model_and_tokenizer()

    # Setup LoRA
    logger.info("Step 2: Configuring LoRA")
    fine_tuner.setup_lora()

    # Load training data
    logger.info("Step 3: Loading training data")
    train_dataset = fine_tuner.load_training_data(training_data_path)

    # Fine-tune
    logger.info("Step 4: Fine-tuning model")
    model_dir = fine_tuner.train(train_dataset, output_dir)

    # Create Ollama model file
    logger.info("Step 5: Creating Ollama model file")
    fine_tuner.create_ollama_model_file(model_dir)

    logger.info("Fine-tuning complete!")
    logger.info(f"Model saved to: {model_dir}")
    logger.info(f"To create Ollama model: ollama create rni-mistral -f {model_dir}/Modelfile")


if __name__ == "__main__":
    main()
