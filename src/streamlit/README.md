

# Streamlit Application - Migration-Ready Architecture

This is the **refactored Streamlit application** with a migration-ready architecture that mirrors React/Next.js patterns. This structure makes transitioning to React/Next.js **80% easier** because the business logic, API layer, and patterns are identical.

## 📁 Directory Structure

```
src/streamlit/
├── config/                     # Configuration layer (→ config/ in React)
│   ├── settings.py             # App configuration (→ settings.ts)
│   ├── env.py                  # Environment variables (→ env.ts)
│   └── constants.py            # Constants (→ constants.ts)
│
├── lib/                        # Libraries & utilities (→ lib/ in React)
│   ├── api/
│   │   └── client.py           # HTTP client (→ client.ts with Axios)
│   └── utils/
│       ├── formatters.py       # Text formatting (→ formatters.ts)
│       ├── validators.py       # Validation helpers (→ validators.ts)
│       └── export.py           # Export utilities (→ export.ts)
│
├── services/                   # Business logic layer (→ services/ in React)
│   ├── chromadb_service.py     # ChromaDB operations (→ chromadb-service.ts)
│   ├── chat_service.py         # Chat operations (→ chat-service.ts)
│   └── document_service.py     # Document operations (→ document-service.ts)
│
├── hooks/                      # State management (→ hooks/ in React)
│   ├── use_collections.py      # Collections hook (→ useCollections.ts)
│   ├── use_chat.py             # Chat hook (→ useChat.ts)
│   └── use_documents.py        # Documents hook (→ useDocuments.ts)
│
├── models/                     # Data models (→ types/ in React)
│   └── models.py               # Pydantic models (→ Zod schemas + TypeScript types)
│
├── components/                 # UI Components (→ components/ in React)
│   ├── ui/                     # Base UI components (→ shadcn/ui in React)
│   │   ├── Button.py
│   │   ├── Card.py
│   │   └── ...
│   │
│   └── features/               # Feature components
│       ├── chat/
│       │   └── DirectChat.py   # Refactored chat (→ DirectChat.tsx)
│       ├── agents/
│       ├── documents/
│       └── legal/
│
├── app/                        # Application pages (→ app/ in Next.js)
│   ├── layout.py               # Root layout (→ layout.tsx)
│   ├── Home.py                 # Home page (→ page.tsx)
│   └── pages/                  # Additional pages
│       └── Files.py            # (→ files/page.tsx)
│
└── store/                      # State management helpers
    ├── session_state.py        # Session state utilities
    └── cache.py                # Caching utilities
```

## 🚀 Quick Start

### Using the New Structure

```python
# Old way (scattered, duplicated)
import os
import requests
FASTAPI = os.getenv("FASTAPI_URL", "http://localhost:9020")
response = requests.post(f"{FASTAPI}/api/chat", json=data)

# New way (clean, centralized)
from config.settings import config
from lib.api.client import api_client

response = api_client.post(config.endpoints.chat, data=data)
```

### Using Hooks for State Management

```python
# Old way
if 'collections' not in st.session_state:
    st.session_state.collections = []

# New way (React-like)
from hooks.use_collections import use_collections

collections = use_collections()
collections.fetch()  # Load collections
st.selectbox("Collection", collections.data)
```

### Using Services for Business Logic

```python
# Old way (mixed concerns)
import requests
response = requests.get(f"{CHROMADB_API}/collections")
collections = response.json().get('collections', [])

# New way (clean separation)
from services.chromadb_service import chromadb_service

collections = chromadb_service.get_collections()
```

## 📚 Documentation

- **[MIGRATION_MAPPING.md](../../MIGRATION_MAPPING.md)** - Complete FROM/TO migration guide
- **[REACT_REFACTORING_GUIDE.md](../../REACT_REFACTORING_GUIDE.md)** - React/Next.js conversion patterns

## 🎯 Key Benefits

### Before (Old Structure)
❌ API endpoints defined in 8+ files
❌ Manual `requests.post/get` everywhere
❌ Scattered state management
❌ No type safety
❌ Mixed concerns in components
❌ Hard to test
❌ Difficult to migrate to React

### After (New Structure)
✅ Single source of truth for config
✅ Centralized API client
✅ Hook-based state management
✅ Type-safe with Pydantic
✅ Separated concerns
✅ Easy to test and mock
✅ Direct 1:1 React mapping

## 📖 Usage Examples

### Example 1: Configuration

```python
from config.settings import config

# Access endpoints
api_url = config.endpoints.chat
health_url = config.endpoints.health

# Access model configuration
gpt4 = config.get_model_by_key("GPT-4")
print(gpt4.description)  # "Most capable GPT-4 model..."

# Get model ID
model_id = config.get_model_id("GPT-4")  # Returns "gpt-4"
```

### Example 2: API Client

```python
from lib.api.client import api_client
from config.settings import config

# GET request
collections = api_client.get(f"{config.endpoints.vectordb}/collections")

# POST request
response = api_client.post(
    config.endpoints.chat,
    data={"query": "Hello", "model": "gpt-4"}
)

# File upload
job = api_client.upload(
    f"{config.endpoints.vectordb}/documents/upload",
    files=files_data,
    params={"collection_name": "docs"}
)
```

### Example 3: Services

```python
from services.chromadb_service import chromadb_service
from services.chat_service import chat_service

# ChromaDB operations
collections = chromadb_service.get_collections()
documents = chromadb_service.get_documents("my_collection")

# Chat operations
response = chat_service.send_message(
    query="Explain this contract",
    model="gpt-4",
    use_rag=True,
    collection_name="contracts"
)
print(response.response)  # ChatResponse object with type safety
```

### Example 4: Hooks

```python
from hooks.use_collections import use_collections
from hooks.use_chat import use_chat

def MyComponent():
    # Initialize hooks
    collections = use_collections()
    chat = use_chat()

    # Fetch data
    if not collections.data:
        collections.fetch()

    # UI
    selected = st.selectbox("Collection", collections.data)
    if selected:
        collections.select(selected)

    # Send chat
    if st.button("Send"):
        response = chat.send("Hello", "gpt-4")
        st.write(response.response)
```

### Example 5: Complete Component (DirectChat)

See [components/features/chat/DirectChat.py](components/features/chat/DirectChat.py) for a complete refactored component example.

```python
from components.features.chat.DirectChat import DirectChat, DirectChatProps

# Use with default props
DirectChat()

# Use with custom props
DirectChat(DirectChatProps(show_history=False, show_help=True))
```

## 🔄 Migration Path

### Phase 1: Streamlit Refactoring (Current)
1. ✅ Create new structure
2. ✅ Implement config layer
3. ✅ Implement API client
4. ✅ Implement services
5. ✅ Implement hooks
6. ✅ Refactor DirectChat (proof of concept)
7. 🔄 Refactor remaining components
8. 🔄 Update app entry points

### Phase 2: React/Next.js Migration (Future)
1. Set up Next.js project with same structure
2. Port configuration files (nearly copy-paste)
3. Port services (update syntax, keep logic)
4. Port types (Pydantic → Zod)
5. Port components (Streamlit → React)
6. Implement routing
7. Add state management (Zustand/React Query)

## 🧪 Testing

### Testing Services

```python
# services are easy to test in isolation
from services.chromadb_service import ChromaDBService
from unittest.mock import Mock

def test_get_collections():
    service = ChromaDBService()
    service.client = Mock()
    service.client.get.return_value = {"collections": ["test"]}

    result = service.get_collections()
    assert result == ["test"]
```

### Testing Hooks

```python
# hooks can be tested with streamlit testing utilities
import streamlit as st
from hooks.use_collections import use_collections

def test_use_collections():
    # Initialize
    collections = use_collections()

    # Test properties
    assert isinstance(collections.data, list)
    assert collections.loading == False
```

## 🛠️ Adding New Features

### Adding a New Service

```python
# 1. Create service file
# services/my_new_service.py
from lib.api.client import api_client
from config.settings import config

class MyNewService:
    def __init__(self):
        self.client = api_client

    def do_something(self, param: str):
        return self.client.post(
            f"{config.endpoints.api}/new-endpoint",
            data={"param": param}
        )

my_new_service = MyNewService()

# 2. Add to services/__init__.py
from .my_new_service import MyNewService, my_new_service

# 3. Use in components
from services.my_new_service import my_new_service
result = my_new_service.do_something("value")
```

### Adding a New Hook

```python
# 1. Create hook file
# hooks/use_my_feature.py
import streamlit as st

class UseMyFeature:
    def __init__(self):
        self._initialize_state()

    def _initialize_state(self):
        if 'my_feature_data' not in st.session_state:
            st.session_state.my_feature_data = []

    @property
    def data(self):
        return st.session_state.my_feature_data

    def fetch(self):
        # Fetch logic here
        pass

def use_my_feature():
    return UseMyFeature()

# 2. Use in components
from hooks.use_my_feature import use_my_feature

feature = use_my_feature()
feature.fetch()
```

## 📦 Dependencies

Current Streamlit dependencies remain the same:
```
streamlit
requests
pydantic
sentence-transformers
```

Future React/Next.js dependencies will be:
```
next
react
react-dom
axios
zustand
@tanstack/react-query
zod
tailwindcss
```

## 🔐 Environment Variables

Create a `.env` file in the project root:

```bash
# API Configuration
FASTAPI_URL=http://localhost:9020

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Application Settings
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# Feature Flags
ENABLE_LEGAL_RESEARCH=true
ENABLE_RAG=true
ENABLE_VISION_MODELS=true

# Performance
REQUEST_TIMEOUT=300
MAX_UPLOAD_SIZE_MB=100
CACHE_TTL_SECONDS=300
```

## 🎓 Learning Resources

- **Old Structure**: See `components/direct_chat.py` (old way)
- **New Structure**: See `components/features/chat/DirectChat.py` (new way)
- **React Patterns**: See `REACT_REFACTORING_GUIDE.md`
- **Migration Guide**: See `MIGRATION_MAPPING.md`

## 🤝 Contributing

When adding new components:

1. **Use the new structure** - No more scattered API calls
2. **Use hooks** - For state management
3. **Use services** - For business logic
4. **Use config** - For all configuration
5. **Add types** - Use Pydantic models
6. **Follow React patterns** - Makes migration easier

## 📞 Support

For questions about:
- **New structure**: See this README
- **Migration**: See `MIGRATION_MAPPING.md`
- **React conversion**: See `REACT_REFACTORING_GUIDE.md`

---

**Status**: ✅ Core infrastructure complete | 🔄 Component refactoring in progress

**Next Steps**:
1. Refactor remaining components to use new structure
2. Create UI component library
3. Add comprehensive tests
4. Prepare for React/Next.js migration
