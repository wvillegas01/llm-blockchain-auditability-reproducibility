# Public Dataset Access

This reproducibility package does not redistribute original third-party conversational datasets. The raw sources remain subject to their original distribution terms and licenses.

## LMSYS-Chat-1M

- Source: https://huggingface.co/datasets/lmsys/lmsys-chat-1m
- Role in the study: public LLM conversation source transformed into canonical prompt-response auditable units.

## WildChat

- Source: https://huggingface.co/datasets/allenai/WildChat
- Role in the study: public LLM conversation source transformed into canonical prompt-response auditable units.

## Chatbot Arena Conversations

- Source: https://huggingface.co/datasets/lmsys/chatbot_arena_conversations
- Role in the study: public pairwise-comparison source transformed into normalized comparison audit records.

## Reproducibility Scope

The included scripts and derived tables support numerical consistency checking of the results reported in the manuscript from the processed audit outputs generated during the project audit. Because the original public datasets are large and externally licensed, this package provides source links, access instructions, derived non-raw result tables, storage audit summaries, downstream traceability scripts, and verification scripts rather than redistributing the raw conversational records. The implementation of the canonical dataset-normalization stage is not included in the public package because it forms part of the potentially commercializable software architecture. The package should therefore be interpreted as a supplementary numerical-audit archive for the reported metrics, not as a redistribution of the underlying third-party datasets or as a complete end-to-end release of the full processing pipeline.
