"""Dataset-import tests (#47): folder pairs, CSV/TSV, JSON, NeMo JSONL, Common
Voice, LibriSpeech → canonical manifest. Pure stdlib parsing, no ML."""

from __future__ import annotations

import json
import wave

import pytest

from talkteach.data.import_manifest import (
    DatasetImportError,
    import_dataset,
    import_json_manifest,
)


def _write_wav(path, seconds=1.0, rate=16000):
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)


def test_folder_pairs(tmp_path):
    _write_wav(tmp_path / "a.wav", seconds=2.0)
    (tmp_path / "a.txt").write_text("hello world", encoding="utf-8")
    _write_wav(tmp_path / "b.wav")
    (tmp_path / "b.txt").write_text("second clip", encoding="utf-8")
    _write_wav(tmp_path / "orphan.wav")  # no sidecar → skipped

    manifest = import_dataset(tmp_path)  # auto → folder
    assert [m["text"] for m in manifest] == ["hello world", "second clip"]
    assert manifest[0]["duration_s"] == pytest.approx(2.0, abs=0.01)
    assert manifest[0]["path"].endswith("a.wav")


def test_csv_manifest_flexible_columns(tmp_path):
    _write_wav(tmp_path / "clip1.wav")
    (tmp_path / "m.csv").write_text("audio,sentence\nclip1.wav,the quick fox\n", encoding="utf-8")
    manifest = import_dataset(tmp_path / "m.csv")
    assert manifest[0]["text"] == "the quick fox"
    assert manifest[0]["path"].endswith("clip1.wav")  # resolved against CSV dir


def test_tsv_detected_as_common_voice(tmp_path):
    clips = tmp_path / "clips"
    clips.mkdir()
    _write_wav(clips / "x.wav")
    (tmp_path / "train.tsv").write_text(
        "path\tsentence\nx.wav\ta common voice line\n", encoding="utf-8"
    )
    manifest = import_dataset(tmp_path / "train.tsv")
    assert manifest[0]["text"] == "a common voice line"
    assert manifest[0]["path"].endswith("clips/x.wav")


def test_nemo_jsonl_uses_declared_duration(tmp_path):
    _write_wav(tmp_path / "u.wav")
    lines = [
        json.dumps({"audio_filepath": "u.wav", "text": "nemo line", "duration": 3.5}),
        "",  # blank line tolerated
    ]
    (tmp_path / "manifest.jsonl").write_text("\n".join(lines), encoding="utf-8")
    manifest = import_json_manifest(tmp_path / "manifest.jsonl")
    assert manifest[0]["text"] == "nemo line"
    assert manifest[0]["duration_s"] == 3.5  # declared duration wins over probing


def test_json_array_manifest(tmp_path):
    _write_wav(tmp_path / "j.wav")
    (tmp_path / "d.json").write_text(
        json.dumps([{"path": "j.wav", "transcript": "json array"}]), encoding="utf-8"
    )
    manifest = import_dataset(tmp_path / "d.json")
    assert manifest[0]["text"] == "json array"


def test_librispeech_tree(tmp_path):
    spk = tmp_path / "1234" / "0"
    spk.mkdir(parents=True)
    _write_wav(spk / "1234-0-0000.wav")
    _write_wav(spk / "1234-0-0001.wav")
    (spk / "1234-0.trans.txt").write_text(
        "1234-0-0000 HELLO THERE\n1234-0-0001 GENERAL KENOBI\n", encoding="utf-8"
    )
    manifest = import_dataset(tmp_path)  # auto → librispeech (has *.trans.txt)
    assert [m["text"] for m in manifest] == ["HELLO THERE", "GENERAL KENOBI"]


def test_empty_and_bad_sources_raise(tmp_path):
    (tmp_path / "empty.csv").write_text("path,text\n", encoding="utf-8")
    with pytest.raises(DatasetImportError):
        import_dataset(tmp_path / "empty.csv")
    # JSON with no usable records (missing transcript field).
    (tmp_path / "norecs.json").write_text(json.dumps([{"path": "x.wav"}]), encoding="utf-8")
    with pytest.raises(DatasetImportError):
        import_dataset(tmp_path / "norecs.json", kind="json")
    with pytest.raises(DatasetImportError):
        import_dataset(tmp_path / "x.csv", kind="bogus")
