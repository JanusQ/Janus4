# UDP Packet Format

The board demo uses UDP packets between the host and FPGA.

## Host to FPGA

The host sends S21/IQ readout data and configuration metadata.

```text
field                 meaning
sample_count          number of IQ samples in the shot
window_start          first sample used by the readout window
window_length         maximum readout window length
threshold_hi_q15      upper confidence threshold in Q15 format
threshold_lo_q15      lower confidence threshold in Q15 format
iq_payload            packed I/Q samples
feedback_branch0      optional preloaded branch-0 feedback waveform
feedback_branch1      optional preloaded branch-1 feedback waveform
```

## FPGA to Host

The FPGA returns the decision metadata and selected feedback waveform.

```text
field                 meaning
predicted_state       selected state/branch
threshold_hit         whether early confidence threshold was reached
latency_cycles        measured cycles from DDR/readout start to feedback output
feedback_payload      selected feedback waveform samples
```

The host-side scripts convert `latency_cycles` into time using the hardware clock frequency used by the ARTERY path.
