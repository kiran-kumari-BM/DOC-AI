# DOC AI

## Intelligent Document Understanding System

DOC AI is an AI-powered document processing platform that converts
handwritten and digital documents into editable digital text and
allows users to interact with their documents using AI.

---

## Features

- User authentication
- Secure document upload
- Handwritten document OCR
- PaddleOCR integration
- TrOCR handwritten text recognition
- Original document preview
- Editable OCR results
- Document-based AI question answering
- RAG-based document interaction
- Chat history
- PDF export
- Word export
- Bulk document download
- Document deletion
- Admin dashboard
- Responsive modern UI

---

## Architecture

```text
                ┌────────────────────┐
                │      DOC AI        │
                │    Web Interface   │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │   Flask Backend    │
                └─────────┬──────────┘
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
      ┌──────────────┐         ┌──────────────┐
      │  PaddleOCR   │         │    TrOCR     │
      │ OCR Pipeline │         │ Handwriting  │
      └──────┬───────┘         └──────┬───────┘
             │                        │
             └───────────┬────────────┘
                         ▼
                ┌────────────────────┐
                │ Extracted Document │
                │       Text         │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │    RAG Engine      │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │    Ask DOC AI      │
                └────────────────────┘