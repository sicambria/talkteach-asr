"""Headless-CLI tests (#54). Pure subcommands run end-to-end; model subcommands are
checked for arg parsing + graceful degradation only (no ML deps required)."""

from __future__ import annotations

import json
import wave

import numpy as np
import pytest

from talkteach.cli import main


def _write_wav(path, seconds=0.5, rate=16000, freq=220.0):
    t = np.arange(int(seconds * rate)) / rate
    pcm = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def test_import_writes_manifest(tmp_path, capsys):
    _write_wav(tmp_path / "a.wav")
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    out = tmp_path / "m.json"
    rc = main(["import", str(tmp_path), "--out", str(out)])
    assert rc == 0
    manifest = json.loads(out.read_text())
    assert manifest[0]["text"] == "hello"
    assert "imported 1 clips" in capsys.readouterr().err


def test_eval_reports_wer(tmp_path, capsys):
    (tmp_path / "refs.txt").write_text("the cat sat\nhello world\n", encoding="utf-8")
    (tmp_path / "hyps.txt").write_text("the cat sat\ngoodbye world\n", encoding="utf-8")
    rc = main(["eval", "--refs", str(tmp_path / "refs.txt"), "--hyps", str(tmp_path / "hyps.txt")])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["per_utterance"][0]["wer"] == 0.0
    assert report["errors"]["counts"]["substitutions"] == 1


def test_eval_length_mismatch_errors(tmp_path):
    (tmp_path / "r.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "h.txt").write_text("a\nb\n", encoding="utf-8")
    rc = main(["eval", "--refs", str(tmp_path / "r.txt"), "--hyps", str(tmp_path / "h.txt")])
    assert rc == 2


def test_augment_roundtrips_wav(tmp_path):
    src = tmp_path / "in.wav"
    _write_wav(src, seconds=1.0)
    out = tmp_path / "out.wav"
    rc = main(["augment", str(src), "--out", str(out), "--speed", "1.1", "--pitch", "2"])
    assert rc == 0
    with wave.open(str(out), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnframes() > 0


def test_metrics_summarize(tmp_path):
    from talkteach.obs import experiment as exp

    exp.log_metrics(str(tmp_path), epoch=1.0, loss=0.9, at=1.0)
    exp.log_metrics(str(tmp_path), epoch=1.0, wer=0.4, at=2.0)
    rc = main(["metrics", str(tmp_path), "--out", str(tmp_path / "s.json")])
    assert rc == 0
    summary = json.loads((tmp_path / "s.json").read_text())
    assert summary["best_wer"] == 0.4
    assert summary["points"] == 2


def test_missing_subcommand_exits_nonzero():
    with pytest.raises(SystemExit):
        main([])


def test_export_dry_run_without_deps(tmp_path, capsys):
    # A model dir with only a simulation checkpoint → export dry-runs, never crashes.
    (tmp_path / "checkpoint_epoch_1.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "export"
    rc = main(["export", "--model", str(tmp_path), "--out", str(out), "--format", "torchscript"])
    assert rc == 0
    assert (out / "export_manifest.json").is_file()  # honest dry-run scaffold
