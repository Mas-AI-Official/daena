#!/usr/bin/env python3
"""
Azure GPU Training Script for gemma_27b
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from datasets import Dataset
import json

def train_gemma_27b_on_azure():
    # Load model
    tokenizer = AutoTokenizer.from_pretrained("google/gemma-2-27b-it")
    model = AutoModelForCausalLM.from_pretrained("google/gemma-2-27b-it")
    
    # Load training data
    with open("./data/gemma_27b_training_data.json", 'r') as f:
        training_data = json.load(f)
    
    # Create dataset
    dataset = Dataset.from_dict({"text": [item['text'] for item in training_data]})
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir="./trained_models/gemma_27b_azure",
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=3e-5,
        warmup_steps=100,
        logging_steps=10,
        save_steps=500,
        eval_steps=500,
        evaluation_strategy="steps",
        save_strategy="steps",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
    )
    
    # Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )
    
    trainer.train()
    trainer.save_model()
    
if __name__ == "__main__":
    train_gemma_27b_on_azure()
