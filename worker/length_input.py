"""Length-only evaluation using FreeCAD; no model-property references.

Normalizes mixed fractions and compound imperial (`1-1/2"` is 1/2", `1 1/2"` is 1.5"; must match `units.gd`),
calls FreeCAD `evalExpression` in a temporary unsaved document and restores the previous active document, returning
finite millimetres. Checked against `units.gd` by `tests/length_cases.json`.
Entry points: evaluate, handle."""
import math
import re
import FreeCAD as App

def evaluate(text, default_unit="mm"):
    text = text.strip()
    if default_unit not in ("mm", "cm", "m", "in", "ft"):
        raise ValueError("Unknown default unit")
    if not text or len(text) > 512:
        raise ValueError("Enter a length (up to 512 characters)")
    # A leading sign on a compound measurement applies to the whole measurement.
    negative_compound = text.startswith("-") and bool(re.search(r"(?:ft|')\s*\d", text))
    if negative_compound:
        text = text[1:]
    # Mixed fractions and compound feet/inches become explicit arithmetic.
    text = re.sub(r"(\d+) +(\d+\s*/\s*\d+)\s*(in|ft|mm|cm|m|['\"])", r"(\1 + \2) * 1 \3", text)
    text = re.sub(r"(?<=\d)\s*(['\"])\s*(?=[\d(])", r"\1 + ", text)
    text = re.sub(r"(ft|in)\s+(?=[\d(])", r"\1 + ", text)
    # A sole trailing unit applies to the scalar arithmetic before it:
    # 1-1/2" means (1-1/2) inches, never a mixed fraction.
    scalar_unit = re.fullmatch(r"([0-9 .+*/()^-]+)\s*(mm|cm|m|in|ft|['\"])", text)
    if scalar_unit:
        text = "(" + scalar_unit[1] + ") * 1 " + scalar_unit[2]
    text = re.sub(r"(\d+\s*/\s*\d+)\s*(in|ft|mm|cm|m|['\"])", r"(\1) * 1 \2", text)
    # Permit numeric expressions and a fixed set of functions/units only.
    allowed = {"mm", "cm", "m", "in", "ft", "sqrt", "abs", "sin", "cos", "tan", "pi", "e"}
    if any(word not in allowed for word in re.findall(r"[A-Za-z_]+", text)) or re.search(r"[^0-9A-Za-z_ .+*/()^'\"-]", text):
        raise ValueError("Use a numeric length expression with mm, cm, m, in or ft")
    previous = App.ActiveDocument
    doc = App.newDocument("LengthInput")
    try:
        obj = doc.addObject("App::FeaturePython", "Evaluator")
        q = obj.evalExpression(text)
        if isinstance(q, (int, float)) or q.Unit == App.Units.Quantity("1").Unit:
            q = App.Units.Quantity((float(q) if isinstance(q, (int, float)) else q.Value), App.Units.Quantity("1 " + default_unit).Unit) * App.Units.Quantity("1 " + default_unit).Value
        if q.Unit != App.Units.Length or not math.isfinite(q.Value):
            raise ValueError("The result must be a finite length")
        return -q.Value if negative_compound else q.Value
    finally:
        App.closeDocument(doc.Name)
        if previous is not None:
            App.setActiveDocument(previous.Name)

def handle(req):
    try:
        values = [evaluate(t, req.get("default_unit", "mm")) for t in req["texts"]]
        return {"cmd": "length", "request_id": req.get("request_id"), "ok": True, "values": values}
    except Exception as exc:
        return {"cmd": "length", "request_id": req.get("request_id"), "ok": False, "error": str(exc)}
