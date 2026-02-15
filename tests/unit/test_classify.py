from tp_cli.core.classify import classify_workout, classify_with_metadata


def test_classify_lt2_workout() -> None:
    workout = {
        "title": "Threshold Intervals",
        "description": "4x8min @ LT2",
        "coachComments": "Zone 4 work",
    }
    assert classify_workout(workout) == "lt2"


def test_classify_easy_default() -> None:
    workout = {"title": "Morning aerobic", "description": "steady effort"}
    # No direct keyword in default rules means fallback other.
    assert classify_workout(workout) == "other"


def test_classification_metadata_ai_fallback() -> None:
    workout = {"title": "VO2 Session", "description": "3x3 hard"}
    result = classify_with_metadata(workout, method="ai")
    assert result.type == "vo2"
    assert result.method == "auto"
    assert result.confidence == 0.6


def test_classify_from_structure_lt2_without_keywords() -> None:
    workout = {
        "title": "Tuesday run",
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "step",
                    "length": {"value": 1, "unit": "repetition"},
                    "steps": [
                        {
                            "length": {"value": 1200, "unit": "second"},
                            "targets": [{"minValue": 96, "maxValue": 100}],
                            "intensityClass": "active",
                        }
                    ],
                }
            ],
        },
    }
    assert classify_workout(workout) == "lt2"


def test_classify_from_structure_lt1_without_keywords() -> None:
    workout = {
        "title": "Steady run",
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "step",
                    "steps": [
                        {
                            "length": {"value": 1800, "unit": "second"},
                            "targets": [{"minValue": 82, "maxValue": 86}],
                            "intensityClass": "active",
                        }
                    ],
                }
            ],
        },
    }
    assert classify_workout(workout) == "lt1"


def test_classify_structure_ignores_short_hard_opener() -> None:
    workout = {
        "title": "Progressive run",
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "step",
                    "steps": [
                        {
                            "length": {"value": 60, "unit": "second"},
                            "targets": [{"minValue": 105, "maxValue": 110}],
                            "intensityClass": "active",
                        },
                        {
                            "length": {"value": 3600, "unit": "second"},
                            "targets": [{"minValue": 68, "maxValue": 72}],
                            "intensityClass": "active",
                        },
                    ],
                }
            ],
        },
    }
    assert classify_workout(workout) == "easy"


def test_classify_race_keyword_overrides_structure_intensity() -> None:
    workout = {
        "title": "Race day prep",
        "description": "Local race effort",
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "step",
                    "steps": [
                        {
                            "length": {"value": 900, "unit": "second"},
                            "targets": [{"minValue": 96, "maxValue": 100}],
                            "intensityClass": "active",
                        }
                    ],
                }
            ],
        },
    }
    assert classify_workout(workout) == "race"


def test_classify_structured_steps_payload() -> None:
    workout = {
        "title": "Hard workout",
        "structuredSteps": [
            {
                "length": {"value": 120, "unit": "second"},
                "targets": [{"minValue": 112, "maxValue": 116}],
                "intensityClass": "active",
            },
            {
                "length": {"value": 120, "unit": "second"},
                "targets": [{"minValue": 112, "maxValue": 116}],
                "intensityClass": "active",
            },
        ],
    }
    assert classify_workout(workout) == "vo2"


def test_classification_metadata_uses_structure_reasoning() -> None:
    workout = {
        "title": "Unlabeled workout",
        "structure": {
            "primaryIntensityMetric": "percentOfThresholdPace",
            "structure": [
                {
                    "type": "step",
                    "steps": [
                        {
                            "length": {"value": 1500, "unit": "second"},
                            "targets": [{"minValue": 95, "maxValue": 99}],
                            "intensityClass": "active",
                        }
                    ],
                }
            ],
        },
    }
    result = classify_with_metadata(workout)
    assert result.type == "lt2"
    assert result.reasoning is not None
    assert "structured workout intensity" in result.reasoning
