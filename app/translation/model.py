import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit.processor import IndicProcessor

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

MODEL_PATHS = {
    "indic-en": "./models/indic-en",
    "en-indic": "./models/en-indic",
    "indic-indic": "./models/indic-indic"
}

class ModelManager:

    def __init__(self):
        self.models = {}

    def load_model(self, model_type):

        if model_type in self.models:
            return self.models[model_type]

        path = MODEL_PATHS[model_type]

        print(f"Loading {model_type} model...")

        tokenizer = AutoTokenizer.from_pretrained(
            path,
            trust_remote_code=True
        )

        model = AutoModelForSeq2SeqLM.from_pretrained(
            path,
            trust_remote_code=True
        ).to(DEVICE)

        model.eval()

        processor = IndicProcessor(inference=True)

        self.models[model_type] = {
            "tokenizer": tokenizer,
            "model": model,
            "processor": processor
        }

        print(f"{model_type} loaded successfully!")

        return self.models[model_type]


manager = ModelManager()
