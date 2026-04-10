# IT Job Offers Analyzer

Analyze IT job offers from [justjoin.it](https://justjoin.it) — a Polish job board for the tech industry.

Features:
- Filter offers by city, category, experience, workplace, employment type
- Statistical salary analysis with percentile distribution
- IQR-based outlier detection
- Top-paying companies ranking
- B2B benefits analysis (paid vacation, sick leave)
- Interactive REPL with tab-completion and session caching

## Requirements

- Python 3.10+
- [rich](https://github.com/Textualize/rich) — terminal formatting
- [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) — interactive REPL

All dependencies are installed automatically via `pip`.

## Installation

```bash
pip install itjobs
```

## Usage

### Interactive CLI (recommended)

```bash
itjobs
```

Commands auto-fetch data when needed:

```
/analyze Kraków python senior b2b
/top b2b >P75
/benefits Kraków python senior
/show
/help
```

## Development

```bash
git clone https://github.com/m-grzesiak/IT-job-offers-analyzer.git
cd IT-job-offers-analyzer
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## License

Apache License 2.0
