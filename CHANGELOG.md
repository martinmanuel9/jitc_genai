# Changelog

All notable changes to GenAI Research will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2025-12-04

### Added
- Initial release of Verification GenAI
- Multi-agent test plan generation system
- RAG-enhanced document analysis
- Test card generation with Word export
- Support for OpenAI GPT models (GPT-4, GPT-4o, GPT-3.5-Turbo, o1, o3-mini)
- Support for local Ollama models (Meta Llama, Microsoft Phi)
- US-based model compliance (Meta, Microsoft, Snowflake)
- Auto-GPU detection for Ollama model selection
- PostgreSQL database for session tracking
- ChromaDB vector store for RAG
- Redis caching and Celery background processing
- Streamlit web interface
- FastAPI REST API backend
- Docker Compose orchestration
- Automated Ollama model pulling script with GPU detection
- Updated installation to automatically install the software
- Fix on managing Agents and Agent Sets
- Installer allows for env input
- Fix the poetry toml and lock files
- Fix to include citations within the direct chat
- Fix persistent models within docker-compose.yml so that the models folder is found within start of install
- Fix created an automatic agent build - aligning with the different types of requests needed for agents


### Features
- **Test Plan Generation**: Multi-agent Actor-Critic system for extracting requirements
- **Test Card Creation**: Generate detailed test procedures with Word export
- **RAG Analysis**: Document-grounded analysis with citation tracking
- **AI Simulation**: Multi-agent debate for comprehensive analysis
- **Chat Interface**: Interactive LLM chat with model selection
- **Document Upload**: Support for PDF, DOCX, TXT formats
- **Model Selection**: Easy switching between cloud and local models
- **On-Premises Support**: Run completely offline with Ollama models

### Infrastructure
- Dockerized microservices architecture
- PostgreSQL 17 for data persistence
- ChromaDB 0.5.23 for vector storage
- Redis 7 for caching
- Celery for async task processing
- Native Ollama integration for local models

### Security & Compliance
- US-based LLM providers only (OpenAI, Meta, Microsoft, Snowflake)
- On-premises deployment option
- No data leaves infrastructure when using local models
- API key management via environment variables

### Documentation
- Complete installation guide
- Ollama model selection guide with GPU detection
- API documentation
- User guide for test plan generation

