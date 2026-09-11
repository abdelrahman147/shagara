# SHAGARA AI Architecture

```mermaid
flowchart TB
  subgraph OFFLINE[Offline ingestion and indexing]
    A[PDF / TXT / Markdown upload] --> B[Validate + SHA-256 checksum]
    B --> C[Parser / PDF text extraction]
    C --> D[Clean + preserve page and section]
    D --> E[Section-aware chunker\n480 chars + 60 overlap]
    E --> F[Deterministic embeddings\noptional SentenceTransformer swap]
    F --> G[(Persisted vector index\nbackend/data/vector_store/index.json)]
  end

  subgraph ONLINE[Online AI question flow]
    U[User question] --> Q[FastAPI /query]
    Q --> R[Query classifier\ndocument / analytics / chat]
    R -->|document| S[Tenant + access filter]
    S --> T[Lexical retrieval\nvector-ready index]
    T --> V[Prompt builder\nquestion + top passages]
    V --> W{Ollama enabled?}
    W -->|yes| X[Ollama local LLM\nllama3.2:3b]
    W -->|no| Y[Deterministic grounded answer]
    X --> Z[Groundedness + injection guard]
    Y --> Z
    Z --> CITE[Citations + confidence + abstention]
    CITE --> UI[React / Three.js or Streamlit UI]
    R -->|analytics| SQL[Future SQL route]
    R -->|chat| CHAT[Short greeting response]
  end

  G -. loaded at startup .-> T
```

## What counts as AI

1. The notebook creates embeddings for each chunk and persists them with metadata.
2. FastAPI loads the persisted index once at startup.
3. Retrieval selects the relevant garden passages after tenant and access filtering.
4. The prompt builder gives only those passages to the generator.
5. With `use_ollama=true`, Ollama runs the local `llama3.2:3b` model.
6. Without Ollama, the deterministic grounded fallback keeps the demo runnable offline.
7. The response includes evidence, confidence, abstention, and safety flags.

The fallback is deliberate: it makes the product demonstrable even when Ollama is not installed, while the real local LLM path is available for the submitted AI demo.


