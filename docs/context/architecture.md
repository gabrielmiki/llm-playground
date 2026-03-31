# Model Architecture Documentation

## Overview
This module contains both pretrained model support and from-scratch implementations for exploring LLM architectures.

## Directory Structure

```
src/model/
├── __init__.py
├── pretrained/        # Fine-tuning pretrained models
│   ├── __init__.py
│   ├── gpt2_finetune.py
│   └── bert_custom.py
├── scratch/           # From-scratch implementations
│   ├── __init__.py
│   ├── transformer.py
│   ├── attention.py
│   ├── embedding.py
│   └── feedforward.py
├── layers/           # Reusable components
│   ├── __init__.py
│   ├── positional_encoding.py
│   └── layer_norm.py
└── training/         # Training utilities
    ├── __init__.py
    ├── trainer.py
    └── optimizer.py
```

## Pretrained Models

### GPT-2 Fine-tuning
```python
from src.model.pretrained import GPT2FineTuner

tuner = GPT2FineTuner(
    model_name="gpt2",
    max_length=512,
    learning_rate=2e-5
)
tuner.train(train_dataset, eval_dataset)
```

### BERT Custom Tasks
```python
from src.model.pretrained import BERTCustom

model = BERTCustom(
    num_labels=3,
    task="classification"
)
```

## From-Scratch Implementations

### Transformer Architecture
Minimal implementation following "Attention is All You Need":

- Multi-head self-attention
- Feed-forward networks
- Positional encoding (sinusoidal)
- Layer normalization
- Residual connections

### Key Components

**Attention (`attention.py`)**
- Scaled dot-product attention
- Multi-head attention with configurable heads
- Flash attention support for memory efficiency

**Embedding (`embedding.py`)**
- Token embeddings
- Learned positional embeddings
- Combined embedding with dropout

**Feedforward (`feedforward.py`)**
- GELU activation (GPT-2 style)
- Configurable hidden dimension

## Training

### Trainer (`training/trainer.py`)
```python
from src.model.training import Trainer

trainer = Trainer(
    model=model,
    optimizer=torch.optim.AdamW,
    lr=1e-4,
    gradient_clip=1.0,
    device="cuda" if torch.cuda.is_available() else "cpu"
)
trainer.train(dataloader, num_epochs=10)
```

### Visualization
- Weights & Biases (`wandb`) for experiment tracking
- TensorBoard (`tensorboard`) for local metrics
- Custom callbacks in `training/callbacks.py`

## Design Principles

1. **Educational clarity**: Code should be readable and well-commented
2. **Configurable**: All hyperparameters exposed
3. **Benchmarked**: Compare scratch vs. pretrained performance
4. **Reproducible**: Deterministic training when possible

## Testing
- Unit tests for individual components
- Integration tests for full forward/backward pass
- Performance benchmarks comparing implementations
