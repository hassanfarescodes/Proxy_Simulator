BIRTH_PERIOD = 10
SIMULATION_DURATION = 50

CENSOR_RATIO = 0.1

SNOWFLAKE_BLOCK_INTERVAL = 10
SNOWFLAKE_BLOCK_FRACTION = 0.05

KIND_PROFILE = {
    "alpha1": 1.0,
    "alpha2": 1.0,
    "alpha3": 1.0,
    "alpha4": 1.0,
    "alpha5": 1.0,
}

STRICT_PROFILE = {
    "alpha1": 1.0,
    "alpha2": 2.0,
    "alpha3": 3.0,
    "alpha4": 3.0,
    "alpha5": 2.0,
}

STATIC_PROFILES = {
    "random": {
        "type": "random",
        "proxies_per_client": 2
    },
    "broadcast": {
        "type": "broadcast"
    },
    "fixed": {
        "type": "fixed"
    }
}
