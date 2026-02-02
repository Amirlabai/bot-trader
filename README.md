# Bot Trader

A Python-based automated trading bot that runs daily on GitHub Actions. It fetches data for crypto and forex, executes strategies, and maintains a persistent ledger using this Git repository as a database.

## Setup Instructions

### 1. Repository Setup
1.  Ensure this repository is **Private**.
2.  Clone the repository locally:
    ```bash
    git clone https://github.com/yourusername/bot-trader.git
    cd bot-trader
    ```

### 2. Environment Variables & Secrets
To run this bot, you need to configure Secrets in your GitHub repository settings (`Settings` -> `Secrets and variables` -> `Actions`).

**Required Secrets:**

| Secret Name | Description |
|Data Provider Keys| |
| `CCXT_API_KEY` | API Key for your Crypto Exchange (if execution enabled) |
| `CCXT_SECRET` | Secret Key for your Crypto Exchange (if execution enabled) |
| `ALPHAVANTAGE_KEY` | API Key for Alpha Vantage (Forex Data) |

**Note**: For local development, create a `.env` file in the root directory with the same keys:
```
ALPHAVANTAGE_KEY=your_key_here
```

### 3. Usage
**Install Dependencies:**
It is recommended to use a virtual environment:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

**Run Manually:**
```bash
python src/main.py
```

## Project Structure
- `data/`: Contains the `ledger.json` (your portfolio state).
- `strategies/`: Contains trading strategy logic.
- `src/`: Core application code (Dynamic Config, Data Ingestion, Ledger Manager, Execution).
- `.github/workflows/`: Contains the GitHub Actions workflow for daily automation.
