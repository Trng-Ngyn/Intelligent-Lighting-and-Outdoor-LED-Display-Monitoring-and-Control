
import os
import json
import joblib

BASE = os.path.dirname(os.path.dirname(__file__))
MODEL_DIR = os.path.join(BASE, "models")


class ModelBundle:
    def __init__(self):
        self.isolation_forest = None
        self.autoencoder = None
        self.preprocessor = None
        self.threshold = None
        self.status = {}

    def load(self):
        if_path = os.path.join(MODEL_DIR, "isolation_forest.joblib")
        prep_path = os.path.join(MODEL_DIR, "autoencoder_preprocessing.joblib")
        ae_path = os.path.join(MODEL_DIR, "autoencoder.keras")
        threshold_path = os.path.join(MODEL_DIR, "autoencoder_threshold.json")

        try:
            self.isolation_forest = joblib.load(if_path)
            self.status["isolation_forest"] = "loaded"
        except Exception as exc:
            self.status["isolation_forest"] = f"load_error: {exc}"

        try:
            self.preprocessor = joblib.load(prep_path)
            self.status["preprocessor"] = "loaded"
        except Exception as exc:
            self.status["preprocessor"] = f"load_error: {exc}"

        try:
            from tensorflow import keras
            self.autoencoder = keras.models.load_model(ae_path, compile=False)
            self.status["autoencoder"] = "loaded"
        except Exception as exc:
            self.status["autoencoder"] = f"load_error: {exc}"

        try:
            with open(threshold_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.threshold = float(data["autoencoder_threshold"])
            self.status["threshold"] = "loaded"
        except Exception as exc:
            self.status["threshold"] = f"load_error: {exc}"

        return self
