# RAG and Retrieval: designing the retriever (Huyen Ch. 6, RAG half)

## Produce
A **RAG design + retrieval-tuning plan**: the retrieval-algorithm choice (term-based / embedding-based / hybrid) with rejected alternatives, a chunking + reranking + query-rewriting + contextual-retrieval tactic set, the multimodal/tabular variant if needed, and a component-level + end-to-end evaluation plan (context precision/recall, embedding quality).

Fire this when someone is building RAG, choosing a retriever/vector DB, debugging retrieval quality, or weighing RAG vs. long context. (Agent/tool-use design → `agents.md`.)

## Trigger checks
- "How do I build / improve a RAG pipeline?" / "my retrieval returns junk"
- Term-based vs. embedding/semantic retrieval; BM25 vs. vector search; hybrid search
- Choosing a vector DB / ANN algorithm; chunking strategy; reranking; query rewriting
- "RAG vs. long context — do I still need RAG?"
- RAG over images/tables (multimodal / text-to-SQL); evaluating a retriever
- Interview: "Design a RAG system" / "How do you evaluate retrieval?"

## Frame: RAG is query-specific context construction
RAG = retrieve relevant info from external memory, then generate. It's the FM equivalent of *feature engineering* — giving the model the right info per query, including per-user data. **RAG vs. long context** (a recurring debate): long context won't kill RAG because (a) data grows faster than context windows, (b) models use long context poorly (lost-in-the-middle) and every token adds cost/latency. RAG sends only the most relevant tokens → often *better* and cheaper. (Anthropic guidance: under ~200k tokens / 500 pages, just stuff the prompt — no RAG needed.)

## How to apply

### 1. Architecture
Two components: **retriever** (indexing + querying) and **generator**. Off-the-shelf both works; end-to-end finetuning improves it. Split documents into **chunks** ("document" = chunk here). Quality of RAG ≈ quality of the retriever.

### 2. Choose the retrieval algorithm
Retrieval = rank documents by relevance to the query. Two mechanisms (Huyen uses term-based vs. embedding-based, not sparse vs. dense — because SPLADE is sparse-but-semantic):
- **Term-based (lexical / sparse)** — keyword match. **TF-IDF** (term frequency × inverse document frequency); **BM25** normalizes TF by doc length; **Elasticsearch** uses an inverted index. **Fast, cheap, strong out-of-the-box baseline, but hard to improve** and blind to meaning (query "transformer" returns the movie). Needs tokenization (n-grams keep "hot dog" together; lowercase, stopword removal).
- **Embedding-based (semantic / dense)** — embed query + chunks, find nearest by **cosine similarity**, store in a **vector database**. **Can outperform term-based after finetuning** and handles natural queries — but slower, costlier (embedding generation + vector search + storage; vector-DB spend can be ⅕–½ of model-API spend), and **obscures exact keywords** (error codes, product names). Vector search = nearest-neighbor: naive **k-NN** (precise, slow, small data) vs. **ANN** for scale.
- **ANN algorithms** (you'll evaluate, not implement): **LSH** (hash similar vectors to buckets), **HNSW** (multi-layer graph — high accuracy/fast query, slow/heavy build), **Product Quantization** (compress vectors), **IVF** (k-means clusters), **Annoy** (random binary trees). Libraries: FAISS, ScaNN, Annoy, Hnswlib. Evaluate via ANN-Benchmarks on recall, QPS, build time, index size (indexing↔querying tradeoff: detailed index like HNSW = accurate but heavy; LSH = light but less accurate).

### 3. Combine for production: hybrid search
- **Sequential / reranking** — cheap retriever (term-based) fetches candidates, then an expensive precise step (k-NN / cross-encoder) reranks. (Fetch all docs containing "X", then vector-search within them.)
- **Parallel / ensemble** — multiple retrievers rank, then fuse with **Reciprocal Rank Fusion (RRF)**: score = Σ 1/(k + rank), k≈60.

### 4. Retrieval optimization tactics
- **Chunking** — equal-length (chars/words/sentences/paragraphs), recursive (section→paragraph→sentence), or content-aware (per-language, Q&A pairs, code splitters); token-based chunks ease downstream but force reindex on tokenizer change. Use **overlap** so boundary info survives ("I left my wife | a note"). Chunk size matters: smaller = more diverse chunks fit but risk losing info + more compute/embeddings; **no universal best — experiment**. Never exceed the generator's (or embedding model's) context limit.
- **Reranking** — improve initial ranking; reduce to fit context; can weight by recency (news, email, markets). In RAG, exact position matters less than in search, but beginning/end placement still helps (lost-in-the-middle).
- **Query rewriting** (reformulation/expansion) — make ambiguous follow-ups self-contained ("How about Emily Doe?" → "When did Emily Doe last buy from us?"); may need identity resolution (acknowledge unsolvable rather than hallucinate a name). Often done by another model.
- **Contextual retrieval** — augment each chunk to make it findable: metadata/tags/keywords (preserve error codes after embedding), the questions a chunk answers (support articles), or an AI-generated 50–100 token context situating the chunk in its parent doc (Anthropic's contextual retrieval), prepended before indexing.

### 5. RAG beyond text
- **Multimodal RAG** — retrieve images/audio/video too; by metadata (captions) or by content via a **multimodal embedding model** (CLIP) into a joint space.
- **Tabular RAG** — different workflow: **text-to-SQL** (generate query from question + schema; predict relevant tables first if schemas don't fit) → **SQL execution** → **generation** from results.

### 6. Evaluate the retriever (component + end-to-end)
- **Context precision** (of retrieved docs, % relevant — cheap, AI-judgeable) and **context recall** (of relevant docs, % retrieved — needs full-corpus annotation, often unsupported in prod).
- Ranking-aware: **NDCG, MAP, MRR**.
- **Embedding quality** (semantic): MTEB benchmark; good if similar docs have closer embeddings.
- **End-to-end**: the retriever is only good if the *final answer* is good. Evaluate (1) retrieval, (2) RAG output, (3) embeddings. Retrieval harness: BEIR.

## Common failure modes
- **Semantic-by-default.** Reaching for embeddings + a vector DB when BM25 is faster, cheaper, and a strong baseline — especially for keyword/code/ID-heavy corpora.
- **Embedding-buries-keywords.** Losing exact error codes / product names after embedding; fix with hybrid search or metadata augmentation.
- **Chunk size set blindly.** Not experimenting; over-small chunks drop cross-chunk info, over-large waste context and dilute relevance; no overlap → severed context.
- **No query rewriting in multi-turn.** Retrieving on a bare follow-up ("How about her?") → irrelevant docs.
- **Only end-to-end eval.** Can't tell if a bad answer is bad retrieval or bad generation; evaluate retrieval separately.
- **Long-context-kills-RAG fallacy.** Stuffing everything into a huge context, then paying for tokens and lost-in-the-middle errors.
- **Stale embeddings ignored.** Frequently-changing data needs re-embedding; cost/latency of regeneration unplanned.

## Interview signal
**AI-Engineer / FDE framing:** Senior signal = defaulting to **hybrid search** (BM25 baseline + embeddings + RRF/reranking) rather than "use a vector DB," articulating the RAG-vs-long-context tradeoff with the lost-in-the-middle and cost reasons, and evaluating retrieval *separately* (context precision/recall) from generation. Knowing chunking + contextual retrieval reads as having shipped RAG, not just read about it.
**One crisp talking point:** *"I start RAG with BM25 as a baseline, then add embedding retrieval and fuse with reranking — hybrid search beats either alone, and BM25 keeps exact keywords like error codes that embeddings blur. Long context doesn't kill RAG: models use long context poorly and every token costs, so sending only the most relevant chunks is both cheaper and more accurate. And I evaluate the retriever on context precision/recall on its own — if the final answer is wrong I need to know whether it's retrieval or generation."*

## Practitioner checklist
- [ ] RAG-vs-long-context decided for this data size + change rate
- [ ] Retrieval algorithm chosen (term / embedding / hybrid) with rationale; BM25 baseline considered
- [ ] If embedding-based: embedding model + ANN algo + vector DB chosen against recall/QPS/build-time/cost
- [ ] Chunking strategy + size + overlap chosen by experiment; within generator/embedding context limits
- [ ] Reranking and/or RRF fusion in place; query rewriting for multi-turn; contextual augmentation where chunks lose context
- [ ] Multimodal/tabular variant designed if needed (CLIP / text-to-SQL)
- [ ] Retriever evaluated separately (context precision/recall, NDCG/MAP/MRR) AND end-to-end; embeddings on MTEB
- [ ] Embedding-regeneration cost/latency planned for changing data

## References
- *AI Engineering* (Huyen, O'Reilly 2024), Ch. 6 (pp. 494–593), RAG sections: RAG Architecture, Retrieval Algorithms, Retrieval Optimization, RAG Beyond Texts.
- Sibling docs: **`agents.md`** (RAG = a special case of an agent where the retriever is a tool; memory system shared — read together), `foundation-models.md` / `evaluation-methodology.md` (embeddings + cosine similarity defined), `evaluating-ai-systems.md` (factual consistency = key RAG metric), `prompt-engineering.md` (context construction; indirect injection via retrieved content).
- Related skills: `claude-api` (Anthropic RAG-vs-context guidance, contextual retrieval), `kleppmann-data-intensive-systems` (the underlying search/index/storage internals).
