def parse_amount(val) -> float:
    if val is None or str(val).strip() == "":
        return 0.0
    s = str(val)
    # Remove thousand separators (., space); keep minus sign
    s = s.replace(",", "").replace(".", "").replace(" ", "")
    # Nếu có phần thập phân với dấu phẩy: "1.234,56" -> sau khi remove ., còn "1234,56"
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        # fallback: bỏ hết non-digit trừ dấu - và .
        import re
        s2 = re.sub(r"[^0-9\.-]", "", s)
        try:
            return float(s2)
        except Exception:
            return 0.0
