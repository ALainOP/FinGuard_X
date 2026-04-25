import csv
from collections import Counter
from statistics import mean

PAY_PATH = r"c:\Users\malle\.cursor\projects\finguard\payment_fraud.csv"
LEGIT_PATH = r"c:\Users\malle\.cursor\projects\finguard\legit_payment_datasets.csv"


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def score_payment_rows():
    with open(PAY_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    modes = {}
    for field in ["paymentMethod", "Category", "isWeekend"]:
        modes[field] = Counter(
            [r.get(field, "") for r in rows if r.get(field, "") != ""]
        ).most_common(1)[0][0]

    scored = []
    missing = {"paymentMethod": 0, "Category": 0, "isWeekend": 0}
    missing_weekend_fraud = 0
    for row in rows:
        was_pm_missing = row.get("paymentMethod", "") == ""
        was_cat_missing = row.get("Category", "") == ""
        was_weekend_missing = row.get("isWeekend", "") == ""
        missing["paymentMethod"] += int(was_pm_missing)
        missing["Category"] += int(was_cat_missing)
        missing["isWeekend"] += int(was_weekend_missing)

        payment_method = row["paymentMethod"] if not was_pm_missing else modes["paymentMethod"]
        category = row["Category"] if not was_cat_missing else modes["Category"]
        label = 1 if str(row.get("label", "0")) == "1" else 0
        if was_weekend_missing and label == 1:
            missing_weekend_fraud += 1

        account_age = max(0.0, min(2000.0, to_float(row.get("accountAgeDays", "0"))))
        method_age = max(0.0, min(2000.0, to_float(row.get("paymentMethodAgeDays", "0"))))
        local_time = max(0.0, min(24.0, to_float(row.get("localTime", "0"))))
        num_items = max(1.0, min(100.0, to_float(row.get("numItems", "1"))))

        account_age_risk = 1 - clamp01(account_age / 365)
        method_age_risk = 1 - clamp01(method_age / 180)
        night_risk = 1 if local_time < 6 or local_time > 23 else 0.2
        item_risk = clamp01((num_items - 1) / 4)
        method_risk = 0.55 if payment_method == "creditcard" else 0.5 if payment_method == "paypal" else 0.35
        category_risk = 0.55 if category == "shopping" else 0.5 if category == "electronics" else 0.45
        missing_signal = (0.05 if was_pm_missing else 0) + (0.05 if was_cat_missing else 0) + (0.05 if was_weekend_missing else 0)
        risk = clamp01(
            account_age_risk * 0.2
            + method_age_risk * 0.25
            + night_risk * 0.15
            + item_risk * 0.1
            + method_risk * 0.15
            + category_risk * 0.1
            + missing_signal
        )
        scored.append((risk, label))
    return scored, missing, missing_weekend_fraud


def score_legit_rows():
    with open(LEGIT_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if rows and rows[0][:5] == ["A", "B", "C", "D", "E"]:
        headers = rows[1]
        start = 2
    else:
        headers = rows[0]
        start = 1
    idx = {h.lower(): i for i, h in enumerate(headers)}
    scored = []
    for row in rows[start:]:
        if not row:
            continue
        text_i = idx.get("text", 0)
        label_i = idx.get("label", 1)
        severity_i = idx.get("severity", 3)
        confidence_i = idx.get("confidence", 4)
        text = row[text_i].strip() if text_i < len(row) else ""
        if not text:
            continue
        label = 1 if (row[label_i] if label_i < len(row) else "0") == "1" else 0
        severity = (row[severity_i] if severity_i < len(row) else "low").lower()
        confidence = clamp01(to_float(row[confidence_i] if confidence_i < len(row) else "0.5", 0.5))

        t = text.lower()
        urgency = sum(w in t for w in ["urgent", "immediately", "minutes", "now"]) / 4
        authority = sum(w in t for w in ["bank", "kyc", "officer", "security", "rbi"]) / 5
        reward = sum(w in t for w in ["reward", "lottery", "cashback", "won"]) / 4
        fear = sum(w in t for w in ["blocked", "suspended", "penalty", "freeze", "legal"]) / 5
        lexical_risk = urgency * 0.3 + authority * 0.2 + reward * 0.2 + fear * 0.3
        severity_weight = 1 if severity == "high" else 0.65 if severity == "medium" else 0.35
        risk = clamp01(lexical_risk * 0.6 + confidence * 0.25 + severity_weight * 0.15)
        scored.append((risk, label))
    return scored


def evaluate(scored, threshold):
    tp = fp = tn = fn = 0
    for risk, label in scored:
        pred = 1 if risk >= threshold else 0
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    return tp, fp, tn, fn, precision, recall, f1, accuracy


payment_scored, missing, leakage = score_payment_rows()
legit_scored = score_legit_rows()
combined = payment_scored + legit_scored

best_threshold = 0.2
best_metrics = evaluate(combined, 0.2)
for i in range(21, 96):
    th = i / 100
    m = evaluate(combined, th)
    if m[6] > best_metrics[6] or (abs(m[6] - best_metrics[6]) < 1e-12 and m[4] > best_metrics[4]):
        best_threshold = th
        best_metrics = m

tp, fp, tn, fn, precision, recall, f1, accuracy = best_metrics

print(f"combined_rows={len(combined)}")
print(
    f"missing_filled paymentMethod={missing['paymentMethod']} category={missing['Category']} isWeekend={missing['isWeekend']}"
)
print(f"leakage_missingWeekendFraud={leakage}")
print(f"avg_risk={mean(r for r, _ in combined) * 100:.2f}%")
print(f"best_f1_threshold={best_threshold:.2f}")
print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
print(
    f"precision={precision * 100:.2f}% recall={recall * 100:.2f}% f1={f1 * 100:.2f}% accuracy={accuracy * 100:.2f}%"
)
