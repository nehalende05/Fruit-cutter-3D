import json
import os
from config import HIGH_SCORE_FILE

def load_high_scores():
    """Loads high scores from the JSON file. Returns a list of dicts with 'name' and 'score'."""
    if not os.path.exists(HIGH_SCORE_FILE):
        return get_default_scores()
    
    try:
        with open(HIGH_SCORE_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Ensure each element is well-formed
                validated_data = []
                for entry in data:
                    if isinstance(entry, dict) and "name" in entry and "score" in entry:
                        validated_data.append({
                            "name": str(entry["name"])[:15],  # Limit name length
                            "score": int(entry["score"])
                        })
                # Sort descending
                validated_data.sort(key=lambda x: x["score"], reverse=True)
                return validated_data[:5]
    except Exception as e:
        print(f"Error loading high scores: {e}. Resetting to defaults.")
        
    return get_default_scores()

def save_high_scores(scores):
    """Saves the high score list to the JSON file."""
    try:
        # Sort and take top 5
        scores.sort(key=lambda x: x["score"], reverse=True)
        scores = scores[:5]
        with open(HIGH_SCORE_FILE, "w") as f:
            json.dump(scores, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving high scores: {e}")
        return False

def add_high_score(name, score):
    """Adds a new high score. Returns True if it made it to the leaderboard, False otherwise."""
    scores = load_high_scores()
    # Check if this score is high enough to enter top 5
    if len(scores) < 5 or score > scores[-1]["score"]:
        scores.append({"name": name, "score": score})
        save_high_scores(scores)
        return True
    return False

def get_default_scores():
    """Returns a list of default high scores if no file exists."""
    defaults = [
        {"name": "Master Ninja", "score": 1000},
        {"name": "Sensei", "score": 750},
        {"name": "Apprentice", "score": 500},
        {"name": "Novice", "score": 250},
        {"name": "Beginner", "score": 100}
    ]
    save_high_scores(defaults)
    return defaults
