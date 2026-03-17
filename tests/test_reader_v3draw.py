from pathlib import Path

import pytest

from pipeline.io.reader_v3draw import read_v3draw_header


def test_read_v3draw_header_reads_magic(tmp_path: Path) -> None:
    sample = tmp_path / "sample.v3draw"
    sample.write_bytes(b"v3draw-mock-header\x00\x00\x00data")
    result = read_v3draw_header(sample)
    assert result["path"] == str(sample)
    assert result["size_bytes"] > 0
    assert "v3draw-mock-header" in result["magic_ascii"]


def test_read_v3draw_header_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_v3draw_header(tmp_path / "missing.v3draw")
