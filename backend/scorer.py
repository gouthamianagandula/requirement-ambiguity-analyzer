def calculate_score(issues):
    """
    Calculate requirement quality score (0–100)
    Higher score = better clarity
    """

    if not issues:
        return 100

    score = 100

    for issue in issues:
        issue_type = (issue.get("issue_type") or "").strip()
        severity = (issue.get("severity") or "Medium").strip()

        # 🔥 BASE PENALTY BY SEVERITY
        if severity == "High":
            penalty = 15
        elif severity == "Medium":
            penalty = 8
        else:
            penalty = 4

        # 🔥 EXTRA PENALTY FOR AMBIGUITY (IMPORTANT)
        if issue_type in {
            "unclear_pronoun",
            "ambiguous_structure",
            "confusing_construction",
            "multiple_meaning",
            "vague_word",
            "vague_time",
            "vague_quantity",
            "unspecified_actor",
            "double_negative"
        }:
            penalty += 5  # extra penalty

        score -= penalty

    # 🔒 Clamp between 0–100
    return max(min(score, 100), 0)


def get_score_label(score):
    """
    Convert numeric score to quality label
    """

    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Good"
    elif score >= 60:
        return "Average"
    elif score >= 40:
        return "Poor"
    else:
        return "Very Ambiguous"