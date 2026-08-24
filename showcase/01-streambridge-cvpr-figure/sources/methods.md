# StreamBridge++ Methods

Our model, StreamBridge++, processes streaming videos using four stages:

1. Video Encoder extracts frame-level visual tokens.
2. Memory Compressor adaptively merges redundant visual tokens while preserving key events.
3. Cross-modal Memory retrieves historical context for the LLM.
4. The LLM generates responses using compressed visual memory and user instructions.

Unlike previous methods, memory compression is event-aware rather than uniform sampling.
