const LLM_PROVIDERS = {
    'zai': {
        url: 'https://api.z.ai/api/paas/v4',
        models: ['glm-4.7', 'glm-5', 'glm-4.6', 'glm-4.5', 'glm-ocr']
    },
    'openai': {
        url: 'https://api.openai.com/v1',
        models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo']
    },
    'groq': {
        url: 'https://api.groq.com/openai/v1',
        models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768']
    },
    'xai': {
        url: 'https://api.x.ai/v1',
        models: ['grok-2-latest', 'grok-2-vision-latest']
    },
    'deepseek': {
        url: 'https://api.deepseek.com/v1',
        models: ['deepseek-chat', 'deepseek-reasoner']
    }
};

function updateLlmProvider() {
    const provider = document.getElementById('llm-provider-select').value;
    const urlInput = document.getElementById('set-LLM_API_BASE_URL');
    const urlContainer = document.getElementById('llm-base-url-container');
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('set-LLM_MODEL_NAME');

    if (provider === 'custom') {
        urlContainer.style.display = 'block';
        modelSelect.style.display = 'none';
        modelInput.style.display = 'block';
    } else {
        urlContainer.style.display = 'none';
        urlInput.value = LLM_PROVIDERS[provider].url;
        
        // Populate models
        modelSelect.innerHTML = LLM_PROVIDERS[provider].models.map(m => `<option value="${m}">${m}</option>`).join('');
        modelSelect.innerHTML += '<option value="custom">Other / Custom</option>';
        modelSelect.style.display = 'block';
        
        // Hide/show custom text input based on selection
        updateLlmModel();
    }
}

function updateLlmModel() {
    const modelSelect = document.getElementById('llm-model-select');
    const modelInput = document.getElementById('set-LLM_MODEL_NAME');
    
    if (modelSelect.value === 'custom') {
        modelInput.style.display = 'block';
        modelInput.value = '';
    } else {
        modelInput.style.display = 'none';
        modelInput.value = modelSelect.value;
    }
}

function initializeLlmUi(savedUrl, savedModel) {
    let matchedProvider = 'custom';
    
    // Find provider by URL
    if (savedUrl) {
        for (const [key, data] of Object.entries(LLM_PROVIDERS)) {
            if (savedUrl === data.url || savedUrl === data.url + '/') {
                matchedProvider = key;
                break;
            }
        }
    }
    
    document.getElementById('llm-provider-select').value = matchedProvider;
    updateLlmProvider();
    
    if (matchedProvider !== 'custom' && savedModel) {
        const modelSelect = document.getElementById('llm-model-select');
        const options = Array.from(modelSelect.options).map(o => o.value);
        if (options.includes(savedModel)) {
            modelSelect.value = savedModel;
            updateLlmModel();
        } else {
            modelSelect.value = 'custom';
            updateLlmModel();
            document.getElementById('set-LLM_MODEL_NAME').value = savedModel;
        }
    } else if (savedModel) {
        document.getElementById('set-LLM_MODEL_NAME').value = savedModel;
    }
}