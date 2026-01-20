# Shared state for models and resources

# these will be initialized by load_models.py
model = None
processor = None
tts_pipeline = None
local_model_available = False

# Runtime LLM provider (can be changed via API)
# Will be initialized from config.LLM_PROVIDER on startup
llm_provider = "openrouter"

