"""Seed vault with design patterns and concepts."""

import sys
sys.path.insert(0, ".")

from src.vault.writer import write_pattern, write_concept

# ── Design Patterns ──

write_pattern(
    name="Circuit Breaker",
    category="design-patterns",
    problem="Cascading failures when a downstream service is slow or dead.",
    solution="Wrap calls in a circuit breaker that opens after N failures, then half-opens to test recovery.",
    diagram=(
        "[Service A] --> [Circuit Breaker] --> [Service B]\n"
        "                     |\n"
        "              CLOSED -> OPEN -> HALF-OPEN\n"
        "              (N failures)  (timeout)  (test call)"
    ),
    components=[
        "Monitor (tracks failures)",
        "Breaker (open/closed/half-open state)",
        "Fallback (degraded response)",
        "Health check (test recovery)",
    ],
    trade_offs=[
        "Prevents cascading failures",
        "Fast failure instead of timeout",
        "Adds latency for state checks",
        "Needs careful threshold tuning",
    ],
    when_to_use="Any service-to-service call that can fail. Essential in microservices.",
    say_this="We should add a circuit breaker here so if that service goes down, we fail fast instead of cascading.",
    related=["Retry Pattern", "Bulkhead Pattern", "Fallback Pattern"],
    tags=["microservices", "resilience", "fault-tolerance"],
)

write_pattern(
    name="CQRS",
    category="design-patterns",
    problem="Read and write patterns have different performance needs.",
    solution="Separate the read model (queries) from the write model (commands). Each scales independently.",
    diagram=(
        "[Client]\n"
        "   |---> [Command Bus] --> [Write Model] --> [Event Store]\n"
        "   |                                              |\n"
        "   +---> [Query Bus]  --> [Read Model]  <---------+\n"
        "                          (denormalized)   (projections)"
    ),
    components=[
        "Command handler (validates + writes)",
        "Event store (append-only log)",
        "Projections (build read models from events)",
        "Query handler (reads denormalized views)",
    ],
    trade_offs=[
        "Independent scaling of reads vs writes",
        "Optimized read models (denormalized)",
        "Eventual consistency between models",
        "More complex than simple CRUD",
    ],
    when_to_use="When reads vastly outnumber writes, or read/write models need different shapes.",
    say_this="If our reads are 100x our writes, CQRS lets us optimize each side independently.",
    related=["Event Sourcing", "Domain-Driven Design", "Eventual Consistency"],
    tags=["architecture", "scaling", "event-driven"],
)

write_pattern(
    name="Saga Pattern",
    category="design-patterns",
    problem="Distributed transactions across multiple services — no single DB transaction possible.",
    solution="Break into a sequence of local transactions, each with a compensating action to undo on failure.",
    diagram=(
        "[Order Service] --> [Payment Service] --> [Inventory Service]\n"
        "       |                    |                     |\n"
        "    Create Order       Charge Card           Reserve Stock\n"
        "       |                    |                     |\n"
        "    (compensate:        (compensate:          (compensate:\n"
        "     cancel order)       refund card)          release stock)"
    ),
    components=[
        "Orchestrator (coordinates saga steps)",
        "Participants (execute local transactions)",
        "Compensating actions (rollback on failure)",
        "Saga log (tracks progress)",
    ],
    trade_offs=[
        "Works across service boundaries",
        "Each service stays autonomous",
        "Eventual consistency (not immediate)",
        "Compensating logic can be complex",
    ],
    when_to_use="Multi-service workflows like checkout, onboarding, or any business process spanning 3+ services.",
    say_this="We need a saga here — each service does its part, and if payment fails we compensate by releasing the inventory.",
    related=["CQRS", "Event Sourcing", "Two-Phase Commit"],
    tags=["microservices", "transactions", "distributed-systems"],
)

write_pattern(
    name="Event Sourcing",
    category="design-patterns",
    problem="Traditional CRUD overwrites state — you lose the history of how you got there.",
    solution="Store every state change as an immutable event. Current state is derived by replaying events.",
    diagram=(
        "[Command] --> [Event Store (append-only)]\n"
        "                    |\n"
        "               [Event 1] -> [Event 2] -> [Event 3]\n"
        "                    |\n"
        "               [Projection] --> [Current State View]"
    ),
    components=[
        "Event store (immutable append-only log)",
        "Aggregates (process commands, emit events)",
        "Projections (materialize current state)",
        "Snapshots (optimize replay for large histories)",
    ],
    trade_offs=[
        "Full audit trail",
        "Time-travel debugging",
        "Event store grows forever",
        "Schema evolution of events is hard",
    ],
    when_to_use="Financial systems, audit-heavy domains, or anywhere you need to answer 'how did we get here?'",
    say_this="With event sourcing we never lose data — we can replay events to debug or build new views retroactively.",
    related=["CQRS", "Saga Pattern", "Append-Only Log"],
    tags=["architecture", "event-driven", "audit"],
)

write_pattern(
    name="RAG Pipeline",
    category="design-patterns",
    problem="LLMs hallucinate and have stale knowledge — you need to ground responses in real data.",
    solution="Retrieve relevant documents first, then generate a response grounded in those documents.",
    diagram=(
        "[User Query]\n"
        "     |\n"
        "     v\n"
        "[Embeddings] --> [Vector DB] --> [Top-K Chunks]\n"
        "                                      |\n"
        "                                      v\n"
        "                              [LLM + Context] --> [Grounded Response]"
    ),
    components=[
        "Chunker (split docs into passages)",
        "Embedder (convert to vectors)",
        "Vector store (similarity search)",
        "Reranker (refine top-K)",
        "Generator (LLM with retrieved context)",
    ],
    trade_offs=[
        "Reduces hallucination",
        "Uses real-time data without retraining",
        "Retrieval quality limits generation",
        "Chunk size and overlap need tuning",
    ],
    when_to_use="Any LLM app that needs factual accuracy — chatbots, search, Q&A, document analysis.",
    say_this="We should use RAG here — retrieve the relevant docs first, then let the model generate from those.",
    related=["Vector Search", "Embeddings", "Semantic Search", "Reranking"],
    tags=["llm", "retrieval", "ai-infrastructure"],
)

write_pattern(
    name="Bulkhead Pattern",
    category="design-patterns",
    problem="One slow dependency consumes all resources — starves everything else.",
    solution="Isolate resources into pools. Each dependency gets its own limited pool so failures are contained.",
    diagram=(
        "[Requests]\n"
        "   |---> [Pool A: 20 threads] --> [Service A]\n"
        "   |---> [Pool B: 10 threads] --> [Service B]\n"
        "   +---> [Pool C: 5 threads]  --> [Service C]\n"
        "         (if C is slow, only Pool C fills up)"
    ),
    components=[
        "Thread/connection pools per dependency",
        "Queue with bounded size",
        "Rejection policy (fail fast when pool full)",
        "Monitoring per pool",
    ],
    trade_offs=[
        "Failure isolation",
        "Predictable resource usage",
        "More complex resource management",
        "Under-utilization if pools sized wrong",
    ],
    when_to_use="When you call multiple external services and one going slow must not kill the others.",
    say_this="Let us bulkhead these calls — if the payment API slows down, it should not starve our inventory checks.",
    related=["Circuit Breaker", "Rate Limiting", "Back Pressure"],
    tags=["microservices", "resilience", "resource-management"],
)

print(f"Patterns written: 6")

# ── Concepts ──

write_concept(
    name="Attention Mechanism",
    definition="A neural network technique that lets the model focus on relevant parts of the input when producing each output token.",
    category="llm-foundations",
    key_ideas=[
        "Query-Key-Value: each token queries all other tokens to compute relevance scores",
        "Self-attention: tokens attend to other tokens in the same sequence",
        "Multi-head: multiple attention heads capture different relationships in parallel",
        "O(n^2) complexity: scales quadratically with sequence length",
    ],
    how_it_works="Each token is projected into Q, K, V vectors. Attention score = softmax(QK^T / sqrt(d)). Output = weighted sum of V vectors.",
    say_this="The attention mechanism is what lets transformers handle long-range dependencies — each token can directly attend to any other token.",
    related=["Transformer Architecture", "Context Window", "Embeddings"],
    tags=["deep-learning", "nlp", "transformer"],
    difficulty="intermediate",
)

write_concept(
    name="Prompt Chaining",
    definition="Breaking a complex task into a sequence of simpler LLM calls where each step uses the output of the previous step.",
    category="agents",
    key_ideas=[
        "Decompose complex tasks into reliable subtasks",
        "Each step can have its own system prompt and validation",
        "Intermediate results can be inspected and debugged",
        "Can mix LLM calls with deterministic code (tool use, validation)",
    ],
    how_it_works="Step 1: Extract entities. Step 2: Classify each entity. Step 3: Generate summary using classified entities. Each step is a separate LLM call.",
    say_this="Instead of one massive prompt, let us chain smaller focused prompts — each step is testable and debuggable.",
    related=["Agent Loop", "Tool Use", "Chain-of-Thought"],
    tags=["llm", "agents", "prompt-engineering"],
    difficulty="intermediate",
)

write_concept(
    name="Retrieval-Augmented Generation",
    definition="A technique that enhances LLM responses by first retrieving relevant documents from a knowledge base, then using them as context.",
    category="rag-and-retrieval",
    key_ideas=[
        "Separates knowledge storage (vector DB) from reasoning (LLM)",
        "Reduces hallucination by grounding in real documents",
        "Allows updating knowledge without retraining",
        "Hybrid search (BM25 + vector) often beats pure vector search",
    ],
    how_it_works="Documents are chunked, embedded, stored in a vector DB. At query time, similar chunks are retrieved, optionally reranked, then passed to the LLM as context.",
    say_this="RAG lets us use the LLM for reasoning while keeping our data in a searchable knowledge base — no fine-tuning needed.",
    related=["Vector Search", "Embeddings", "Semantic Search"],
    tags=["llm", "retrieval", "knowledge-base"],
    difficulty="intermediate",
)

write_concept(
    name="Eventual Consistency",
    definition="A consistency model where all replicas converge to the same state given enough time, but reads may return stale data in the interim.",
    category="infra-and-serving",
    key_ideas=[
        "Trade-off: availability over immediate consistency (CAP theorem)",
        "Conflict resolution: last-write-wins, vector clocks, CRDTs",
        "Event-driven systems are naturally eventually consistent",
        "Read-your-own-writes consistency as a middle ground",
    ],
    how_it_works="After a write, the update propagates asynchronously to replicas. During propagation, some replicas serve old data. Eventually all converge.",
    say_this="We can accept eventual consistency here — the data will converge within seconds, and we avoid synchronous replication latency.",
    related=["CAP Theorem", "CQRS", "Event Sourcing"],
    tags=["distributed-systems", "consistency", "architecture"],
    difficulty="intermediate",
)

write_concept(
    name="Context Window Management",
    definition="Strategies for fitting the most relevant information into an LLM context window, which has a fixed token limit.",
    category="context-engineering",
    key_ideas=[
        "Token budget: system prompt + examples + retrieved context + user input must fit",
        "Prioritization: most relevant context first, least relevant truncated",
        "Summarization: compress older conversation turns to save tokens",
        "Sliding window: keep recent turns verbatim, summarize older ones",
    ],
    how_it_works="Calculate available tokens = max_context - system_prompt - output_reserve. Fill with recent conversation, retrieved context ranked by relevance, summarized history.",
    say_this="We need to be smarter about context window management — prioritize the most relevant chunks and summarize the rest.",
    related=["Prompt Chaining", "RAG Pipeline", "Token Counting"],
    tags=["llm", "optimization", "prompt-engineering"],
    difficulty="advanced",
)

write_concept(
    name="Model Evaluation",
    definition="Systematic measurement of LLM output quality using automated metrics, human judges, or LLM-as-judge to catch regressions.",
    category="evals-and-quality",
    key_ideas=[
        "Offline evals: test suite of inputs vs expected results",
        "Online evals: monitor production outputs for quality signals",
        "LLM-as-judge: use a stronger model to grade weaker model outputs",
        "Regression testing: new prompt/model must beat baseline on eval set",
    ],
    how_it_works="Build dataset of (input, expected_output) pairs. Run pipeline, score outputs. Track scores over time. Block deploys that regress.",
    say_this="Before we ship this prompt change, let us run it against our eval set to make sure we did not regress.",
    related=["A/B Testing", "Data Drift", "LLM-as-Judge"],
    tags=["quality", "testing", "llm"],
    difficulty="intermediate",
)

print(f"Concepts written: 6")

# Summary
import os
patterns_dir = os.path.expanduser("~/.lexicon/vault/patterns")
concepts_dir = os.path.expanduser("~/.lexicon/vault/concepts")
print(f"\nVault patterns: {len(os.listdir(patterns_dir))} files")
print(f"Vault concepts: {len(os.listdir(concepts_dir))} files")
