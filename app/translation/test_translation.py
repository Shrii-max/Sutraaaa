
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from IndicTransToolkit.processor import IndicProcessor

MODEL_PATH = "./models/indic-en"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("=" * 50)
print("INDICTRANS2 TRANSLATION ENGINE")
print("=" * 50)

print("Device:", DEVICE)
print("Loading model...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True
)

model = AutoModelForSeq2SeqLM.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True
).to(DEVICE)

model.eval()

processor = IndicProcessor(inference=True)

print("\nModel loaded successfully!")

source_language = "hin_Deva"
target_language = "eng_Latn"

input_sentences = [
    "भारत एक विविधताओं वाला देश है।",
    "न्यायालय ने मामले की अगली सुनवाई की तारीख निर्धारित की।",
    "शिक्षा प्रत्येक व्यक्ति का मौलिक अधिकार है।"
]

print("\nTranslating sentences...\n")

processed_text = processor.preprocess_batch(
    input_sentences,
    src_lang=source_language,
    tgt_lang=target_language
)

inputs = tokenizer(
    processed_text,
    truncation=True,
    padding="longest",
    return_tensors="pt",
    return_attention_mask=True
).to(DEVICE)

with torch.inference_mode():
    generated_tokens = model.generate(
        **inputs,
        use_cache=False,
        min_length=0,
        max_length=256,
        num_beams=5,
        num_return_sequences=1
    )

decoded = tokenizer.batch_decode(
    generated_tokens,
    skip_special_tokens=True,
    clean_up_tokenization_spaces=True
)

translations = processor.postprocess_batch(
    decoded,
    lang=target_language
)

for original, translated in zip(input_sentences, translations):
    print("Original Hindi:")
    print(original)

    print("\nTranslated English:")
    print(translated)

    print("\n" + "-" * 50)

print("\nTranslation completed successfully!")
