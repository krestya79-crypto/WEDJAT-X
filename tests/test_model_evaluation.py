"""
Unit and Integration Tests for WEDJAT-X Model Evaluation Engine (Phase 5)
NASA Space Apps Challenge - Astronaut Health Monitoring Prototype
"""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest

from intelligence.model_evaluation import (
    MODEL_BAYESIAN,
    MODEL_ISOLATION_FOREST,
    MODEL_STATISTICAL,
    SELECTION_IMPROVEMENT,
    SELECTION_NO_IMPROVEMENT,
    SELECTION_TRADEOFF,
    BayesianAnomalyDetector,
    IsolationForestDetector,
    ModelComparisonEngine,
    NasaBiomarkerEvaluator,
    StatisticalBaselineDetector,
    SyntheticTelemetryEvaluator,
    calculate_evaluation_metrics,
    explain_anomaly_detection,
)


def test_evaluation_metrics_perfect() -> None:
    """Verify metrics under perfect classification."""
    y_true = [0, 0, 1, 1, 0, 1]
    y_pred = [0, 0, 1, 1, 0, 1]
    y_scores = [0.1, 0.2, 0.9, 0.85, 0.15, 0.95]

    m = calculate_evaluation_metrics(y_true, y_pred, y_scores)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0
    assert m["specificity"] == 1.0
    assert m["fpr"] == 0.0
    assert m["fnr"] == 0.0
    assert m["tp"] == 3
    assert m["tn"] == 3
    assert m["fp"] == 0
    assert m["fn"] == 0
    assert m["roc_auc"] == 1.0


def test_evaluation_metrics_single_class_handled_safely() -> None:
    """Verify that when only nominal samples exist (all zeros), metrics do not crash."""
    y_true = [0, 0, 0, 0, 0]
    y_pred = [0, 1, 0, 0, 0]  # 1 false positive
    y_scores = [0.1, 0.8, 0.2, 0.1, 0.3]

    m = calculate_evaluation_metrics(y_true, y_pred, y_scores)
    assert m["tp"] == 0
    assert m["fp"] == 1
    assert m["tn"] == 4
    assert m["fpr"] == 0.2
    # ROC-AUC is undefined when only one class is present
    assert m["roc_auc"] is None


def test_evaluation_metrics_empty() -> None:
    """Verify metrics return gracefully on empty inputs."""
    m = calculate_evaluation_metrics([], [])
    assert m["total_samples"] == 0
    assert np.isnan(m["precision"])
    assert np.isnan(m["f1"])


def test_statistical_baseline_detector() -> None:
    """Verify Statistical Baseline detector fits baseline and detects outliers."""
    train_vals = [70.0, 71.0, 72.0, 71.5, 70.5, 72.5]
    detector = StatisticalBaselineDetector(threshold=3.0)
    detector.fit(train_vals)

    assert detector.baseline_median == 71.25 or np.isclose(detector.baseline_median, 71.25, atol=0.5)

    test_vals = [71.0, 120.0, np.nan, 71.5]
    flags, scores = detector.predict(test_vals)

    assert flags[0] == 0  # Nominal
    assert flags[1] == 1  # 120 bpm is a significant spike (> 3.0 robust z)
    assert flags[2] == 0  # Missing/NaN handled without crashing
    assert scores[1] > 3.0


def test_isolation_forest_detector() -> None:
    """Verify Isolation Forest detector fitting, predicting, and explainability."""
    rng = np.random.RandomState(42)
    # Generate nominal 2D Gaussian cluster
    X_train = rng.normal(loc=10.0, scale=1.0, size=(100, 3))
    detector = IsolationForestDetector(contamination=0.05, random_state=42)
    detector.fit(X_train)

    # Test nominal point and severe outlier
    X_test = np.array([
        [10.1, 9.9, 10.2],   # Nominal
        [50.0, 45.0, 60.0],  # Severe multi-feature outlier
    ])
    flags, scores = detector.predict(X_test)

    assert flags[0] == 0
    assert flags[1] == 1
    assert scores[1] > scores[0]

    # Explain sample
    explanation = detector.explain_sample(X_test[1], ["feat_A", "feat_B", "feat_C"])
    assert "top_deviating_features" in explanation
    assert len(explanation["top_deviating_features"]) > 0
    assert "explainability_notice" in explanation


def test_bayesian_anomaly_detector_student_t() -> None:
    """Verify Bayesian Detector posterior predictive updates and tail probabilities."""
    rng = np.random.RandomState(42)
    train_vals = rng.normal(loc=100.0, scale=2.0, size=50)

    detector = BayesianAnomalyDetector(probability_threshold=0.01)
    detector.fit(train_vals)

    summary = detector.get_predictive_summary()
    assert summary["training_samples"] == 50
    assert summary["degrees_of_freedom"] > 50
    assert np.isclose(summary["predictive_mean"], 100.0, atol=1.0)

    test_vals = [100.2, 135.0, np.nan]
    flags, scores, p_vals = detector.predict(test_vals)

    assert flags[0] == 0  # Nominal: high p-value
    assert p_vals[0] > 0.05
    assert flags[1] == 1  # Extreme outlier: tiny p-value < 0.01
    assert p_vals[1] < 0.001
    assert scores[1] > 0.99
    assert flags[2] == 0  # NaN handled gracefully


def test_synthetic_telemetry_evaluator_independent_runs() -> None:
    """Verify Track A synthetic evaluation pipeline runs without error."""
    evaluator = SyntheticTelemetryEvaluator()
    # Fast benchmark on 1 sensor, 2 scenarios, duration 20s
    results = evaluator.run_benchmark(
        train_seed=42,
        test_seed=999,
        duration_s=20.0,
        sensors=["heart_rate"],
        scenarios=["NORMAL", "MOTION_ARTIFACT"],
    )

    assert len(results) == 6  # 1 sensor * 2 scenarios * 3 models
    for r in results:
        assert r.sensor_type == "heart_rate"
        assert r.run_type == "Independent_Test"
        assert r.model_name in [MODEL_STATISTICAL, MODEL_ISOLATION_FOREST, MODEL_BAYESIAN]
        assert "f1" in r.metrics
        assert "fpr" in r.metrics


def test_stability_evaluation() -> None:
    """Verify stability evaluation across multiple random seeds."""
    evaluator = SyntheticTelemetryEvaluator()
    stab = evaluator.evaluate_stability(
        seeds=[111, 222],
        sensor="heart_rate",
        scenario="MOTION_ARTIFACT",
    )

    assert MODEL_STATISTICAL in stab
    assert MODEL_ISOLATION_FOREST in stab
    assert MODEL_BAYESIAN in stab
    for m in [MODEL_STATISTICAL, MODEL_ISOLATION_FOREST, MODEL_BAYESIAN]:
        assert "f1_mean" in stab[m]
        assert "f1_std" in stab[m]
        assert stab[m]["f1_std"] >= 0.0


def test_nasa_biomarker_evaluator_participant_aware() -> None:
    """Verify Track B participant-aware evaluation on real NASA dataset."""
    evaluator = NasaBiomarkerEvaluator()
    assert "C001" in evaluator.participants

    records = evaluator.evaluate_participant_biomarkers(
        participant_id="C001",
        biomarker_names=["CRP", "IL-6"],
    )

    # Should evaluate without participant leakage
    for rec in records:
        assert rec.participant_id == "C001"
        assert rec.biomarker_name in ["CRP", "IL-6"]
        assert rec.stat_flag in [0, 1]
        assert rec.iso_flag in [0, 1]
        assert rec.bayes_flag in [0, 1]


def test_model_comparison_engine_verdicts() -> None:
    """Verify model comparison summaries and selection verdicts."""
    evaluator = SyntheticTelemetryEvaluator()
    results = evaluator.run_benchmark(
        train_seed=42, test_seed=999, duration_s=15.0, sensors=["heart_rate"], scenarios=["NORMAL", "MOTION_ARTIFACT"]
    )
    stab = evaluator.evaluate_stability(seeds=[111, 222], sensor="heart_rate", scenario="MOTION_ARTIFACT")

    engine = ModelComparisonEngine()
    summaries = engine.compare_models(results, stab)

    assert len(summaries) == 3
    for s in summaries:
        assert s.selection_verdict in [
            SELECTION_IMPROVEMENT,
            SELECTION_NO_IMPROVEMENT,
            SELECTION_TRADEOFF,
        ]
        assert len(s.decision_rationale) > 10


def test_explain_anomaly_detection_structure() -> None:
    """Verify Part 8 explainability payload structure and disclaimers."""
    expl = explain_anomaly_detection(
        model_name=MODEL_ISOLATION_FOREST,
        sensor_type="heart_rate",
        timestamp=pd.Timestamp("2026-01-01 00:00:15"),
        anomaly_score=0.92,
        threshold=0.50,
        feature_values={"raw_value": 115.0, "rolling_median": 72.0},
        motion_correlated=True,
        is_synthetic=True,
    )

    assert expl["model_name"] == MODEL_ISOLATION_FOREST
    assert expl["is_synthetic"] is True
    assert expl["motion_correlation_detected"] is True
    assert "non_clinical_notice" in expl
    assert "accelerometer motion" in expl["explanation"]

    # Verify JSON serializability
    json_str = json.dumps(expl)
    assert len(json_str) > 50
