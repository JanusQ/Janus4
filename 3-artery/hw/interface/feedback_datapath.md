# Feedback Datapath

The reproduced ARTERY feedback path follows this tutorial-level structure:

```text
10G UDP RX
  -> DDR write buffer
  -> DDR readout stream
  -> NCO / mixer
  -> trajectory analyzer
  -> branch history table
  -> Bayesian predictor
  -> feedback selector
  -> UDP TX metadata and waveform return
```

## Early Decision

The feedback core evaluates the integrated readout trajectory as samples arrive.

```text
if P(state1) >= threshold_hi:
    choose branch 1
elif P(state1) <= threshold_lo:
    choose branch 0
else:
    continue accumulating samples
```

If no threshold is reached before `max_decision_length`, the implementation falls back to the final classification result at the end of the readout window.

## Latency Measurement

The hardware latency counter starts when the DDR/readout stream begins feeding the ARTERY path and stops when the feedback waveform stream becomes valid.

```text
latency_time = latency_cycles / feedback_clock_frequency
```

The demo reports this value through the host UDP result and displays it in the GUI.
