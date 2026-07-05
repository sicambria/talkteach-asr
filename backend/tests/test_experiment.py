"""Local experiment-metrics tests (#53): JSONL write/read/summarize. No ML deps."""

from __future__ import annotations

from talkteach.obs import experiment as exp


def test_log_and_read_curve(tmp_path):
    wd = str(tmp_path)
    exp.log_metrics(wd, step=1, epoch=1.0, loss=0.9, at=100.0)
    exp.log_metrics(wd, step=2, epoch=2.0, loss=0.5, wer=0.3, at=200.0)
    curve = exp.read_curve(wd)
    assert len(curve) == 2
    assert curve[0]["loss"] == 0.9
    assert curve[1]["wer"] == 0.3
    assert curve[0]["t"] == 100.0  # pinned timestamp


def test_non_finite_values_dropped(tmp_path):
    wd = str(tmp_path)
    exp.log_metrics(wd, epoch=1.0, cer=float("nan"), wer=0.2, at=1.0)
    point = exp.read_curve(wd)[0]
    assert "cer" not in point  # NaN dropped so the chart stays valid
    assert point["wer"] == 0.2


def test_read_curve_missing_is_empty(tmp_path):
    assert exp.read_curve(str(tmp_path / "nope")) == []


def test_summarize_best_and_final(tmp_path):
    wd = str(tmp_path)
    exp.log_metrics(wd, epoch=1.0, wer=0.5, loss=1.0, at=1.0)
    exp.log_metrics(wd, epoch=2.0, wer=0.2, loss=0.4, at=2.0)
    exp.log_metrics(wd, epoch=3.0, wer=0.3, loss=0.6, at=3.0)
    summary = exp.summarize(wd)
    assert summary["best_wer"] == 0.2
    assert summary["final_wer"] == 0.3
    assert summary["final_loss"] == 0.6
    assert summary["final_epoch"] == 3.0
    assert summary["points"] == 3


def test_malformed_line_skipped(tmp_path):
    wd = str(tmp_path)
    exp.log_metrics(wd, wer=0.1, at=1.0)
    with open(exp.metrics_path(wd), "a", encoding="utf-8") as fh:
        fh.write("not json\n")
    assert len(exp.read_curve(wd)) == 1  # bad line ignored, good one kept
