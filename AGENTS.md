# AGENTS.md

## Project Overview
LLM playground for exploring AI tooling: data collection, cleaning, tokenization, model architecture, and text generation. Includes both pretrained model support and from-scratch implementations. Solo exploration, no production deployment.

## Tech Stack

### Package Manager
- `uv` for all dependency management (no requirements.txt)

### Core ML
- `torch` — tensor computation and neural networks
- `transformers` — pretrained models (BERT, GPT, etc.) and from-scratch components
- `accelerate` — distributed/multi-GPU training

### Data Collection
- `httpx` — async HTTP client for APIs
- `beautifulsoup4` — web scraping (HTML)
- `pypdf` — PDF text extraction
- `python-docx` — Word document extraction
- `pandas` — CSV/Excel/file-based data

### Preprocessing
- `regex` — advanced text operations
- `ftfy` — fix text encoding issues
- `langdetect` — language detection/filtering
- `nltk` — NLP utilities (stopwords, tokenization helpers)

### Tokenization
- `tiktoken` — fast OpenAI-style BPE tokenization
- `tokenizers` — HuggingFace fast tokenizers
- `sentencepiece` — subword tokenization (SentencePiece)

### Training Visualization
- `wandb` — experiment tracking and visualization (Weights & Biases)
- `tensorboard` — local training metrics (TensorBoard)

### Utilities
- `tqdm` — progress bars

## Repository Structure
```
.opencode/           # OpenCode configuration
  agents/            # Specialist agents (YAML frontmatter)
  skills/            # Reusable skills (SKILL.md format)
  handoffs/          # Session handoffs
data/
  raw/               # original data (immutable)
  processed/          # cleaned & tokenized data
src/
  collect/            # data collection scripts
  preprocess/         # cleaning & tokenization
  model/              # architecture definitions
  generate/           # text generation
docs/
  context/            # detailed documentation (progressive disclosure)
notebooks/            # exploration & experiments
```

## Build & Run Commands

```bash
# Data pipeline
python -m src.collect           # run collection
python -m src.preprocess       # clean & tokenize

# Model
python -m src.model             # train model
python -m src.model.pretrained  # fine-tune pretrained

# Generation
python -m src.generate          # generate text

# Code quality
uv run ruff check .             # lint
uv run ruff format .            # format
uv run mypy src/                # type check
```

## Code Style
- Line length: 100 characters
- Use type hints in `src/`
- Import order: stdlib → third-party → local
- Docstrings: Google style

## Three-Tier Boundaries

**Always do:**
- Verify new packages exist on PyPI before adding to project
- Run `uv run ruff check .` before commit
- Keep `data/raw/` immutable — never modify source data

**Ask first:**
- Modifying model architecture
- Changing tokenization approach
- Adding new data sources

**Never do:**
- Commit API keys, tokens, or secrets
- Modify files in `data/raw/`
- Push to remote without verifying package existence

## Extended Context
For data pipeline implementation details, see @docs/context/pipeline.md
For model architecture documentation, see @docs/context/architecture.md
For complete workflow process, see @docs/context/process-flow.md

## Specialist Agents

Invoke these agents for specific review tasks:

| Agent | When to Use | Command |
|-------|-------------|---------|
| `@.opencode/agents/architecture-reviewer.md` | Before planning phase | Review architecture plans |
| `@.opencode/agents/security-diagnosis.md` | After adding dependencies | Verify packages exist |
| `@.opencode/agents/pre-commit-checker.md` | After running lint/tests | Explain errors |
| `@.opencode/agents/tdd-reviewer.md` | Before implementation | Validate test plans |
| `@.opencode/agents/code-reviewer.md` | Before commits | C.L.E.A.R. review |

## Skills

Load these skills for structured workflows:

| Skill | Purpose | Load Command |
|-------|---------|-------------|
| `@.opencode/skills/prd-writer/SKILL.md` | Socratic PRD elicitation | /skill prd-writer |
| `@.opencode/skills/ticket-generator/SKILL.md` | PRD → tickets | /skill ticket-generator |
| `@.opencode/skills/continuation/SKILL.md` | Session handoffs | /skill continuation |
| `@.opencode/skills/clear-review/SKILL.md` | C.L.E.A.R. checklist | /skill clear-review |

## Session Handoffs

Session handoffs use a folder-based structure for organized context preservation:

```
.opencode/handoffs/YYYY-MM-DD-title/
├── handoff.md                    # Main handoff document
├── input/context/               # Previous session outputs
└── output/
    ├── reviews/                 # Agent review outputs
    ├── decisions/               # Architectural decisions
    └── analysis/                # Research/analysis
```

**How to use:**
1. Generate handoff using `@.opencode/skills/continuation/SKILL.md`
2. Create folder: `.opencode/handoffs/YYYY-MM-DD-title/`
3. Save handoff.md and any outputs to the folder
4. Start new session by reading the handoff file

**How agents get code context:**
Agents use `git diff HEAD~1` to see implementation changes — no need to copy code to handoff folders.

## Context Management

- Compact context at 60% (not 90%)
- Fresh session with written handoff > resuming stale context
- Document progress after every meaningful increment
