import pickle
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

def predict_label(sentence):
    prediction = model.predict([sentence])[0]
    return prediction