import json
import os
import logging

class RunState:
    def __init__(self, state_file="servus_state.json"):
        self.state_file = state_file
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load state file: {e}")
                self.data = {}

    def save(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save state: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

# 🛠️ THE FIX: Add an alias so both __main__.py and orchestrator.py are happy
StateManager = RunState
