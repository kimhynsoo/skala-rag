import pytest
from agents._report_render import build_reference, cited_ids, strip_invalid_ids


def test_reference_recognizes_real_rag_and_dart_identifiers():
    ids = ["DIR-C03-01", "TEC-02-0007", "MKT-13-0001", "ELG-C03-DART", "ELG-C03-WEB-G1", "ELG-C03-ID-03"]
    body = " ".join(f"[{item}]" for item in ids)
    evidence = [{"근거ID": item, "출처명": item} for item in ids]
    result = build_reference(body, evidence)
    assert cited_ids(body) == ids
    assert all(item in result for item in ids)


def test_invalid_rag_reference_is_removed():
    cleaned, removed = strip_invalid_ids("수치 [TEC-99-9999]", set())
    assert "TEC-99-9999" not in cleaned
    assert removed == ["TEC-99-9999"]


def test_pdf_page_limit_preserves_existing_output(monkeypatch, tmp_path):
    import pymupdf
    from agents import _report_pdf

    def print_pdf(args, **kwargs):
        destination = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--print-to-pdf="))
        with pymupdf.open() as document:
            for _ in range(6):
                document.new_page()
            document.save(destination)
    monkeypatch.setattr(_report_pdf, "_find_chrome", lambda: "chrome")
    monkeypatch.setattr(_report_pdf, "render_html", lambda *a: "<html>report</html>")
    monkeypatch.setattr(_report_pdf.subprocess, "run", print_pdf)
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous valid report")
    with pytest.raises(ValueError, match="5쪽"):
        _report_pdf.export_pdf("report", {}, output)
    assert output.read_bytes() == b"previous valid report"


def test_pdf_reference_numbers_include_dart_ids():
    from agents import _report_pdf

    _report_pdf._REFS.update({"ELG-C03-DART": 2, "TEC-02-0007": 3})
    try:
        result = _report_pdf._inline("근거 [ELG-C03-DART, TEC-02-0007]")
        assert '<sup class="ref">2,3</sup>' in result
    finally:
        _report_pdf._REFS.clear()


def test_report_groups_diagnostic_gaps_without_changing_evaluation():
    from agents._report_render import limitations

    gaps = [f"성능지표.{i}.검증수준 인용 구절이 원문과 불일치" for i in range(40)]
    record = {"scorecard": {"unknown_items": []}, "technology_analysis": {"미확인정보": gaps}}
    text = limitations({}, record, [])
    assert "40건" in text and "실측 성능" in text
    assert "성능지표.0" not in text
    assert record["technology_analysis"]["미확인정보"] == gaps
