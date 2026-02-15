"""Static constants and mappings for TrainingPeaks CLI."""

from __future__ import annotations

API_BASE = "https://tpapi.trainingpeaks.com"

SPORT_MAP = {1: "swim", 2: "bike", 3: "run"}
SPORT_NAME_BY_ID = {1: "Swim", 2: "Bike", 3: "Run"}
SPORT_ID_BY_NAME = {"swim": 1, "bike": 2, "run": 3}

TYPE_RULES = [
    ("race", ["race", "competition", "event", "marathon", "triathlon", "70.3"]),
    ("test", ["test", "ftp test", "time trial", "benchmark", "ramp test"]),
    ("vo2", ["vo2", "vo2max", "zone 5", "z5"]),
    (
        "sprint",
        ["sprint", "anaerobic", "zone 6", "z6", "neuromuscular", "20/40"],
    ),
    (
        "lt2",
        [
            "lt2",
            "lactate threshold",
            "threshold",
            "zone 4",
            "z4",
            "ftp",
            "over under",
            "sweetspot",
            "sst",
        ],
    ),
    (
        "lt1",
        ["lt1", "aerobic threshold", "tempo", "zone 3", "z3", "sweet spot"],
    ),
    (
        "long",
        ["long run", "long ride", "long swim", "endurance long", "weekend long"],
    ),
    ("strength", ["strength", "gym", "weights", "dryland", "core"]),
    (
        "easy",
        [
            "easy",
            "recovery",
            "endurance",
            "zone 1",
            "zone 2",
            "z1",
            "z2",
            "base z2",
            "warm down",
            "spin",
            "technique",
        ],
    ),
]

TYPE_LABELS = {
    "easy": "Easy/Recovery",
    "lt1": "LT1 (Aerobic Threshold)",
    "lt2": "LT2 (Lactate Threshold)",
    "vo2": "VO2max",
    "sprint": "Sprint/Anaerobic",
    "race": "Race",
    "strength": "Strength",
    "test": "Test",
    "long": "Long",
    "other": "Other",
}

INTENSITY_METRIC_LABELS = {
    "percentOfFtp": "% FTP",
    "percentOfThresholdPace": "% Threshold Pace",
    "percentOfThresholdHr": "% LTHR",
    "roundOrStridePerMinute": "rpm/spm",
    "beatsPerMinute": "bpm",
    "metersPerSecond": "m/s",
    "percentOfMax": "% Max",
}

INTENSITY_CLASS_LABELS = {
    "warmUp": "Warm-up",
    "coolDown": "Cool-down",
    "rest": "Recovery",
    "recovery": "Recovery",
    "active": "",
}

DEFAULT_ZONE_THRESHOLDS = {
    "easy_max": 75,
    "lt1_max": 93,
    "lt2_max": 100,
}
