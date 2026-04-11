def calculate_score(detected_items):
    score = 100

    for item in detected_items:
        if item["severity"] == "High":
            score -= 15
        elif item["severity"] == "Medium":
            score -= 10
        else:
            score -= 5

    if score < 0:
        score = 0

    return score

def get_score_label(score):
    if score >= 85:
        return "Clear"
    elif score >= 65:
        return "Moderate"
    else:
        return "Ambiguous"