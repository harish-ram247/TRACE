# Verifier calibration

Pairs: 111 human-labelled supported claims, 42 value-swap and 109 wrong-source negatives. Threshold chosen on the calib split; numbers below are on the eval split.

| Verifier | Threshold | Accepts true claims | Rejects value-swapped | Rejects wrong source | Balanced accuracy |
|---|---|---|---|---|---|
| xsmall (calibrated) | 0.027 | 0.95 (n=43) | 0.92 (n=13) | 0.91 (n=43) | 0.93 |
| xsmall (0.5) | 0.500 | 0.67 (n=43) | 1.00 (n=13) | 1.00 (n=43) | 0.89 |
| small (calibrated) | 0.790 | 0.72 (n=43) | 0.92 (n=13) | 1.00 (n=43) | 0.88 |
| small (0.5) | 0.500 | 0.77 (n=43) | 0.92 (n=13) | 0.95 (n=43) | 0.88 |
| gemini (calibrated) | 0.500 | 0.93 (n=43) | 1.00 (n=13) | 0.88 (n=43) | 0.94 |
