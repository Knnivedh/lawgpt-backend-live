# Family Law Assistant

## How to Run

### Prerequisites

**Install Docker** → [https://docs.docker.com/get-docker/](https://docs.docker.com/get-docker/)

---

### 1. Start Milvus (Vector Database)

In your terminal, run:

```bash
curl -sfL https://raw.githubusercontent.com/milvus-io/milvus/master/scripts/standalone_embed.sh -o standalone_embed.sh
bash standalone_embed.sh start
```

---

### 2. Clone the Repository

Open VS Code and in the terminal:

```bash
git clone https://github.com/madhans476/family-law-assistant.git
cd family-law-assistant
```

---

### 3. Set Up the Environment

Install dependencies using `uv`:

```bash
uv sync
```

> If `uv` is not found, install it first:
> ```bash
> pip install uv
> ```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows
source .venv\bin\activate
```

Configure Environment Variables:
Create a .env file in the root directory using the provided template:

```bash
cp env.template .env
```

---

### 4. Process & Store Data

Run the following scripts in order:

```bash
uv run python chunking.py
uv run python embedding.py
uv run python milvus_store.py
```

---

### 5. Start the Backend

```bash
cd family-law-assistant
source .venv/bin/activate
uvicorn main:app --reload
```

---

### 6. Start the Frontend

In a new terminal:

```bash
cd family-law-assistant/frontend
npm run dev
```

<img alt="workflow" src="image.png" />
