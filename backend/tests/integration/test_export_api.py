def test_export_preview_rows_returns_download_metadata(client) -> None:
    response = client.post(
        "/api/conversion-runs/run-1/exports",
        json={
            "file_type": "csv",
            "columns": ["日期", "摘要", "科目", "金额"],
            "rows": [
                {"日期": "2026-06-01", "摘要": "收到客户款项", "科目": "银行存款", "金额": "12000.00"}
            ],
            "exported_by": "user-1",
            "only_confirmed": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_type"] == "csv"
    assert payload["row_count"] == 1
    assert payload["download_url"].startswith("/api/exports/")
