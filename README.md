---
title: Porsche Repair Reader
emoji: 🏎️
colorFrom: red
colorTo: black
sdk: docker
pinned: false
---

# 🏎️ Porsche Repair Instruction Reader API

This is the high-performance, automated Python FastAPI backend for the Porsche Repair Instruction Reader application. It processes PDF manuals, translates them into professional-grade Georgian, and stores manuals in Supabase.

### Architecture
- **Framework:** FastAPI
- **SDK:** Docker (Listening natively on port `7860`)
- **AI Processing:** Gemini 2.5 Flash with structured output schema and key rotation
- **Database & Storage:** Supabase REST API & Storage Buckets
